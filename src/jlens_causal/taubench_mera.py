"""Token-adaptive MERA probe extraction for TauBench airline Task 18."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import build_mera_artifact, save_mera_artifact
from jlens_causal.modeling import ModelRuntime, capture_block_outputs
from jlens_causal.taubench_caa import (
    TauBenchCAAConfig,
    _failure_prompt_prefix,
    load_taubench_caa_config,
)

TAUBENCH_MERA_SCHEMA = "taubench-failure-mera-v1"


@dataclass(frozen=True)
class TauBenchMERAConfig:
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

    def artifact_path(self, layer: int) -> Path:
        return self.output_dir / "artifacts" / f"mera-layer-{int(layer)}.pt"


def load_taubench_mera_config(path: str | Path) -> TauBenchMERAConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_MERA_SCHEMA:
        raise ValueError("unsupported TauBench MERA config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the failure-specific MERA pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "annahedstroem/MERA-steering"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("MERA source must pin its official repository to a commit")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    layers = extraction.get("layers")
    if (
        not isinstance(layers, list)
        or not layers
        or not all(isinstance(value, int) and value >= 0 for value in layers)
    ):
        raise ValueError("MERA extraction layers must be non-negative integers")
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
        raise ValueError("MERA train and validation pair indices must be non-empty and disjoint")
    alpha_grid = extraction.get("alpha_grid")
    if (
        not isinstance(alpha_grid, list)
        or not alpha_grid
        or any(not 0.0 < float(value) <= 1.0 for value in alpha_grid)
    ):
        raise ValueError("MERA alpha grid must be in (0, 1]")
    if extraction.get("site") != "post_attention_layernorm_output_last_assistant_content":
        raise ValueError("MERA extraction site does not match the official hook")
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
    if max(train_indices + validation_indices) >= pair_count:
        raise ValueError("MERA pair index is outside the behavior source")
    if set(train_indices + validation_indices) != set(range(pair_count)):
        raise ValueError("MERA train/validation indices must partition all behavior pairs")
    if behavior_config.source_meta_path != source_meta:
        raise ValueError("MERA and behavior configs do not share the source prompt")
    return TauBenchMERAConfig(path, raw, source_meta, behavior_config, output)


def _mera_modules(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        module = getattr(block, "post_attention_layernorm", None)
        if module is None:
            raise ValueError(f"model layer {index} has no post_attention_layernorm")
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
        raise ValueError("MERA response has no token positions")
    modules = _mera_modules(runtime)
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(modules, layers) as outputs,
    ):
        runtime.lens_model.forward(input_ids)
    position = positions[-1]
    return {
        layer: outputs[layer][0, position].detach().float().cpu() for layer in layers
    }


def extract_taubench_task18_mera(
    config: TauBenchMERAConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    layers = tuple(int(value) for value in config.extraction["layers"])
    paths = [config.artifact_path(layer) for layer in layers]
    if not force and all(path.is_file() for path in paths):
        return {"paths": [str(path) for path in paths], "status": "already_complete"}
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
    saved = []
    selections = {}
    for layer in layers:
        artifact = build_mera_artifact(
            runtime.torch,
            model_id=config.model["model_id"],
            model_revision=config.model["model_revision"],
            layer=layer,
            train_correct=[correct[layer][index] for index in train_indices],
            train_failure=[failure[layer][index] for index in train_indices],
            validation_correct=[correct[layer][index] for index in validation_indices],
            validation_failure=[failure[layer][index] for index in validation_indices],
            train_pair_ids=[f"task18-binding-pair-{index:02d}" for index in train_indices],
            validation_correct_ids=[
                f"task18-binding-pair-{index:02d}:correct" for index in validation_indices
            ],
            validation_failure_ids=[
                f"task18-binding-pair-{index:02d}:failure" for index in validation_indices
            ],
            alpha_grid=config.extraction["alpha_grid"],
            benchmark="taubench-airline-task18",
            calibration_split={
                "task_id": "18",
                "simulation_id": config.raw["simulation_id"],
                "source_call_index": int(config.raw["source_call_index"]),
                "behavior_source_config": str(config.behavior_config.path),
                "behavior_source_sha256": source_hash,
                "train_pair_indices": train_indices,
                "validation_pair_indices": validation_indices,
            },
            site=config.extraction["site"],
            source=config.raw["source"],
            target_epsilon=float(config.extraction["target_epsilon"]),
        )
        saved.append(
            str(
                save_mera_artifact(
                    runtime.torch,
                    artifact,
                    config.artifact_path(layer),
                )
            )
        )
        selections[str(layer)] = {
            "selected_alpha": artifact["selected_alpha"],
            "selection_metrics": artifact["selection_metrics"],
        }
    return {"paths": saved, "selections": selections}
