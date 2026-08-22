"""Shared paired outcome analysis for every ToolAlign steering baseline."""

from __future__ import annotations

import json
import math
from collections.abc import Iterable
from pathlib import Path
from typing import Any


def exact_mcnemar_p(improved: int, worsened: int) -> float | None:
    """Two-sided exact McNemar p-value for paired binary outcome changes."""
    discordant = int(improved) + int(worsened)
    if discordant == 0:
        return None
    tail = sum(math.comb(discordant, index) for index in range(min(improved, worsened) + 1)) / (
        2**discordant
    )
    return min(1.0, 2.0 * tail)


def _case_key(record: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(record.get("domain", "")),
        str(record.get("document", "")),
        str(record.get("scenario_type", "")),
    )


def _dose_verified(record: dict[str, Any]) -> bool:
    for coefficient in ("signed_alpha", "strength", "scale", "alpha"):
        value = record.get(coefficient)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if float(value) == 0.0:
                return False
            break
    for step in record.get("steps") or []:
        intervention = step.get("intervention") or {}
        if not intervention.get("active"):
            continue
        for key, value in intervention.items():
            if key.startswith("applied_") and isinstance(value, (int, float)) and value > 0:
                return True
    return False


def paired_toolalign_transitions(
    records: Iterable[dict[str, Any]],
    *,
    role: str,
    parameter_fields: Iterable[str],
) -> dict[str, Any]:
    """Pair every treatment to the exact case baseline and count both flip directions."""
    if role not in {"aligned", "abliterated"}:
        raise ValueError("ToolAlign role must be aligned or abliterated")
    values = list(records)
    baselines: dict[tuple[str, str, str], dict[str, Any]] = {}
    for record in values:
        if record.get("method") != "baseline":
            continue
        key = _case_key(record)
        if key in baselines:
            raise ValueError(f"duplicate ToolAlign baseline for {key}")
        baselines[key] = record
    if not baselines:
        raise ValueError("ToolAlign paired analysis requires baseline records")

    fields = tuple(str(field) for field in parameter_fields)
    trials: list[dict[str, Any]] = []
    for record in values:
        if record.get("method") == "baseline":
            continue
        baseline = baselines.get(_case_key(record))
        if baseline is None:
            continue
        baseline_behavior = baseline.get("behavior") or {}
        treatment_behavior = record.get("behavior") or {}
        baseline_class = str(baseline_behavior.get("behavior_class", "invalid"))
        treatment_class = str(treatment_behavior.get("behavior_class", "invalid"))
        baseline_valid = bool(baseline_behavior.get("valid_for_pairing"))
        treatment_valid = bool(treatment_behavior.get("valid_for_pairing"))
        aligned_to_misaligned = int(
            baseline_valid
            and treatment_valid
            and baseline_class == "aligned"
            and treatment_class == "misaligned"
        )
        misaligned_to_aligned = int(
            baseline_valid
            and treatment_valid
            and baseline_class == "misaligned"
            and treatment_class == "aligned"
        )
        target_flip = misaligned_to_aligned if role == "abliterated" else aligned_to_misaligned
        target_opportunity = int(
            baseline_valid
            and baseline_class == ("misaligned" if role == "abliterated" else "aligned")
        )
        baseline_alignment = 1 if baseline_class == "aligned" and baseline_valid else 0
        treatment_alignment = 1 if treatment_class == "aligned" and treatment_valid else 0
        trials.append(
            {
                "run_id": record.get("run_id"),
                "case_id": ":".join(_case_key(record)),
                "domain": record.get("domain"),
                "document": record.get("document"),
                "scenario_type": record.get("scenario_type"),
                "method": record.get("method"),
                "parameters": {field: record.get(field) for field in fields},
                "baseline_class": baseline_class,
                "treatment_class": treatment_class,
                "baseline_valid": baseline_valid,
                "treatment_valid": treatment_valid,
                "aligned_to_misaligned": aligned_to_misaligned,
                "misaligned_to_aligned": misaligned_to_aligned,
                "role_target_flip": target_flip,
                "role_target_opportunity": target_opportunity,
                "alignment_delta": treatment_alignment - baseline_alignment,
                "tool_signature_changed": int(
                    baseline_behavior.get("tool_signature")
                    != treatment_behavior.get("tool_signature")
                ),
                "verified_nonzero_dose": int(_dose_verified(record)),
                "tool_call_loop": int(record.get("stop_reason") == "tool_call_loop"),
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = {}
    group_metadata: dict[str, dict[str, Any]] = {}
    for trial in trials:
        metadata = {
            "method": trial["method"],
            "parameters": trial["parameters"],
            "scenario_type": trial["scenario_type"],
        }
        key = json.dumps(metadata, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        grouped.setdefault(key, []).append(trial)
        group_metadata[key] = metadata
    summary = []
    for key in sorted(grouped):
        items = grouped[key]
        valid = [item for item in items if item["baseline_valid"] and item["treatment_valid"]]
        aligned_opportunities = sum(
            item["baseline_valid"] and item["baseline_class"] == "aligned" for item in items
        )
        misaligned_opportunities = sum(
            item["baseline_valid"] and item["baseline_class"] == "misaligned" for item in items
        )
        target_opportunities = sum(item["role_target_opportunity"] for item in items)
        alignment_improved = sum(item["misaligned_to_aligned"] for item in items)
        alignment_worsened = sum(item["aligned_to_misaligned"] for item in items)
        summary.append(
            {
                **group_metadata[key],
                "n": len(items),
                "valid_pair_n": len(valid),
                "aligned_to_misaligned": alignment_worsened,
                "aligned_to_misaligned_rate": (
                    sum(item["aligned_to_misaligned"] for item in items) / aligned_opportunities
                    if aligned_opportunities
                    else None
                ),
                "misaligned_to_aligned": alignment_improved,
                "misaligned_to_aligned_rate": (
                    sum(item["misaligned_to_aligned"] for item in items) / misaligned_opportunities
                    if misaligned_opportunities
                    else None
                ),
                "role_target_opportunities": target_opportunities,
                "role_target_flips": sum(item["role_target_flip"] for item in items),
                "role_target_flip_rate": (
                    sum(item["role_target_flip"] for item in items) / target_opportunities
                    if target_opportunities
                    else None
                ),
                "mean_alignment_delta": (
                    sum(item["alignment_delta"] for item in valid) / len(valid) if valid else None
                ),
                "mcnemar_exact_p": exact_mcnemar_p(
                    alignment_improved,
                    alignment_worsened,
                ),
                "invalid_treatment_rate": (
                    sum(not item["treatment_valid"] for item in items) / len(items)
                ),
                "tool_signature_change_rate": (
                    sum(item["tool_signature_changed"] for item in items) / len(items)
                ),
                "verified_nonzero_dose_rate": (
                    sum(item["verified_nonzero_dose"] for item in items) / len(items)
                ),
                "tool_call_loop_rate": sum(item["tool_call_loop"] for item in items) / len(items),
            }
        )
    return {
        "schema_version": "toolalign-paired-transitions-v1",
        "model_role": role,
        "role_target": (
            "misaligned_to_aligned" if role == "abliterated" else "aligned_to_misaligned"
        ),
        "baseline_cases": len(baselines),
        "paired_trials": len(trials),
        "trial_metrics": trials,
        "summary": summary,
    }


def write_toolalign_analysis(path: str | Path, value: dict[str, Any]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return output
