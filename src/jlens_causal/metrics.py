"""Paired causal metrics and cluster-bootstrap summaries."""

from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

from jlens_causal.config import PilotConfig


def load_records(path: Path) -> list[dict[str, Any]]:
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
            if record.get("schema_version") != "jlens-causal-record-v1":
                raise ValueError(f"unsupported record schema at {path}:{line_number}")
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


def paired_trial_metrics(
    config: PilotConfig, records: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Pair each treatment with source/target alpha=0 and matched random trials."""
    baselines = {
        _baseline_key(record): record
        for record in records
        if record["method"] == "baseline"
    }
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
        treatment_class_target = _same_class(treatment, target)
        source_signature_target = _same_signature(source, target)
        treatment_signature_target = _same_signature(treatment, target)
        source_aligned = _binary_behavior(source, "behavior_class", "aligned")
        treatment_aligned = _binary_behavior(treatment, "behavior_class", "aligned")
        source_parse_error = int(bool(source["behavior"].get("parse_error")))
        treatment_parse_error = int(bool(treatment["behavior"].get("parse_error")))
        source_no_tool = _binary_behavior(source, "behavior_class", "no_tool")
        treatment_no_tool = _binary_behavior(treatment, "behavior_class", "no_tool")
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
                "baseline_target_class_success": source_class_target,
                "steer_target_class_success": treatment_class_target,
                "target_class_effect": treatment_class_target - source_class_target,
                "baseline_target_signature_success": source_signature_target,
                "steer_target_signature_success": treatment_signature_target,
                "target_signature_effect": treatment_signature_target
                - source_signature_target,
                "source_class_retained": _same_class(treatment, source),
                "source_signature_retained": _same_signature(treatment, source),
                "output_text_changed": int(treatment["output_text"] != source["output_text"]),
                "parse_error_increase": treatment_parse_error - source_parse_error,
                "no_tool_increase": treatment_no_tool - source_no_tool,
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
        row["random_target_class_effect_mean"] = random_class
        row["random_target_signature_effect_mean"] = random_signature
        row["causal_delta_class_vs_random"] = row["target_class_effect"] - random_class
        row["causal_delta_signature_vs_random"] = (
            row["target_signature_effect"] - random_signature
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
    "no_tool_increase",
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


def analyze_runs(
    config: PilotConfig,
    *,
    bootstrap_samples: int = 2_000,
) -> dict[str, Any]:
    records = load_records(config.records_path)
    rows = paired_trial_metrics(config, records)
    summaries = summarize_rows(
        rows,
        bootstrap_samples=bootstrap_samples,
        seed=int(config.generation["seed"]),
    )
    trial_path = config.output_dir / "trial_metrics.csv"
    summary_path = config.output_dir / "summary.csv"
    _write_csv(trial_path, rows)
    _write_csv(summary_path, summaries)
    return {
        "records": len(records),
        "treatments": len(rows),
        "summary_rows": len(summaries),
        "trial_metrics": str(trial_path),
        "summary": str(summary_path),
    }
