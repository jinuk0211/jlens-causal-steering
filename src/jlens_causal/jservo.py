"""Failure-mode adaptive steering in Jacobian-lens coordinates.

J-Servo treats a validated repair state as a layer-local set point.  At an
eligible structural boundary it observes a source/target J-space margin, then
adds the minimum residual edit predicted to reach the calibrated repair
margin.  Directions are projected away from stable protected concepts, and
the controller abstains when the required edit exceeds a natural residual
delta observed in the calibration pairs.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Iterable, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import numpy as np

from jlens_causal.failure_caa import paired_action_inputs
from jlens_causal.failure_core_extractors import select_failure_pairs
from jlens_causal.modeling import ModelRuntime, capture_block_outputs

JSERVO_ARTIFACT_SCHEMA = "jlens-jservo-v1"
JSERVO_CONTROLLER_VERSION = "failure-mode-adaptive-v1"

# These names match the mechanisms used in the paper rather than the surface
# error tags emitted by Tau2's reviewer.
FAILURE_MODE_ALIASES = {
    "missed_required_action": "skipped_evidence_acquisition",
    "unresolved_tool_call": "state_update_miss",
    "tool_call_argument_error": "unsupported_commitment",
    "hallucination": "unsupported_commitment",
    "incorrect_interpretation": "unsupported_commitment",
    "guideline_violation": "policy_goal_drift",
    "wrong_sequence": "goal_state_maintenance",
    "irrelevant_tool_call": "semantic_action_error",
    "tool_call_schema_error": "malformed_serialization",
    "mixed_content_and_tool_call": "malformed_serialization",
    "empty_message": "malformed_serialization",
    "repeated_tool_call": "completion_not_released",
    "short_tool_cycle": "retry_without_state_change",
    "premature_termination": "premature_completion",
    "tool_call_error": "unsupported_commitment",
    "retry_without_state_change": "retry_without_state_change",
    "completion_not_released": "completion_not_released",
    "toolalign_value_routing": "toolalign_value_routing",
}

MODE_BOUNDARIES = {
    "skipped_evidence_acquisition": ("initial_decision", "after_user_message"),
    "state_update_miss": ("after_tool_result",),
    "unsupported_commitment": (
        "initial_decision",
        "after_user_message",
        "after_tool_result",
        "after_tool_error",
    ),
    "policy_goal_drift": ("initial_decision", "after_user_message", "after_tool_result"),
    "goal_state_maintenance": ("after_user_message", "after_tool_result"),
    "semantic_action_error": ("after_user_message", "after_tool_result"),
    "action_loss_before_output": ("after_user_message", "after_tool_result"),
    "malformed_serialization": ("after_user_message", "after_tool_result"),
    "argument_binding_error": ("after_user_message", "after_tool_result"),
    "result_validation_miss": ("after_tool_result", "after_successful_tool_result"),
    "completion_not_released": ("after_successful_tool_result",),
    "retry_without_state_change": (
        "after_tool_error",
        "after_repeated_tool_error",
        "after_short_tool_cycle",
    ),
    "premature_completion": ("after_user_message", "after_tool_result"),
    "toolalign_value_routing": ("initial_decision", "after_user_message"),
}

MODE_LAYER_POLICY = {
    "skipped_evidence_acquisition": ((16,), (16, 20)),
    "state_update_miss": ((16,), (20, 24)),
    "unsupported_commitment": ((20,), (20, 24)),
    "policy_goal_drift": ((16,), (20, 24)),
    "goal_state_maintenance": ((16,), (20, 24)),
    "semantic_action_error": ((20,), (20, 24)),
    "action_loss_before_output": ((24,), (24, 28)),
    "malformed_serialization": ((28,), (28, 30)),
    "argument_binding_error": ((20,), (24, 28)),
    "result_validation_miss": ((16,), (20, 24)),
    "completion_not_released": ((20,), (20, 24)),
    "retry_without_state_change": ((20,), (20, 24)),
    "premature_completion": ((20,), (20, 24)),
    "toolalign_value_routing": ((16,), (20, 24)),
}

VALID_CONTROL_TYPES = {
    "targeted",
    "fixed_strength",
    "fixed_layer",
    "wrong_mode",
    "random",
    "reverse",
    "validator_only",
}

_WORD = re.compile(r"[\w][\w-]+", re.UNICODE)


def canonical_failure_mode(category: str, correct_behavior: str | None = None) -> str:
    """Map reviewer/structural labels onto the analyzed mechanism taxonomy."""
    normalized = str(category).strip().lower()
    text = str(correct_behavior or "").lower()
    if normalized in {"tool_call_argument_error", "tool_call_error"}:
        if any(term in text for term in (" id", "identifier", "each", "per-", "argument")):
            return "argument_binding_error"
    if normalized == "premature_termination":
        return "premature_completion"
    return FAILURE_MODE_ALIASES.get(normalized, normalized)


def default_mode_boundaries(mode: str) -> tuple[str, ...]:
    """Return deployable, prefix-visible boundaries for one failure mode."""
    return MODE_BOUNDARIES.get(str(mode), ())


def mode_layer_policy(
    mode: str,
    *,
    fallback_observation: Sequence[int] = (16,),
    fallback_control: Sequence[int] = (20, 24),
) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return the preregistered stage-local observer and control layers."""
    return MODE_LAYER_POLICY.get(
        str(mode),
        (tuple(map(int, fallback_observation)), tuple(map(int, fallback_control))),
    )


def _tensor_sha256(tensor: Any) -> str:
    return hashlib.sha256(
        tensor.detach().contiguous().float().cpu().numpy().tobytes()
    ).hexdigest()


def _json_fingerprint(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _clean_token(text: str) -> str:
    value = str(text).replace("\u2581", " ").replace("\u0120", " ").strip()
    return " ".join(_WORD.findall(value)).lower()


def _unit(vector: Any, *, label: str) -> Any:
    value = vector.detach().float().cpu()
    norm = value.norm()
    if not bool(torch_isfinite(norm)) or float(norm) <= 1e-12:
        raise ValueError(f"{label} has zero or non-finite norm")
    return value / norm


def torch_isfinite(value: Any) -> bool:
    """Avoid importing torch globally in artifact-only inspection commands."""
    return bool(__import__("torch").isfinite(value).all())


def project_away(vector: Any, protected: Any, *, ridge: float = 1e-6) -> Any:
    """Project ``vector`` away from the columns of a protected direction matrix."""
    torch = __import__("torch")
    value = vector.detach().float().cpu()
    if protected is None or int(protected.numel()) == 0:
        return value
    basis = protected.detach().float().cpu()
    if basis.ndim != 2 or int(basis.shape[0]) != int(value.numel()):
        raise ValueError("protected directions must have shape [d_model, concepts]")
    gram = basis.T @ basis
    identity = torch.eye(gram.shape[0], dtype=gram.dtype)
    coefficients = torch.linalg.solve(gram + float(ridge) * identity, basis.T @ value)
    return value - basis @ coefficients


def minimum_state_edit(
    current: Any,
    *,
    margin_direction: Any,
    projected_direction: Any,
    target_margin: float,
    dose_cap: float,
    cumulative_dose: float = 0.0,
    cumulative_cap: float | None = None,
) -> dict[str, Any]:
    """Return the minimum edit that reaches a linear J-space target margin.

    The denominator uses the unprojected read direction and protected-space
    projected write direction.  This preserves the exact predicted margin
    change even when target and protected J-vectors are non-orthogonal.
    """
    torch = __import__("torch")
    point = current.detach().float()
    read = margin_direction.to(device=point.device, dtype=point.dtype)
    write = projected_direction.to(device=point.device, dtype=point.dtype)
    margin = float((point @ read).detach().cpu())
    deficit = max(0.0, float(target_margin) - margin)
    denominator = float((read @ write).detach().cpu())
    output = {
        "pre_margin": margin,
        "target_margin": float(target_margin),
        "deficit": deficit,
        "denominator": denominator,
        "dose_norm": 0.0,
        "predicted_post_margin": margin,
        "feasible": True,
        "reason": "target_already_reached" if deficit == 0.0 else "selected",
        "delta": torch.zeros_like(point),
    }
    if deficit == 0.0:
        return output
    if not math.isfinite(denominator) or denominator <= 1e-12:
        output.update(feasible=False, reason="non_positive_control_gain")
        return output
    delta = deficit / denominator * write
    dose = float(delta.norm().detach().cpu())
    cumulative_limit = math.inf if cumulative_cap is None else float(cumulative_cap)
    if not math.isfinite(dose) or dose > float(dose_cap) + 1e-9:
        output.update(feasible=False, reason="layer_dose_cap_exceeded", dose_norm=dose)
        return output
    if float(cumulative_dose) + dose > cumulative_limit + 1e-9:
        output.update(feasible=False, reason="cumulative_dose_cap_exceeded", dose_norm=dose)
        return output
    output.update(
        delta=delta,
        dose_norm=dose,
        predicted_post_margin=margin + float((delta @ read).detach().cpu()),
    )
    return output


def _quantile(values: Any, q: float) -> float:
    torch = __import__("torch")
    tensor = torch.as_tensor(values, dtype=torch.float32).flatten()
    if not int(tensor.numel()):
        raise ValueError("cannot compute a quantile of an empty tensor")
    return float(torch.quantile(tensor, float(q)).item())


def _readout_scores(activations: Any, jacobian: Any, unembedding: Any) -> Any:
    hidden = activations.detach().float().cpu()
    transport = jacobian.detach().float().cpu()
    output = unembedding.detach().float().cpu()
    return hidden @ transport.T @ output.T


def _eligible_token_mask(token_texts: Sequence[str]) -> np.ndarray:
    values = []
    for text in token_texts:
        cleaned = _clean_token(str(text))
        values.append(bool(cleaned) and len(cleaned) >= 2 and not cleaned.isdigit())
    return np.asarray(values, dtype=bool)


def select_concept_bundles(
    train_correct_scores: Any,
    train_failure_scores: Any,
    validation_correct_scores: Any,
    validation_failure_scores: Any,
    token_texts: Sequence[str],
    *,
    bundle_size: int = 8,
    protected_size: int = 8,
    minimum_consistency: float = 0.7,
) -> dict[str, Any]:
    """Select repair, failure, and stable protected tokens without eval data."""
    train_correct = train_correct_scores.detach().float().cpu().numpy()
    train_failure = train_failure_scores.detach().float().cpu().numpy()
    val_correct = validation_correct_scores.detach().float().cpu().numpy()
    val_failure = validation_failure_scores.detach().float().cpu().numpy()
    if train_correct.shape != train_failure.shape or val_correct.shape != val_failure.shape:
        raise ValueError("correct/failure score matrices must be paired")
    if train_correct.ndim != 2 or train_correct.shape[1] != len(token_texts):
        raise ValueError("score matrices must have shape [pairs, vocabulary]")
    delta = train_correct - train_failure
    validation_delta = val_correct - val_failure
    mean_delta = delta.mean(axis=0)
    positive_consistency = (delta > 0).mean(axis=0)
    negative_consistency = (delta < 0).mean(axis=0)
    val_positive = (validation_delta > 0).mean(axis=0)
    val_negative = (validation_delta < 0).mean(axis=0)
    lexical = _eligible_token_mask(token_texts)

    def choose(sign: int) -> list[int]:
        train_consistency = positive_consistency if sign > 0 else negative_consistency
        validation_consistency = val_positive if sign > 0 else val_negative
        mask = (
            lexical
            & (sign * mean_delta > 0)
            & (train_consistency >= float(minimum_consistency))
            & (validation_consistency >= float(minimum_consistency))
        )
        score = np.abs(mean_delta) * np.minimum(train_consistency, validation_consistency)
        candidates = np.flatnonzero(mask)
        ordered = candidates[np.argsort(score[candidates])[::-1]]
        return [int(item) for item in ordered[: int(bundle_size)]]

    target_ids = choose(1)
    source_ids = choose(-1)
    excluded = set(target_ids) | set(source_ids)
    common = np.mean(np.abs(np.concatenate((train_correct, train_failure), axis=0)), axis=0)
    low_change = np.abs(mean_delta) <= np.quantile(np.abs(mean_delta[lexical]), 0.25)
    protected_candidates = np.flatnonzero(
        lexical & low_change & ~np.asarray([index in excluded for index in range(len(lexical))])
    )
    protected_ordered = protected_candidates[np.argsort(common[protected_candidates])[::-1]]
    protected_ids = [int(item) for item in protected_ordered[: int(protected_size)]]

    def weights(ids: list[int]) -> list[float]:
        raw = np.asarray([abs(float(mean_delta[index])) for index in ids], dtype=np.float64)
        if not len(raw):
            return []
        total = float(raw.sum())
        return [float(value / total) for value in raw] if total > 0 else [1.0 / len(raw)] * len(raw)

    def rows(ids: list[int], values: list[float]) -> list[dict[str, Any]]:
        return [
            {
                "token_id": token_id,
                "token": str(token_texts[token_id]),
                "normalized": _clean_token(str(token_texts[token_id])),
                "weight": float(weight),
                "mean_repair_minus_failure": float(mean_delta[token_id]),
                "train_consistency": float(
                    positive_consistency[token_id]
                    if mean_delta[token_id] >= 0
                    else negative_consistency[token_id]
                ),
                "validation_consistency": float(
                    val_positive[token_id]
                    if mean_delta[token_id] >= 0
                    else val_negative[token_id]
                ),
            }
            for token_id, weight in zip(ids, values, strict=True)
        ]

    target_weights = weights(target_ids)
    source_weights = weights(source_ids)
    return {
        "target": rows(target_ids, target_weights),
        "source": rows(source_ids, source_weights),
        "protected": rows(protected_ids, [1.0] * len(protected_ids)),
        "selection": {
            "bundle_size": int(bundle_size),
            "protected_size": int(protected_size),
            "minimum_consistency": float(minimum_consistency),
            "train_pairs": int(train_correct.shape[0]),
            "validation_pairs": int(val_correct.shape[0]),
        },
    }


def _weighted_unembedding(unembedding: Any, rows: list[dict[str, Any]]) -> Any:
    torch = __import__("torch")
    if not rows:
        return torch.zeros(unembedding.shape[1], dtype=torch.float32)
    ids = torch.tensor([int(row["token_id"]) for row in rows], dtype=torch.long)
    weights = torch.tensor([float(row["weight"]) for row in rows], dtype=torch.float32)
    return (unembedding.detach().float().cpu().index_select(0, ids) * weights[:, None]).sum(0)


def _layer_payload(
    *,
    torch: Any,
    layer: int,
    jacobian: Any,
    unembedding: Any,
    bundles: dict[str, Any],
    train_correct: Any,
    train_failure: Any,
    validation_correct: Any,
    validation_failure: Any,
    role: str,
    random_seed: int,
) -> dict[str, Any]:
    target = _weighted_unembedding(unembedding, bundles["target"])
    source = _weighted_unembedding(unembedding, bundles["source"])
    transport = jacobian.detach().float().cpu()
    margin_direction = transport.T @ (target - source)
    protected_vectors = [
        transport.T @ unembedding[int(row["token_id"])].detach().float().cpu()
        for row in bundles["protected"]
    ]
    protected = (
        torch.stack(protected_vectors, dim=1)
        if protected_vectors
        else torch.empty(margin_direction.numel(), 0)
    )
    projected = project_away(margin_direction, protected)
    denominator = float(margin_direction @ projected)
    train_correct_margin = train_correct.detach().float().cpu() @ margin_direction
    train_failure_margin = train_failure.detach().float().cpu() @ margin_direction
    validation_correct_margin = validation_correct.detach().float().cpu() @ margin_direction
    validation_failure_margin = validation_failure.detach().float().cpu() @ margin_direction
    target_margin = _quantile(train_correct_margin, 0.25)
    gate_threshold = _quantile(validation_correct_margin, 0.05)
    reverse_gate_threshold = _quantile(validation_failure_margin, 0.95)
    reverse_target_margin = -_quantile(train_failure_margin, 0.75)
    combined = torch.cat((train_correct_margin, train_failure_margin))
    margin_scale = max(float(combined.std(unbiased=False)), 1e-6)
    natural_deltas = (train_correct - train_failure).detach().float().cpu().norm(dim=-1)
    residual_norms = torch.cat((train_correct, train_failure)).norm(dim=-1)
    residual_scale = _quantile(residual_norms, 0.5)
    dose_cap = _quantile(natural_deltas, 0.95)
    if dose_cap <= 1e-8:
        dose_cap = 0.05 * residual_scale
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(random_seed) + 1_000_003 * int(layer))
    random_direction = torch.randn(projected.shape, generator=generator)
    projected_norm = float(projected.norm())
    random_direction = (
        _unit(random_direction, label=f"random[{layer}]") * projected_norm
        if projected_norm > 1e-12
        else torch.zeros_like(projected)
    )
    validation_fpr = float((validation_correct_margin < gate_threshold).float().mean())
    validation_tpr = float((validation_failure_margin < gate_threshold).float().mean())
    eligible = bool(
        bundles["target"]
        and bundles["source"]
        and math.isfinite(denominator)
        and denominator > 1e-10
        and validation_tpr > 0.0
    )
    return {
        "layer": int(layer),
        "role": str(role),
        "margin_direction": margin_direction,
        "projected_direction": projected,
        "random_direction": random_direction,
        "control_gain": denominator,
        "gate_threshold": gate_threshold,
        "target_margin": target_margin,
        "reverse_gate_threshold": reverse_gate_threshold,
        "reverse_target_margin": reverse_target_margin,
        "margin_scale": margin_scale,
        "dose_cap": float(dose_cap),
        "residual_scale": float(residual_scale),
        "protected_rank": int(torch.linalg.matrix_rank(protected)) if protected.numel() else 0,
        "validation_false_trigger_rate": validation_fpr,
        "validation_failure_trigger_rate": validation_tpr,
        "steering_eligible": eligible,
    }


def build_jservo_mode(
    torch: Any,
    *,
    failure_category: str,
    correct_behavior: str | None,
    train_correct_by_layer: dict[int, Sequence[Any]],
    train_failure_by_layer: dict[int, Sequence[Any]],
    validation_correct_by_layer: dict[int, Sequence[Any]],
    validation_failure_by_layer: dict[int, Sequence[Any]],
    jacobians: dict[int, Any],
    unembedding: Any,
    token_texts: Sequence[str],
    observation_layers: Sequence[int],
    control_layers: Sequence[int],
    train_pair_ids: Sequence[str],
    validation_pair_ids: Sequence[str],
    bundle_size: int = 8,
    protected_size: int = 8,
    minimum_consistency: float = 0.7,
    random_seed: int = 42,
) -> dict[str, Any]:
    """Build one failure-mode controller from disjoint repair pairs."""
    mode = canonical_failure_mode(failure_category, correct_behavior)
    layers = tuple(dict.fromkeys([*map(int, observation_layers), *map(int, control_layers)]))
    if not layers or not control_layers:
        raise ValueError("J-Servo requires observation and control layers")
    if set(train_pair_ids) & set(validation_pair_ids):
        raise ValueError("J-Servo train and validation pair IDs must be disjoint")
    stacked: dict[int, dict[str, Any]] = {}
    for layer in layers:
        if layer not in jacobians:
            raise ValueError(f"missing Jacobian for layer {layer}")
        stacked[layer] = {
            "train_correct": torch.stack(list(train_correct_by_layer[layer])).float().cpu(),
            "train_failure": torch.stack(list(train_failure_by_layer[layer])).float().cpu(),
            "validation_correct": torch.stack(list(validation_correct_by_layer[layer])).float().cpu(),
            "validation_failure": torch.stack(list(validation_failure_by_layer[layer])).float().cpu(),
        }
    selection_layer = int(control_layers[0])
    selected = stacked[selection_layer]
    bundles = select_concept_bundles(
        _readout_scores(selected["train_correct"], jacobians[selection_layer], unembedding),
        _readout_scores(selected["train_failure"], jacobians[selection_layer], unembedding),
        _readout_scores(selected["validation_correct"], jacobians[selection_layer], unembedding),
        _readout_scores(selected["validation_failure"], jacobians[selection_layer], unembedding),
        token_texts,
        bundle_size=bundle_size,
        protected_size=protected_size,
        minimum_consistency=minimum_consistency,
    )
    payloads = {}
    for layer in layers:
        values = stacked[layer]
        payloads[str(layer)] = _layer_payload(
            torch=torch,
            layer=layer,
            jacobian=jacobians[layer],
            unembedding=unembedding,
            bundles=bundles,
            train_correct=values["train_correct"],
            train_failure=values["train_failure"],
            validation_correct=values["validation_correct"],
            validation_failure=values["validation_failure"],
            role="observe" if layer in set(map(int, observation_layers)) else "control",
            random_seed=random_seed,
        )
    eligible = all(
        payloads[str(layer)]["steering_eligible"] for layer in map(int, control_layers)
    )
    cumulative_cap = sum(payloads[str(layer)]["dose_cap"] for layer in map(int, control_layers))
    return {
        "mode": mode,
        "source_failure_category": str(failure_category),
        "boundaries": list(default_mode_boundaries(mode)),
        "observation_layers": list(map(int, observation_layers)),
        "control_layers": list(map(int, control_layers)),
        "max_active_layers_per_position": len(tuple(control_layers)),
        "cumulative_dose_cap": float(cumulative_cap),
        "steering_eligible": bool(eligible),
        "fallback": "validator_or_abstain" if not eligible else "abstain_on_infeasible_edit",
        "token_bundles": bundles,
        "layers": payloads,
        "train_pair_ids": list(map(str, train_pair_ids)),
        "validation_pair_ids": list(map(str, validation_pair_ids)),
    }


def build_jservo_artifact(
    *,
    model_id: str,
    model_revision: str,
    lens_revision: str | None,
    benchmark: str,
    modes: Iterable[dict[str, Any]],
    calibration: dict[str, Any],
) -> dict[str, Any]:
    """Combine independently calibrated failure modes into one runtime artifact."""
    by_mode: dict[str, dict[str, Any]] = {}
    for mode in modes:
        name = str(mode["mode"])
        if name in by_mode:
            raise ValueError(f"duplicate J-Servo mode {name}")
        by_mode[name] = mode
    if not by_mode:
        raise ValueError("J-Servo artifact requires at least one failure mode")
    identity = {
        "schema_version": JSERVO_ARTIFACT_SCHEMA,
        "controller_version": JSERVO_CONTROLLER_VERSION,
        "model_id": str(model_id),
        "model_revision": str(model_revision),
        "lens_revision": lens_revision,
        "benchmark": str(benchmark),
        "calibration": calibration,
        "calibration_fingerprint": _json_fingerprint(calibration),
        "modes": {
            name: {
                "source_failure_category": value["source_failure_category"],
                "boundaries": value["boundaries"],
                "observation_layers": value["observation_layers"],
                "control_layers": value["control_layers"],
                "train_pair_ids": value["train_pair_ids"],
                "validation_pair_ids": value["validation_pair_ids"],
                "max_active_layers_per_position": value[
                    "max_active_layers_per_position"
                ],
                "cumulative_dose_cap": value["cumulative_dose_cap"],
                "steering_eligible": value["steering_eligible"],
                "token_bundles": value["token_bundles"],
                "layer_contracts": {
                    layer: {
                        "margin_direction": _tensor_sha256(
                            payload["margin_direction"]
                        ),
                        "projected_direction": _tensor_sha256(
                            payload["projected_direction"]
                        ),
                        "random_direction": _tensor_sha256(
                            payload["random_direction"]
                        ),
                        "gate_threshold": payload["gate_threshold"],
                        "target_margin": payload["target_margin"],
                        "reverse_gate_threshold": payload.get(
                            "reverse_gate_threshold"
                        ),
                        "reverse_target_margin": payload.get(
                            "reverse_target_margin"
                        ),
                        "dose_cap": payload["dose_cap"],
                        "residual_scale": payload["residual_scale"],
                    }
                    for layer, payload in value["layers"].items()
                },
            }
            for name, value in sorted(by_mode.items())
        },
    }
    return {
        **identity,
        "artifact_fingerprint": _json_fingerprint(identity),
        "modes": by_mode,
    }


def validate_jservo_artifact(
    artifact: dict[str, Any],
    *,
    expected_model_id: str | None = None,
    expected_model_revision: str | None = None,
) -> dict[str, Any]:
    """Validate scientific identity and runtime tensors for a J-Servo artifact."""
    if artifact.get("schema_version") != JSERVO_ARTIFACT_SCHEMA:
        raise ValueError("unsupported J-Servo artifact schema")
    if artifact.get("controller_version") != JSERVO_CONTROLLER_VERSION:
        raise ValueError("unsupported J-Servo controller version")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("J-Servo artifact model_id mismatch")
    if (
        expected_model_revision is not None
        and artifact.get("model_revision") != expected_model_revision
    ):
        raise ValueError("J-Servo artifact model_revision mismatch")
    modes = artifact.get("modes")
    if not isinstance(modes, dict) or not modes:
        raise ValueError("J-Servo artifact modes are missing")
    for name, mode in modes.items():
        if name != mode.get("mode"):
            raise ValueError("J-Servo mode key mismatch")
        if not mode.get("observation_layers") or not mode.get("control_layers"):
            raise ValueError(f"J-Servo mode {name} is missing layer roles")
        layers = mode.get("layers")
        if not isinstance(layers, dict):
            raise ValueError(f"J-Servo mode {name} has no layer payloads")
        for layer in [*mode["observation_layers"], *mode["control_layers"]]:
            payload = layers.get(str(layer))
            if not isinstance(payload, dict):
                raise ValueError(f"J-Servo mode {name} is missing layer {layer}")
            for field in ("margin_direction", "projected_direction", "random_direction"):
                tensor = payload.get(field)
                if tensor is None or getattr(tensor, "ndim", None) != 1 or not torch_isfinite(tensor):
                    raise ValueError(f"J-Servo mode {name} layer {layer} has invalid {field}")
            if not math.isfinite(float(payload["dose_cap"])) or float(payload["dose_cap"]) <= 0:
                raise ValueError(f"J-Servo mode {name} layer {layer} has invalid dose cap")
    return artifact


def save_jservo_artifact(torch: Any, artifact: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    torch.save(validate_jservo_artifact(artifact), temporary)
    temporary.replace(output)
    return output


def load_jservo_artifact(
    torch: Any,
    path: str | Path,
    *,
    expected_model_id: str | None = None,
    expected_model_revision: str | None = None,
) -> dict[str, Any]:
    resolved = Path(path).expanduser().resolve()
    try:
        artifact = torch.load(resolved, map_location="cpu", weights_only=True)
    except TypeError:
        artifact = torch.load(resolved, map_location="cpu")
    if not isinstance(artifact, dict):
        raise ValueError("J-Servo artifact must be an object")
    return validate_jservo_artifact(
        artifact,
        expected_model_id=expected_model_id,
        expected_model_revision=expected_model_revision,
    )


def _capture_pair(
    runtime: ModelRuntime,
    pair: dict[str, Any],
    *,
    layers: Sequence[int],
    tools: list[dict[str, Any]] | None,
) -> tuple[dict[int, Any], dict[int, Any]]:
    positive, negative = paired_action_inputs(
        runtime,
        context_messages=pair["context_messages"],
        positive_message=pair["positive_repaired_message"],
        negative_message=pair["negative_failed_message"],
        tools=tools,
    )

    def capture(value: tuple[Any, int]) -> dict[int, Any]:
        input_ids, position = value
        with (
            runtime.torch.inference_mode(),
            capture_block_outputs(runtime.lens_model.layers, layers) as activations,
        ):
            runtime.lens_model.forward(input_ids)
        return {
            int(layer): activations[int(layer)][0, int(position)].detach().float().cpu()
            for layer in layers
        }

    return capture(positive), capture(negative)


def extract_failure_jservo(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_categories: Sequence[str],
    observation_layers: Sequence[int],
    control_layers: Sequence[int],
    output_path: str | Path,
    tools: list[dict[str, Any]] | None = None,
    bundle_size: int = 8,
    protected_size: int = 8,
    minimum_consistency: float = 0.7,
    random_seed: int = 42,
    force: bool = False,
) -> dict[str, Any]:
    """Extract a multi-mode J-Servo artifact from validated TauBench repairs."""
    output = Path(output_path).expanduser().resolve()
    if output.is_file() and not force:
        artifact = load_jservo_artifact(
            runtime.torch,
            output,
            expected_model_id=model_id,
            expected_model_revision=model_revision,
        )
        return {
            "path": str(output),
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "modes": sorted(artifact["modes"]),
            "status": "already_complete",
        }
    pair_list = list(pairs)
    category_layers = {
        str(category): mode_layer_policy(
            canonical_failure_mode(str(category)),
            fallback_observation=observation_layers,
            fallback_control=control_layers,
        )
        for category in failure_categories
    }
    layers = tuple(
        dict.fromkeys(
            layer
            for observation, control in category_layers.values()
            for layer in (*observation, *control)
        )
    )
    jacobians = {
        layer: runtime.lens.jacobians[layer].detach().float().cpu() for layer in layers
    }
    unembedding = runtime.hf_model.get_output_embeddings().weight.detach().float().cpu()
    token_texts = [
        str(value)
        for value in runtime.tokenizer.convert_ids_to_tokens(range(int(unembedding.shape[0])))
    ]
    modes = []
    all_train_ids: set[str] = set()
    all_validation_ids: set[str] = set()
    for category in failure_categories:
        mode_observation_layers, mode_control_layers = category_layers[str(category)]
        mode_layers = tuple(
            dict.fromkeys([*mode_observation_layers, *mode_control_layers])
        )
        train, validation = select_failure_pairs(pair_list, str(category))
        correct_behavior = next(
            (str(pair.get("review_correct_behavior")) for pair in train if pair.get("review_correct_behavior")),
            None,
        )
        collections = {
            "train_correct": {layer: [] for layer in mode_layers},
            "train_failure": {layer: [] for layer in mode_layers},
            "validation_correct": {layer: [] for layer in mode_layers},
            "validation_failure": {layer: [] for layer in mode_layers},
        }
        for split, selected in (("train", train), ("validation", validation)):
            for pair in selected:
                correct, failure = _capture_pair(runtime, pair, layers=layers, tools=tools)
                for layer in mode_layers:
                    collections[f"{split}_correct"][layer].append(correct[layer])
                    collections[f"{split}_failure"][layer].append(failure[layer])
        train_ids = [str(pair["pair_id"]) for pair in train]
        validation_ids = [str(pair["pair_id"]) for pair in validation]
        all_train_ids.update(train_ids)
        all_validation_ids.update(validation_ids)
        modes.append(
            build_jservo_mode(
                runtime.torch,
                failure_category=str(category),
                correct_behavior=correct_behavior,
                train_correct_by_layer=collections["train_correct"],
                train_failure_by_layer=collections["train_failure"],
                validation_correct_by_layer=collections["validation_correct"],
                validation_failure_by_layer=collections["validation_failure"],
                jacobians=jacobians,
                unembedding=unembedding,
                token_texts=token_texts,
                observation_layers=mode_observation_layers,
                control_layers=mode_control_layers,
                train_pair_ids=train_ids,
                validation_pair_ids=validation_ids,
                bundle_size=bundle_size,
                protected_size=protected_size,
                minimum_consistency=minimum_consistency,
                random_seed=random_seed,
            )
        )
    if all_train_ids & all_validation_ids:
        raise ValueError("J-Servo categories leak pair IDs across train and validation")
    artifact = build_jservo_artifact(
        model_id=model_id,
        model_revision=model_revision,
        lens_revision=getattr(runtime.lens, "revision", None),
        benchmark="taubench-airline-failure-modes",
        modes=modes,
        calibration={
            "pair_schema": "agent-failure-repair-pair-v1",
            "train_pair_count": len(all_train_ids),
            "validation_pair_count": len(all_validation_ids),
            "future_messages_excluded": True,
            "evaluation_pairs_used": False,
        },
    )
    save_jservo_artifact(runtime.torch, artifact, output)
    return {
        "path": str(output),
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "modes": sorted(artifact["modes"]),
        "steering_eligible_modes": sorted(
            name for name, mode in artifact["modes"].items() if mode["steering_eligible"]
        ),
    }


def _replace_output(original: Any, tensor: Any) -> Any:
    if hasattr(original, "shape"):
        return tensor
    if isinstance(original, tuple):
        return (tensor, *original[1:])
    if isinstance(original, list):
        return [tensor, *original[1:]]
    raise TypeError(f"unsupported transformer block output {type(original).__name__}")


@contextmanager
def jservo_generation_hooks(
    blocks: Any,
    *,
    artifact: dict[str, Any],
    boundaries: Sequence[str],
    control_type: str = "targeted",
    mode_override: str | None = None,
    layer_override: int | None = None,
    fixed_strength: float | None = None,
    apply_prefill_decision: bool = True,
    apply_decode: bool = True,
):
    """Run J-Servo sequentially across observer and controller layers."""
    if control_type not in VALID_CONTROL_TYPES:
        raise ValueError(f"unknown J-Servo control type {control_type!r}")
    validate_jservo_artifact(artifact)
    boundary_set = set(map(str, boundaries))
    candidates = {
        name: mode
        for name, mode in artifact["modes"].items()
        if boundary_set.intersection(mode.get("boundaries") or ())
        and (mode_override is None or name == mode_override or control_type == "wrong_mode")
    }
    if control_type == "wrong_mode" and mode_override is not None:
        candidates = (
            {mode_override: artifact["modes"][mode_override]}
            if mode_override in artifact["modes"]
            else {}
        )
    layers = sorted(
        {
            int(layer)
            for mode in candidates.values()
            for layer in [*mode["observation_layers"], *mode["control_layers"]]
        }
    )
    trace: dict[str, Any] = {
        "schema_version": "jlens-jservo-trace-v1",
        "requested": True,
        "active": False,
        "reason": "no_boundary_matched" if not candidates else "monitoring",
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "control_type": control_type,
        "boundaries": sorted(boundary_set),
        "candidate_modes": sorted(candidates),
        "selected_modes": [],
        "sites": [],
        "applied_positions": 0,
        "cumulative_dose": 0.0,
        "abstain_requested": False,
        "abstain_reasons": [],
        "controller_abstained": not bool(candidates),
    }
    if not layers:
        yield trace
        return

    calls = {layer: 0 for layer in layers}
    selected_by_site: dict[int, str] = {}
    active_layers_by_site: dict[int, int] = {}
    cumulative_by_mode = {name: 0.0 for name in candidates}
    handles = []

    def make_hook(layer: int):
        def hook(_module: Any, _inputs: Any, output: Any) -> Any:
            tensor = output if hasattr(output, "shape") else output[0]
            site = calls[layer]
            calls[layer] += 1
            is_prefill = site == 0
            should_apply = apply_prefill_decision if is_prefill else apply_decode
            current = tensor[:, -1, :]
            observing = [
                (name, mode)
                for name, mode in candidates.items()
                if layer in set(map(int, mode["observation_layers"]))
            ]
            if observing:
                scored = []
                for name, mode in observing:
                    payload = mode["layers"][str(layer)]
                    direction = payload["margin_direction"].to(
                        device=current.device, dtype=current.dtype
                    )
                    margin = float((current[0] @ direction).detach().float().cpu())
                    if control_type == "reverse":
                        deficit = (
                            margin - float(payload.get("reverse_gate_threshold", margin))
                        ) / max(float(payload["margin_scale"]), 1e-6)
                        gate_threshold = float(
                            payload.get("reverse_gate_threshold", payload["gate_threshold"])
                        )
                    else:
                        deficit = (float(payload["gate_threshold"]) - margin) / max(
                            float(payload["margin_scale"]), 1e-6
                        )
                        gate_threshold = float(payload["gate_threshold"])
                    trace["sites"].append(
                        {
                            "site": site,
                            "phase": "prefill" if is_prefill else "decode",
                            "layer": layer,
                            "mode": name,
                            "role": "observe",
                            "margin": margin,
                            "gate_threshold": gate_threshold,
                            "standardized_deficit": deficit,
                            "triggered": bool(deficit > 0 and mode["steering_eligible"]),
                        }
                    )
                    if deficit > 0 and mode["steering_eligible"]:
                        scored.append((deficit, name))
                if scored:
                    selected_by_site[site] = max(scored)[1]

            selected = selected_by_site.get(site)
            if selected is None or selected not in candidates:
                return output
            mode = candidates[selected]
            if layer not in set(map(int, mode["control_layers"])):
                return output
            if layer_override is not None and layer != int(layer_override):
                return output
            if control_type == "fixed_layer" and layer_override is None:
                raise ValueError("fixed_layer control requires layer_override")
            if not should_apply or control_type == "validator_only":
                return output
            if active_layers_by_site.get(site, 0) >= int(mode["max_active_layers_per_position"]):
                return output
            payload = mode["layers"][str(layer)]
            reverse = control_type == "reverse" and "reverse_target_margin" in payload
            result = minimum_state_edit(
                current[0],
                margin_direction=(
                    -payload["margin_direction"] if reverse else payload["margin_direction"]
                ),
                projected_direction=(
                    -payload["projected_direction"]
                    if reverse
                    else payload["projected_direction"]
                ),
                target_margin=float(
                    payload["reverse_target_margin"] if reverse else payload["target_margin"]
                ),
                dose_cap=float(payload["dose_cap"]),
                cumulative_dose=cumulative_by_mode[selected],
                cumulative_cap=float(mode["cumulative_dose_cap"]),
            )
            if control_type == "fixed_strength":
                if fixed_strength is None or not math.isfinite(float(fixed_strength)):
                    raise ValueError("fixed_strength control requires a finite strength")
                direction = _unit(
                    payload["projected_direction"], label="fixed_strength_direction"
                ).to(device=current.device, dtype=current.dtype)
                result["delta"] = float(fixed_strength) * float(payload["residual_scale"]) * direction
                result["dose_norm"] = float(result["delta"].norm().detach().cpu())
                result["feasible"] = result["dose_norm"] <= float(payload["dose_cap"])
                result["reason"] = "selected" if result["feasible"] else "layer_dose_cap_exceeded"
            elif control_type == "reverse" and not reverse:
                result["delta"] = -result["delta"]

            if control_type in {"fixed_strength", "random"} or (
                control_type == "reverse" and not reverse
            ):
                read_direction = (
                    -payload["margin_direction"]
                    if reverse
                    else payload["margin_direction"]
                ).to(device=current.device, dtype=current.dtype)
                result["predicted_post_margin"] = float(
                    result["pre_margin"]
                    + (
                        result["delta"].to(
                            device=current.device, dtype=current.dtype
                        )
                        @ read_direction
                    )
                    .detach()
                    .cpu()
                )
            elif control_type == "random":
                random = _unit(payload["random_direction"], label="random_direction").to(
                    device=current.device, dtype=current.dtype
                )
                result["delta"] = float(result["dose_norm"]) * random

            site_record = {
                key: value
                for key, value in result.items()
                if key != "delta"
            }
            site_record.update(
                {
                    "site": site,
                    "phase": "prefill" if is_prefill else "decode",
                    "layer": layer,
                    "mode": selected,
                    "role": "control",
                    "control_type": control_type,
                }
            )
            trace["sites"].append(site_record)
            if not result["feasible"]:
                trace["abstain_requested"] = True
                trace["abstain_reasons"].append(str(result["reason"]))
                return output
            if float(result["dose_norm"]) <= 0.0:
                return output
            modified = tensor.clone()
            modified[:, -1, :] = current + result["delta"].to(
                device=current.device, dtype=current.dtype
            )
            active_layers_by_site[site] = active_layers_by_site.get(site, 0) + 1
            cumulative_by_mode[selected] += float(result["dose_norm"])
            trace["active"] = True
            trace["reason"] = "selected"
            trace["applied_positions"] += int(modified.shape[0])
            trace["cumulative_dose"] += float(result["dose_norm"])
            if selected not in trace["selected_modes"]:
                trace["selected_modes"].append(selected)
            return _replace_output(output, modified)

        return hook

    try:
        for layer in layers:
            handles.append(blocks[layer].register_forward_hook(make_hook(layer)))
        yield trace
    finally:
        for handle in reversed(handles):
            handle.remove()
        trace["abstain_reasons"] = sorted(set(trace["abstain_reasons"]))
        if not trace["active"]:
            trace["controller_abstained"] = True
            if trace["abstain_requested"]:
                trace["reason"] = "infeasible_edit"
            elif control_type == "validator_only" and selected_by_site:
                trace["reason"] = "validator_only"
            elif selected_by_site:
                trace["reason"] = "target_already_reached"
            elif candidates:
                trace["reason"] = "signal_not_confirmed"
