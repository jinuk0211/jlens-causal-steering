"""Contrastive Activation Addition through nrimsky/CAA's own code.

Upstream code that runs unchanged:
  * ``generate_vectors.generate_save_vectors_for_behavior`` builds the vector:
    one forward pass per A/B answer, the block output at token ``-2`` (the
    answer letter), ``mean(pos - neg)`` per layer, saved with ``torch.save``.
  * ``utils.helpers.find_instruction_end_postion`` and
    ``utils.helpers.add_vector_from_position`` decide where and how the vector
    is added during generation (every position from the end of the last
    instruction marker onward, prefill and decode).

What this adapter supplies, because the upstream is wired to Llama-2:
  * the A/B dataset (Tau2 context + "Choices: (A) ... (B) ..." user turn, the
    repaired action as ``answer_matching_behavior``, letters balanced);
  * a Qwen chat-template tokenizer in place of ``tokenize_llama_chat``;
  * a duck-typed replacement for ``LlamaWrapper`` that records decoder block
    outputs through forward hooks (``BlockOutputWrapper`` assumes Llama blocks
    that return tuples and own ``self_attn``, which Qwen3.5 linear-attention
    blocks do not);
  * the instruction-end marker ``<|im_start|>assistant\\n`` instead of ``[/INST]``.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import (
    RenderedPair,
    RenderSettings,
    action_text,
    pair_summary,
    render,
)
from jlens_causal.official.modelparts import (
    ForwardCounter,
    decoder_layers,
    first_tensor,
    hooks,
    model_device,
    replace_first,
)

METHOD = "caa"
UPSTREAM_FILES = (
    "generate_vectors.py",
    "llama_wrapper.py",
    "behaviors.py",
    "utils/helpers.py",
    "utils/tokenize.py",
    "LICENSE",
)
CHOICE_TEMPLATE = (
    "Which of the following is the correct next assistant action?\n\n"
    "Choices:\n(A) {a}\n(B) {b}"
)
INSTRUCTION_END = "<|im_start|>assistant\n"
DEVIATIONS = [
    "A/B items are built from Tau2 repair pairs: the prompt is the rendered Tau2 context "
    "plus a user turn listing both candidate actions; the repaired action is "
    "answer_matching_behavior.",
    "tokenize_llama_chat is replaced by the Qwen chat template (generation header, then "
    "the answer '(A)'/'(B)'); token -2 is asserted to carry the answer letter.",
    "LlamaWrapper/BlockOutputWrapper are replaced by forward hooks on the decoder blocks; "
    "the vector math and the position rule are the upstream helper functions.",
    "Instruction end is the last '<|im_start|>assistant\\n' token instead of '[/INST]'.",
    "normalize_vectors.py is not applied: it rescales across the seven CAA behaviors and "
    "is the identity for a single behavior.",
]


class _CAAModelView:
    """The subset of ``LlamaWrapper`` that ``generate_save_vectors_for_behavior`` uses."""

    def __init__(self, model: Any, tokenizer_dir: Path, layers: list[int]):
        import torch

        self._torch = torch
        self._model = model
        self._layers = sorted(set(layers))
        self._activations: dict[int, Any] = {}
        self.device = model_device(model)
        self.use_chat = True
        self.model_name_path = str(tokenizer_dir)

    def set_save_internal_decodings(self, value: bool) -> None:  # noqa: ARG002
        return None

    def reset_all(self) -> None:
        self._activations = {}

    def get_logits(self, tokens: Any) -> Any:
        blocks = decoder_layers(self._model)

        def record(index: int):
            def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
                self._activations[index] = first_tensor(output)

            return hook

        handles = [blocks[index].register_forward_hook(record(index)) for index in self._layers]
        with hooks(handles), self._torch.no_grad():
            # logits_to_keep=1 only avoids materialising full-vocabulary logits for
            # long Tau2 prompts; the recorded block outputs are unaffected.
            return self._model(input_ids=tokens, logits_to_keep=1).logits

    def get_last_activations(self, layer: int) -> Any:
        return self._activations[layer]


def _tokenize_qwen_chat(tokenizer: Any, user_input: str, model_output: str | None = None,
                        system_prompt: str | None = None) -> list[int]:  # noqa: ARG001
    """Stand-in for ``utils.tokenize.tokenize_llama_chat`` with the Qwen template.

    ``user_input`` already holds the rendered chat prompt ending in the assistant
    generation header (built in :func:`build_ab_items`).
    """
    text = user_input + (model_output.strip() if model_output is not None else "")
    tokens = tokenizer.encode(text, add_special_tokens=False)
    if model_output is not None:
        letter = model_output.strip().strip("()")
        if letter not in tokenizer.decode(tokens[-2:-1]):
            raise ValueError(
                f"token -2 of the CAA answer {model_output!r} does not carry its letter under "
                "this tokenizer; generate_vectors.py reads the activation there"
            )
    return tokens


def build_ab_items(tokenizer: Any, pairs: list[RenderedPair], settings: RenderSettings) -> list[dict[str, str]]:
    items = []
    for index, pair in enumerate(pairs):
        positive_first = index % 2 == 0
        first, second = (
            (pair.positive_message, pair.negative_message)
            if positive_first
            else (pair.negative_message, pair.positive_message)
        )
        question = CHOICE_TEMPLATE.format(a=action_text(first), b=action_text(second))
        prompt = render(
            tokenizer,
            [*pair.context, {"role": "user", "content": question}],
            settings,
            add_generation_prompt=True,
        )
        items.append(
            {
                "question": prompt,
                "answer_matching_behavior": "(A)" if positive_first else "(B)",
                "answer_not_matching_behavior": "(B)" if positive_first else "(A)",
            }
        )
    return items


def build_ab_items_from_rendered(examples: list[dict[str, Any]]) -> list[dict[str, str]]:
    """A/B items from exact rendered prompts (e.g. the logged Tau2 ``rendered_context``).

    Each example holds ``prompt`` (ending in the assistant generation header),
    ``positive`` and ``negative`` assistant messages.  The choice question is
    inserted as a user turn right before the generation header, which is what
    :func:`build_ab_items` renders through the chat template.
    """
    items = []
    for index, example in enumerate(examples):
        prompt = example["prompt"]
        cut = prompt.rfind(INSTRUCTION_END)
        if cut < 0:
            raise ValueError("rendered prompt has no assistant generation header")
        history, header = prompt[:cut], prompt[cut:]
        positive_first = index % 2 == 0
        first, second = (
            (example["positive"], example["negative"])
            if positive_first
            else (example["negative"], example["positive"])
        )
        question = CHOICE_TEMPLATE.format(a=action_text(first), b=action_text(second))
        items.append(
            {
                "question": f"{history}<|im_start|>user\n{question}<|im_end|>\n{header}",
                "answer_matching_behavior": "(A)" if positive_first else "(B)",
                "answer_not_matching_behavior": "(B)" if positive_first else "(A)",
            }
        )
    return items


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    settings: RenderSettings,
    layers: list[int],
    behavior: str,
    output_path: Path,
    model_id: str,
    model_revision: str,
) -> Path:
    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 2:
        raise ValueError("CAA needs at least two training repair pairs")
    return fit_items(
        runtime,
        build_ab_items(runtime.tokenizer, train, settings),
        layers=layers,
        behavior=behavior,
        output_path=output_path,
        model_id=model_id,
        model_revision=model_revision,
        data=pair_summary(train),
    )


def fit_items(
    runtime: Any,
    items: list[dict[str, str]],
    *,
    layers: list[int],
    behavior: str,
    output_path: Path,
    model_id: str,
    model_revision: str,
    data: dict[str, Any],
    extra_deviations: tuple[str, ...] = (),
) -> Path:
    """Run ``generate_save_vectors_for_behavior`` on prepared A/B items."""
    torch = runtime.torch
    if len(items) < 2:
        raise ValueError("CAA needs at least two A/B items")
    generate_vectors = upstream.import_upstream(METHOD, "generate_vectors")
    with tempfile.TemporaryDirectory(prefix="caa-official-") as scratch:
        scratch_path = Path(scratch)
        tokenizer_dir = scratch_path / "tokenizer"
        runtime.tokenizer.save_pretrained(tokenizer_dir)
        dataset_path = scratch_path / "generate_dataset.json"
        dataset_path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        vector_dir = scratch_path / "vectors"
        vector_dir.mkdir()
        # Redirect the module-level path helpers and the Llama tokenizer helper that
        # generate_save_vectors_for_behavior looks up as globals.
        overrides = {
            "get_ab_data_path": lambda behavior_name: str(dataset_path),
            "get_vector_dir": lambda behavior_name: str(vector_dir),
            "get_vector_path": lambda behavior_name, layer, model_name_path: str(
                vector_dir / f"vec_layer_{layer}.pt"
            ),
            "get_activations_dir": lambda behavior_name: str(vector_dir),
            "get_activations_path": lambda behavior_name, layer, model_name_path, kind: str(
                vector_dir / f"activations_{kind}_{layer}.pt"
            ),
            "tokenize_llama_chat": _tokenize_qwen_chat,
            "HUGGINGFACE_TOKEN": None,
        }
        saved = {name: getattr(generate_vectors, name) for name in overrides}
        try:
            for name, value in overrides.items():
                setattr(generate_vectors, name, value)
            generate_vectors.generate_save_vectors_for_behavior(
                layers=list(layers),
                save_activations=False,
                behavior=behavior,
                model=_CAAModelView(runtime.hf_model, tokenizer_dir, layers),
            )
        finally:
            for name, value in saved.items():
                setattr(generate_vectors, name, value)
        vectors = {
            str(layer): torch.load(vector_dir / f"vec_layer_{layer}.pt", map_location="cpu").float()
            for layer in layers
        }
    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={
            "behavior": behavior,
            "layers": list(layers),
            "extraction_position": "token -2 (answer letter) of the A/B prompt",
            "application": "add_vector_from_position from the last instruction-end token",
            "instruction_end": INSTRUCTION_END,
            "data": data,
            "letter_balance": {
                "A": sum(item["answer_matching_behavior"] == "(A)" for item in items),
                "B": sum(item["answer_matching_behavior"] == "(B)" for item in items),
            },
        },
        deviations=[*DEVIATIONS, *extra_deviations],
        state={"vectors": vectors},
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,
    prompt_ids: list[int],
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    import torch

    helpers = upstream.import_upstream(METHOD, "utils.helpers")
    vectors = artifact["state"]["vectors"]
    # vector_layer selects which fitted vector to add; `layer` is where it is added.
    # They differ only for the wrong-layer control (prompting_with_steering.py's
    # override_vector: one layer's vector injected at another layer).
    vector_layer = int(options.get("vector_layer", layer))
    if str(vector_layer) not in vectors:
        raise ValueError(
            f"CAA artifact has no vector for layer {vector_layer}; fit layers {sorted(vectors)}"
        )
    marker = str(options.get("instruction_end", artifact["fit"]["instruction_end"]))
    end_str = torch.tensor(tokenizer.encode(marker, add_special_tokens=False))
    from_position = helpers.find_instruction_end_postion(torch.tensor(prompt_ids), end_str)
    if from_position == -1:
        # Upstream would silently steer every position here.
        raise ValueError(f"instruction-end marker {marker!r} is absent from the prompt")
    block = decoder_layers(model)[layer]
    counter = ForwardCounter()
    trace = {
        "from_position": int(from_position),
        "multiplier": float(strength),
        "hook_layer": int(layer),
        "vector_layer": vector_layer,
        "vector_norm": float(vectors[str(vector_layer)].norm()),
        "applied_edits": 0,
    }
    scaled: dict[str, Any] = {}

    def hook(module: Any, args: Any, output: Any) -> Any:  # noqa: ARG001
        hidden = first_tensor(output)
        start, end = counter.advance(hidden.shape[1])
        position_ids = torch.arange(start, end, device=hidden.device).unsqueeze(0)
        if "vector" not in scaled:
            # LlamaWrapper.set_add_activations(layer, multiplier * vector)
            scaled["vector"] = (strength * vectors[str(vector_layer)]).to(
                device=hidden.device, dtype=hidden.dtype
            )
        augmented = helpers.add_vector_from_position(
            matrix=hidden, vector=scaled["vector"], position_ids=position_ids, from_pos=from_position
        )
        trace["applied_edits"] += int((position_ids >= from_position).sum())
        return replace_first(output, augmented)

    with hooks([block.register_forward_hook(hook)]):
        yield trace
