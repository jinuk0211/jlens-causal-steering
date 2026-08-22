"""Attention-unit AUSteer extraction for TauBench airline Task 18."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_austeer_artifact,
    load_austeer_artifact,
    save_austeer_artifact,
)
from jlens_causal.modeling import ModelRuntime
from jlens_causal.taubench_caa import (
    TauBenchCAAConfig,
    _failure_prompt_prefix,
    load_taubench_caa_config,
)

TAUBENCH_AUSTEER_SCHEMA = "taubench-failure-austeer-v1"


@dataclass(frozen=True)
class TauBenchAUSteerConfig:
    path: Path
    raw: dict[str, Any]
    source_meta_path: Path
    behavior_config: TauBenchCAAConfig
    output_dir: Path

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    def artifact_path(self) -> Path:
        return self.output_dir / "artifacts" / "austeer-attention-aus.pt"


def load_taubench_austeer_config(path: str | Path) -> TauBenchAUSteerConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_AUSTEER_SCHEMA:
        raise ValueError("unsupported TauBench AUSteer config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the failure-specific AUSteer pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "zijian678/AUSteer"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("AUSteer source must pin its official repository to a commit")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    layers = extraction.get("layers")
    if (
        not isinstance(layers, list)
        or not layers
        or not all(isinstance(value, int) and value >= 0 for value in layers)
        or len(set(layers)) != len(layers)
    ):
        raise ValueError("AUSteer extraction layers must be unique non-negative integers")
    train_indices = extraction.get("train_pair_indices")
    validation_indices = extraction.get("validation_pair_indices")
    if (
        not isinstance(train_indices, list)
        or not isinstance(validation_indices, list)
        or not train_indices
        or not validation_indices
        or not all(isinstance(value, int) and value >= 0 for value in train_indices + validation_indices)
        or set(train_indices).intersection(validation_indices)
    ):
        raise ValueError("AUSteer train and validation indices must be non-empty and disjoint")
    if extraction.get("site") != "self_attn_o_proj_input_last_assistant_content":
        raise ValueError("AUSteer extraction site does not match its attention AU site")
    if int(extraction.get("window_size", 0)) != 1:
        raise ValueError("confirmatory AUSteer requires scalar window_size=1")
    if int(extraction.get("max_top_k", 0)) <= 0:
        raise ValueError("AUSteer max_top_k must be positive")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("AUSteer sweep section is required")
    top_k_values = sweep.get("top_k_values")
    alphas = sweep.get("alphas")
    if (
        not isinstance(top_k_values, list)
        or not top_k_values
        or not all(isinstance(value, int) and value > 0 for value in top_k_values)
        or max(top_k_values) != int(extraction["max_top_k"])
    ):
        raise ValueError("AUSteer top_k grid must end at extraction.max_top_k")
    if (
        not isinstance(alphas, list)
        or not alphas
        or any(float(value) <= 0.0 for value in alphas)
        or float(sweep.get("primary_alpha", 0.0)) not in {float(value) for value in alphas}
        or int(sweep.get("primary_top_k", 0)) not in top_k_values
    ):
        raise ValueError("AUSteer primary alpha/top_k must occur in the positive grid")
    seeds = sweep.get("random_seeds")
    if not isinstance(seeds, list) or len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("AUSteer requires at least three unique random-AU controls")
    source_meta = Path(raw["source_meta_path"]).expanduser()
    behavior_path = Path(raw["behavior_source_config"]).expanduser()
    output = Path(raw["output_dir"]).expanduser()
    source_meta = (
        source_meta if source_meta.is_absolute() else path.parent / source_meta
    ).resolve()
    behavior_path = (
        behavior_path if behavior_path.is_absolute() else path.parent / behavior_path
    ).resolve()
    output = (output if output.is_absolute() else path.parent / output).resolve()
    if not source_meta.is_file():
        raise FileNotFoundError(f"Task 18 source metadata is missing: {source_meta}")
    behavior_config = load_taubench_caa_config(behavior_path)
    pair_count = len(behavior_config.extraction["positive_responses"])
    if set(train_indices + validation_indices) != set(range(pair_count)):
        raise ValueError("AUSteer train/validation indices must partition all behavior pairs")
    if behavior_config.source_meta_path != source_meta:
        raise ValueError("AUSteer and behavior configs do not share the source prompt")
    return TauBenchAUSteerConfig(path, raw, source_meta, behavior_config, output)


def _output_projections(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        module = getattr(getattr(block, "self_attn", None), "o_proj", None)
        if module is None:
            raise ValueError(f"model layer {index} has no attention output projection")
        modules.append(module)
    return modules


@contextmanager
def _capture_projection_inputs(modules: list[Any], layers: tuple[int, ...]):
    captured: dict[int, Any] = {}
    handles = []
    try:
        for layer in layers:

            def hook(_module: Any, inputs: Any, *, selected_layer: int = layer) -> None:
                captured[selected_layer] = inputs[0].detach()
                return None

            handles.append(modules[layer].register_forward_pre_hook(hook))
        yield captured
    finally:
        for handle in reversed(handles):
            handle.remove()


def _response_activations(
    runtime: ModelRuntime,
    *,
    prefix: str,
    response: str,
    closing_text: str,
    layers: tuple[int, ...],
) -> dict[int, Any]:
    full_text = prefix + response + closing_text
    encoded = runtime.tokenizer(
        full_text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    input_ids = encoded["input_ids"].to(runtime.device)
    offsets = [tuple(map(int, item)) for item in encoded["offset_mapping"][0].tolist()]
    start = len(prefix)
    end = start + len(response)
    positions = [
        index
        for index, (left, right) in enumerate(offsets)
        if right > left and right > start and left < end
    ]
    if not positions:
        raise ValueError("AUSteer response has no token positions")
    with (
        runtime.torch.inference_mode(),
        _capture_projection_inputs(_output_projections(runtime), layers) as captured,
    ):
        runtime.lens_model.forward(input_ids)
    position = positions[-1]
    return {
        layer: captured[layer][0, position].detach().float().cpu()
        for layer in layers
    }


def extract_taubench_task18_austeer(
    config: TauBenchAUSteerConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    path = config.artifact_path()
    if path.is_file() and not force:
        artifact = load_austeer_artifact(
            runtime.torch, path, expected_model_id=config.model["model_id"]
        )
        return {
            "path": str(path),
            "status": "already_complete",
            "selected_unit_count": int(artifact["top_k"]),
        }
    layers = tuple(int(value) for value in config.extraction["layers"])
    source = config.behavior_config.extraction
    prefix = _failure_prompt_prefix(config.behavior_config)
    closing = str(config.extraction["assistant_closing_text"])
    correct: dict[int, list[Any]] = {layer: [] for layer in layers}
    failure: dict[int, list[Any]] = {layer: [] for layer in layers}
    for correct_response, failure_response in zip(
        source["positive_responses"], source["negative_responses"], strict=True
    ):
        correct_values = _response_activations(
            runtime,
            prefix=prefix,
            response=correct_response,
            closing_text=closing,
            layers=layers,
        )
        failure_values = _response_activations(
            runtime,
            prefix=prefix,
            response=failure_response,
            closing_text=closing,
            layers=layers,
        )
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    train_indices = [int(value) for value in config.extraction["train_pair_indices"]]
    validation_indices = [
        int(value) for value in config.extraction["validation_pair_indices"]
    ]
    source_hash = hashlib.sha256(config.behavior_config.path.read_bytes()).hexdigest()
    artifact = build_austeer_artifact(
        runtime.torch,
        model_id=config.model["model_id"],
        model_revision=config.model["model_revision"],
        train_correct_by_layer={
            layer: [correct[layer][index] for index in train_indices] for layer in layers
        },
        train_failure_by_layer={
            layer: [failure[layer][index] for index in train_indices] for layer in layers
        },
        validation_correct_by_layer={
            layer: [correct[layer][index] for index in validation_indices]
            for layer in layers
        },
        validation_failure_by_layer={
            layer: [failure[layer][index] for index in validation_indices]
            for layer in layers
        },
        train_pair_ids=[f"task18-binding-pair-{index:02d}" for index in train_indices],
        validation_pair_ids=[
            f"task18-binding-pair-{index:02d}" for index in validation_indices
        ],
        top_k=int(config.extraction["max_top_k"]),
        benchmark="taubench-airline-task18",
        calibration_split={
            "task_id": "18",
            "simulation_id": config.raw["simulation_id"],
            "source_call_index": int(config.raw["source_call_index"]),
            "behavior_source_config": str(config.behavior_config.path),
            "behavior_source_sha256": source_hash,
            "train_pair_indices": train_indices,
            "validation_pair_indices": validation_indices,
            "hyperparameter_selection": "preregistered_grid_not_task_reward_tuned",
        },
        site=config.extraction["site"],
        source=config.raw["source"],
    )
    save_austeer_artifact(runtime.torch, artifact, path)
    return {
        "path": str(path),
        "selected_unit_count": int(artifact["top_k"]),
        "validation_sign_agreement_count": int(
            artifact["validation_sign_agreement_count"]
        ),
    }
