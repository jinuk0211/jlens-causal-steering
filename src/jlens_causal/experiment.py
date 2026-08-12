"""Resumable paired ToolAlign steering sweep."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterator
from contextlib import ExitStack
from dataclasses import asdict, dataclass
from typing import Any

from jlens_causal.config import PilotConfig
from jlens_causal.directions import load_directions
from jlens_causal.interventions import (
    AdditiveOperator,
    CoordinateSwapOperator,
    finalize_thought_trace,
    intervention_band_hooks,
    intervention_hook,
    matched_prompt_positions,
    thought_trace_hook,
)
from jlens_causal.modeling import (
    ModelRuntime,
    RenderedPrompt,
    generate_text,
    render_messages,
    token_ids_sha256,
)
from jlens_causal.toolalign import ScenarioCase, classify_behavior, load_cases, messages_for_case

RECORD_SCHEMA_VERSION = "jlens-causal-record-v3"
MANIFEST_SCHEMA_VERSION = "jlens-causal-run-v3"
GENERATED_ARTIFACTS = (
    "directions.pt",
    "target_selection.json",
    "manifest.json",
    "runs.jsonl",
    "thought_trajectories.csv",
    "behavior_profiles.csv",
    "trial_metrics.csv",
    "summary.csv",
)


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
    vector_layer_band: tuple[int, ...] | None = None
    applied_layer_band: tuple[int, ...] | None = None


def _stable_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def trial_run_id(config: PilotConfig, spec: TrialSpec) -> str:
    return _stable_hash({"run_fingerprint": config.run_fingerprint, **asdict(spec)})


def reset_output_artifacts(config: PilotConfig) -> list[str]:
    """Remove only files owned by this runner, never arbitrary directory contents."""
    targets = []
    for name in GENERATED_ARTIFACTS:
        path = config.output_dir / name
        if not path.exists():
            continue
        if not path.is_file() and not path.is_symlink():
            raise ValueError(f"refusing to remove non-file generated artifact: {path}")
        targets.append(path)
    removed: list[str] = []
    for path in targets:
        path.unlink()
        removed.append(str(path))
    return removed


def validate_output_compatibility(config: PilotConfig) -> None:
    """Reject stale v1 or semantically different outputs before model loading."""
    manifest_path = config.output_dir / "manifest.json"
    records_exist = config.records_path.is_file()
    if not manifest_path.is_file():
        if records_exist:
            raise ValueError(
                f"{config.records_path} exists without a manifest; rerun with "
                f"`jlens-causal all {config.path} --fresh`"
            )
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if (
        manifest.get("schema_version") != MANIFEST_SCHEMA_VERSION
        or manifest.get("run_fingerprint") != config.run_fingerprint
    ):
        raise ValueError(
            f"output directory contains results from an incompatible configuration: "
            f"{config.output_dir}; rerun with `jlens-causal all {config.path} --fresh`"
        )


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
                        candidate_band = tuple(map(int, sweep["coordinate_swap_layers"]))
                        wrong_band = tuple(map(int, sweep["wrong_layer_band"]))
                        for alpha in map(float, sweep["coordinate_swap_alphas"]):
                            for site, applied_band, position in (
                                ("candidate", candidate_band, sweep["position_policy"]),
                                ("wrong_layer", wrong_band, sweep["position_policy"]),
                                (
                                    "wrong_position",
                                    candidate_band,
                                    sweep["wrong_position_policy"],
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
                                    vector_layer=None,
                                    applied_layer=None,
                                    alpha=alpha,
                                    position_policy=position,
                                    site=site,
                                    vector_layer_band=candidate_band,
                                    applied_layer_band=applied_band,
                                )


def _case_map(cases: list[ScenarioCase]) -> dict[tuple[str, int, str], ScenarioCase]:
    return {(case.domain, case.document, case.scenario_type): case for case in cases}


def _completed_ids(config: PilotConfig) -> set[str]:
    path = config.records_path
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
            if record.get("schema_version") != RECORD_SCHEMA_VERSION:
                raise ValueError(
                    f"stale record schema at {path}:{line_number}; rerun with "
                    f"`jlens-causal all {config.path} --fresh`"
                )
            if record.get("run_fingerprint") != config.run_fingerprint:
                raise ValueError(
                    f"record fingerprint mismatch at {path}:{line_number}; rerun with "
                    f"`jlens-causal all {config.path} --fresh`"
                )
            if record.get("method") == "baseline" and not record.get("valid_for_pairing", False):
                raise ValueError(
                    f"invalid alpha=0 baseline at {path}:{line_number}; rerun with "
                    f"`jlens-causal all {config.path} --fresh`"
                )
            run_id = record.get("run_id")
            if isinstance(run_id, str):
                completed.add(run_id)
    return completed


def _operator_for(spec: TrialSpec, artifact: dict[str, Any]) -> Any:
    if spec.vector_layer is None:
        raise ValueError("intervention trial has no vector layer")
    layer_data = artifact["layers"][int(spec.vector_layer)]
    if spec.method == "random":
        if spec.random_seed is None:
            raise ValueError("random trial has no seed")
        vector = layer_data["random"][spec.direction][int(spec.random_seed)]
    else:
        vector = layer_data[spec.method][spec.direction]
    return AdditiveOperator(vector=vector, alpha=spec.alpha)


def _swap_operators(spec: TrialSpec, artifact: dict[str, Any]) -> list[tuple[int, Any]]:
    if spec.vector_layer_band is None or spec.applied_layer_band is None:
        raise ValueError("coordinate swap trial has no layer band")
    if len(spec.vector_layer_band) != len(spec.applied_layer_band):
        raise ValueError("coordinate swap layer bands have different widths")
    operators: list[tuple[int, Any]] = []
    for vector_layer, applied_layer in zip(
        spec.vector_layer_band, spec.applied_layer_band, strict=True
    ):
        layer_data = artifact["layers"][int(vector_layer)]
        operators.append(
            (
                int(applied_layer),
                CoordinateSwapOperator(
                    concept_a=layer_data["concept_a"],
                    concept_b=layer_data["concept_b"],
                    alpha=spec.alpha,
                    direction=spec.direction,
                ),
            )
        )
    return operators


def _record_manifest(config: PilotConfig, planned: int) -> None:
    manifest = {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "direction_fingerprint": config.direction_fingerprint,
        "run_fingerprint": config.run_fingerprint,
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
    validate_output_compatibility(config)
    artifact = load_directions(config, runtime.torch)
    all_specs = list(iter_trial_specs(config))
    expected = config.estimated_generations()["total"]
    if len(all_specs) != expected:
        raise AssertionError(f"planned {len(all_specs)} trials but count estimator says {expected}")
    if int(config.sweep["wrong_layer"]) >= runtime.lens_model.n_layers:
        raise ValueError("wrong_layer is outside the loaded model")
    for layer in [
        *config.sweep["coordinate_swap_layers"],
        *config.sweep["wrong_layer_band"],
    ]:
        if int(layer) >= runtime.lens_model.n_layers:
            raise ValueError(f"intervention layer {layer} is outside the loaded model")

    common, cases = load_cases(
        config.toolalign_root,
        domains=config.data["evaluation_domains"],
        documents=config.data["evaluation_documents"],
        scenario_types=[config.data["scenario_a"], config.data["scenario_b"]],
    )
    cases_by_key = _case_map(cases)
    completed = _completed_ids(config)
    _record_manifest(config, len(all_specs))
    stats = {"planned": len(all_specs), "already_complete": 0, "written": 0}
    prompt_cache: dict[tuple[str, int, str, str], tuple[RenderedPrompt, str]] = {}

    with config.records_path.open("a", encoding="utf-8", buffering=1) as sink:
        for spec in all_specs:
            run_id = trial_run_id(config, spec)
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
                prompt = render_messages(runtime, messages)
                cached = (prompt, token_ids_sha256(prompt.input_ids))
                prompt_cache[cache_key] = cached
            prompt, prompt_hash = cached

            started = time.perf_counter()
            with ExitStack() as stack:
                trace = stack.enter_context(
                    thought_trace_hook(
                        runtime.lens_model.layers,
                        layer=int(artifact["thought_probe"]["layer"]),
                        probe_vector=artifact["thought_probe"]["vector_b_minus_a"],
                        user_positions=prompt.user_positions,
                        max_response_tokens=int(config.sweep["thought_trace_tokens"]),
                    )
                )
                selected_positions: tuple[int, ...] = ()
                if spec.method != "baseline":
                    selected_positions = matched_prompt_positions(
                        str(spec.position_policy),
                        user_positions=prompt.user_positions,
                        system_positions=prompt.system_positions,
                    )
                    if spec.method == "jlens_swap":
                        stack.enter_context(
                            intervention_band_hooks(
                                runtime.lens_model.layers,
                                layer_operators=_swap_operators(spec, artifact),
                                prompt_positions=selected_positions,
                            )
                        )
                    else:
                        stack.enter_context(
                            intervention_hook(
                                runtime.lens_model.layers,
                                layer=int(spec.applied_layer),
                                prompt_positions=selected_positions,
                                operator=_operator_for(spec, artifact),
                            )
                        )
                generation = generate_text(
                    runtime,
                    input_ids=prompt.input_ids,
                    attention_mask=prompt.attention_mask,
                    generation_config=config.generation,
                )
                thought_trace = finalize_thought_trace(trace)
            elapsed = time.perf_counter() - started
            behavior = classify_behavior(
                generation.text,
                case.tools,
                truncated=generation.hit_token_limit,
            )
            valid_for_pairing = bool(behavior["valid_for_pairing"])
            record = {
                "schema_version": RECORD_SCHEMA_VERSION,
                "run_id": run_id,
                "direction_fingerprint": config.direction_fingerprint,
                "run_fingerprint": config.run_fingerprint,
                **asdict(spec),
                "prompt_token_sha256": prompt_hash,
                "prompt_tokens": int(prompt.input_ids.shape[1]),
                "user_span_tokens": len(prompt.user_positions),
                "intervened_prompt_tokens": len(selected_positions),
                "completion_token_ids": generation.completion_ids,
                "completion_tokens": len(generation.completion_ids),
                "terminated_by_eos": generation.terminated_by_eos,
                "truncated": generation.hit_token_limit,
                "termination_reason": generation.termination_reason,
                "valid_for_pairing": valid_for_pairing,
                "output_text": generation.text,
                "elapsed_seconds": elapsed,
                "behavior": behavior,
                "thought_trace": thought_trace,
            }
            sink.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            sink.flush()
            completed.add(run_id)
            stats["written"] += 1
            if spec.method == "baseline" and not valid_for_pairing:
                raise RuntimeError(
                    "alpha=0 baseline is truncated or unparsable; the raw record was saved, "
                    f"and the sweep stopped before treatments. Rerun with "
                    f"`jlens-causal all {config.path} --fresh` after fixing generation."
                )
    return stats
