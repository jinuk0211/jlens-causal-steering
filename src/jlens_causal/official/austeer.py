"""AUSteer (atomic-unit steering) through zijian678/AUSteer's own code.

Upstream code that runs unchanged:
  * ``steer.MFU_screening`` computes the signed sign-consistency score beta
    of every scalar unit of the ``o_proj`` input from ``prompt+pos`` versus
    ``prompt+neg`` activations (window size 1);
  * ``steer.set_MFU`` keeps the global Top-K units by |beta| and writes
    ``alpha * beta`` into each layer's ``activation_mask``.

Reproduced from ``rmodels/modeling_qwen3.py`` line 287 (the forked modeling
file cannot load under transformers 5 nor describe the Qwen3.5 hybrid):
``attn_output = attn_output + attn_output * activation_mask`` immediately
before ``o_proj``, at every position of every forward pass.

What this adapter supplies:
  * ``obtain_act`` (swapped into the ``steer`` module for the duration of the
    fit): the same site and last-token read-out, through forward pre-hooks,
    without the hard-coded 512-token right truncation that would cut every
    Tau2 prompt before the action;
  * a proxy model exposing only the full-attention layers to ``MFU_screening``
    and ``set_MFU`` (Gated DeltaNet layers have no ``self_attn.o_proj``).
"""

from __future__ import annotations

import contextlib
import io
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import RenderedPair, encode, pair_summary
from jlens_causal.official.modelparts import (
    attention_shape,
    decoder_layers,
    full_attention_layers,
    hidden_size,
    hooks,
    model_device,
)

METHOD = "austeer"
UPSTREAM_FILES = ("steer.py", "rmodels/modeling_qwen3.py", "main_test.py", "reproduce.sh")
DEVIATIONS = [
    "obtain_act is replaced for the fit: same o_proj-input site and last token, but no "
    "512-token right truncation (Tau2 prompts are far longer) and fp16 read-out via hooks "
    "instead of pyvene.",
    "Only Qwen3.5 full-attention layers are exposed to MFU_screening/set_MFU.",
    "The mask application line of rmodels/modeling_qwen3.py is reproduced in a forward "
    "pre-hook on o_proj because the forked modeling file targets transformers 4.51/Qwen3.",
]


def _steer_module() -> Any:
    def unavailable(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise RuntimeError("pyvene is not used by the AUSteer adapter")

    return upstream.import_upstream(
        METHOD,
        "steer",
        stubs={"pyvene": upstream.stub_module("pyvene", IntervenableModel=unavailable)},
    )


def _proxy(model: Any) -> Any:
    """Expose full-attention layers under the attribute names steer.py expects."""
    import torch

    heads, head_dim = attention_shape(model)
    layers = full_attention_layers(model)
    return SimpleNamespace(
        config=SimpleNamespace(
            num_hidden_layers=len(layers),
            num_attention_heads=heads,
            head_dim=head_dim,
            hidden_size=hidden_size(model),
        ),
        model=SimpleNamespace(
            layers=[
                SimpleNamespace(
                    self_attn=SimpleNamespace(
                        activation_mask=torch.nn.Parameter(
                            torch.zeros(heads * head_dim), requires_grad=False
                        )
                    )
                )
                for _ in layers
            ]
        ),
        eval=lambda: None,
        real_layers=layers,
    )


def _make_obtain_act(model: Any) -> Any:
    import torch

    blocks = decoder_layers(model)
    layers = full_attention_layers(model)
    device = model_device(model)

    def obtain_act(_proxy_model: Any, tokenizer: Any, samples: list[str], applied_module: str) -> Any:
        if applied_module != "attention":
            raise ValueError("the Tau2 AUSteer adapter supports applied_module='attention'")
        captured: dict[int, Any] = {}

        def pre_hook(index: int):
            def hook(module: Any, args: Any) -> None:  # noqa: ARG001
                captured[index] = args[0][0, -1].detach().to(torch.float16).cpu()

            return hook

        handles = [
            blocks[layer].self_attn.o_proj.register_forward_pre_hook(pre_hook(slot))
            for slot, layer in enumerate(layers)
        ]
        sample_acts = []
        with hooks(handles), torch.no_grad():
            for sample in samples:
                ids = torch.tensor([encode(tokenizer, sample)], device=device)
                model(input_ids=ids, logits_to_keep=1)
                sample_acts.append(torch.stack([captured[slot] for slot in range(len(layers))]))
        return torch.stack(sample_acts)

    return obtain_act


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    output_path: Path,
    model_id: str,
    model_revision: str,
) -> Path:
    import torch

    steer_module = _steer_module()
    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 2:
        raise ValueError("AUSteer needs at least two training repair pairs")
    train_dataset = [[pair.prompt, pair.positive, pair.negative] for pair in train]
    proxy = _proxy(runtime.hf_model)
    original = steer_module.obtain_act
    output_dir = Path(output_path).expanduser().resolve().parent / (Path(output_path).stem + "-screening")
    output_dir.mkdir(parents=True, exist_ok=True)
    log = io.StringIO()
    try:
        steer_module.obtain_act = _make_obtain_act(runtime.hf_model)
        with contextlib.redirect_stdout(log):  # MFU_screening prints whole prompts
            all_scores, all_layer_ids, all_indices = steer_module.MFU_screening(
                train_dataset,
                proxy,
                runtime.tokenizer,
                str(output_dir),
                window_size=1,
                applied_module="attention",
            )
    finally:
        steer_module.obtain_act = original
    (output_dir / "mfu_screening.log").write_text(log.getvalue(), encoding="utf-8")
    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={
            "applied_module": "attention",
            "window_size": 1,
            "full_attention_layers": proxy.real_layers,
            "data": pair_summary(train),
            "nonzero_beta_units": sum(score != 0 for score in all_scores),
        },
        deviations=DEVIATIONS,
        state={
            "all_scores": torch.tensor(all_scores, dtype=torch.float32),
            "all_layer_ids": torch.tensor(all_layer_ids, dtype=torch.long),
            "all_indices": torch.tensor([list(item) for item in all_indices], dtype=torch.long),
        },
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,  # noqa: ARG001
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,  # noqa: ARG001  (units span several layers)
    prompt_ids: list[int],  # noqa: ARG001
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    steer_module = _steer_module()
    top_k = int(options.get("top_k", 8))
    state = artifact["state"]
    proxy = _proxy(model)
    if proxy.real_layers != artifact["fit"]["full_attention_layers"]:
        raise ValueError("AUSteer artifact was fit on a different full-attention layout")
    steer_module.set_MFU(
        [float(value) for value in state["all_scores"].tolist()],
        [int(value) for value in state["all_layer_ids"].tolist()],
        [tuple(int(item) for item in pair) for pair in state["all_indices"].tolist()],
        top_k,
        float(strength),
        proxy,
        "attention",
    )
    masks = {
        real: proxy.model.layers[slot].self_attn.activation_mask.data
        for slot, real in enumerate(proxy.real_layers)
    }
    active = {real: mask for real, mask in masks.items() if bool(mask.abs().sum() > 0)}
    blocks = decoder_layers(model)
    trace = {
        "alpha": float(strength),
        "top_k": top_k,
        "units": {str(real): int((mask != 0).sum()) for real, mask in active.items()},
        "forward_calls": 0,
        "applied_edits": 0,
    }

    def make_hook(mask: Any):
        cache: dict[str, Any] = {}

        def hook(module: Any, args: Any) -> Any:  # noqa: ARG001
            attn_output = args[0]
            key = f"{attn_output.device}:{attn_output.dtype}"
            if key not in cache:
                cache[key] = mask.to(device=attn_output.device, dtype=attn_output.dtype)
            # rmodels/modeling_qwen3.py:287
            attn_output[:, :, :] = attn_output[:, :, :] + attn_output[:, :, :] * cache[key]
            trace["forward_calls"] += 1
            trace["applied_edits"] += int(attn_output.shape[1])  # positions x this layer
            return (attn_output, *args[1:])

        return hook

    handles = [
        blocks[real].self_attn.o_proj.register_forward_pre_hook(make_hook(mask))
        for real, mask in active.items()
    ]
    with hooks(handles):
        yield trace
