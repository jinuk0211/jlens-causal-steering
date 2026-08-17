"""Sparse dynamic SADI unit extraction for TauBench airline Task 18."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import build_sadi_artifact, load_sadi_artifact, save_sadi_artifact
from jlens_causal.modeling import ModelRuntime, capture_block_outputs
from jlens_causal.taubench_caa import (
    TauBenchCAAConfig,
    _failure_prompt_prefix,
    load_taubench_caa_config,
)

TAUBENCH_SADI_SCHEMA = "taubench-failure-sadi-v1"


@dataclass(frozen=True)
class TauBenchSADIConfig:
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
        return self.output_dir / "artifacts" / "sadi-hidden-units.pt"


def load_taubench_sadi_config(path: str | Path) -> TauBenchSADIConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_SADI_SCHEMA:
        raise ValueError("unsupported TauBench SADI config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the failure-specific SADI pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "weixuan-wang123/SADI"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("SADI source must pin its official repository to a commit")
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
        raise ValueError("SADI extraction layers must be unique non-negative integers")
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
        raise ValueError("SADI train and validation pair indices must be non-empty and disjoint")
    if extraction.get("site") != "mlp_output_last_assistant_content":
        raise ValueError("SADI extraction site does not match the official hidden-output hook")
    if int(extraction.get("max_top_k", 0)) <= 0:
        raise ValueError("SADI max_top_k must be positive")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("SADI sweep section is required")
    top_k_values = sweep.get("top_k_values")
    strengths = sweep.get("strengths")
    if (
        not isinstance(top_k_values, list)
        or not top_k_values
        or not all(isinstance(value, int) and value > 0 for value in top_k_values)
        or max(top_k_values) != int(extraction["max_top_k"])
    ):
        raise ValueError("SADI top_k grid must end at extraction.max_top_k")
    if (
        not isinstance(strengths, list)
        or not strengths
        or any(float(value) < 0.0 for value in strengths)
        or float(sweep.get("primary_strength", -1.0)) not in {float(value) for value in strengths}
        or int(sweep.get("primary_top_k", 0)) not in top_k_values
    ):
        raise ValueError("SADI primary strength/top_k must occur in the non-negative grid")
    seeds = sweep.get("random_seeds")
    if not isinstance(seeds, list) or len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("SADI requires at least three unique random-unit controls")
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
        raise ValueError("SADI train/validation indices must partition all behavior pairs")
    if behavior_config.source_meta_path != source_meta:
        raise ValueError("SADI and behavior configs do not share the source prompt")
    return TauBenchSADIConfig(path, raw, source_meta, behavior_config, output)


def _sadi_modules(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        module = getattr(block, "mlp", None)
        if module is None:
            raise ValueError(f"model layer {index} has no MLP module")
        modules.append(module)
    return modules


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
        raise ValueError("SADI response has no token positions")
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(_sadi_modules(runtime), layers) as outputs,
    ):
        runtime.lens_model.forward(input_ids)
    position = positions[-1]
    return {
        layer: outputs[layer][0, position].detach().float().cpu() for layer in layers
    }


def extract_taubench_task18_sadi(
    config: TauBenchSADIConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    path = config.artifact_path()
    if path.is_file() and not force:
        artifact = load_sadi_artifact(
            runtime.torch,
            path,
            expected_model_id=config.model["model_id"],
        )
        return {
            "path": str(path),
            "status": "already_complete",
            "selected_unit_count": artifact["top_k"],
            "validation_positive_selected_count": artifact[
                "validation_positive_selected_count"
            ],
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
    artifact = build_sadi_artifact(
        runtime.torch,
        model_id=config.model["model_id"],
        model_revision=config.model["model_revision"],
        correct_by_layer={
            layer: [correct[layer][index] for index in train_indices] for layer in layers
        },
        failure_by_layer={
            layer: [failure[layer][index] for index in train_indices] for layer in layers
        },
        pair_ids=[f"task18-binding-pair-{index:02d}" for index in train_indices],
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
            "strength_selection": "preregistered_grid_not_task_reward_tuned",
        },
        site=config.extraction["site"],
        source=config.raw["source"],
        validation_correct_by_layer={
            layer: [correct[layer][index] for index in validation_indices]
            for layer in layers
        },
        validation_failure_by_layer={
            layer: [failure[layer][index] for index in validation_indices]
            for layer in layers
        },
        validation_pair_ids=[
            f"task18-binding-pair-{index:02d}" for index in validation_indices
        ],
    )
    save_sadi_artifact(runtime.torch, artifact, path)
    return {
        "path": str(path),
        "selected_unit_count": artifact["top_k"],
        "validation_positive_selected_count": artifact[
            "validation_positive_selected_count"
        ],
    }
