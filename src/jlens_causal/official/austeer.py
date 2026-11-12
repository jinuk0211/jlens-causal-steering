"""AUSteer (atomic-unit steering) through zijian678/AUSteer's own code.

Upstream code that runs unchanged:
  * ``steer.MFU_screening`` computes the signed sign-consistency score beta
    of every scalar unit (window size 1) from ``prompt+pos`` versus
    ``prompt+neg`` last-token activations;
  * ``steer.set_MFU`` keeps the global Top-K units by |beta| and writes
    ``alpha * beta`` into each layer's ``activation_mask``.

Reproduced from ``rmodels/modeling_qwen3.py`` (the forked modeling file
cannot load under transformers 5 nor describe the Qwen3.5 hybrid), at every
position of every forward pass:
  * ``applied_module='attention'`` (line 287):
    ``attn_output = attn_output + attn_output * activation_mask`` before ``o_proj``;
  * ``applied_module='ffn'`` (line 102):
    ``down_proj = down_proj + down_proj * activation_mask`` on the MLP output.

What this adapter supplies:
  * ``obtain_act`` (swapped into the ``steer`` module for the duration of the
    fit): the same sites and last-token read-out, through hooks, without the
    hard-coded 512-token right truncation that would cut every Tau2 prompt
    before the action;
  * a proxy model with the attribute names ``steer.py`` expects.  For
    ``attention`` it exposes only the full-attention layers (Gated DeltaNet
    layers have no ``self_attn.o_proj``); ``ffn`` exists on every layer.
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
    first_tensor,
    full_attention_layers,
    hidden_size,
    hooks,
    model_device,
    replace_first,
)

METHOD = "austeer"
UPSTREAM_FILES = ("steer.py", "rmodels/modeling_qwen3.py", "main_test.py", "reproduce.sh")
APPLIED_MODULES = ("attention", "ffn")
REFUSAL_SPECIAL_CASE = "I'm sorry, but I can't assist"  # steer.py:260
DEVIATIONS = [
    "obtain_act is replaced for the fit: same sites (o_proj input / MLP output) and last "
    "token, but no 512-token right truncation (Tau2 prompts are far longer) and fp16 "
    "read-out via hooks instead of pyvene.",
    "For applied_module='attention' only Qwen3.5 full-attention layers are exposed to "
    "MFU_screening/set_MFU; 'ffn' uses all layers.",
    "The mask application lines of rmodels/modeling_qwen3.py are reproduced in hooks because "
    "the forked modeling file targets transformers 4.51/Qwen3.",
    "Pairs whose positive contains MFU_screening's dataset-specific refusal string are "
    "rejected instead of being silently screened without their prompt.",
]


def _steer_module() -> Any:
    def unavailable(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise RuntimeError("pyvene is not used by the AUSteer adapter")

    return upstream.import_upstream(
        METHOD,
        "steer",
        stubs={"pyvene": upstream.stub_module("pyvene", IntervenableModel=unavailable)},
    )


def _layers_for(model: Any, applied_module: str) -> list[int]:
    if applied_module == "attention":
        return full_attention_layers(model)
    if applied_module == "ffn":
        return list(range(len(decoder_layers(model))))
    raise ValueError(f"AUSteer applied_module must be one of {APPLIED_MODULES}")


def _proxy(model: Any, applied_module: str) -> Any:
    """Expose the steerable layers under the attribute names steer.py expects."""
    import torch

    heads, head_dim = attention_shape(model)
    layers = _layers_for(model, applied_module)
    width = heads * head_dim if applied_module == "attention" else hidden_size(model)

    def slot() -> Any:
        mask = SimpleNamespace(
            activation_mask=torch.nn.Parameter(torch.zeros(width), requires_grad=False)
        )
        return SimpleNamespace(self_attn=mask) if applied_module == "attention" else SimpleNamespace(mlp=mask)

    return SimpleNamespace(
        config=SimpleNamespace(
            num_hidden_layers=len(layers),
            num_attention_heads=heads,
            head_dim=head_dim,
            hidden_size=hidden_size(model),
        ),
        model=SimpleNamespace(layers=[slot() for _ in layers]),
        eval=lambda: None,
        real_layers=layers,
    )


def _mask(proxy: Any, slot: int, applied_module: str) -> Any:
    owner = proxy.model.layers[slot]
    return (owner.self_attn if applied_module == "attention" else owner.mlp).activation_mask.data


def _make_obtain_act(model: Any) -> Any:
    import torch

    blocks = decoder_layers(model)
    device = model_device(model)

    def obtain_act(_proxy_model: Any, tokenizer: Any, samples: list[str], applied_module: str) -> Any:
        layers = _layers_for(model, applied_module)
        captured: dict[int, Any] = {}

        def pre_hook(index: int):  # o_proj input
            def hook(module: Any, args: Any) -> None:  # noqa: ARG001
                captured[index] = args[0][0, -1].detach().to(torch.float16).cpu()

            return hook

        def post_hook(index: int):  # mlp output
            def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
                captured[index] = first_tensor(output)[0, -1].detach().to(torch.float16).cpu()

            return hook

        if applied_module == "attention":
            handles = [
                blocks[layer].self_attn.o_proj.register_forward_pre_hook(pre_hook(slot))
                for slot, layer in enumerate(layers)
            ]
        else:
            handles = [
                blocks[layer].mlp.register_forward_hook(post_hook(slot))
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


def _tie_summary(scores: list[float]) -> dict[str, Any]:
    magnitudes = sorted((abs(score) for score in scores), reverse=True)
    top = magnitudes[0] if magnitudes else 0.0
    return {
        "top_abs_beta": float(top),
        "units_at_top_abs_beta": sum(value == top for value in magnitudes),
        "nonzero_beta_units": sum(value != 0 for value in magnitudes),
    }


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    output_path: Path,
    model_id: str,
    model_revision: str,
    applied_modules: tuple[str, ...] = APPLIED_MODULES,
) -> Path:
    import torch

    steer_module = _steer_module()
    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 2:
        raise ValueError("AUSteer needs at least two training repair pairs")
    flagged = [pair.pair_id for pair in train if REFUSAL_SPECIAL_CASE in pair.positive]
    if flagged:
        raise ValueError(
            "MFU_screening drops the prompt of positives containing "
            f"{REFUSAL_SPECIAL_CASE!r} (a dataset-specific rule); remove pairs {flagged}"
        )
    train_dataset = [[pair.prompt, pair.positive, pair.negative] for pair in train]
    output_dir = Path(output_path).expanduser().resolve().parent / (Path(output_path).stem + "-screening")
    original = steer_module.obtain_act
    state: dict[str, Any] = {}
    record: dict[str, Any] = {}
    try:
        steer_module.obtain_act = _make_obtain_act(runtime.hf_model)
        for applied_module in applied_modules:
            proxy = _proxy(runtime.hf_model, applied_module)
            module_dir = output_dir / applied_module
            module_dir.mkdir(parents=True, exist_ok=True)
            log = io.StringIO()
            with contextlib.redirect_stdout(log):  # MFU_screening prints whole prompts
                all_scores, all_layer_ids, all_indices = steer_module.MFU_screening(
                    train_dataset,
                    proxy,
                    runtime.tokenizer,
                    str(module_dir),
                    window_size=1,
                    applied_module=applied_module,
                )
            (module_dir / "mfu_screening.log").write_text(log.getvalue(), encoding="utf-8")
            state[applied_module] = {
                "all_scores": torch.tensor(all_scores, dtype=torch.float32),
                "all_layer_ids": torch.tensor(all_layer_ids, dtype=torch.long),
                "all_indices": torch.tensor([list(item) for item in all_indices], dtype=torch.long),
            }
            record[applied_module] = {"layers": proxy.real_layers, **_tie_summary(all_scores)}
    finally:
        steer_module.obtain_act = original
    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={"window_size": 1, "modules": record, "data": pair_summary(train)},
        deviations=DEVIATIONS,
        state=state,
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
    applied_module = str(options.get("applied_module", "attention"))
    top_k = int(options.get("top_k", 8))
    if applied_module not in artifact["state"]:
        raise ValueError(f"AUSteer artifact has no {applied_module!r} screening")
    state = artifact["state"][applied_module]
    proxy = _proxy(model, applied_module)
    if proxy.real_layers != artifact["fit"]["modules"][applied_module]["layers"]:
        raise ValueError("AUSteer artifact was fit on a different layer layout")
    steer_module.set_MFU(
        [float(value) for value in state["all_scores"].tolist()],
        [int(value) for value in state["all_layer_ids"].tolist()],
        [tuple(int(item) for item in pair) for pair in state["all_indices"].tolist()],
        top_k,
        float(strength),
        proxy,
        applied_module,
    )
    masks = {real: _mask(proxy, slot, applied_module) for slot, real in enumerate(proxy.real_layers)}
    active = {real: mask for real, mask in masks.items() if bool(mask.abs().sum() > 0)}
    blocks = decoder_layers(model)
    trace = {
        "alpha": float(strength),
        "top_k": top_k,
        "applied_module": applied_module,
        "units": {str(real): int((mask != 0).sum()) for real, mask in active.items()},
        "forward_calls": 0,
        "applied_edits": 0,
    }

    def cast_mask(cache: dict[str, Any], mask: Any, tensor: Any) -> Any:
        key = f"{tensor.device}:{tensor.dtype}"
        if key not in cache:
            cache[key] = mask.to(device=tensor.device, dtype=tensor.dtype)
        return cache[key]

    def attention_hook(mask: Any):
        cache: dict[str, Any] = {}

        def hook(module: Any, args: Any) -> Any:  # noqa: ARG001
            attn_output = args[0]
            # rmodels/modeling_qwen3.py:287
            attn_output[:, :, :] = attn_output[:, :, :] + attn_output[:, :, :] * cast_mask(cache, mask, attn_output)
            trace["forward_calls"] += 1
            trace["applied_edits"] += int(attn_output.shape[1])  # positions x this layer
            return (attn_output, *args[1:])

        return hook

    def ffn_hook(mask: Any):
        cache: dict[str, Any] = {}

        def hook(module: Any, args: Any, output: Any) -> Any:  # noqa: ARG001
            down_proj = first_tensor(output)
            # rmodels/modeling_qwen3.py:102
            down_proj[:, :, :] = down_proj[:, :, :] + down_proj[:, :, :] * cast_mask(cache, mask, down_proj)
            trace["forward_calls"] += 1
            trace["applied_edits"] += int(down_proj.shape[1])
            return replace_first(output, down_proj)

        return hook

    if applied_module == "attention":
        handles = [
            blocks[real].self_attn.o_proj.register_forward_pre_hook(attention_hook(mask))
            for real, mask in active.items()
        ]
    else:
        handles = [blocks[real].mlp.register_forward_hook(ffn_hook(mask)) for real, mask in active.items()]
    with hooks(handles):
        yield trace
