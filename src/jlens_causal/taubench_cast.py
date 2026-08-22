"""Failure-conditioned CAST extraction for TauBench airline Task 18."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_cast_artifact,
    cast_condition_similarity,
    cast_pca_pairwise,
    save_cast_artifact,
    select_cast_gate,
)
from jlens_causal.modeling import (
    ModelRuntime,
    capture_block_inputs,
    capture_block_outputs,
)
from jlens_causal.taubench_caa import (
    TauBenchCAAConfig,
    _failure_prompt_prefix,
    load_taubench_caa_config,
)

TAUBENCH_CAST_SCHEMA = "taubench-failure-cast-v1"


@dataclass(frozen=True)
class TauBenchCASTConfig:
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

    def artifact_path(self, behavior_layer: int) -> Path:
        return self.output_dir / "artifacts" / f"cast-layer-{int(behavior_layer)}.pt"


def _string_pairs(section: Any, *, label: str, minimum: int) -> tuple[list[str], list[str]]:
    if not isinstance(section, dict):
        raise ValueError(f"{label} must be an object")
    positive = section.get("positive")
    negative = section.get("negative")
    if (
        not isinstance(positive, list)
        or not isinstance(negative, list)
        or len(positive) != len(negative)
        or len(positive) < minimum
        or not all(isinstance(value, str) and value.strip() for value in positive + negative)
    ):
        raise ValueError(f"{label} requires at least {minimum} non-empty paired strings")
    if set(positive).intersection(negative):
        raise ValueError(f"{label} positive and negative strings overlap")
    return positive, negative


def load_taubench_cast_config(path: str | Path) -> TauBenchCASTConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_CAST_SCHEMA:
        raise ValueError("unsupported TauBench CAST config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the failure-specific CAST pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "IBM/activation-steering"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("CAST source must pin IBM/activation-steering to a commit")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    for key in ("behavior_layers", "condition_layers"):
        values = extraction.get(key)
        if (
            not isinstance(values, list)
            or not values
            or not all(isinstance(value, int) and value >= 0 for value in values)
            or len(set(values)) != len(values)
        ):
            raise ValueError(f"extraction.{key} must be unique non-negative integers")
    if extraction.get("comparison_mode") not in {"mean", "last"}:
        raise ValueError("CAST comparison_mode must be mean or last")
    _string_pairs(extraction.get("condition_train"), label="condition_train", minimum=4)
    _string_pairs(extraction.get("gate_validation"), label="gate_validation", minimum=2)
    train_values = set(
        extraction["condition_train"]["positive"]
        + extraction["condition_train"]["negative"]
    )
    validation_values = set(
        extraction["gate_validation"]["positive"]
        + extraction["gate_validation"]["negative"]
    )
    if train_values.intersection(validation_values):
        raise ValueError("CAST condition training and gate validation strings overlap")
    expected_sites = {
        "behavior_extraction": "block_output_assistant_content_mean",
        "condition_extraction": "block_output_prompt_mean",
        "gate_measurement": "block_input_prompt",
        "behavior_application": "block_input",
    }
    if extraction.get("sites") != expected_sites:
        raise ValueError("CAST extraction.sites must match the official layer sites")
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
    if behavior_config.source_meta_path != source_meta:
        raise ValueError("CAST and behavior-pair configs do not share the same source prompt")
    if behavior_config.model["model_id"] != model["model_id"]:
        raise ValueError("CAST and behavior-pair configs do not share the same model")
    return TauBenchCASTConfig(
        path=path,
        raw=raw,
        source_meta_path=source_meta,
        behavior_config=behavior_config,
        output_dir=output,
    )


def _replace_last_user_message(config: TauBenchCASTConfig, content: str) -> str:
    prompt = _failure_prompt_prefix(config.behavior_config)
    assistant_marker = str(config.extraction["assistant_marker"])
    user_marker = str(config.extraction["user_marker"])
    closing = str(config.extraction["message_closing_text"])
    if not prompt.endswith(assistant_marker):
        raise ValueError("failure prefix does not end at the configured assistant marker")
    before_assistant = prompt[: -len(assistant_marker)]
    marker_index = before_assistant.rfind(user_marker)
    if marker_index < 0:
        raise ValueError("failure prefix has no final user message")
    content_start = marker_index + len(user_marker)
    content_end = before_assistant.find(closing, content_start)
    if content_end < 0:
        raise ValueError("failure prefix final user message is not closed")
    return (
        before_assistant[:content_start]
        + content
        + before_assistant[content_end:]
        + assistant_marker
    )


def _raw_prompt_captures(
    runtime: ModelRuntime,
    *,
    text: str,
    output_layers: tuple[int, ...] = (),
    input_layers: tuple[int, ...] = (),
) -> tuple[dict[int, Any], dict[int, Any]]:
    input_ids = runtime.tokenizer(
        text,
        add_special_tokens=False,
        return_tensors="pt",
    )["input_ids"].to(runtime.device)
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, output_layers) as outputs,
        capture_block_inputs(runtime.lens_model.layers, input_layers) as inputs,
    ):
        runtime.lens_model.forward(input_ids)
    return (
        {layer: value[0].detach().float().cpu() for layer, value in outputs.items()},
        {layer: value[0].detach().float().cpu() for layer, value in inputs.items()},
    )


def _raw_response_output_means(
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
        raise ValueError("CAST behavior response has no token positions")
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, layers) as outputs,
    ):
        runtime.lens_model.forward(input_ids)
    return {
        layer: outputs[layer][0, positions, :].mean(dim=0).detach().float().cpu()
        for layer in layers
    }


def extract_taubench_task18_cast(
    config: TauBenchCASTConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Build CAST artifacts from paired plans and disjoint prompt paraphrases."""
    behavior_layers = tuple(int(value) for value in config.extraction["behavior_layers"])
    condition_layers = tuple(int(value) for value in config.extraction["condition_layers"])
    paths = [config.artifact_path(layer) for layer in behavior_layers]
    if not force and all(path.is_file() for path in paths):
        return {"paths": [str(path) for path in paths], "status": "already_complete"}
    behavior_source = config.behavior_config.extraction
    prefix = _failure_prompt_prefix(config.behavior_config)
    closing = str(config.extraction["assistant_closing_text"])
    behavior_positive: dict[int, list[Any]] = {layer: [] for layer in behavior_layers}
    behavior_negative: dict[int, list[Any]] = {layer: [] for layer in behavior_layers}
    for positive_response, negative_response in zip(
        behavior_source["positive_responses"],
        behavior_source["negative_responses"],
        strict=True,
    ):
        positive = _raw_response_output_means(
            runtime,
            prefix=prefix,
            response=positive_response,
            closing_text=closing,
            layers=behavior_layers,
        )
        negative = _raw_response_output_means(
            runtime,
            prefix=prefix,
            response=negative_response,
            closing_text=closing,
            layers=behavior_layers,
        )
        for layer in behavior_layers:
            behavior_positive[layer].append(positive[layer])
            behavior_negative[layer].append(negative[layer])

    train_positive, train_negative = _string_pairs(
        config.extraction["condition_train"], label="condition_train", minimum=4
    )
    condition_positive: dict[int, list[Any]] = {layer: [] for layer in condition_layers}
    condition_negative: dict[int, list[Any]] = {layer: [] for layer in condition_layers}
    for positive_text, negative_text in zip(train_positive, train_negative, strict=True):
        positive_outputs, _ = _raw_prompt_captures(
            runtime,
            text=_replace_last_user_message(config, positive_text),
            output_layers=condition_layers,
        )
        negative_outputs, _ = _raw_prompt_captures(
            runtime,
            text=_replace_last_user_message(config, negative_text),
            output_layers=condition_layers,
        )
        for layer in condition_layers:
            condition_positive[layer].append(positive_outputs[layer].mean(dim=0))
            condition_negative[layer].append(negative_outputs[layer].mean(dim=0))
    condition_results = {
        layer: cast_pca_pairwise(
            runtime.torch,
            positive=condition_positive[layer],
            negative=condition_negative[layer],
        )
        for layer in condition_layers
    }

    gate_positive, gate_negative = _string_pairs(
        config.extraction["gate_validation"], label="gate_validation", minimum=2
    )
    positive_scores: dict[int, list[float]] = {layer: [] for layer in condition_layers}
    negative_scores: dict[int, list[float]] = {layer: [] for layer in condition_layers}
    comparison_mode = str(config.extraction["comparison_mode"])
    for positive_text, negative_text in zip(gate_positive, gate_negative, strict=True):
        _, positive_inputs = _raw_prompt_captures(
            runtime,
            text=_replace_last_user_message(config, positive_text),
            input_layers=condition_layers,
        )
        _, negative_inputs = _raw_prompt_captures(
            runtime,
            text=_replace_last_user_message(config, negative_text),
            input_layers=condition_layers,
        )
        for layer in condition_layers:
            direction = condition_results[layer]["direction"]
            positive_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        positive_inputs[layer],
                        direction,
                        comparison_mode=comparison_mode,
                    )
                )
            )
            negative_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        negative_inputs[layer],
                        direction,
                        comparison_mode=comparison_mode,
                    )
                )
            )
    gate = select_cast_gate(
        positive_scores=positive_scores,
        negative_scores=negative_scores,
    )
    condition_layer = int(gate["condition_layer"])
    behavior_pair_ids = [
        f"task18-binding-pair-{index:02d}"
        for index in range(len(behavior_source["positive_responses"]))
    ]
    condition_pair_ids = [
        f"task18-condition-train-{index:02d}" for index in range(len(train_positive))
    ]
    validation_ids = [
        f"task18-condition-validation-{index:02d}"
        for index in range(len(gate_positive))
    ]
    behavior_config_hash = hashlib.sha256(
        config.behavior_config.path.read_bytes()
    ).hexdigest()
    saved: list[str] = []
    for behavior_layer in behavior_layers:
        artifact = build_cast_artifact(
            runtime.torch,
            model_id=config.model["model_id"],
            model_revision=config.model["model_revision"],
            behavior_layer=behavior_layer,
            condition_layer=condition_layer,
            behavior_positive=behavior_positive[behavior_layer],
            behavior_negative=behavior_negative[behavior_layer],
            condition_positive=condition_positive[condition_layer],
            condition_negative=condition_negative[condition_layer],
            behavior_pair_ids=behavior_pair_ids,
            condition_pair_ids=condition_pair_ids,
            gate_positive_ids=[f"{value}:positive" for value in validation_ids],
            gate_negative_ids=[f"{value}:negative" for value in validation_ids],
            gate_positive_scores=positive_scores[condition_layer],
            gate_negative_scores=negative_scores[condition_layer],
            gate=gate,
            comparison_mode=comparison_mode,
            benchmark="taubench-airline-task18",
            calibration_split={
                "task_id": "18",
                "simulation_id": config.raw["simulation_id"],
                "source_call_index": int(config.raw["source_call_index"]),
                "source_meta_path": str(config.source_meta_path),
                "behavior_source_config": str(config.behavior_config.path),
                "behavior_source_sha256": behavior_config_hash,
                "condition_training": "paired_counterfactual_final_user_paraphrases",
                "gate_validation": "disjoint_paired_counterfactual_paraphrases",
            },
            sites=config.extraction["sites"],
            source=config.raw["source"],
        )
        saved.append(
            str(
                save_cast_artifact(
                    runtime.torch,
                    artifact,
                    config.artifact_path(behavior_layer),
                )
            )
        )
    return {
        "behavior_pair_count": len(behavior_pair_ids),
        "condition_pair_count": len(condition_pair_ids),
        "gate_pair_count": len(validation_ids),
        "selected_gate": gate,
        "paths": saved,
    }
