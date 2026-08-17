"""Failure-specific CAA direction extraction for TauBench trajectories."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import build_caa_artifact, save_caa_artifact
from jlens_causal.modeling import ModelRuntime, capture_block_outputs

TAUBENCH_CAA_SCHEMA = "taubench-failure-caa-v1"


@dataclass(frozen=True)
class TauBenchCAAConfig:
    path: Path
    raw: dict[str, Any]
    source_meta_path: Path
    output_dir: Path

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    def direction_path(self, layer: int) -> Path:
        return self.output_dir / "directions" / f"caa-layer-{int(layer)}.pt"


def load_taubench_caa_config(path: str | Path) -> TauBenchCAAConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_CAA_SCHEMA:
        raise ValueError("unsupported TauBench CAA config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the first failure-specific CAA pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    revision = model.get("model_revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    layers = extraction.get("layers")
    if (
        not isinstance(layers, list)
        or not layers
        or not all(isinstance(layer, int) and layer >= 0 for layer in layers)
    ):
        raise ValueError("extraction.layers must be non-negative integers")
    positive = extraction.get("positive_responses")
    negative = extraction.get("negative_responses")
    if (
        not isinstance(positive, list)
        or not isinstance(negative, list)
        or len(positive) != len(negative)
        or len(positive) < 4
        or not all(isinstance(value, str) and value.strip() for value in positive + negative)
    ):
        raise ValueError("CAA requires at least four non-empty paired responses")
    if extraction.get("site") != "assistant_response_last_content":
        raise ValueError("unknown TauBench CAA extraction site")
    source = Path(raw["source_meta_path"]).expanduser()
    output = Path(raw["output_dir"]).expanduser()
    source = (source if source.is_absolute() else path.parent / source).resolve()
    output = (output if output.is_absolute() else path.parent / output).resolve()
    if not source.is_file():
        raise FileNotFoundError(f"Task 18 source metadata is missing: {source}")
    return TauBenchCAAConfig(
        path=path,
        raw=raw,
        source_meta_path=source,
        output_dir=output,
    )


def _failure_prompt_prefix(config: TauBenchCAAConfig) -> str:
    metadata = json.loads(config.source_meta_path.read_text(encoding="utf-8"))
    prompt = metadata.get("prompt")
    if not isinstance(prompt, str):
        raise ValueError("source meta.json has no rendered prompt")
    marker = str(config.extraction["assistant_marker"])
    if marker not in prompt:
        raise ValueError("assistant marker is absent from the rendered failure prompt")
    prefix, _failure_response = prompt.rsplit(marker, 1)
    return prefix + marker


def _raw_response_activations(
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
    response_positions = [
        index
        for index, (left, right) in enumerate(offsets)
        if right > left and right > start and left < end
    ]
    if not response_positions:
        raise ValueError("paired response has no token positions")
    position = response_positions[-1]
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, layers) as activations,
    ):
        runtime.lens_model.forward(input_ids)
    return {layer: activations[layer][0, position].detach().float().cpu() for layer in layers}


def _prefill_prefix_cache(runtime: ModelRuntime, prefix: str) -> tuple[Any, Any]:
    """Run the shared long Task-18 prefix once and retain its exact HF cache."""

    encoded = runtime.tokenizer(
        prefix,
        add_special_tokens=False,
        return_tensors="pt",
    )
    prefix_ids = encoded["input_ids"].to(runtime.device)
    attention_mask = encoded["attention_mask"].to(runtime.device)
    with runtime.torch.inference_mode():
        outputs = runtime.hf_model(
            input_ids=prefix_ids,
            attention_mask=attention_mask,
            use_cache=True,
            logits_to_keep=1,
            return_dict=True,
        )
    cache = getattr(outputs, "past_key_values", None)
    if cache is None:
        raise ValueError("the HF model did not return a prefix cache")
    return prefix_ids.detach().cpu(), cache


def _cached_response_activations(
    runtime: ModelRuntime,
    *,
    prefix: str,
    prefix_ids: Any,
    prefix_cache: Any,
    response: str,
    closing_text: str,
    layers: tuple[int, ...],
) -> dict[int, Any]:
    """Teacher-force one response from a cloned common-prefix cache."""

    full_text = prefix + response + closing_text
    encoded = runtime.tokenizer(
        full_text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    full_ids = encoded["input_ids"]
    prefix_length = int(prefix_ids.shape[1])
    if full_ids.shape[1] <= prefix_length or not runtime.torch.equal(
        full_ids[:, :prefix_length].cpu(), prefix_ids.cpu()
    ):
        raise ValueError("response tokenization is not separable from the cached prefix")
    offsets = [tuple(map(int, item)) for item in encoded["offset_mapping"][0].tolist()]
    response_start = len(prefix)
    response_end = response_start + len(response)
    response_positions = [
        index
        for index, (left, right) in enumerate(offsets)
        if right > left and right > response_start and left < response_end
    ]
    if not response_positions:
        raise ValueError("paired response has no token positions")
    absolute_position = response_positions[-1]
    suffix_position = absolute_position - prefix_length
    if suffix_position < 0:
        raise ValueError("the response position falls inside the cached prefix")
    suffix_ids = full_ids[:, prefix_length:].to(runtime.device)
    attention_mask = runtime.torch.ones(
        (1, int(full_ids.shape[1])),
        dtype=runtime.torch.long,
        device=runtime.device,
    )
    cache = deepcopy(prefix_cache)
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, layers) as activations,
    ):
        runtime.hf_model(
            input_ids=suffix_ids,
            attention_mask=attention_mask,
            past_key_values=cache,
            use_cache=True,
            logits_to_keep=1,
            return_dict=True,
        )
    return {
        layer: activations[layer][0, suffix_position].detach().float().cpu()
        for layer in layers
    }


def extract_taubench_task18_caa(
    config: TauBenchCAAConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    """Build per-layer correct-binding minus global-template CAA artifacts."""
    layers = tuple(int(layer) for layer in config.extraction["layers"])
    paths = [config.direction_path(layer) for layer in layers]
    if not force and all(path.is_file() for path in paths):
        return {
            "pair_count": len(config.extraction["positive_responses"]),
            "paths": [str(path) for path in paths],
        }
    prefix = _failure_prompt_prefix(config)
    closing_text = str(config.extraction["assistant_closing_text"])
    reuse_prefix_cache = bool(config.extraction.get("reuse_prefix_cache", True))
    prefix_ids = None
    prefix_cache = None
    if reuse_prefix_cache:
        prefix_ids, prefix_cache = _prefill_prefix_cache(runtime, prefix)
    positive: dict[int, list[Any]] = {layer: [] for layer in layers}
    negative: dict[int, list[Any]] = {layer: [] for layer in layers}
    for positive_response, negative_response in zip(
        config.extraction["positive_responses"],
        config.extraction["negative_responses"],
        strict=True,
    ):
        if reuse_prefix_cache:
            positive_values = _cached_response_activations(
                runtime,
                prefix=prefix,
                prefix_ids=prefix_ids,
                prefix_cache=prefix_cache,
                response=positive_response,
                closing_text=closing_text,
                layers=layers,
            )
            negative_values = _cached_response_activations(
                runtime,
                prefix=prefix,
                prefix_ids=prefix_ids,
                prefix_cache=prefix_cache,
                response=negative_response,
                closing_text=closing_text,
                layers=layers,
            )
        else:
            positive_values = _raw_response_activations(
                runtime,
                prefix=prefix,
                response=positive_response,
                closing_text=closing_text,
                layers=layers,
            )
            negative_values = _raw_response_activations(
                runtime,
                prefix=prefix,
                response=negative_response,
                closing_text=closing_text,
                layers=layers,
            )
        for layer in layers:
            positive[layer].append(positive_values[layer])
            negative[layer].append(negative_values[layer])
    pair_ids = [
        f"task18-binding-pair-{index:02d}"
        for index in range(len(config.extraction["positive_responses"]))
    ]
    written: list[str] = []
    for layer in layers:
        artifact = build_caa_artifact(
            runtime.torch,
            model_id=config.model["model_id"],
            model_revision=config.model["model_revision"],
            layer=layer,
            positive=positive[layer],
            negative=negative[layer],
            pair_ids=pair_ids,
            positive_label="correct_per_reservation_payment_binding",
            negative_label="global_same_payment_template",
            extraction_site=config.extraction["site"],
            benchmark="taubench-airline-task18",
            calibration_split={
                "task_id": "18",
                "simulation_id": config.raw["simulation_id"],
                "source_call_index": int(config.raw["source_call_index"]),
                "source_meta_path": str(config.source_meta_path),
                "pair_construction": "matched_handwritten_counterfactual_plans",
                "reuse_prefix_cache": reuse_prefix_cache,
            },
        )
        written.append(
            str(
                save_caa_artifact(
                    runtime.torch,
                    artifact,
                    config.direction_path(layer),
                )
            )
        )
    return {"pair_count": len(pair_ids), "paths": written}
