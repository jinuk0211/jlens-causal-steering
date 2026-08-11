"""Resumable paired ToolAlign steering sweep."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

from jlens_causal.config import PilotConfig
from jlens_causal.directions import load_directions
from jlens_causal.interventions import (
    AdditiveOperator,
    CoordinateSwapOperator,
    intervention_hook,
)
from jlens_causal.modeling import ModelRuntime, generate_text, render_messages, token_ids_sha256
from jlens_causal.toolalign import ScenarioCase, classify_behavior, load_cases, messages_for_case


@dataclass(frozen=True)
class TrialSpec:
    domain: str
    document: int
    condition: str
    source_scenario: str
    target_scenario: str | None
    direction: str
    method: str
    vector_layer: int | None
    applied_layer: int | None
    alpha: float
    position_policy: str | None
    site: str
    random_seed: int | None = None


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _method_variants(config: PilotConfig, methods: list[str]) -> Iterator[tuple[str, int | None]]:
    for method in methods:
        if method == "random":
            for seed in config.directions["random_seeds"]:
                yield method, int(seed)
        else:
            yield method, None


def iter_trial_specs(config: PilotConfig) -> Iterator[TrialSpec]:
    """Yield the complete grid, sharing one alpha=0 baseline per source case."""
    data = config.data
    sweep = config.sweep
    a = data["scenario_a"]
    b = data["scenario_b"]
    for domain in data["evaluation_domains"]:
        for document in data["evaluation_documents"]:
            for condition in data["conditions"]:
                for scenario in (a, b):
                    yield TrialSpec(
                        domain=domain,
                        document=int(document),
                        condition=condition,
                        source_scenario=scenario,
                        target_scenario=None,
                        direction="none",
                        method="baseline",
                        vector_layer=None,
                        applied_layer=None,
                        alpha=0.0,
                        position_policy=None,
                        site="baseline",
                    )

                for direction in sweep["directions"]:
                    source, target = (a, b) if direction == "a_to_b" else (b, a)
                    for layer in map(int, sweep["layers"]):
                        for alpha in map(float, sweep["alphas"]):
                            if alpha == 0.0:
                                continue
                            for method, random_seed in _method_variants(config, sweep["methods"]):
                                yield TrialSpec(
                                    domain=domain,
                                    document=int(document),
                                    condition=condition,
                                    source_scenario=source,
                                    target_scenario=target,
                                    direction=direction,
                                    method=method,
                                    vector_layer=layer,
                                    applied_layer=layer,
                                    alpha=alpha,
                                    position_policy=sweep["position_policy"],
                                    site="candidate",
                                    random_seed=random_seed,
                                )

                        for alpha in map(float, sweep["site_control_alphas"]):
                            for method, random_seed in _method_variants(
                                config, sweep["site_control_methods"]
                            ):
                                yield TrialSpec(
                                    domain=domain,
                                    document=int(document),
                                    condition=condition,
                                    source_scenario=source,
                                    target_scenario=target,
                                    direction=direction,
                                    method=method,
                                    vector_layer=layer,
                                    applied_layer=int(sweep["wrong_layer"]),
                                    alpha=alpha,
                                    position_policy=sweep["position_policy"],
                                    site="wrong_layer",
                                    random_seed=random_seed,
                                )
                                yield TrialSpec(
                                    domain=domain,
                                    document=int(document),
                                    condition=condition,
                                    source_scenario=source,
                                    target_scenario=target,
                                    direction=direction,
                                    method=method,
                                    vector_layer=layer,
                                    applied_layer=layer,
                                    alpha=alpha,
                                    position_policy=sweep.get(
                                        "wrong_position_policy", "prompt_first"
                                    ),
                                    site="wrong_position",
                                    random_seed=random_seed,
                                )

                        if sweep["include_paper_coordinate_swap"]:
                            for alpha in map(float, sweep["coordinate_swap_alphas"]):
                                for site, applied_layer, position in (
                                    ("candidate", layer, sweep["position_policy"]),
                                    (
                                        "wrong_layer",
                                        int(sweep["wrong_layer"]),
                                        sweep["position_policy"],
                                    ),
                                    (
                                        "wrong_position",
                                        layer,
                                        sweep.get("wrong_position_policy", "prompt_first"),
                                    ),
                                ):
                                    yield TrialSpec(
                                        domain=domain,
                                        document=int(document),
                                        condition=condition,
                                        source_scenario=source,
                                        target_scenario=target,
                                        direction=direction,
                                        method="jlens_swap",
                                        vector_layer=layer,
                                        applied_layer=applied_layer,
                                        alpha=alpha,
                                        position_policy=position,
                                        site=site,
                                    )


def _case_map(cases: list[ScenarioCase]) -> dict[tuple[str, int, str], ScenarioCase]:
    return {(case.domain, case.document, case.scenario_type): case for case in cases}


def _completed_ids(path: Path) -> set[str]:
    if not path.is_file():
        return set()
    completed: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
            run_id = record.get("run_id")
            if isinstance(run_id, str):
                completed.add(run_id)
    return completed


def _operator_for(spec: TrialSpec, artifact: dict[str, Any]) -> Any:
    if spec.vector_layer is None:
        raise ValueError("intervention trial has no vector layer")
    layer_data = artifact["layers"][int(spec.vector_layer)]
    if spec.method == "jlens_swap":
        return CoordinateSwapOperator(
            concept_a=layer_data["j_concept_a"],
            concept_b=layer_data["j_concept_b"],
            alpha=spec.alpha,
        )
    if spec.method == "random":
        if spec.random_seed is None:
            raise ValueError("random trial has no seed")
        vector = layer_data["random"][int(spec.random_seed)]
    else:
        vector = layer_data[spec.method]
    sign = 1.0 if spec.direction == "a_to_b" else -1.0
    return AdditiveOperator(vector=vector, alpha=spec.alpha, sign=sign)


def _record_manifest(config: PilotConfig, planned: int) -> None:
    manifest = {
        "schema_version": "jlens-causal-run-v1",
        "direction_fingerprint": config.direction_fingerprint,
        "planned_generations": planned,
        "estimated_breakdown": config.estimated_generations(),
        "config": config.public_dict(),
    }
    config.output_dir.mkdir(parents=True, exist_ok=True)
    (config.output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8"
    )


def run_sweep(
    config: PilotConfig,
    runtime: ModelRuntime,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Run missing trials, appending one durable JSON record per generation."""
    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative")
    artifact = load_directions(config, runtime.torch)
    all_specs = list(iter_trial_specs(config))
    expected = config.estimated_generations()["total"]
    if len(all_specs) != expected:
        raise AssertionError(f"planned {len(all_specs)} trials but count estimator says {expected}")
    if int(config.sweep["wrong_layer"]) >= runtime.lens_model.n_layers:
        raise ValueError("wrong_layer is outside the loaded model")
    for layer in config.sweep["layers"]:
        if int(layer) >= runtime.lens_model.n_layers:
            raise ValueError(f"candidate layer {layer} is outside the loaded model")

    common, cases = load_cases(
        config.toolalign_root,
        domains=config.data["evaluation_domains"],
        documents=config.data["evaluation_documents"],
        scenario_types=[config.data["scenario_a"], config.data["scenario_b"]],
    )
    cases_by_key = _case_map(cases)
    _record_manifest(config, len(all_specs))
    completed = _completed_ids(config.records_path)
    stats = {"planned": len(all_specs), "already_complete": 0, "written": 0}
    prompt_cache: dict[tuple[str, int, str, str], tuple[Any, Any, str]] = {}

    with config.records_path.open("a", encoding="utf-8", buffering=1) as sink:
        for spec in all_specs:
            identity = {"direction_fingerprint": config.direction_fingerprint, **asdict(spec)}
            run_id = _stable_hash(identity)
            if run_id in completed:
                stats["already_complete"] += 1
                continue
            if limit is not None and stats["written"] >= limit:
                break

            case = cases_by_key[(spec.domain, spec.document, spec.source_scenario)]
            cache_key = (spec.domain, spec.document, spec.source_scenario, spec.condition)
            cached = prompt_cache.get(cache_key)
            if cached is None:
                messages = messages_for_case(common, case, spec.condition)
                input_ids, attention_mask = render_messages(runtime, messages)
                cached = (input_ids, attention_mask, token_ids_sha256(input_ids))
                prompt_cache[cache_key] = cached
            input_ids, attention_mask, prompt_hash = cached

            started = time.perf_counter()
            if spec.method == "baseline":
                output_text, completion_ids = generate_text(
                    runtime,
                    input_ids=input_ids,
                    attention_mask=attention_mask,
                    generation_config=config.generation,
                )
            else:
                operator = _operator_for(spec, artifact)
                with intervention_hook(
                    runtime.lens_model.layers,
                    layer=int(spec.applied_layer),
                    position_policy=str(spec.position_policy),
                    operator=operator,
                ):
                    output_text, completion_ids = generate_text(
                        runtime,
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        generation_config=config.generation,
                    )
            elapsed = time.perf_counter() - started
            record = {
                "schema_version": "jlens-causal-record-v1",
                "run_id": run_id,
                "direction_fingerprint": config.direction_fingerprint,
                **asdict(spec),
                "prompt_token_sha256": prompt_hash,
                "completion_token_ids": completion_ids,
                "output_text": output_text,
                "elapsed_seconds": elapsed,
                "behavior": classify_behavior(output_text, case.tools),
            }
            sink.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            sink.flush()
            completed.add(run_id)
            stats["written"] += 1
    return stats
