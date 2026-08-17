"""Compile leakage-controlled failure-mode steering manifests for TauBench."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FAILURE_STEERING_SCHEMA = "agent-failure-steering-v1"
FAILURE_MATRIX_SCHEMA = "agent-failure-steering-matrix-v1"
FAILURE_MATRIX_COMPILER_VERSION = "failure-steering-compiler-v2"
CORE_METHODS = ("caa", "cast", "mera", "sadi", "iti", "austeer", "loreft")
JSERVO_CONTROLS = {
    "targeted",
    "fixed_strength",
    "fixed_layer",
    "wrong_mode",
    "random",
    "reverse",
    "validator_only",
}

STEERING_OPPORTUNITY_BOUNDARIES = {
    "tool_call_error": "after_tool_error",
    # These boundaries precede the action we want to change.  Waiting for an
    # exact repeat to be observed would make the intervention post-hoc.
    "retry_without_state_change": "after_tool_error",
    "repeated_tool_call": "after_successful_tool_result",
    "short_tool_cycle": "after_short_tool_cycle",
    "completion_not_released": "after_successful_tool_result",
}
# Compatibility alias for code that imported the original public name.
STRUCTURAL_BOUNDARIES = STEERING_OPPORTUNITY_BOUNDARIES


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _string_ids(value: Any, *, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{label} must be a non-empty list")
    ids = tuple(str(item) for item in value)
    if len(ids) != len(set(ids)):
        raise ValueError(f"{label} contains duplicate task IDs")
    return ids


@dataclass(frozen=True)
class FailureSteeringManifest:
    path: Path
    raw: dict[str, Any]
    train_task_ids: tuple[str, ...]
    validation_task_ids: tuple[str, ...]
    evaluation_task_ids: tuple[str, ...]
    tool_schema_path: Path | None = None

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.raw)


def load_failure_steering_manifest(path: str | Path) -> FailureSteeringManifest:
    """Validate remote-only execution, disjoint splits, and Core-7 contracts."""
    resolved = Path(path).expanduser().resolve()
    raw = json.loads(resolved.read_text(encoding="utf-8"))
    if raw.get("schema_version") != FAILURE_STEERING_SCHEMA:
        raise ValueError("unsupported failure steering manifest schema")
    if raw.get("benchmark") != "taubench-airline":
        raise ValueError("failure steering currently targets taubench-airline")
    execution = raw.get("execution")
    if not isinstance(execution, dict) or execution.get("mode") != "remote":
        raise ValueError("failure steering execution.mode must be 'remote'")
    if not execution.get("endpoint_env") or not execution.get("token_env"):
        raise ValueError("remote endpoint_env and token_env are required")
    if "endpoint" in execution or "token" in execution:
        raise ValueError("store remote endpoint/token in environment variables, not manifests")

    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    revision = model.get("model_revision")
    if not isinstance(revision, str) or len(revision) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")

    tool_schema_path = None
    tool_schema = raw.get("tool_schema")
    if tool_schema is not None:
        if not isinstance(tool_schema, dict) or tool_schema.get("domain") != "airline":
            raise ValueError("tool_schema must identify the airline domain")
        relative_path = tool_schema.get("path")
        expected_sha256 = tool_schema.get("sha256")
        if not isinstance(relative_path, str) or not isinstance(expected_sha256, str):
            raise ValueError("tool_schema path and sha256 are required")
        candidate = Path(relative_path).expanduser()
        tool_schema_path = (
            candidate if candidate.is_absolute() else resolved.parent / candidate
        ).resolve()
        if not tool_schema_path.is_file():
            raise FileNotFoundError(f"tool schema file is missing: {tool_schema_path}")
        try:
            tool_schema_value = json.loads(tool_schema_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("tool schema must be valid UTF-8 JSON") from error
        # Fingerprint the JSON value rather than platform-specific file bytes.
        # Git checks out text with LF on Linux and may use CRLF on Windows.
        actual_sha256 = _fingerprint(tool_schema_value)
        if actual_sha256 != expected_sha256:
            raise ValueError("tool schema sha256 does not match the pinned manifest")

    splits = raw.get("splits")
    if not isinstance(splits, dict):
        raise ValueError("splits are required")
    train = _string_ids(splits.get("train_task_ids"), label="splits.train_task_ids")
    validation = _string_ids(splits.get("validation_task_ids"), label="splits.validation_task_ids")
    evaluation = _string_ids(splits.get("evaluation_task_ids"), label="splits.evaluation_task_ids")
    if (
        set(train) & set(validation)
        or set(train) & set(evaluation)
        or set(validation) & set(evaluation)
    ):
        raise ValueError("train, validation, and evaluation task IDs must be disjoint")

    modes = raw.get("failure_modes")
    if not isinstance(modes, dict) or not modes:
        raise ValueError("failure_modes must be a non-empty object")
    seen_methods: set[str] = set()
    for category, mode in modes.items():
        if category not in STRUCTURAL_BOUNDARIES:
            raise ValueError(f"unsupported online structural failure category {category!r}")
        if not isinstance(mode, dict):
            raise ValueError(f"failure_modes.{category} must be an object")
        boundary = mode.get("boundary", STRUCTURAL_BOUNDARIES[category])
        if boundary != STRUCTURAL_BOUNDARIES[category]:
            raise ValueError(f"{category} must use boundary {STRUCTURAL_BOUNDARIES[category]!r}")
        methods = mode.get("methods")
        if not isinstance(methods, dict) or not methods:
            raise ValueError(f"failure_modes.{category}.methods is required")
        for method, specification in methods.items():
            if method not in CORE_METHODS:
                raise ValueError(f"unknown steering method {method!r}")
            seen_methods.add(method)
            if not isinstance(specification, dict):
                raise ValueError(f"{category}.{method} must be an object")
            intervention = specification.get("intervention")
            if not isinstance(intervention, dict):
                raise ValueError(f"{category}.{method}.intervention is required")
            if intervention.get("method") != method:
                raise ValueError(f"{category}.{method} intervention method mismatch")
            if intervention.get("turn_indices"):
                raise ValueError("default failure steering may not hard-code turn_indices")
            if intervention.get("boundaries"):
                raise ValueError("manifest compiler owns intervention boundaries")
            strengths = specification.get("strengths")
            if (
                not isinstance(strengths, list)
                or not strengths
                or not all(isinstance(item, (int, float)) for item in strengths)
            ):
                raise ValueError(f"{category}.{method}.strengths must be numeric")
    missing = set(CORE_METHODS) - seen_methods
    if missing:
        raise ValueError(f"manifest must cover every Core-7 method; missing {sorted(missing)}")
    adaptive = raw.get("adaptive_controller")
    if adaptive is not None:
        if not isinstance(adaptive, dict) or not isinstance(
            adaptive.get("artifact_path"), str
        ):
            raise ValueError("adaptive_controller.artifact_path is required")
        conditions = adaptive.get("conditions")
        if not isinstance(conditions, list) or not conditions:
            raise ValueError("adaptive_controller.conditions must be non-empty")
        for condition in conditions:
            if not isinstance(condition, dict) or condition.get("control_type") not in JSERVO_CONTROLS:
                raise ValueError("adaptive_controller has an unknown control_type")
            if condition.get("control_type") == "fixed_strength" and not isinstance(
                condition.get("fixed_strength"), (int, float)
            ):
                raise ValueError("fixed_strength control requires fixed_strength")
            if condition.get("control_type") == "fixed_layer" and not isinstance(
                condition.get("layer_override"), int
            ):
                raise ValueError("fixed_layer control requires layer_override")
    return FailureSteeringManifest(
        path=resolved,
        raw=raw,
        train_task_ids=train,
        validation_task_ids=validation,
        evaluation_task_ids=evaluation,
        tool_schema_path=tool_schema_path,
    )


def _condition(
    manifest: FailureSteeringManifest,
    *,
    name: str,
    method: str,
    category: str,
    control_type: str,
    intervention: dict[str, Any] | None,
    controller: dict[str, Any] | None = None,
) -> dict[str, Any]:
    generation = dict(manifest.raw.get("generation", {}))
    model = manifest.raw["model"]
    args = {
        **generation,
        "hf_revision": model["model_revision"],
        "hf_dtype": model.get("dtype", "bfloat16"),
        "hf_sdpa_backend": model.get("attention", "auto"),
        "hf_trust_remote_code": bool(model.get("trust_remote_code", False)),
        "jlens_require_remote": True,
        "jlens_mode": (
            "observe" if intervention is None and controller is None else "intervene"
        ),
    }
    if intervention is not None:
        args["jlens_intervention"] = intervention
    if controller is not None:
        args["jlens_controller"] = controller
    return {
        "name": name,
        "method": method,
        "failure_category": category,
        "control_type": control_type,
        "agent_llm_args": args,
    }


def compile_failure_steering_matrix(
    manifest: FailureSteeringManifest,
) -> dict[str, Any]:
    """Expand Core-7 treatments and causal controls without fixed task turns."""
    conditions = [
        _condition(
            manifest,
            name="baseline",
            method="none",
            category="none",
            control_type="no_steer",
            intervention=None,
        )
    ]
    categories = list(manifest.raw["failure_modes"])
    for category, mode in manifest.raw["failure_modes"].items():
        boundary = STRUCTURAL_BOUNDARIES[category]
        wrong_category = next((item for item in categories if item != category), None)
        wrong_boundary = (
            STRUCTURAL_BOUNDARIES[wrong_category]
            if wrong_category is not None
            else "after_successful_tool_result"
        )
        for method, specification in mode["methods"].items():
            template = deepcopy(specification["intervention"])
            for strength_value in specification["strengths"]:
                strength = float(strength_value)
                positive = {**deepcopy(template), "strength": strength, "boundaries": [boundary]}
                stem = f"{category}-{method}-s{strength:g}"
                conditions.append(
                    _condition(
                        manifest,
                        name=stem,
                        method=method,
                        category=category,
                        control_type="targeted",
                        intervention=positive,
                    )
                )
                negative_strength = float(
                    specification.get(
                        "negative_strength",
                        0.0 if method == "sadi" else -strength,
                    )
                )
                negative = {
                    **deepcopy(template),
                    "strength": negative_strength,
                    "boundaries": [boundary],
                }
                negative_control_type = (
                    "zero_dose" if negative_strength == 0.0 else "negative_direction"
                )
                negative_suffix = "zero" if negative_strength == 0.0 else "negative"
                conditions.append(
                    _condition(
                        manifest,
                        name=f"{stem}-{negative_suffix}",
                        method=method,
                        category=category,
                        control_type=negative_control_type,
                        intervention=negative,
                    )
                )
                wrong = {
                    **deepcopy(template),
                    "strength": strength,
                    "boundaries": [wrong_boundary],
                }
                conditions.append(
                    _condition(
                        manifest,
                        name=f"{stem}-wrong-category",
                        method=method,
                        category=category,
                        control_type="wrong_category",
                        intervention=wrong,
                    )
                )
                if specification.get("wrong_layer") is not None:
                    wrong_layer = {
                        **deepcopy(template),
                        "layer": int(specification["wrong_layer"]),
                        "strength": strength,
                        "boundaries": [boundary],
                    }
                    conditions.append(
                        _condition(
                            manifest,
                            name=f"{stem}-wrong-layer",
                            method=method,
                            category=category,
                            control_type="wrong_layer",
                            intervention=wrong_layer,
                        )
                    )
    adaptive = manifest.raw.get("adaptive_controller")
    if adaptive is not None:
        for index, specification in enumerate(adaptive["conditions"]):
            control_type = str(specification["control_type"])
            controller = {
                "artifact_path": adaptive["artifact_path"],
                **deepcopy(specification),
            }
            conditions.append(
                _condition(
                    manifest,
                    name=f"jservo-{control_type}-{index}",
                    method="jservo",
                    category="adaptive_router",
                    control_type=control_type,
                    intervention=None,
                    controller=controller,
                )
            )
    matrix = {
        "schema_version": FAILURE_MATRIX_SCHEMA,
        "compiler_version": FAILURE_MATRIX_COMPILER_VERSION,
        "manifest_path": str(manifest.path),
        "manifest_fingerprint": manifest.fingerprint,
        "benchmark": manifest.raw["benchmark"],
        "model": manifest.raw["model"],
        "execution": manifest.raw["execution"],
        "generation": manifest.raw.get("generation", {}),
        "splits": {
            "train_task_ids": list(manifest.train_task_ids),
            "validation_task_ids": list(manifest.validation_task_ids),
            "evaluation_task_ids": list(manifest.evaluation_task_ids),
        },
        "conditions": conditions,
        "notes": {
            "oracle_gate": "Post-hoc upper bound only; never report as deployable.",
            "learned_gate": "Fit thresholds on train/validation task IDs only.",
            "review": "Run tau2 review in full mode and separate agent from user errors.",
        },
    }
    matrix["matrix_fingerprint"] = _fingerprint(matrix)
    return matrix


def write_failure_steering_matrix(path: str | Path, matrix: dict[str, Any]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(output)
    return output
