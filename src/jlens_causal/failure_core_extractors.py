"""Generic MERA/SADI/ITI/AUSteer extraction from Tau2 repair pairs."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_austeer_artifact,
    build_iti_artifact,
    build_mera_artifact,
    build_sadi_artifact,
    save_austeer_artifact,
    save_iti_artifact,
    save_mera_artifact,
    save_sadi_artifact,
)
from jlens_causal.failure_caa import paired_action_inputs
from jlens_causal.modeling import ModelRuntime, capture_block_outputs

_SOURCES = {
    "mera": {
        "repository": "annahedstroem/MERA-steering",
        "revision": "1a1e6880e885ef9905815baed065e0cbbeed70c7",
    },
    "sadi": {
        "repository": "weixuan-wang123/SADI",
        "revision": "47b11e4f0818ce4ca625f0c86e59f882ddb0656b",
    },
    "iti": {
        "repository": "likenneth/honest_llama",
        "revision": "2c6b2179be7b5aa8f0a171688cf9e01b812ca327",
    },
    "austeer": {
        "repository": "zijian678/AUSteer",
        "revision": "d6573876734f662824062a69c5b9dee31ae57f81",
    },
}


def select_failure_pairs(
    pairs: Iterable[dict[str, Any]], failure_category: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Return disjoint artifact-fit and hyperparameter-validation pairs."""
    selected = [pair for pair in pairs if pair.get("failure_category") == failure_category]
    train = [pair for pair in selected if pair.get("split") == "train"]
    validation = [pair for pair in selected if pair.get("split") == "validation"]
    if len(train) < 2 or len(validation) < 2:
        raise ValueError(
            "generic Core extraction requires at least two train and two validation pairs"
        )
    ids = [str(pair["pair_id"]) for pair in selected]
    if len(ids) != len(set(ids)):
        raise ValueError("failure repair pair IDs must be unique")
    return train, validation


def _modules(runtime: ModelRuntime, site: str) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        if site == "post_attention_layernorm":
            module = getattr(block, "post_attention_layernorm", None)
        elif site == "mlp_output":
            module = getattr(block, "mlp", None)
        elif site == "attention_o_proj_input":
            module = getattr(getattr(block, "self_attn", None), "o_proj", None)
        else:
            raise ValueError(f"unknown extraction site {site}")
        if module is None:
            raise ValueError(f"model layer {index} lacks site {site}")
        modules.append(module)
    return modules


@contextmanager
def _capture_inputs(modules: list[Any], layers: tuple[int, ...]):
    captured: dict[int, Any] = {}
    handles = []
    try:
        for layer in layers:

            def hook(_module: Any, inputs: Any, *, selected: int = layer) -> None:
                captured[selected] = inputs[0].detach()
                return None

            handles.append(modules[layer].register_forward_pre_hook(hook))
        yield captured
    finally:
        for handle in reversed(handles):
            handle.remove()


def _capture(
    runtime: ModelRuntime,
    *,
    input_ids: Any,
    position: int,
    layers: tuple[int, ...],
    site: str,
    reshape: Callable[[Any], Any] | None = None,
) -> dict[int, Any]:
    modules = _modules(runtime, site)
    context = (
        _capture_inputs(modules, layers)
        if site == "attention_o_proj_input"
        else capture_block_outputs(modules, layers)
    )
    with runtime.torch.inference_mode(), context as activations:
        runtime.lens_model.forward(input_ids)
    values = {layer: activations[layer][0, position].detach().float().cpu() for layer in layers}
    if reshape is not None:
        values = {layer: reshape(value) for layer, value in values.items()}
    return values


def _pair_activations(
    runtime: ModelRuntime,
    pair: dict[str, Any],
    *,
    layers: tuple[int, ...],
    site: str,
    reshape: Callable[[Any], Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> tuple[dict[int, Any], dict[int, Any]]:
    positive, negative = paired_action_inputs(
        runtime,
        context_messages=pair["context_messages"],
        positive_message=pair["positive_repaired_message"],
        negative_message=pair["negative_failed_message"],
        tools=tools,
    )
    return (
        _capture(
            runtime,
            input_ids=positive[0],
            position=positive[1],
            layers=layers,
            site=site,
            reshape=reshape,
        ),
        _capture(
            runtime,
            input_ids=negative[0],
            position=negative[1],
            layers=layers,
            site=site,
            reshape=reshape,
        ),
    )


def _collect(
    runtime: ModelRuntime,
    pairs: list[dict[str, Any]],
    *,
    layers: tuple[int, ...],
    site: str,
    reshape: Callable[[Any], Any] | None = None,
    tools: list[dict[str, Any]] | None = None,
) -> tuple[dict[int, list[Any]], dict[int, list[Any]]]:
    correct = {layer: [] for layer in layers}
    failure = {layer: [] for layer in layers}
    for pair in pairs:
        positive, negative = _pair_activations(
            runtime, pair, layers=layers, site=site, reshape=reshape, tools=tools
        )
        for layer in layers:
            correct[layer].append(positive[layer])
            failure[layer].append(negative[layer])
    return correct, failure


def _metadata(failure_category: str) -> dict[str, Any]:
    return {
        "failure_category": failure_category,
        "pair_schema": "agent-failure-repair-pair-v1",
        "train_split": "train",
        "validation_split": "validation",
        "future_messages_excluded": True,
    }


def extract_failure_mera(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    output_dir: str | Path,
    alpha_grid: Iterable[float] = (0.5, 0.7, 0.8, 0.9, 0.95),
    tools: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    train, validation = select_failure_pairs(pairs, failure_category)
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    output = Path(output_dir).expanduser().resolve()
    expected = [output / f"mera-layer-{layer}.pt" for layer in layer_tuple]
    if not force and all(path.is_file() for path in expected):
        return {"paths": [str(path) for path in expected], "status": "already_complete"}
    train_correct, train_failure = _collect(
        runtime,
        train,
        layers=layer_tuple,
        site="post_attention_layernorm",
        tools=tools,
    )
    val_correct, val_failure = _collect(
        runtime,
        validation,
        layers=layer_tuple,
        site="post_attention_layernorm",
        tools=tools,
    )
    paths = []
    selections = {}
    for layer in layer_tuple:
        artifact = build_mera_artifact(
            runtime.torch,
            model_id=model_id,
            model_revision=model_revision,
            layer=layer,
            train_correct=train_correct[layer],
            train_failure=train_failure[layer],
            validation_correct=val_correct[layer],
            validation_failure=val_failure[layer],
            train_pair_ids=[str(pair["pair_id"]) for pair in train],
            validation_correct_ids=[f"{pair['pair_id']}:correct" for pair in validation],
            validation_failure_ids=[f"{pair['pair_id']}:failure" for pair in validation],
            alpha_grid=list(alpha_grid),
            benchmark="taubench-airline-failure-modes",
            calibration_split=_metadata(failure_category),
            site="post_attention_layernorm_last_divergent_action_token",
            source=_SOURCES["mera"],
        )
        path = output / f"mera-layer-{layer}.pt"
        paths.append(str(save_mera_artifact(runtime.torch, artifact, path)))
        selections[str(layer)] = artifact["selected_alpha"]
    return {"paths": paths, "selected_alpha": selections}


def extract_failure_sadi(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    output_dir: str | Path,
    top_k: int = 20,
    tools: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    path = Path(output_dir).expanduser().resolve() / "sadi-hidden-units.pt"
    if path.is_file() and not force:
        return {"path": str(path), "status": "already_complete"}
    train, validation = select_failure_pairs(pairs, failure_category)
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    train_correct, train_failure = _collect(
        runtime, train, layers=layer_tuple, site="mlp_output", tools=tools
    )
    val_correct, val_failure = _collect(
        runtime, validation, layers=layer_tuple, site="mlp_output", tools=tools
    )
    artifact = build_sadi_artifact(
        runtime.torch,
        model_id=model_id,
        model_revision=model_revision,
        correct_by_layer=train_correct,
        failure_by_layer=train_failure,
        pair_ids=[str(pair["pair_id"]) for pair in train],
        top_k=top_k,
        benchmark="taubench-airline-failure-modes",
        calibration_split=_metadata(failure_category),
        site="mlp_output_last_divergent_action_token",
        source=_SOURCES["sadi"],
        validation_correct_by_layer=val_correct,
        validation_failure_by_layer=val_failure,
        validation_pair_ids=[str(pair["pair_id"]) for pair in validation],
    )
    save_sadi_artifact(runtime.torch, artifact, path)
    return {"path": str(path), "top_k": int(artifact["top_k"])}


def _attention_shape(runtime: ModelRuntime) -> tuple[int, int]:
    config = runtime.hf_model.config
    text_config = getattr(config, "text_config", config)
    heads = int(text_config.num_attention_heads)
    width = int(runtime.lens_model.d_model)
    if width % heads:
        raise ValueError("model width is not divisible by attention heads")
    return heads, width // heads


def extract_failure_iti(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    output_dir: str | Path,
    top_k: int = 8,
    regularization_c: float = 1.0,
    tools: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    path = Path(output_dir).expanduser().resolve() / "iti-heads.pt"
    if path.is_file() and not force:
        return {"path": str(path), "status": "already_complete"}
    train, validation = select_failure_pairs(pairs, failure_category)
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    heads, head_dim = _attention_shape(runtime)

    def reshape(value: Any) -> Any:
        return value.reshape(heads, head_dim)

    train_correct, train_failure = _collect(
        runtime,
        train,
        layers=layer_tuple,
        site="attention_o_proj_input",
        reshape=reshape,
        tools=tools,
    )
    val_correct, val_failure = _collect(
        runtime,
        validation,
        layers=layer_tuple,
        site="attention_o_proj_input",
        reshape=reshape,
        tools=tools,
    )
    artifact = build_iti_artifact(
        runtime.torch,
        model_id=model_id,
        model_revision=model_revision,
        train_correct_by_layer=train_correct,
        train_failure_by_layer=train_failure,
        validation_correct_by_layer=val_correct,
        validation_failure_by_layer=val_failure,
        train_pair_ids=[str(pair["pair_id"]) for pair in train],
        validation_pair_ids=[str(pair["pair_id"]) for pair in validation],
        top_k=top_k,
        benchmark="taubench-airline-failure-modes",
        calibration_split=_metadata(failure_category),
        site="self_attn_o_proj_input_last_divergent_action_token",
        source=_SOURCES["iti"],
        regularization_c=regularization_c,
    )
    save_iti_artifact(runtime.torch, artifact, path)
    return {
        "path": str(path),
        "selected_heads": artifact["selected_heads"].tolist(),
    }


def extract_failure_austeer(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    output_dir: str | Path,
    top_k: int = 100,
    tools: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    path = Path(output_dir).expanduser().resolve() / "austeer-attention-aus.pt"
    if path.is_file() and not force:
        return {"path": str(path), "status": "already_complete"}
    train, validation = select_failure_pairs(pairs, failure_category)
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    train_correct, train_failure = _collect(
        runtime,
        train,
        layers=layer_tuple,
        site="attention_o_proj_input",
        tools=tools,
    )
    val_correct, val_failure = _collect(
        runtime,
        validation,
        layers=layer_tuple,
        site="attention_o_proj_input",
        tools=tools,
    )
    artifact = build_austeer_artifact(
        runtime.torch,
        model_id=model_id,
        model_revision=model_revision,
        train_correct_by_layer=train_correct,
        train_failure_by_layer=train_failure,
        validation_correct_by_layer=val_correct,
        validation_failure_by_layer=val_failure,
        train_pair_ids=[str(pair["pair_id"]) for pair in train],
        validation_pair_ids=[str(pair["pair_id"]) for pair in validation],
        top_k=top_k,
        benchmark="taubench-airline-failure-modes",
        calibration_split=_metadata(failure_category),
        site="self_attn_o_proj_input_last_divergent_action_token",
        source=_SOURCES["austeer"],
    )
    save_austeer_artifact(runtime.torch, artifact, path)
    return {"path": str(path), "top_k": int(artifact["top_k"])}
