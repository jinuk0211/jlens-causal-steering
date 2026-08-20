"""Audit implementation and empirical readiness for the baseline benchmark protocol."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

CORE_METHODS = ("caa", "cast", "mera", "sadi", "iti", "austeer")
STRUCTURAL_BOUNDARIES = {
    "after_tool_error",
    "after_repeated_tool_error",
    "after_repeated_tool_call",
    "after_short_tool_cycle",
    "after_successful_tool_result",
}
EXPECTED_CONTROLS = {
    "caa": {"targeted", "negative_direction", "wrong_category", "wrong_layer"},
    "cast": {"targeted", "negative_direction", "wrong_category", "wrong_layer"},
    "mera": {"targeted", "negative_direction", "wrong_category", "wrong_layer"},
    "sadi": {"targeted", "wrong_category", "zero_dose"},
    "iti": {"targeted", "negative_direction", "wrong_category"},
    "austeer": {"targeted", "negative_direction", "wrong_category"},
}
EXPECTED_JSERVO_CONTROLS = {
    "targeted",
    "fixed_strength",
    "fixed_layer",
    "wrong_mode",
    "random",
    "reverse",
    "validator_only",
}


def _read(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object at {path}")
    return value


def _check(passed: bool, evidence: Any) -> dict[str, Any]:
    return {"passed": bool(passed), "evidence": evidence}


def _matrix_fingerprint_valid(matrix: dict[str, Any]) -> bool:
    expected = matrix.get("matrix_fingerprint")
    unsigned = dict(matrix)
    unsigned.pop("matrix_fingerprint", None)
    actual = hashlib.sha256(
        json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return expected == actual


def audit_protocol(
    project_root: Path,
    tau_root: Path,
    *,
    matrix_path: Path,
) -> dict[str, Any]:
    project_root = project_root.resolve()
    tau_root = tau_root.resolve()
    matrix = _read(matrix_path.resolve())
    conditions = matrix.get("conditions") or []
    method_set = {
        str(condition.get("method"))
        for condition in conditions
        if condition.get("method") != "none"
    }
    interventions = [
        condition.get("agent_llm_args", {}).get("jlens_intervention") or {}
        for condition in conditions
        if condition.get("method") != "none"
    ]
    used_boundaries = {
        str(boundary)
        for intervention in interventions
        for boundary in intervention.get("boundaries") or []
    }
    remote_only = matrix.get("execution", {}).get("mode") == "remote" and all(
        condition.get("agent_llm_args", {}).get("jlens_require_remote") is True
        and "hf_device" not in condition.get("agent_llm_args", {})
        and "local_path" not in condition.get("agent_llm_args", {})
        for condition in conditions
    )
    generic_selection = all(
        not intervention.get("turn_indices") for intervention in interventions
    ) and used_boundaries.issubset(STRUCTURAL_BOUNDARIES)
    retry_boundaries = {
        tuple(intervention.get("boundaries") or [])
        for condition, intervention in zip(
            [item for item in conditions if item.get("method") != "none"],
            interventions,
            strict=True,
        )
        if condition.get("failure_category") == "retry_without_state_change"
        and condition.get("control_type") == "targeted"
    }
    controls = {
        method: {
            str(condition.get("control_type"))
            for condition in conditions
            if condition.get("method") == method
        }
        for method in CORE_METHODS
    }
    jservo_controls = {
        str(condition.get("control_type"))
        for condition in conditions
        if condition.get("method") == "jservo"
    }

    official_splits = _read(tau_root / "data" / "tau2" / "domains" / "airline" / "split_tasks.json")
    splits = matrix.get("splits") or {}
    train = {str(value) for value in splits.get("train_task_ids") or []}
    validation = {str(value) for value in splits.get("validation_task_ids") or []}
    evaluation = {str(value) for value in splits.get("evaluation_task_ids") or []}
    official_split_valid = (
        train.isdisjoint(validation)
        and train.union(validation) == set(official_splits.get("train") or [])
        and evaluation == set(official_splits.get("test") or [])
        and evaluation.isdisjoint(train.union(validation))
    )

    toolalign_configs: dict[str, dict[str, Any]] = {}
    expected_toolalign_analyses: list[Path] = []
    toolalign_contracts: dict[str, Any] = {}
    for method in CORE_METHODS:
        config_path = project_root / "configs" / f"toolalign_{method}_llama8b.json"
        config = _read(config_path)
        toolalign_configs[method] = config
        data = config.get("data") or {}
        calibration_domains = set(data.get("calibration_domains") or [])
        evaluation_domains = set(data.get("evaluation_domains") or [])
        expected_cases = (
            len(evaluation_domains)
            * len(data.get("evaluation_documents") or [])
            * len(data.get("evaluation_scenario_types") or [])
        )
        models = config.get("models") or {}
        toolalign_contracts[method] = {
            "both_model_roles": set(models) == {"aligned", "abliterated"},
            "domain_disjoint": calibration_domains.isdisjoint(evaluation_domains),
            "evaluation_cases": expected_cases,
        }
        output = Path(str(config["output_dir"])).expanduser()
        if not output.is_absolute():
            output = (config_path.parent / output).resolve()
        expected_toolalign_analyses.extend(
            output / "analysis" / f"{role}.json" for role in ("aligned", "abliterated")
        )
    jservo_config_path = project_root / "configs" / "toolalign_jservo_llama8b.json"
    jservo_config = _read(jservo_config_path)
    jservo_data = jservo_config.get("data") or {}
    jservo_domain_sets = [
        set(jservo_data.get(key) or [])
        for key in (
            "calibration_domains",
            "probe_validation_domains",
            "evaluation_domains",
        )
    ]
    jservo_output = Path(str(jservo_config["output_dir"])).expanduser()
    if not jservo_output.is_absolute():
        jservo_output = (jservo_config_path.parent / jservo_output).resolve()
    expected_toolalign_analyses.extend(
        jservo_output / "jservo" / "analysis" / f"{role}.json"
        for role in ("aligned", "abliterated")
    )

    tau_runner_source = (tau_root / "scripts" / "run_airline_failure_steering.py").read_text(
        encoding="utf-8"
    )
    tau_analyzer_source = (tau_root / "scripts" / "analyze_airline_failure_steering.py").read_text(
        encoding="utf-8"
    )
    tau_backend_source = (tau_root / "src" / "tau2" / "agent" / "jlens_backend.py").read_text(
        encoding="utf-8"
    )
    tau_agent_source = (tau_root / "src" / "tau2" / "agent" / "jlens_agent.py").read_text(
        encoding="utf-8"
    )
    runtime_method_evidence = {
        method: (
            (method == "caa" and "load_caa_direction_artifact" in tau_backend_source)
            or f'intervention.method == "{method}"' in tau_backend_source
        )
        for method in CORE_METHODS
    }

    implementation_checks = {
        "matrix_fingerprint": _check(
            _matrix_fingerprint_valid(matrix), matrix.get("matrix_fingerprint")
        ),
        "core7_matrix_coverage": _check(
            set(CORE_METHODS).issubset(method_set), sorted(method_set)
        ),
        "core7_runtime_dispatch": _check(
            all(runtime_method_evidence.values()), runtime_method_evidence
        ),
        "remote_only_no_local_model": _check(remote_only, matrix.get("execution")),
        "generic_structural_selection": _check(
            generic_selection,
            {"turn_indices_present": False, "boundaries": sorted(used_boundaries)},
        ),
        "preventive_retry_boundary": _check(
            retry_boundaries == {("after_tool_error",)},
            [list(value) for value in sorted(retry_boundaries)],
        ),
        "method_specific_controls": _check(
            controls == EXPECTED_CONTROLS,
            {method: sorted(values) for method, values in controls.items()},
        ),
        "jservo_adaptive_controls": _check(
            jservo_controls == EXPECTED_JSERVO_CONTROLS
            and "jservo_generation_hooks" in tau_backend_source
            and "_buffer_and_validate_candidate" in tau_agent_source,
            {
                "controls": sorted(jservo_controls),
                "runtime_hook": "jservo_generation_hooks" in tau_backend_source,
                "pre_execution_buffer": "_buffer_and_validate_candidate" in tau_agent_source,
            },
        ),
        "official_airline_split": _check(
            official_split_valid,
            {
                "artifact_train": len(train),
                "validation": len(validation),
                "evaluation": len(evaluation),
            },
        ),
        "toolalign_aligned_abliterated_contract": _check(
            all(
                item["both_model_roles"]
                and item["domain_disjoint"]
                and item["evaluation_cases"] == 32
                for item in toolalign_contracts.values()
            ),
            toolalign_contracts,
        ),
        "toolalign_jservo_split_contract": _check(
            all(
                jservo_domain_sets[index].isdisjoint(jservo_domain_sets[other])
                for index in range(len(jservo_domain_sets))
                for other in range(index + 1, len(jservo_domain_sets))
            )
            and set(jservo_config.get("models") or {}) == {"aligned", "abliterated"}
            and (project_root / "src" / "jlens_causal" / "toolalign_jservo.py").is_file(),
            {
                "train_domains": len(jservo_domain_sets[0]),
                "validation_domains": len(jservo_domain_sets[1]),
                "evaluation_domains": len(jservo_domain_sets[2]),
            },
        ),
        "official_full_review_command": _check(
            all(token in tau_runner_source for token in ('"--mode"', '"full"', '"--show-details"')),
            "tau2 review <results> --mode full --show-details",
        ),
        "separate_agent_user_analysis": _check(
            all(
                token in tau_analyzer_source
                for token in (
                    "agent_review_error_count",
                    "user_review_error_count",
                    "mcnemar_exact_p",
                )
            ),
            ["agent review", "user review", "paired McNemar"],
        ),
    }

    tau_results_root = tau_root / "data" / "simulations" / "failure-steering" / "evaluation"
    expected_tau_results = [
        tau_results_root / str(condition["name"]) / "results_reviewed.json"
        for condition in conditions
    ]
    present_tau_results = [path for path in expected_tau_results if path.is_file()]
    present_toolalign_analyses = [path for path in expected_toolalign_analyses if path.is_file()]
    empirical_checks = {
        "taubench_reviewed_conditions": _check(
            len(present_tau_results) == len(expected_tau_results),
            {
                "present": len(present_tau_results),
                "expected": len(expected_tau_results),
            },
        ),
        "toolalign_paired_analyses": _check(
            len(present_toolalign_analyses) == len(expected_toolalign_analyses),
            {
                "present": len(present_toolalign_analyses),
                "expected": len(expected_toolalign_analyses),
            },
        ),
    }
    return {
        "schema_version": "core7-benchmark-protocol-audit-v1",
        "implementation_ready": all(item["passed"] for item in implementation_checks.values()),
        "empirical_complete": all(item["passed"] for item in empirical_checks.values()),
        "implementation_checks": implementation_checks,
        "empirical_checks": empirical_checks,
        "remaining_external_requirements": [
            "authenticated remote CUDA worker",
            "remote steering artifacts",
            "Tau2 user/reviewer provider key",
            "Hugging Face access for the gated ToolAlign aligned model",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--tau-root", type=Path, default=Path("../tau2-bench"))
    parser.add_argument(
        "--matrix",
        type=Path,
        default=Path("outputs/taubench-airline-failure-matrix.json"),
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    project_root = args.project_root.expanduser().resolve()
    matrix_path = args.matrix.expanduser()
    if not matrix_path.is_absolute():
        matrix_path = (project_root / matrix_path).resolve()
    report = audit_protocol(
        project_root,
        args.tau_root.expanduser().resolve(),
        matrix_path=matrix_path,
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output.expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(output.suffix + ".tmp")
        temporary.write_text(rendered, encoding="utf-8")
        temporary.replace(output)
    print(rendered, end="")
    return 0 if report["implementation_ready"] and report["empirical_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
