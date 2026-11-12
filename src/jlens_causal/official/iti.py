"""Inference-Time Intervention through likenneth/honest_llama's own code.

Upstream code that runs unchanged:
  * ``interveners.Collector`` records the ``o_proj`` input (all heads,
    concatenated) at the last token of each example;
  * ``utils.get_com_directions`` / ``utils.get_top_heads`` (which calls
    ``utils.train_probes``: one sklearn ``LogisticRegression`` per head, ranked
    by validation accuracy) select heads and their mass-mean directions;
  * ``interveners.ITI_Intervener`` performs the edit
    ``b[0, -1] = b[0, -1] + direction * alpha`` during generation.

Transcribed verbatim from ``validation/validate_2fold.py`` (code inside
``main()`` that cannot be imported): the train/validation split of the
development questions (lines 143-144) and the per-layer direction assembly
with projection-std scaling (lines 163-175).

What this adapter supplies:
  * forward pre-hooks on ``self_attn.o_proj`` of the full-attention layers
    (pyvene's ``IntervenableModel`` is replaced; Qwen3.5 linear-attention
    layers have no heads at that site and are excluded);
  * examples = rendered Tau2 prompt + repaired (label 1) or failed (label 0)
    action, grouped per repair pair the way TruthfulQA groups answers per
    question;
  * stand-ins for the TruthfulQA/baukit/openai imports of ``utils.py`` that the
    functions above never call.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import RenderedPair, encode, pair_summary
from jlens_causal.official.modelparts import (
    attention_shape,
    decoder_layers,
    full_attention_layers,
    hooks,
    model_device,
)

METHOD = "iti"
UPSTREAM_FILES = ("utils.py", "interveners.py", "validation/validate_2fold.py", "LICENSE")
DEVIATIONS = [
    "Heads are searched only in Qwen3.5 full-attention layers (self_attn.o_proj); "
    "Gated DeltaNet layers have no softmax heads at that site.",
    "pyvene's IntervenableModel is replaced by forward pre-hooks that call the upstream "
    "Collector and ITI_Intervener objects.",
    "Examples are Tau2 prompt + repaired/failed action (labels 1/0) grouped per repair pair.",
    "The std tuning set mirrors the upstream default activations_dataset='tqa_gen_end_q' "
    "(activations at the end of the question, i.e. the generation position): the last token "
    "of each training pair's rendered prompt.",
    "By default the edit is skipped on the prefill forward and applied at every decode step, "
    "matching pyvene generate(intervene_on_prompt=False) as used by the upstream evaluation.",
    "K defaults to 6 heads: the paper's 48 of 1024 Llama-7B heads scaled to the 128 "
    "full-attention heads of Qwen3.5-4B.",
]


def _truthfulqa_stubs() -> dict[str, Any]:
    """Stand-ins for evaluation-only imports at the top of ``utils.py``."""

    def unavailable(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise RuntimeError("TruthfulQA evaluation helpers are not used by the Tau2 adapter")

    names = {
        "truthfulqa.utilities": (
            "format_prompt",
            "format_prompt_with_answer_strings",
            "split_multi_answer",
            "format_best",
            "find_start",
        ),
        "truthfulqa.presets": ("preset_map", "COMPARE_PRIMER"),
        "truthfulqa.models": ("find_subsequence", "set_columns", "MC_calcs"),
        "truthfulqa.evaluate": ("format_frame", "data_to_dict"),
        "truthfulqa.configs": ("BEST_COL", "ANSWER_COL", "INCORRECT_COL"),
        "truthfulqa.metrics": (),
    }
    stubs: dict[str, Any] = {}
    children = {}
    for name, attributes in names.items():
        children[name.split(".")[1]] = stubs[name] = upstream.stub_module(
            name, **{attribute: unavailable for attribute in attributes}
        )
    parent = upstream.stub_module("truthfulqa", **children)
    baukit = upstream.stub_module("baukit", Trace=unavailable, TraceDict=unavailable)
    # Used only when the real package cannot be imported (load_dataset is never called).
    datasets = upstream.stub_module("datasets", load_dataset=unavailable)
    openai = upstream.stub_module("openai")  # TruthfulQA judge only
    return {"truthfulqa": parent, **stubs, "baukit": baukit, "datasets": datasets, "openai": openai}


def _modules() -> tuple[Any, Any]:
    utils = upstream.import_upstream(METHOD, "utils", stubs=_truthfulqa_stubs())
    interveners = upstream.import_upstream(METHOD, "interveners")
    return utils, interveners


def _head_activations(model: Any, tokenizer: Any, texts: list[str], interveners: Any) -> Any:
    """Return ``(N, L_full, H*D)`` float16 o_proj inputs at each text's last token."""
    import numpy as np
    import torch

    blocks = decoder_layers(model)
    layers = full_attention_layers(model)
    device = model_device(model)
    collectors = [interveners.Collector(multiplier=0, head=-1) for _ in layers]

    def pre_hook(collector: Any):
        def hook(module: Any, args: Any) -> None:  # noqa: ARG001
            collector(args[0], None)

        return hook

    rows = []
    handles = [
        blocks[layer].self_attn.o_proj.register_forward_pre_hook(pre_hook(collector))
        for layer, collector in zip(layers, collectors, strict=True)
    ]
    with hooks(handles), torch.no_grad():
        for text in texts:
            ids = torch.tensor([encode(tokenizer, text)], device=device)
            model(input_ids=ids, logits_to_keep=1)
            # Same reduction as get_llama_activations_pyvene: stack per layer, fp16.
            rows.append(
                np.stack(
                    [collector.states[-1].to(torch.float16).cpu().numpy() for collector in collectors]
                )
            )
            for collector in collectors:
                collector.reset()
    return np.stack(rows)


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    num_heads_to_intervene: int,
    seed: int,
    val_ratio: float,
    output_path: Any,
    model_id: str,
    model_revision: str,
) -> Any:
    import numpy as np
    import torch
    from einops import rearrange

    utils, interveners = _modules()
    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 3:
        raise ValueError("ITI needs at least three training repair pairs (probe train/val split)")
    model = runtime.hf_model
    num_heads, head_dim = attention_shape(model)
    layers = full_attention_layers(model)
    num_layers = len(layers)
    texts = [text for pair in train for text in (pair.prompt + pair.positive, pair.prompt + pair.negative)]
    activations = _head_activations(model, runtime.tokenizer, texts, interveners)
    head_wise = rearrange(activations, "b l (h d) -> b l h d", h=num_heads)
    separated_head_wise_activations = [head_wise[2 * index : 2 * index + 2] for index in range(len(train))]
    separated_labels = [[1, 0] for _ in train]

    # validate_2fold.py: np.random.seed(args.seed); lines 143-144.
    np.random.seed(seed)
    train_idxs = np.arange(len(train))
    train_set_idxs = np.random.choice(train_idxs, size=int(len(train_idxs) * (1 - val_ratio)), replace=False)
    val_set_idxs = np.array([x for x in train_idxs if x not in train_set_idxs])
    if len(train_set_idxs) == 0 or len(val_set_idxs) == 0:
        raise ValueError("ITI probe split left an empty train or validation set")

    com_directions = utils.get_com_directions(
        num_layers, num_heads, train_set_idxs, val_set_idxs,
        separated_head_wise_activations, separated_labels,
    )
    top_heads, _probes = utils.get_top_heads(
        train_set_idxs, val_set_idxs, separated_head_wise_activations, separated_labels,
        num_layers, num_heads, seed, num_heads_to_intervene, False,
    )

    # validate_2fold.py lines 160-175.  tuning_activations follows the default
    # activations_dataset='tqa_gen_end_q': o_proj inputs at the end of the prompt.
    tuning_activations = rearrange(
        _head_activations(model, runtime.tokenizer, [pair.prompt for pair in train], interveners),
        "b l (h d) -> b l h d",
        h=num_heads,
    )
    top_heads_by_layer: dict[int, list[int]] = {}
    for layer, head in top_heads:
        if layer not in top_heads_by_layer:
            top_heads_by_layer[layer] = []
        top_heads_by_layer[layer].append(head)
    directions: dict[str, Any] = {}
    for layer, heads in top_heads_by_layer.items():
        direction = torch.zeros(head_dim * num_heads).to("cpu")
        for head in heads:
            dir = torch.tensor(com_directions[utils.layer_head_to_flattened_idx(layer, head, num_heads)], dtype=torch.float32).to("cpu")  # noqa: A001
            dir = dir / torch.norm(dir)  # noqa: A001
            activations_ = torch.tensor(tuning_activations[:, layer, head, :], dtype=torch.float32).to("cpu")
            proj_vals = activations_ @ dir.T
            proj_val_std = torch.std(proj_vals)
            direction[head * head_dim : (head + 1) * head_dim] = dir * proj_val_std
        directions[str(layers[int(layer)])] = direction

    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={
            "num_heads_to_intervene": int(num_heads_to_intervene),
            "seed": int(seed),
            "val_ratio": float(val_ratio),
            "use_center_of_mass": True,
            "tuning_activations": "last token of each training prompt (tqa_gen_end_q analogue)",
            "full_attention_layers": layers,
            "top_heads": [[int(layers[int(layer)]), int(head)] for layer, head in top_heads],
            "probe_train_pairs": [train[int(i)].pair_id for i in train_set_idxs],
            "probe_val_pairs": [train[int(i)].pair_id for i in val_set_idxs],
            "data": pair_summary(train),
        },
        deviations=DEVIATIONS,
        state={"directions": directions},
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,  # noqa: ARG001
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,  # noqa: ARG001  (heads span several layers)
    prompt_ids: list[int],  # noqa: ARG001
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    _utils, interveners = _modules()
    blocks = decoder_layers(model)
    intervene_on_prompt = bool(options.get("intervene_on_prompt", False))
    trace = {"alpha": float(strength), "intervene_on_prompt": intervene_on_prompt,
             "layers": sorted(int(key) for key in artifact["state"]["directions"]),
             "applied_edits": 0}
    handles = []
    used = []
    for key, direction in artifact["state"]["directions"].items():
        intervener = interveners.ITI_Intervener(direction, strength)
        used.append(intervener)

        def hook(module: Any, args: Any, intervener: Any = intervener) -> Any:  # noqa: ARG001
            b = args[0]
            if b.shape[1] > 1 and not intervene_on_prompt:
                return None
            intervener(b, None)
            trace["applied_edits"] += 1  # one position (b[0, -1]) of one layer
            return (b, *args[1:])

        handles.append(blocks[int(key)].self_attn.o_proj.register_forward_pre_hook(hook))
    try:
        with hooks(handles):
            yield trace
    finally:
        for intervener in used:
            intervener.reset()
