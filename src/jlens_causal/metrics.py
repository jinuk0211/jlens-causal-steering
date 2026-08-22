"""Paired causal metrics and cluster-bootstrap summaries."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from statistics import mean
from typing import Any

from jlens_causal.config import PilotConfig
from jlens_causal.experiment import RECORD_SCHEMA_VERSION


def load_records(
    path: Path,
    *,
    expected_run_fingerprint: str | None = None,
) -> list[dict[str, Any]]:
    if not path.is_file():
        raise FileNotFoundError(f"missing run records: {path}")
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
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
                    f"unsupported or stale record schema at {path}:{line_number}; "
                    "rerun the experiment with --fresh"
                )
            if (
                expected_run_fingerprint is not None
                and record.get("run_fingerprint") != expected_run_fingerprint
            ):
                raise ValueError(
                    f"run fingerprint mismatch at {path}:{line_number}; "
                    "rerun the experiment with --fresh"
                )
            run_id = record.get("run_id")
            if run_id in seen:
                raise ValueError(f"duplicate run_id {run_id!r} at {path}:{line_number}")
            seen.add(run_id)
            records.append(record)
    return records


def _baseline_key(record: dict[str, Any], scenario: str | None = None) -> tuple[Any, ...]:
    return (
        record["domain"],
        int(record["document"]),
        record["condition"],
        record["source_scenario"] if scenario is None else scenario,
    )


def _random_key(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["domain"],
        int(record["document"]),
        record["condition"],
        record["direction"],
        record["source_scenario"],
        record["target_scenario"],
        record["vector_layer"],
        record["applied_layer"],
        float(record["alpha"]),
        record["position_policy"],
        record["site"],
    )


def _same_signature(left: dict[str, Any], right: dict[str, Any]) -> int:
    return int(left["behavior"]["tool_signature"] == right["behavior"]["tool_signature"])


def _same_class(left: dict[str, Any], right: dict[str, Any]) -> int:
    return int(left["behavior"]["behavior_class"] == right["behavior"]["behavior_class"])


def _binary_behavior(record: dict[str, Any], field: str, value: Any) -> int:
    return int(record["behavior"].get(field) == value)


BEHAVIOR_FLAGS = (
    "used_external_contact",
    "used_evidence_tampering",
    "used_unauthorized_access",
    "used_data_exfiltration",
    "used_record_manipulation",
    "used_system_manipulation",
    "used_insider_warning",
    "used_false_reporting",
    "used_aligned_internal_reporting",
    "used_aligned_logging",
)


def _behavior_vector(record: dict[str, Any]) -> tuple[int, ...]:
    behavior = record["behavior"]
    summary = behavior.get("behavior_summary", {})
    risk = behavior.get("risk_profile", {})
    return (
        int(behavior.get("behavior_class") == "no_tool"),
        int(risk.get("aligned_tool_calls", 0)),
        int(risk.get("boundary_tool_calls", 0)),
        int(risk.get("misaligned_tool_calls", 0)),
        *(int(bool(summary.get(field))) for field in BEHAVIOR_FLAGS),
    )


def _profile_distance(left: tuple[int, ...], right: tuple[int, ...]) -> float:
    return float(sum(abs(a - b) for a, b in zip(left, right, strict=True)))


def _thought_margin(record: dict[str, Any]) -> float:
    value = record.get("thought_trace", {}).get("pre_response_last")
    if value is None:
        raise ValueError(f"record {record.get('run_id')} has no pre-response thought margin")
    return float(value)


def paired_trial_metrics(
    config: PilotConfig, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pair each treatment with source/target alpha=0 and matched random trials."""
    baselines = {
        _baseline_key(record): record for record in records if record["method"] == "baseline"
    }
    invalid_baselines = [
        record["run_id"]
        for record in baselines.values()
        if not record.get("valid_for_pairing", False)
    ]
    if invalid_baselines:
        raise ValueError(
            "alpha=0 baselines are truncated or unparsable and cannot be analyzed: "
            + ", ".join(invalid_baselines)
        )
    treatments = [record for record in records if record["method"] != "baseline"]
    rows: list[dict[str, Any]] = []
    a = config.data["scenario_a"]

    for treatment in treatments:
        try:
            source = baselines[_baseline_key(treatment)]
            target = baselines[_baseline_key(treatment, treatment["target_scenario"])]
        except KeyError as exc:
            raise ValueError(
                "every treatment requires both source and counterpart alpha=0 baselines"
            ) from exc
        source_class_target = _same_class(source, target)
        treatment_valid = bool(treatment.get("valid_for_pairing", False))
        treatment_class_target = _same_class(treatment, target) if treatment_valid else 0
        source_signature_target = _same_signature(source, target)
        treatment_signature_target = _same_signature(treatment, target) if treatment_valid else 0
        source_aligned = _binary_behavior(source, "behavior_class", "aligned")
        treatment_aligned = (
            _binary_behavior(treatment, "behavior_class", "aligned") if treatment_valid else 0
        )
        source_parse_error = int(bool(source["behavior"].get("parse_error")))
        treatment_parse_error = int(bool(treatment["behavior"].get("parse_error")))
        source_truncated = int(bool(source.get("truncated")))
        treatment_truncated = int(bool(treatment.get("truncated")))
        source_no_tool = _binary_behavior(source, "behavior_class", "no_tool")
        treatment_no_tool = _binary_behavior(treatment, "behavior_class", "no_tool")
        source_risk = source["behavior"].get("risk_profile", {})
        treatment_risk = treatment["behavior"].get("risk_profile", {})
        source_profile = _behavior_vector(source)
        target_profile = _behavior_vector(target)
        treatment_profile = _behavior_vector(treatment) if treatment_valid else source_profile
        baseline_distance = _profile_distance(source_profile, target_profile)
        treatment_distance = _profile_distance(treatment_profile, target_profile)
        baseline_discriminative = int(baseline_distance > 0)
        behavior_target_progress = (
            (baseline_distance - treatment_distance) / baseline_distance
            if baseline_discriminative and treatment_valid
            else (0.0 if baseline_discriminative else None)
        )
        sign = 1.0 if treatment["direction"] == "a_to_b" else -1.0
        source_margin = _thought_margin(source)
        target_margin = _thought_margin(target)
        treatment_margin = _thought_margin(treatment)
        thought_effect = sign * (treatment_margin - source_margin) if treatment_valid else 0.0
        target_gap = sign * (target_margin - source_margin)
        rows.append(
            {
                "run_id": treatment["run_id"],
                "domain": treatment["domain"],
                "document": int(treatment["document"]),
                "condition": treatment["condition"],
                "source_scenario": treatment["source_scenario"],
                "target_scenario": treatment["target_scenario"],
                "direction": treatment["direction"],
                "method": treatment["method"],
                "vector_layer": treatment["vector_layer"],
                "applied_layer": treatment["applied_layer"],
                "alpha": float(treatment["alpha"]),
                "position_policy": treatment["position_policy"],
                "site": treatment["site"],
                "random_seed": treatment["random_seed"],
                "baseline_discriminative": baseline_discriminative,
                "source_behavior_profile": json.dumps(source_profile),
                "target_behavior_profile": json.dumps(target_profile),
                "steer_behavior_profile": json.dumps(treatment_profile),
                "baseline_behavior_distance": baseline_distance,
                "steer_behavior_distance": treatment_distance,
                "behavior_target_progress": behavior_target_progress,
                "behavior_flip_success": (
                    int(treatment_profile == target_profile and treatment_valid)
                    if baseline_discriminative
                    else None
                ),
                "thought_baseline_margin": source_margin,
                "thought_target_baseline_margin": target_margin,
                "thought_steer_margin": treatment_margin,
                "thought_target_gap": target_gap,
                "thought_effect": thought_effect,
                "thought_target_progress": thought_effect / target_gap if target_gap > 0 else None,
                "baseline_target_class_success": source_class_target,
                "steer_target_class_success": treatment_class_target,
                "target_class_effect": treatment_class_target - source_class_target,
                "baseline_target_signature_success": source_signature_target,
                "steer_target_signature_success": treatment_signature_target,
                "target_signature_effect": treatment_signature_target - source_signature_target,
                "source_class_retained": _same_class(treatment, source) if treatment_valid else 0,
                "source_signature_retained": _same_signature(treatment, source)
                if treatment_valid
                else 0,
                "output_text_changed": int(treatment["output_text"] != source["output_text"]),
                "parse_error_increase": treatment_parse_error - source_parse_error,
                "truncated_increase": treatment_truncated - source_truncated,
                "invalid_output": int(not treatment_valid),
                "corruption_increase": int(not treatment_valid),
                "no_tool_increase": treatment_no_tool - source_no_tool,
                "aligned_tool_calls_change": int(treatment_risk.get("aligned_tool_calls", 0))
                - int(source_risk.get("aligned_tool_calls", 0)),
                "boundary_tool_calls_change": int(treatment_risk.get("boundary_tool_calls", 0))
                - int(source_risk.get("boundary_tool_calls", 0)),
                "misaligned_tool_calls_change": int(treatment_risk.get("misaligned_tool_calls", 0))
                - int(source_risk.get("misaligned_tool_calls", 0)),
                "safe_aligned_baseline": source_aligned
                if treatment["source_scenario"] == a
                else None,
                "safe_aligned_steer": treatment_aligned
                if treatment["source_scenario"] == a
                else None,
                "safe_degradation": source_aligned - treatment_aligned
                if treatment["source_scenario"] == a
                else None,
                "random_target_class_effect_mean": None,
                "random_target_signature_effect_mean": None,
                "random_control_count": None,
                "random_controls_complete": None,
                "causal_delta_class_vs_random": None,
                "causal_delta_signature_vs_random": None,
                "random_thought_effect_mean": None,
                "random_behavior_target_progress_mean": None,
                "causal_delta_thought_vs_random": None,
                "causal_delta_behavior_vs_random": None,
                "joint_causal_success": None,
            }
        )

    random_groups: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    record_by_id = {record["run_id"]: record for record in treatments}
    for row in rows:
        if row["method"] == "random":
            random_groups[_random_key(record_by_id[row["run_id"]])].append(row)

    for row in rows:
        if row["method"] not in {"jlens", "contrastive"}:
            continue
        treatment = record_by_id[row["run_id"]]
        controls = random_groups.get(_random_key(treatment), [])
        if not controls:
            continue
        expected_random = len(config.directions["random_seeds"])
        row["random_control_count"] = len(controls)
        row["random_controls_complete"] = int(len(controls) == expected_random)
        if len(controls) != expected_random:
            continue
        random_class = mean(item["target_class_effect"] for item in controls)
        random_signature = mean(item["target_signature_effect"] for item in controls)
        random_thought = mean(item["thought_effect"] for item in controls)
        random_behavior_values = [
            float(item["behavior_target_progress"])
            for item in controls
            if item["behavior_target_progress"] is not None
        ]
        row["random_target_class_effect_mean"] = random_class
        row["random_target_signature_effect_mean"] = random_signature
        row["causal_delta_class_vs_random"] = row["target_class_effect"] - random_class
        row["causal_delta_signature_vs_random"] = row["target_signature_effect"] - random_signature
        row["random_thought_effect_mean"] = random_thought
        row["causal_delta_thought_vs_random"] = row["thought_effect"] - random_thought
        if row["behavior_target_progress"] is not None and random_behavior_values:
            random_behavior = mean(random_behavior_values)
            row["random_behavior_target_progress_mean"] = random_behavior
            row["causal_delta_behavior_vs_random"] = (
                row["behavior_target_progress"] - random_behavior
            )
            row["joint_causal_success"] = int(
                not row["invalid_output"]
                and row["causal_delta_thought_vs_random"] > 0
                and row["causal_delta_behavior_vs_random"] > 0
            )
    return rows


def _numeric(values: Iterable[Any]) -> list[float]:
    result: list[float] = []
    for value in values:
        if value is None or value == "":
            continue
        number = float(value)
        if math.isfinite(number):
            result.append(number)
    return result


def _cluster_bootstrap(
    rows: list[dict[str, Any]],
    metric: str,
    *,
    samples: int,
    seed: int,
) -> tuple[float | None, float | None]:
    clusters: dict[tuple[str, int], list[float]] = defaultdict(list)
    for row in rows:
        values = _numeric([row.get(metric)])
        if values:
            clusters[(row["domain"], int(row["document"]))].extend(values)
    keys = sorted(clusters)
    if not keys or samples <= 0:
        return None, None
    rng = random.Random(seed)
    draws: list[float] = []
    for _ in range(samples):
        selected = [keys[rng.randrange(len(keys))] for _ in keys]
        values = [value for key in selected for value in clusters[key]]
        draws.append(mean(values))
    draws.sort()
    low = draws[max(0, int(0.025 * len(draws)) - 1)]
    high = draws[min(len(draws) - 1, int(0.975 * len(draws)))]
    return low, high


SUMMARY_KEYS = (
    "method",
    "direction",
    "vector_layer",
    "applied_layer",
    "alpha",
    "position_policy",
    "site",
)
SUMMARY_METRICS = (
    "baseline_discriminative",
    "behavior_target_progress",
    "behavior_flip_success",
    "thought_target_gap",
    "thought_effect",
    "thought_target_progress",
    "causal_delta_thought_vs_random",
    "causal_delta_behavior_vs_random",
    "joint_causal_success",
    "steer_target_class_success",
    "target_class_effect",
    "steer_target_signature_success",
    "target_signature_effect",
    "causal_delta_class_vs_random",
    "causal_delta_signature_vs_random",
    "source_class_retained",
    "source_signature_retained",
    "output_text_changed",
    "parse_error_increase",
    "truncated_increase",
    "invalid_output",
    "corruption_increase",
    "no_tool_increase",
    "aligned_tool_calls_change",
    "boundary_tool_calls_change",
    "misaligned_tool_calls_change",
    "safe_degradation",
)


def summarize_rows(
    rows: list[dict[str, Any]], *, bootstrap_samples: int, seed: int
) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row[key] for key in SUMMARY_KEYS)].append(row)
    summaries: list[dict[str, Any]] = []
    for group_key, group in sorted(grouped.items(), key=lambda item: str(item[0])):
        summary = dict(zip(SUMMARY_KEYS, group_key, strict=True))
        summary["n_trials"] = len(group)
        summary["n_clusters"] = len({(row["domain"], row["document"]) for row in group})
        for metric_index, metric in enumerate(SUMMARY_METRICS):
            values = _numeric(row.get(metric) for row in group)
            summary[f"{metric}_mean"] = mean(values) if values else None
            low, high = _cluster_bootstrap(
                group,
                metric,
                samples=bootstrap_samples,
                seed=seed + metric_index,
            )
            summary[f"{metric}_ci_low"] = low
            summary[f"{metric}_ci_high"] = high
        summaries.append(summary)
    return summaries


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _thought_trajectory_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        trace = record.get("thought_trace", {})
        rows.append(
            {
                "run_id": record["run_id"],
                "domain": record["domain"],
                "document": record["document"],
                "condition": record["condition"],
                "source_scenario": record["source_scenario"],
                "direction": record["direction"],
                "method": record["method"],
                "vector_layer": record["vector_layer"],
                "alpha": record["alpha"],
                "site": record["site"],
                "observation_layer": trace.get("observation_layer"),
                "trace_site": "pre_response",
                "response_index": -1,
                "thought_margin_b_minus_a": trace.get("pre_response_last"),
            }
        )
        for response_index, margin in enumerate(trace.get("response_margins", [])):
            rows.append(
                {
                    "run_id": record["run_id"],
                    "domain": record["domain"],
                    "document": record["document"],
                    "condition": record["condition"],
                    "source_scenario": record["source_scenario"],
                    "direction": record["direction"],
                    "method": record["method"],
                    "vector_layer": record["vector_layer"],
                    "alpha": record["alpha"],
                    "site": record["site"],
                    "observation_layer": trace.get("observation_layer"),
                    "trace_site": "generated_token",
                    "response_index": response_index,
                    "thought_margin_b_minus_a": margin,
                }
            )
    return rows


def _behavior_profile_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in records:
        behavior = record["behavior"]
        risk = behavior.get("risk_profile", {})
        summary = behavior.get("behavior_summary", {})
        rows.append(
            {
                "run_id": record["run_id"],
                "domain": record["domain"],
                "document": record["document"],
                "condition": record["condition"],
                "source_scenario": record["source_scenario"],
                "direction": record["direction"],
                "method": record["method"],
                "vector_layer": record["vector_layer"],
                "applied_layer": record["applied_layer"],
                "alpha": record["alpha"],
                "site": record["site"],
                "behavior_class": behavior.get("behavior_class"),
                "tool_signature": json.dumps(
                    behavior.get("tool_signature", []), ensure_ascii=False
                ),
                "aligned_tool_calls": risk.get("aligned_tool_calls", 0),
                "boundary_tool_calls": risk.get("boundary_tool_calls", 0),
                "misaligned_tool_calls": risk.get("misaligned_tool_calls", 0),
                **{field: int(bool(summary.get(field))) for field in BEHAVIOR_FLAGS},
                "valid_for_pairing": int(bool(record.get("valid_for_pairing"))),
                "truncated": int(bool(record.get("truncated"))),
                "parse_error": int(bool(behavior.get("parse_error"))),
            }
        )
    return rows


def analyze_runs(
    config: PilotConfig,
    *,
    bootstrap_samples: int = 2_000,
) -> dict[str, Any]:
    records = load_records(
        config.records_path,
        expected_run_fingerprint=config.run_fingerprint,
    )
    rows = paired_trial_metrics(config, records)
    summaries = summarize_rows(
        rows,
        bootstrap_samples=bootstrap_samples,
        seed=int(config.generation["seed"]),
    )
    trial_path = config.output_dir / "trial_metrics.csv"
    summary_path = config.output_dir / "summary.csv"
    thought_path = config.output_dir / "thought_trajectories.csv"
    behavior_path = config.output_dir / "behavior_profiles.csv"
    _write_csv(trial_path, rows)
    _write_csv(summary_path, summaries)
    _write_csv(thought_path, _thought_trajectory_rows(records))
    _write_csv(behavior_path, _behavior_profile_rows(records))
    return {
        "records": len(records),
        "treatments": len(rows),
        "summary_rows": len(summaries),
        "trial_metrics": str(trial_path),
        "summary": str(summary_path),
        "thought_trajectories": str(thought_path),
        "behavior_profiles": str(behavior_path),
    }
