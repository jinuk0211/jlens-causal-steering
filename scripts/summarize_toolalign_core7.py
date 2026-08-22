"""Combine paired aligned/abliterated transition analyses for all baseline methods."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

METHODS = ("caa", "cast", "mera", "sadi", "iti", "austeer")
ROLES = ("aligned", "abliterated")


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def collect_core7(
    config_dir: Path,
    *,
    allow_partial: bool = False,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    missing: list[str] = []
    for method in METHODS:
        config_path = config_dir / f"toolalign_{method}_llama8b.json"
        config = _read(config_path)
        data = config.get("data") or {}
        expected_baseline_cases = None
        if all(
            isinstance(data.get(field), list) and data.get(field)
            for field in (
                "evaluation_domains",
                "evaluation_documents",
                "evaluation_scenario_types",
            )
        ):
            expected_baseline_cases = (
                len(data["evaluation_domains"])
                * len(data["evaluation_documents"])
                * len(data["evaluation_scenario_types"])
            )
        output = Path(str(config["output_dir"])).expanduser()
        if not output.is_absolute():
            output = (config_path.parent / output).resolve()
        method_fingerprints: set[str] = set()
        for role in ROLES:
            analysis_path = output / "analysis" / f"{role}.json"
            if not analysis_path.is_file():
                missing.append(str(analysis_path))
                continue
            analysis = _read(analysis_path)
            paired = analysis.get("paired_transitions")
            if not isinstance(paired, dict) or paired.get("schema_version") != (
                "toolalign-paired-transitions-v1"
            ):
                raise ValueError(f"missing paired transition analysis in {analysis_path}")
            if paired.get("model_role") != role:
                raise ValueError(f"model role mismatch in {analysis_path}")
            if (
                expected_baseline_cases is not None
                and paired.get("baseline_cases") != expected_baseline_cases
            ):
                raise ValueError(
                    f"baseline case coverage mismatch in {analysis_path}: "
                    f"expected {expected_baseline_cases}"
                )
            fingerprint = analysis.get("config_fingerprint")
            if not isinstance(fingerprint, str) or not fingerprint:
                raise ValueError(f"missing config fingerprint in {analysis_path}")
            method_fingerprints.add(fingerprint)
            sources.append(
                {
                    "method_family": method,
                    "model_role": role,
                    "path": str(analysis_path),
                    "config_fingerprint": fingerprint,
                    "baseline_cases": paired.get("baseline_cases"),
                    "paired_trials": paired.get("paired_trials"),
                }
            )
            for summary in paired.get("summary") or []:
                parameters = summary.get("parameters") or {}
                rows.append(
                    {
                        "method_family": method,
                        "model_role": role,
                        "role_target": paired.get("role_target"),
                        "method_condition": summary.get("method"),
                        "scenario_type": summary.get("scenario_type"),
                        "parameters_json": json.dumps(
                            parameters,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        **{
                            key: value
                            for key, value in summary.items()
                            if key not in {"method", "scenario_type", "parameters"}
                        },
                    }
                )
        if len(method_fingerprints) > 1:
            raise ValueError(f"aligned/abliterated config fingerprint mismatch for {method}")
    if missing and not allow_partial:
        raise FileNotFoundError(
            f"Core-6 summary requires all {len(METHODS) * len(ROLES)} analyses; "
            f"missing {len(missing)} (first: {missing[0]})"
        )
    return {
        "schema_version": "toolalign-core7-paired-summary-v1",
        "required_methods": list(METHODS),
        "required_roles": list(ROLES),
        "complete": not missing,
        "missing": missing,
        "sources": sources,
        "rows": rows,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-dir", type=Path, default=Path("configs"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/toolalign-core7-summary"))
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    result = collect_core7(args.config_dir.resolve(), allow_partial=args.allow_partial)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "paired-summary.json"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_csv(output_dir / "paired-summary.csv", result["rows"])
    print(
        json.dumps(
            {
                "output": str(json_path),
                "complete": result["complete"],
                "sources": len(result["sources"]),
                "rows": len(result["rows"]),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
