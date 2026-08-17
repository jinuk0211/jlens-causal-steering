"""Shared artifacts and math for published steering baselines.

The module is deliberately benchmark-agnostic.  ToolAlign and TauBench may
render conversations differently, but they must consume the same versioned
direction artifact and use the same orientation convention.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Sequence
from pathlib import Path
from typing import Any

BASELINE_ARTIFACT_SCHEMA_VERSION = "agent-steering-vector-v1"
CAST_ARTIFACT_SCHEMA_VERSION = "agent-cast-v1"
MERA_ARTIFACT_SCHEMA_VERSION = "agent-mera-v1"
SADI_ARTIFACT_SCHEMA_VERSION = "agent-sadi-v1"
ITI_ARTIFACT_SCHEMA_VERSION = "agent-iti-v1"
AUSTEER_ARTIFACT_SCHEMA_VERSION = "agent-austeer-v1"
LOREFT_ARTIFACT_SCHEMA_VERSION = "agent-loreft-v1"
_TENSOR_FIELDS = {
    "direction",
    "unit_direction",
    "positive_mean",
    "negative_mean",
}


def _as_sample_matrix(torch: Any, values: Sequence[Any] | Any, *, label: str) -> Any:
    """Return a finite ``[examples, d_model]`` float32 CPU tensor."""
    if hasattr(values, "shape"):
        matrix = values.detach().float().cpu()
    else:
        items = [value.detach().float().cpu() for value in values]
        if not items:
            raise ValueError(f"{label} samples cannot be empty")
        matrix = torch.stack(items)
    if matrix.ndim != 2 or matrix.shape[0] == 0 or matrix.shape[1] == 0:
        raise ValueError(f"{label} samples must have shape [examples, d_model]")
    if not bool(torch.isfinite(matrix).all()):
        raise ValueError(f"{label} samples contain non-finite values")
    return matrix


def caa_mean_difference(
    torch: Any,
    *,
    positive: Sequence[Any] | Any,
    negative: Sequence[Any] | Any,
) -> dict[str, Any]:
    """Compute the CAA paired mean direction ``mean(h+ - h-)``.

    This matches the official CAA construction rather than subtracting two
    independently sampled class means.  Pairing is checked explicitly because
    both agent benchmarks have strong prompt- and trajectory-level nuisance
    variation that otherwise leaks into the direction.
    """
    positive_matrix = _as_sample_matrix(torch, positive, label="positive")
    negative_matrix = _as_sample_matrix(torch, negative, label="negative")
    if positive_matrix.shape != negative_matrix.shape:
        raise ValueError(
            "positive and negative CAA samples must have the same shape; "
            f"got {tuple(positive_matrix.shape)} and {tuple(negative_matrix.shape)}"
        )
    paired_deltas = positive_matrix - negative_matrix
    direction = paired_deltas.mean(dim=0)
    norm = torch.linalg.vector_norm(direction)
    if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
        raise ValueError("CAA direction is zero or non-finite")
    return {
        "direction": direction,
        "unit_direction": direction / norm,
        "direction_norm": float(norm),
        "positive_mean": positive_matrix.mean(dim=0),
        "negative_mean": negative_matrix.mean(dim=0),
        "paired_deltas": paired_deltas,
        "pair_count": int(positive_matrix.shape[0]),
        "d_model": int(positive_matrix.shape[1]),
    }


def _tensor_sha256(tensor: Any) -> str:
    value = tensor.detach().contiguous().float().cpu().numpy().tobytes()
    return hashlib.sha256(value).hexdigest()


def _artifact_metadata(artifact: dict[str, Any]) -> dict[str, Any]:
    """Return the JSON-only fields covered by the metadata fingerprint."""
    return {
        key: value
        for key, value in artifact.items()
        if key not in _TENSOR_FIELDS
        and key not in {"metadata_fingerprint", "vector_fingerprint", "direction_norm"}
    }


def _metadata_sha256(metadata: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(metadata, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def build_caa_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    layer: int,
    positive: Sequence[Any] | Any,
    negative: Sequence[Any] | Any,
    pair_ids: Sequence[str],
    positive_label: str,
    negative_label: str,
    extraction_site: str,
    benchmark: str,
    calibration_split: dict[str, Any],
) -> dict[str, Any]:
    """Build a tensor-only, fingerprinted CAA direction artifact."""
    result = caa_mean_difference(torch, positive=positive, negative=negative)
    ids = tuple(str(value) for value in pair_ids)
    if len(ids) != result["pair_count"]:
        raise ValueError(
            f"pair_ids has {len(ids)} entries but activations have {result['pair_count']} pairs"
        )
    if len(set(ids)) != len(ids):
        raise ValueError("pair_ids must be unique")
    metadata = {
        "schema_version": BASELINE_ARTIFACT_SCHEMA_VERSION,
        "method": "caa",
        "orientation": "positive_minus_negative",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layer": int(layer),
        "positive_label": str(positive_label),
        "negative_label": str(negative_label),
        "extraction_site": str(extraction_site),
        "benchmark": str(benchmark),
        "pair_ids": list(ids),
        "pair_count": result["pair_count"],
        "d_model": result["d_model"],
        "calibration_split": calibration_split,
    }
    metadata_fingerprint = _metadata_sha256(metadata)
    artifact = {
        **metadata,
        "metadata_fingerprint": metadata_fingerprint,
        "vector_fingerprint": _tensor_sha256(result["direction"]),
        "direction": result["direction"],
        "unit_direction": result["unit_direction"],
        "direction_norm": result["direction_norm"],
        "positive_mean": result["positive_mean"],
        "negative_mean": result["negative_mean"],
    }
    return artifact


def validate_caa_artifact(
    artifact: dict[str, Any],
    *,
    expected_model_id: str | None = None,
    expected_layer: int | None = None,
) -> dict[str, Any]:
    """Reject stale, malformed, or silently cross-model CAA artifacts."""
    import torch

    if artifact.get("schema_version") != BASELINE_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported baseline direction artifact schema")
    if artifact.get("method") != "caa":
        raise ValueError("direction artifact is not CAA")
    if artifact.get("orientation") != "positive_minus_negative":
        raise ValueError("CAA artifact has an unknown direction orientation")
    if _metadata_sha256(_artifact_metadata(artifact)) != artifact.get("metadata_fingerprint"):
        raise ValueError("CAA artifact metadata fingerprint mismatch")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError(
            f"CAA artifact model {artifact.get('model_id')!r} does not match {expected_model_id!r}"
        )
    if expected_layer is not None and int(artifact.get("layer", -1)) != int(expected_layer):
        raise ValueError(
            f"CAA artifact layer {artifact.get('layer')!r} does not match {expected_layer}"
        )
    direction = artifact.get("direction")
    unit = artifact.get("unit_direction")
    if direction is None or unit is None or direction.ndim != 1 or unit.shape != direction.shape:
        raise ValueError("CAA artifact vectors are missing or malformed")
    if int(artifact.get("d_model", -1)) != int(direction.numel()):
        raise ValueError("CAA artifact d_model does not match its direction")
    if not bool(torch.isfinite(direction).all()) or not bool(torch.isfinite(unit).all()):
        raise ValueError("CAA artifact vectors contain non-finite values")
    norm = torch.linalg.vector_norm(direction.float())
    if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
        raise ValueError("CAA artifact direction has zero or non-finite norm")
    if abs(float(artifact.get("direction_norm", -1.0)) - float(norm)) > max(
        1e-6, float(norm) * 1e-5
    ):
        raise ValueError("CAA artifact direction_norm is inconsistent")
    if not torch.allclose(unit.float(), direction.float() / norm, rtol=1e-5, atol=1e-6):
        raise ValueError("CAA artifact unit_direction is inconsistent")
    if _tensor_sha256(direction) != artifact.get("vector_fingerprint"):
        raise ValueError("CAA direction fingerprint mismatch")
    return artifact


def save_caa_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    """Validate and atomically replace one owned CAA artifact file."""
    validate_caa_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_caa_artifact(
    torch: Any,
    path: Path,
    *,
    expected_model_id: str | None = None,
    expected_layer: int | None = None,
) -> dict[str, Any]:
    """Load a tensor-only CAA artifact without permitting arbitrary pickle code."""
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("CAA artifact must be a dictionary")
    return validate_caa_artifact(
        artifact,
        expected_model_id=expected_model_id,
        expected_layer=expected_layer,
    )


def caa_vector(artifact: dict[str, Any], *, scaling: str = "raw") -> Any:
    """Select the preregistered raw or unit CAA vector."""
    validate_caa_artifact(artifact)
    if scaling == "raw":
        return artifact["direction"]
    if scaling == "unit":
        return artifact["unit_direction"]
    raise ValueError("CAA scaling must be 'raw' or 'unit'")


def cast_pca_pairwise(
    torch: Any,
    *,
    positive: Sequence[Any] | Any,
    negative: Sequence[Any] | Any,
) -> dict[str, Any]:
    """Reproduce CAST's oriented one-component pairwise-centered PCA."""
    positive_matrix = _as_sample_matrix(torch, positive, label="positive")
    negative_matrix = _as_sample_matrix(torch, negative, label="negative")
    if positive_matrix.shape != negative_matrix.shape:
        raise ValueError(
            "positive and negative CAST samples must have the same shape; "
            f"got {tuple(positive_matrix.shape)} and {tuple(negative_matrix.shape)}"
        )
    centers = (positive_matrix + negative_matrix) / 2
    train = torch.cat(
        (positive_matrix - centers, negative_matrix - centers),
        dim=0,
    )
    _u, singular_values, vh = torch.linalg.svd(train, full_matrices=False)
    direction = vh[0].detach().float().cpu()
    positive_projection = positive_matrix @ direction
    negative_projection = negative_matrix @ direction
    if float((positive_projection > negative_projection).float().mean()) < 0.5:
        direction = -direction
        positive_projection = -positive_projection
        negative_projection = -negative_projection
    norm = torch.linalg.vector_norm(direction)
    if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
        raise ValueError("CAST PCA direction is zero or non-finite")
    direction = direction / norm
    variance = singular_values.square()
    variance_total = variance.sum()
    explained = (
        float(variance[0] / variance_total)
        if bool(torch.isfinite(variance_total)) and float(variance_total) > 0
        else 0.0
    )
    return {
        "direction": direction,
        "explained_variance_ratio": explained,
        "pair_count": int(positive_matrix.shape[0]),
        "d_model": int(positive_matrix.shape[1]),
        "positive_projection_mean": float(positive_projection.mean()),
        "negative_projection_mean": float(negative_projection.mean()),
    }


def cast_condition_similarity(
    torch: Any,
    hidden_states: Any,
    direction: Any,
    *,
    comparison_mode: str = "mean",
) -> Any:
    """Compute the official CAST cosine to ``tanh(P_condition h)``."""
    hidden = hidden_states.float()
    if hidden.ndim == 2:
        if comparison_mode == "mean":
            hidden = hidden.mean(dim=0)
        elif comparison_mode == "last":
            hidden = hidden[-1]
        else:
            raise ValueError("CAST comparison_mode must be 'mean' or 'last'")
    if hidden.ndim != 1:
        raise ValueError("CAST condition hidden state must have shape [tokens, d] or [d]")
    vector = direction.to(hidden.device, dtype=hidden.dtype)
    denominator = torch.dot(vector, vector)
    if not bool(torch.isfinite(denominator)) or float(denominator) == 0.0:
        raise ValueError("CAST condition direction is zero or non-finite")
    projected = torch.tanh(vector * (torch.dot(vector, hidden) / denominator))
    hidden_norm = torch.linalg.vector_norm(hidden)
    projected_norm = torch.linalg.vector_norm(projected)
    if (
        not bool(torch.isfinite(hidden_norm))
        or not bool(torch.isfinite(projected_norm))
        or float(hidden_norm) == 0.0
        or float(projected_norm) == 0.0
    ):
        raise ValueError("CAST condition similarity has a zero or non-finite norm")
    return torch.dot(hidden, projected) / (hidden_norm * projected_norm)


def _binary_metrics(predictions: list[bool], labels: list[bool]) -> dict[str, float]:
    tp = sum(prediction and label for prediction, label in zip(predictions, labels, strict=True))
    fp = sum(prediction and not label for prediction, label in zip(predictions, labels, strict=True))
    tn = sum(
        not prediction and not label
        for prediction, label in zip(predictions, labels, strict=True)
    )
    fn = sum(
        not prediction and label
        for prediction, label in zip(predictions, labels, strict=True)
    )
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "f1": f1,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "balanced_accuracy": (recall + specificity) / 2,
        "accuracy": (tp + tn) / len(labels),
    }


def select_cast_gate(
    *,
    positive_scores: dict[int, Sequence[float]],
    negative_scores: dict[int, Sequence[float]],
) -> dict[str, Any]:
    """Select layer, threshold, and direction by calibration F1."""
    if set(positive_scores) != set(negative_scores) or not positive_scores:
        raise ValueError("CAST positive/negative score layers must match and be non-empty")
    candidates: list[dict[str, Any]] = []
    for layer in sorted(positive_scores):
        positives = [float(value) for value in positive_scores[layer]]
        negatives = [float(value) for value in negative_scores[layer]]
        if not positives or not negatives:
            raise ValueError("CAST calibration score lists cannot be empty")
        values = sorted(set(positives + negatives))
        epsilon = max(1e-9, (values[-1] - values[0]) * 1e-9)
        thresholds = [values[0] - epsilon]
        thresholds.extend(
            (left + right) / 2 for left, right in zip(values, values[1:], strict=False)
        )
        thresholds.append(values[-1] + epsilon)
        labels = [True] * len(positives) + [False] * len(negatives)
        scores = positives + negatives
        for comparator in ("greater", "less"):
            for threshold in thresholds:
                if comparator == "greater":
                    predictions = [score > threshold for score in scores]
                else:
                    predictions = [score < threshold for score in scores]
                metrics = _binary_metrics(predictions, labels)
                candidates.append(
                    {
                        "condition_layer": int(layer),
                        "threshold": float(threshold),
                        "comparator": comparator,
                        **metrics,
                    }
                )
    return max(
        candidates,
        key=lambda item: (
            item["f1"],
            item["balanced_accuracy"],
            item["accuracy"],
            -item["condition_layer"],
            item["comparator"] == "greater",
            -abs(item["threshold"]),
        ),
    )


def build_cast_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    behavior_layer: int,
    condition_layer: int,
    behavior_positive: Sequence[Any] | Any,
    behavior_negative: Sequence[Any] | Any,
    condition_positive: Sequence[Any] | Any,
    condition_negative: Sequence[Any] | Any,
    behavior_pair_ids: Sequence[str],
    condition_pair_ids: Sequence[str],
    gate_positive_ids: Sequence[str],
    gate_negative_ids: Sequence[str],
    gate_positive_scores: Sequence[float],
    gate_negative_scores: Sequence[float],
    gate: dict[str, Any],
    comparison_mode: str,
    benchmark: str,
    calibration_split: dict[str, Any],
    sites: dict[str, str],
    source: dict[str, str],
) -> dict[str, Any]:
    """Build a fingerprinted CAST behavior-vector plus condition-gate artifact."""
    behavior = cast_pca_pairwise(
        torch,
        positive=behavior_positive,
        negative=behavior_negative,
    )
    condition = cast_pca_pairwise(
        torch,
        positive=condition_positive,
        negative=condition_negative,
    )
    behavior_ids = [str(value) for value in behavior_pair_ids]
    condition_ids = [str(value) for value in condition_pair_ids]
    positive_gate_ids = [str(value) for value in gate_positive_ids]
    negative_gate_ids = [str(value) for value in gate_negative_ids]
    positive_gate_scores = [float(value) for value in gate_positive_scores]
    negative_gate_scores = [float(value) for value in gate_negative_scores]
    if len(behavior_ids) != behavior["pair_count"] or len(set(behavior_ids)) != len(
        behavior_ids
    ):
        raise ValueError("CAST behavior_pair_ids must be unique and match the samples")
    if len(condition_ids) != condition["pair_count"] or len(set(condition_ids)) != len(
        condition_ids
    ):
        raise ValueError("CAST condition_pair_ids must be unique and match the samples")
    if (
        not positive_gate_ids
        or not negative_gate_ids
        or len(positive_gate_ids) != len(positive_gate_scores)
        or len(negative_gate_ids) != len(negative_gate_scores)
        or len(set(positive_gate_ids + negative_gate_ids))
        != len(positive_gate_ids) + len(negative_gate_ids)
    ):
        raise ValueError("CAST gate IDs must be unique, non-empty, and match gate scores")
    if int(gate["condition_layer"]) != int(condition_layer):
        raise ValueError("CAST gate layer does not match the condition vector layer")
    if gate["comparator"] not in {"greater", "less"}:
        raise ValueError("CAST gate comparator must be greater or less")
    if comparison_mode not in {"mean", "last"}:
        raise ValueError("CAST comparison_mode must be mean or last")
    gate_predictions = [
        score > float(gate["threshold"])
        if gate["comparator"] == "greater"
        else score < float(gate["threshold"])
        for score in positive_gate_scores + negative_gate_scores
    ]
    gate_metrics = _binary_metrics(
        gate_predictions,
        [True] * len(positive_gate_scores) + [False] * len(negative_gate_scores),
    )
    for key, value in gate_metrics.items():
        if abs(float(gate[key]) - value) > 1e-9:
            raise ValueError(f"CAST gate metric {key} does not match supplied scores")
    metadata = {
        "schema_version": CAST_ARTIFACT_SCHEMA_VERSION,
        "method": "cast",
        "pca_method": "pca_pairwise",
        "orientation": "positive_over_negative_pair_majority",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "behavior_layer": int(behavior_layer),
        "condition_layer": int(condition_layer),
        "condition_threshold": float(gate["threshold"]),
        "condition_comparator": str(gate["comparator"]),
        "condition_comparison_mode": comparison_mode,
        "gate_metrics": gate_metrics,
        "gate_positive_ids": positive_gate_ids,
        "gate_negative_ids": negative_gate_ids,
        "gate_positive_scores": positive_gate_scores,
        "gate_negative_scores": negative_gate_scores,
        "threshold_search": "exact_observed_midpoints",
        "behavior_pair_ids": behavior_ids,
        "condition_pair_ids": condition_ids,
        "behavior_pair_count": behavior["pair_count"],
        "condition_pair_count": condition["pair_count"],
        "d_model": behavior["d_model"],
        "benchmark": str(benchmark),
        "calibration_split": calibration_split,
        "sites": {str(key): str(value) for key, value in sites.items()},
        "source": {str(key): str(value) for key, value in source.items()},
        "behavior_explained_variance_ratio": behavior["explained_variance_ratio"],
        "condition_explained_variance_ratio": condition["explained_variance_ratio"],
    }
    if behavior["d_model"] != condition["d_model"]:
        raise ValueError("CAST behavior and condition vectors have different widths")
    artifact = {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        "behavior_vector_fingerprint": _tensor_sha256(behavior["direction"]),
        "condition_vector_fingerprint": _tensor_sha256(condition["direction"]),
        "behavior_direction": behavior["direction"],
        "condition_direction": condition["direction"],
    }
    return artifact


def validate_cast_artifact(
    artifact: dict[str, Any],
    *,
    expected_model_id: str | None = None,
    expected_behavior_layer: int | None = None,
) -> dict[str, Any]:
    """Validate a shared CAST artifact and both tensor fingerprints."""
    import torch

    if artifact.get("schema_version") != CAST_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported CAST artifact schema")
    if artifact.get("method") != "cast":
        raise ValueError("artifact is not CAST")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("CAST artifact model does not match the loaded model")
    if expected_behavior_layer is not None and int(
        artifact.get("behavior_layer", -1)
    ) != int(expected_behavior_layer):
        raise ValueError("CAST artifact behavior layer does not match")
    behavior = artifact.get("behavior_direction")
    condition = artifact.get("condition_direction")
    if (
        behavior is None
        or condition is None
        or behavior.ndim != 1
        or condition.shape != behavior.shape
    ):
        raise ValueError("CAST artifact vectors are missing or malformed")
    if int(artifact.get("d_model", -1)) != int(behavior.numel()):
        raise ValueError("CAST artifact d_model does not match its vectors")
    if not bool(torch.isfinite(behavior).all()) or not bool(torch.isfinite(condition).all()):
        raise ValueError("CAST artifact vectors contain non-finite values")
    if abs(float(behavior.float().norm()) - 1.0) > 1e-5:
        raise ValueError("CAST behavior direction is not unit norm")
    if abs(float(condition.float().norm()) - 1.0) > 1e-5:
        raise ValueError("CAST condition direction is not unit norm")
    positive_ids = artifact.get("gate_positive_ids", [])
    negative_ids = artifact.get("gate_negative_ids", [])
    positive_scores = artifact.get("gate_positive_scores", [])
    negative_scores = artifact.get("gate_negative_scores", [])
    if (
        not positive_ids
        or not negative_ids
        or len(positive_ids) != len(positive_scores)
        or len(negative_ids) != len(negative_scores)
        or len(set(positive_ids + negative_ids)) != len(positive_ids) + len(negative_ids)
    ):
        raise ValueError("CAST artifact gate calibration records are malformed")
    threshold = float(artifact.get("condition_threshold"))
    comparator = artifact.get("condition_comparator")
    predictions = [
        float(score) > threshold if comparator == "greater" else float(score) < threshold
        for score in positive_scores + negative_scores
    ]
    metrics = _binary_metrics(
        predictions,
        [True] * len(positive_scores) + [False] * len(negative_scores),
    )
    if any(
        abs(float(artifact.get("gate_metrics", {}).get(key, -1.0)) - value) > 1e-9
        for key, value in metrics.items()
    ):
        raise ValueError("CAST artifact gate metrics do not match calibration scores")
    metadata = {
        key: value
        for key, value in artifact.items()
        if key
        not in {
            "metadata_fingerprint",
            "behavior_vector_fingerprint",
            "condition_vector_fingerprint",
            "behavior_direction",
            "condition_direction",
        }
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("CAST artifact metadata fingerprint mismatch")
    if _tensor_sha256(behavior) != artifact.get("behavior_vector_fingerprint"):
        raise ValueError("CAST behavior vector fingerprint mismatch")
    if _tensor_sha256(condition) != artifact.get("condition_vector_fingerprint"):
        raise ValueError("CAST condition vector fingerprint mismatch")
    if artifact.get("condition_comparator") not in {"greater", "less"}:
        raise ValueError("CAST artifact comparator is invalid")
    if artifact.get("condition_comparison_mode") not in {"mean", "last"}:
        raise ValueError("CAST artifact comparison mode is invalid")
    return artifact


def save_cast_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_cast_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_cast_artifact(
    torch: Any,
    path: Path,
    *,
    expected_model_id: str | None = None,
    expected_behavior_layer: int | None = None,
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("CAST artifact must be a dictionary")
    return validate_cast_artifact(
        artifact,
        expected_model_id=expected_model_id,
        expected_behavior_layer=expected_behavior_layer,
    )


def fit_mera_error_probe(
    torch: Any,
    *,
    correct: Sequence[Any] | Any,
    failure: Sequence[Any] | Any,
    target_epsilon: float = 1e-8,
) -> dict[str, Any]:
    """Fit MERA's no-intercept linear error probe in log-odds space."""
    correct_matrix = _as_sample_matrix(torch, correct, label="correct")
    failure_matrix = _as_sample_matrix(torch, failure, label="failure")
    if correct_matrix.shape != failure_matrix.shape:
        raise ValueError("MERA correct/failure samples must have the same paired shape")
    if not 0.0 < float(target_epsilon) < 0.5:
        raise ValueError("MERA target_epsilon must be between zero and one half")
    features = torch.cat((correct_matrix, failure_matrix), dim=0).double()
    probabilities = torch.cat(
        (
            torch.full(
                (correct_matrix.shape[0],), float(target_epsilon), dtype=torch.float64
            ),
            torch.full(
                (failure_matrix.shape[0],),
                1.0 - float(target_epsilon),
                dtype=torch.float64,
            ),
        )
    )
    targets = torch.logit(probabilities)
    vector = (torch.linalg.pinv(features) @ targets).float()
    residual = features @ vector.double() - targets
    norm = vector.norm()
    if not bool(torch.isfinite(vector).all()) or float(norm) == 0.0:
        raise ValueError("MERA probe is zero or non-finite")
    return {
        "probe_vector": vector.detach().float().cpu(),
        "probe_norm": float(norm),
        "training_rmse_logit": float(residual.square().mean().sqrt()),
        "pair_count": int(correct_matrix.shape[0]),
        "d_model": int(correct_matrix.shape[1]),
        "target_epsilon": float(target_epsilon),
    }


def mera_error_probabilities(torch: Any, hidden_states: Any, probe_vector: Any) -> Any:
    """Return the sigmoid-transformed error estimate used by MERA."""
    hidden = hidden_states.float()
    vector = probe_vector.to(hidden.device, dtype=hidden.dtype)
    if hidden.shape[-1] != vector.numel():
        raise ValueError("MERA hidden width does not match its probe")
    return torch.sigmoid(hidden @ vector)


def select_mera_alpha(
    *,
    correct_scores: Sequence[float],
    failure_scores: Sequence[float],
    alpha_grid: Sequence[float],
) -> dict[str, Any]:
    """Select MERA's abstention threshold by held-out failure-detection F1."""
    correct = [float(value) for value in correct_scores]
    failure = [float(value) for value in failure_scores]
    alphas = sorted(set(float(value) for value in alpha_grid))
    if not correct or not failure:
        raise ValueError("MERA validation scores cannot be empty")
    if not alphas or any(not 0.0 < value <= 1.0 for value in alphas):
        raise ValueError("MERA alpha grid values must be in (0, 1]")
    labels = [False] * len(correct) + [True] * len(failure)
    scores = correct + failure
    candidates = []
    for alpha in alphas:
        metrics = _binary_metrics([score > alpha for score in scores], labels)
        candidates.append({"alpha": alpha, **metrics})
    return max(
        candidates,
        key=lambda item: (
            item["f1"],
            item["balanced_accuracy"],
            item["accuracy"],
            item["alpha"],
        ),
    )


def mera_closed_form_delta(
    torch: Any,
    hidden_states: Any,
    probe_vector: Any,
    *,
    alpha: float,
) -> tuple[Any, Any, Any]:
    """Return MERA's exact per-position theta, condition, and error score."""
    if not 0.0 < float(alpha) <= 1.0:
        raise ValueError("MERA alpha must be in (0, 1]")
    hidden = hidden_states.float()
    vector = probe_vector.to(hidden.device, dtype=hidden.dtype)
    scores = torch.sigmoid(hidden @ vector)
    if float(alpha) == 1.0:
        condition = torch.zeros_like(scores, dtype=torch.bool)
        return torch.zeros_like(hidden), condition, scores
    threshold = torch.logit(
        torch.tensor(float(alpha), dtype=hidden.dtype, device=hidden.device)
    )
    logits = hidden @ vector
    condition = scores > float(alpha)
    theta = ((threshold - logits) / (vector.square().sum() + 1e-8)).unsqueeze(
        -1
    ) * vector
    delta = torch.where(condition.unsqueeze(-1), theta, torch.zeros_like(theta))
    return delta.to(dtype=hidden_states.dtype), condition, scores


def build_mera_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    layer: int,
    train_correct: Sequence[Any] | Any,
    train_failure: Sequence[Any] | Any,
    validation_correct: Sequence[Any] | Any,
    validation_failure: Sequence[Any] | Any,
    train_pair_ids: Sequence[str],
    validation_correct_ids: Sequence[str],
    validation_failure_ids: Sequence[str],
    alpha_grid: Sequence[float],
    benchmark: str,
    calibration_split: dict[str, Any],
    site: str,
    source: dict[str, str],
    target_epsilon: float = 1e-8,
) -> dict[str, Any]:
    """Build a calibrated, fingerprinted MERA error-probe artifact."""
    probe = fit_mera_error_probe(
        torch,
        correct=train_correct,
        failure=train_failure,
        target_epsilon=target_epsilon,
    )
    train_ids = [str(value) for value in train_pair_ids]
    correct_ids = [str(value) for value in validation_correct_ids]
    failure_ids = [str(value) for value in validation_failure_ids]
    validation_correct_matrix = _as_sample_matrix(
        torch, validation_correct, label="validation_correct"
    )
    validation_failure_matrix = _as_sample_matrix(
        torch, validation_failure, label="validation_failure"
    )
    if len(train_ids) != probe["pair_count"] or len(set(train_ids)) != len(train_ids):
        raise ValueError("MERA train_pair_ids must be unique and match training pairs")
    if (
        len(correct_ids) != validation_correct_matrix.shape[0]
        or len(failure_ids) != validation_failure_matrix.shape[0]
        or len(set(correct_ids + failure_ids)) != len(correct_ids) + len(failure_ids)
    ):
        raise ValueError("MERA validation IDs must be unique and match validation samples")
    if (
        validation_correct_matrix.shape[1] != probe["d_model"]
        or validation_failure_matrix.shape[1] != probe["d_model"]
    ):
        raise ValueError("MERA validation samples have the wrong hidden width")
    vector = probe["probe_vector"]
    correct_scores = [
        float(value)
        for value in mera_error_probabilities(torch, validation_correct_matrix, vector)
    ]
    failure_scores = [
        float(value)
        for value in mera_error_probabilities(torch, validation_failure_matrix, vector)
    ]
    selection = select_mera_alpha(
        correct_scores=correct_scores,
        failure_scores=failure_scores,
        alpha_grid=alpha_grid,
    )
    metadata = {
        "schema_version": MERA_ARTIFACT_SCHEMA_VERSION,
        "method": "mera",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layer": int(layer),
        "d_model": probe["d_model"],
        "probe_fit": "linear_regression_no_intercept_logit_error",
        "target_epsilon": probe["target_epsilon"],
        "training_rmse_logit": probe["training_rmse_logit"],
        "train_pair_ids": train_ids,
        "train_pair_count": probe["pair_count"],
        "validation_correct_ids": correct_ids,
        "validation_failure_ids": failure_ids,
        "validation_correct_scores": correct_scores,
        "validation_failure_scores": failure_scores,
        "alpha_grid": sorted(set(float(value) for value in alpha_grid)),
        "selected_alpha": float(selection["alpha"]),
        "selection_metrics": {
            key: float(selection[key])
            for key in (
                "f1",
                "precision",
                "recall",
                "specificity",
                "balanced_accuracy",
                "accuracy",
            )
        },
        "selection_objective": "heldout_failure_detection_f1",
        "benchmark": str(benchmark),
        "calibration_split": calibration_split,
        "site": str(site),
        "source": {str(key): str(value) for key, value in source.items()},
    }
    return {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        "probe_vector_fingerprint": _tensor_sha256(vector),
        "probe_vector": vector,
    }


def validate_mera_artifact(
    artifact: dict[str, Any],
    *,
    expected_model_id: str | None = None,
    expected_layer: int | None = None,
) -> dict[str, Any]:
    """Validate a calibrated MERA artifact and its held-out evidence."""
    import torch

    if artifact.get("schema_version") != MERA_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported MERA artifact schema")
    if artifact.get("method") != "mera":
        raise ValueError("artifact is not MERA")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("MERA artifact model does not match")
    if expected_layer is not None and int(artifact.get("layer", -1)) != int(expected_layer):
        raise ValueError("MERA artifact layer does not match")
    vector = artifact.get("probe_vector")
    if vector is None or vector.ndim != 1 or int(vector.numel()) != int(
        artifact.get("d_model", -1)
    ):
        raise ValueError("MERA probe vector is missing or malformed")
    if not bool(torch.isfinite(vector).all()) or float(vector.float().norm()) == 0.0:
        raise ValueError("MERA probe vector is zero or non-finite")
    metadata = {
        key: value
        for key, value in artifact.items()
        if key not in {"metadata_fingerprint", "probe_vector_fingerprint", "probe_vector"}
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("MERA artifact metadata fingerprint mismatch")
    if _tensor_sha256(vector) != artifact.get("probe_vector_fingerprint"):
        raise ValueError("MERA probe vector fingerprint mismatch")
    selection = select_mera_alpha(
        correct_scores=artifact.get("validation_correct_scores", []),
        failure_scores=artifact.get("validation_failure_scores", []),
        alpha_grid=artifact.get("alpha_grid", []),
    )
    if abs(float(selection["alpha"]) - float(artifact.get("selected_alpha", -1.0))) > 1e-12:
        raise ValueError("MERA selected alpha is inconsistent")
    if any(
        abs(float(artifact.get("selection_metrics", {}).get(key, -1.0)) - selection[key])
        > 1e-9
        for key in (
            "f1",
            "precision",
            "recall",
            "specificity",
            "balanced_accuracy",
            "accuracy",
        )
    ):
        raise ValueError("MERA selection metrics are inconsistent")
    return artifact


def save_mera_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_mera_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_mera_artifact(
    torch: Any,
    path: Path,
    *,
    expected_model_id: str | None = None,
    expected_layer: int | None = None,
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("MERA artifact must be a dictionary")
    return validate_mera_artifact(
        artifact,
        expected_model_id=expected_model_id,
        expected_layer=expected_layer,
    )


def build_sadi_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    correct_by_layer: dict[int, Sequence[Any] | Any],
    failure_by_layer: dict[int, Sequence[Any] | Any],
    pair_ids: Sequence[str],
    top_k: int,
    benchmark: str,
    calibration_split: dict[str, Any],
    site: str,
    source: dict[str, str],
    validation_correct_by_layer: dict[int, Sequence[Any] | Any] | None = None,
    validation_failure_by_layer: dict[int, Sequence[Any] | Any] | None = None,
    validation_pair_ids: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Select SADI's globally strongest positive hidden-output units."""
    layers = sorted(int(value) for value in correct_by_layer)
    if layers != sorted(int(value) for value in failure_by_layer) or not layers:
        raise ValueError("SADI correct/failure layers must match and be non-empty")
    correct_matrices = {
        layer: _as_sample_matrix(torch, correct_by_layer[layer], label=f"correct_l{layer}")
        for layer in layers
    }
    failure_matrices = {
        layer: _as_sample_matrix(torch, failure_by_layer[layer], label=f"failure_l{layer}")
        for layer in layers
    }
    shapes = {tuple(value.shape) for value in correct_matrices.values()}
    shapes.update(tuple(value.shape) for value in failure_matrices.values())
    if len(shapes) != 1:
        raise ValueError("SADI layer activation matrices must all share one shape")
    pair_count, d_model = next(iter(shapes))
    ids = [str(value) for value in pair_ids]
    if len(ids) != pair_count or len(set(ids)) != len(ids):
        raise ValueError("SADI pair_ids must be unique and match activation pairs")
    if int(top_k) <= 0 or int(top_k) > len(layers) * d_model:
        raise ValueError("SADI top_k is outside the available unit count")
    differences = torch.stack(
        [
            (correct_matrices[layer] - failure_matrices[layer]).mean(dim=0)
            for layer in layers
        ]
    )
    values, flat_indices = torch.topk(differences.flatten(), k=int(top_k))
    layer_offsets = flat_indices // d_model
    dimensions = flat_indices % d_model
    selected_units = torch.stack(
        (
            torch.tensor([layers[int(offset)] for offset in layer_offsets]),
            dimensions.cpu(),
        ),
        dim=1,
    ).to(dtype=torch.int64)
    validation_scores = None
    validation_ids: list[str] = []
    validation_pair_count = 0
    validation_inputs = (
        validation_correct_by_layer,
        validation_failure_by_layer,
        validation_pair_ids,
    )
    if any(value is not None for value in validation_inputs):
        if any(value is None for value in validation_inputs):
            raise ValueError("SADI validation activations and IDs must be supplied together")
        assert validation_correct_by_layer is not None
        assert validation_failure_by_layer is not None
        assert validation_pair_ids is not None
        if sorted(int(value) for value in validation_correct_by_layer) != layers or sorted(
            int(value) for value in validation_failure_by_layer
        ) != layers:
            raise ValueError("SADI validation layers must match training layers")
        validation_correct = {
            layer: _as_sample_matrix(
                torch,
                validation_correct_by_layer[layer],
                label=f"validation_correct_l{layer}",
            )
            for layer in layers
        }
        validation_failure = {
            layer: _as_sample_matrix(
                torch,
                validation_failure_by_layer[layer],
                label=f"validation_failure_l{layer}",
            )
            for layer in layers
        }
        validation_shapes = {tuple(value.shape) for value in validation_correct.values()}
        validation_shapes.update(tuple(value.shape) for value in validation_failure.values())
        if len(validation_shapes) != 1:
            raise ValueError("SADI validation activation matrices must share one shape")
        validation_pair_count, validation_width = next(iter(validation_shapes))
        if validation_width != d_model:
            raise ValueError("SADI validation width must match training width")
        validation_ids = [str(value) for value in validation_pair_ids]
        if len(validation_ids) != validation_pair_count or len(set(validation_ids)) != len(
            validation_ids
        ):
            raise ValueError("SADI validation IDs must be unique and match validation pairs")
        validation_differences = torch.stack(
            [
                (validation_correct[layer] - validation_failure[layer]).mean(dim=0)
                for layer in layers
            ]
        )
        validation_scores = validation_differences[layer_offsets, dimensions].detach().float().cpu()
    metadata = {
        "schema_version": SADI_ARTIFACT_SCHEMA_VERSION,
        "method": "sadi_hidden",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layers": layers,
        "d_model": int(d_model),
        "pair_ids": ids,
        "pair_count": int(pair_count),
        "top_k": int(top_k),
        "selection": "global_top_positive_mean_correct_minus_failure",
        "positive_selected_count": int((values > 0).sum()),
        "validation_pair_ids": validation_ids,
        "validation_pair_count": int(validation_pair_count),
        "validation_positive_selected_count": (
            int((validation_scores > 0).sum()) if validation_scores is not None else None
        ),
        "benchmark": str(benchmark),
        "calibration_split": calibration_split,
        "site": str(site),
        "source": {str(key): str(value) for key, value in source.items()},
    }
    result = {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        "selected_units_fingerprint": _tensor_sha256(selected_units),
        "unit_scores_fingerprint": _tensor_sha256(values),
        "selected_units": selected_units,
        "unit_scores": values.detach().float().cpu(),
    }
    if validation_scores is not None:
        result["validation_unit_scores_fingerprint"] = _tensor_sha256(validation_scores)
        result["validation_unit_scores"] = validation_scores
    return result


def validate_sadi_artifact(
    artifact: dict[str, Any],
    *,
    expected_model_id: str | None = None,
) -> dict[str, Any]:
    """Validate a shared SADI hidden-unit selection artifact."""
    import torch

    if artifact.get("schema_version") != SADI_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported SADI artifact schema")
    if artifact.get("method") != "sadi_hidden":
        raise ValueError("artifact is not SADI hidden-unit steering")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("SADI artifact model does not match")
    units = artifact.get("selected_units")
    scores = artifact.get("unit_scores")
    validation_scores = artifact.get("validation_unit_scores")
    if (
        units is None
        or scores is None
        or units.ndim != 2
        or units.shape[1] != 2
        or scores.ndim != 1
        or units.shape[0] != scores.shape[0]
        or int(units.shape[0]) != int(artifact.get("top_k", -1))
    ):
        raise ValueError("SADI selected units are missing or malformed")
    if units.dtype != torch.int64 or not bool(torch.isfinite(scores).all()):
        raise ValueError("SADI selected unit tensors have invalid dtype or values")
    if validation_scores is not None and (
        validation_scores.ndim != 1
        or validation_scores.shape != scores.shape
        or not bool(torch.isfinite(validation_scores).all())
    ):
        raise ValueError("SADI validation unit scores are malformed")
    if bool(artifact.get("validation_pair_count", 0)) != bool(validation_scores is not None):
        raise ValueError("SADI validation evidence is incomplete")
    layers = {int(value) for value in artifact.get("layers", [])}
    d_model = int(artifact.get("d_model", -1))
    pairs = [(int(layer), int(dimension)) for layer, dimension in units.tolist()]
    if (
        len(set(pairs)) != len(pairs)
        or any(layer not in layers or not 0 <= dimension < d_model for layer, dimension in pairs)
    ):
        raise ValueError("SADI selected unit indices are invalid")
    metadata = {
        key: value
        for key, value in artifact.items()
        if key
        not in {
            "metadata_fingerprint",
            "selected_units_fingerprint",
            "unit_scores_fingerprint",
            "validation_unit_scores_fingerprint",
            "selected_units",
            "unit_scores",
            "validation_unit_scores",
        }
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("SADI artifact metadata fingerprint mismatch")
    if _tensor_sha256(units) != artifact.get("selected_units_fingerprint"):
        raise ValueError("SADI selected unit fingerprint mismatch")
    if _tensor_sha256(scores) != artifact.get("unit_scores_fingerprint"):
        raise ValueError("SADI unit score fingerprint mismatch")
    if validation_scores is not None and _tensor_sha256(validation_scores) != artifact.get(
        "validation_unit_scores_fingerprint"
    ):
        raise ValueError("SADI validation unit score fingerprint mismatch")
    return artifact


def sadi_units_by_layer(
    artifact: dict[str, Any], *, top_k: int | None = None
) -> dict[int, tuple[int, ...]]:
    validate_sadi_artifact(artifact)
    count = int(artifact["top_k"]) if top_k is None else int(top_k)
    if count <= 0 or count > int(artifact["top_k"]):
        raise ValueError("SADI requested top_k is outside the selected artifact")
    grouped: dict[int, list[int]] = {}
    for layer, dimension in artifact["selected_units"][:count].tolist():
        grouped.setdefault(int(layer), []).append(int(dimension))
    return {layer: tuple(values) for layer, values in grouped.items()}


def save_sadi_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_sadi_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_sadi_artifact(
    torch: Any,
    path: Path,
    *,
    expected_model_id: str | None = None,
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("SADI artifact must be a dictionary")
    return validate_sadi_artifact(artifact, expected_model_id=expected_model_id)


def _as_head_tensor(torch: Any, value: Any, *, label: str) -> Any:
    if hasattr(value, "shape"):
        tensor = value.detach().float().cpu()
    else:
        items = [item.detach().float().cpu() for item in value]
        if not items:
            raise ValueError(f"{label} cannot be empty")
        tensor = torch.stack(items)
    if tensor.ndim != 3 or min(tensor.shape) <= 0 or not bool(torch.isfinite(tensor).all()):
        raise ValueError(f"{label} must be finite [examples, heads, head_dim]")
    return tensor


def fit_iti_logistic_probe(
    torch: Any,
    correct: Any,
    failure: Any,
    *,
    regularization_c: float = 1.0,
    max_iter: int = 100,
    tolerance: float = 1e-9,
) -> tuple[Any, float]:
    """Fit sklearn-compatible binary L2 logistic regression by Newton steps."""
    correct = correct.detach().to(dtype=torch.float64, device="cpu")
    failure = failure.detach().to(dtype=torch.float64, device="cpu")
    if correct.ndim != 2 or correct.shape != failure.shape or correct.shape[0] == 0:
        raise ValueError("ITI probe classes must be paired non-empty matrices")
    if not 0.0 < float(regularization_c) or int(max_iter) <= 0:
        raise ValueError("ITI logistic parameters are invalid")
    x = torch.cat((correct, failure), dim=0)
    y = torch.cat(
        (
            torch.ones(correct.shape[0], dtype=torch.float64),
            torch.zeros(failure.shape[0], dtype=torch.float64),
        )
    )
    design = torch.cat((x, torch.ones(x.shape[0], 1, dtype=torch.float64)), dim=1)
    parameters = torch.zeros(design.shape[1], dtype=torch.float64)
    regularizer = torch.zeros_like(parameters)
    regularizer[:-1] = 1.0 / float(regularization_c)
    for _ in range(int(max_iter)):
        probabilities = torch.sigmoid(design @ parameters)
        gradient = design.T @ (probabilities - y) + regularizer * parameters
        weights = probabilities * (1.0 - probabilities)
        hessian = design.T @ (design * weights.unsqueeze(1))
        hessian += torch.diag(regularizer)
        step = torch.linalg.pinv(hessian) @ gradient
        parameters -= step
        if float(step.abs().max()) <= float(tolerance):
            break
    return parameters[:-1].float(), float(parameters[-1])


def build_iti_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    train_correct_by_layer: dict[int, Any],
    train_failure_by_layer: dict[int, Any],
    validation_correct_by_layer: dict[int, Any],
    validation_failure_by_layer: dict[int, Any],
    train_pair_ids: Sequence[str],
    validation_pair_ids: Sequence[str],
    top_k: int,
    benchmark: str,
    calibration_split: dict[str, Any],
    site: str,
    source: dict[str, str],
    regularization_c: float = 1.0,
) -> dict[str, Any]:
    """Fit ITI probes, select held-out-best heads, and build COM directions."""
    layers = sorted(int(value) for value in train_correct_by_layer)
    mappings = (
        train_failure_by_layer,
        validation_correct_by_layer,
        validation_failure_by_layer,
    )
    if not layers or any(sorted(int(value) for value in mapping) != layers for mapping in mappings):
        raise ValueError("ITI activation mappings must contain identical layers")
    train_correct = {
        layer: _as_head_tensor(torch, train_correct_by_layer[layer], label=f"train_correct_l{layer}")
        for layer in layers
    }
    train_failure = {
        layer: _as_head_tensor(torch, train_failure_by_layer[layer], label=f"train_failure_l{layer}")
        for layer in layers
    }
    validation_correct = {
        layer: _as_head_tensor(
            torch, validation_correct_by_layer[layer], label=f"validation_correct_l{layer}"
        )
        for layer in layers
    }
    validation_failure = {
        layer: _as_head_tensor(
            torch, validation_failure_by_layer[layer], label=f"validation_failure_l{layer}"
        )
        for layer in layers
    }
    train_shapes = {tuple(value.shape) for value in train_correct.values()}
    train_shapes.update(tuple(value.shape) for value in train_failure.values())
    validation_shapes = {tuple(value.shape) for value in validation_correct.values()}
    validation_shapes.update(tuple(value.shape) for value in validation_failure.values())
    if len(train_shapes) != 1 or len(validation_shapes) != 1:
        raise ValueError("ITI class tensors must share shapes within each split")
    train_count, num_heads, head_dim = next(iter(train_shapes))
    validation_count, validation_heads, validation_dim = next(iter(validation_shapes))
    if (validation_heads, validation_dim) != (num_heads, head_dim):
        raise ValueError("ITI validation head shape must match training")
    train_ids = [str(value) for value in train_pair_ids]
    validation_ids = [str(value) for value in validation_pair_ids]
    if len(train_ids) != train_count or len(set(train_ids)) != len(train_ids):
        raise ValueError("ITI train IDs must uniquely match training pairs")
    if len(validation_ids) != validation_count or len(set(validation_ids)) != len(
        validation_ids
    ):
        raise ValueError("ITI validation IDs must uniquely match validation pairs")
    if set(train_ids).intersection(validation_ids):
        raise ValueError("ITI train and validation IDs must be disjoint")
    if int(top_k) <= 0 or int(top_k) > len(layers) * num_heads:
        raise ValueError("ITI top_k is outside the available heads")

    probe_weights = torch.empty(len(layers), num_heads, head_dim, dtype=torch.float32)
    probe_intercepts = torch.empty(len(layers), num_heads, dtype=torch.float32)
    accuracies = torch.empty(len(layers), num_heads, dtype=torch.float32)
    for layer_offset, layer in enumerate(layers):
        for head in range(num_heads):
            weight, intercept = fit_iti_logistic_probe(
                torch,
                train_correct[layer][:, head, :],
                train_failure[layer][:, head, :],
                regularization_c=regularization_c,
            )
            probe_weights[layer_offset, head] = weight
            probe_intercepts[layer_offset, head] = intercept
            correct_prediction = (
                validation_correct[layer][:, head, :] @ weight + intercept >= 0.0
            )
            failure_prediction = (
                validation_failure[layer][:, head, :] @ weight + intercept < 0.0
            )
            accuracies[layer_offset, head] = torch.cat(
                (correct_prediction, failure_prediction)
            ).float().mean()
    order = torch.argsort(accuracies.flatten(), descending=True, stable=True)
    selected_flat = order[: int(top_k)]
    layer_offsets = selected_flat // num_heads
    selected_head_numbers = selected_flat % num_heads
    selected_heads = torch.stack(
        (
            torch.tensor([layers[int(offset)] for offset in layer_offsets]),
            selected_head_numbers,
        ),
        dim=1,
    ).to(dtype=torch.int64)
    directions = []
    scales = []
    for offset, head in zip(layer_offsets.tolist(), selected_head_numbers.tolist(), strict=True):
        layer = layers[int(offset)]
        correct = torch.cat((train_correct[layer], validation_correct[layer]), dim=0)
        failure = torch.cat((train_failure[layer], validation_failure[layer]), dim=0)
        direction = correct[:, head, :].mean(dim=0) - failure[:, head, :].mean(dim=0)
        norm = direction.norm()
        if not bool(torch.isfinite(norm)) or float(norm) == 0.0:
            raise ValueError("ITI selected center-of-mass direction is zero or non-finite")
        direction = direction / norm
        tuning = torch.cat((correct[:, head, :], failure[:, head, :]), dim=0)
        scale = torch.std(tuning @ direction, correction=1)
        if not bool(torch.isfinite(scale)) or float(scale) == 0.0:
            raise ValueError("ITI selected projection standard deviation is invalid")
        directions.append(direction)
        scales.append(scale)
    direction_tensor = torch.stack(directions).float().cpu()
    scale_tensor = torch.stack(scales).float().cpu()
    metadata = {
        "schema_version": ITI_ARTIFACT_SCHEMA_VERSION,
        "method": "iti",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layers": layers,
        "num_attention_heads": int(num_heads),
        "head_dim": int(head_dim),
        "d_model": int(num_heads * head_dim),
        "top_k": int(top_k),
        "train_pair_ids": train_ids,
        "train_pair_count": int(train_count),
        "validation_pair_ids": validation_ids,
        "validation_pair_count": int(validation_count),
        "probe": "binary_l2_logistic_regression_with_intercept",
        "regularization_c": float(regularization_c),
        "selection": "global_top_heldout_head_accuracy",
        "direction": "center_of_mass_correct_minus_failure_train_plus_validation",
        "scale": "sample_std_projection_train_plus_validation",
        "benchmark": str(benchmark),
        "calibration_split": calibration_split,
        "site": str(site),
        "source": {str(key): str(value) for key, value in source.items()},
    }
    tensors = {
        "selected_heads": selected_heads,
        "head_directions": direction_tensor,
        "projection_stds": scale_tensor,
        "validation_accuracies": accuracies,
        "probe_weights": probe_weights,
        "probe_intercepts": probe_intercepts,
    }
    return {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        **{f"{name}_fingerprint": _tensor_sha256(value) for name, value in tensors.items()},
        **tensors,
    }


def validate_iti_artifact(
    artifact: dict[str, Any], *, expected_model_id: str | None = None
) -> dict[str, Any]:
    import torch

    if artifact.get("schema_version") != ITI_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported ITI artifact schema")
    if artifact.get("method") != "iti":
        raise ValueError("artifact is not ITI")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("ITI artifact model does not match")
    top_k = int(artifact.get("top_k", -1))
    num_heads = int(artifact.get("num_attention_heads", -1))
    head_dim = int(artifact.get("head_dim", -1))
    layers = [int(value) for value in artifact.get("layers", [])]
    expected_shapes = {
        "selected_heads": (top_k, 2),
        "head_directions": (top_k, head_dim),
        "projection_stds": (top_k,),
        "validation_accuracies": (len(layers), num_heads),
        "probe_weights": (len(layers), num_heads, head_dim),
        "probe_intercepts": (len(layers), num_heads),
    }
    for name, shape in expected_shapes.items():
        tensor = artifact.get(name)
        if tensor is None or tuple(tensor.shape) != shape:
            raise ValueError(f"ITI {name} is missing or malformed")
        if name == "selected_heads":
            if tensor.dtype != torch.int64:
                raise ValueError("ITI selected_heads must be int64")
        elif not bool(torch.isfinite(tensor).all()):
            raise ValueError(f"ITI {name} contains non-finite values")
        if _tensor_sha256(tensor) != artifact.get(f"{name}_fingerprint"):
            raise ValueError(f"ITI {name} fingerprint mismatch")
    pairs = [(int(layer), int(head)) for layer, head in artifact["selected_heads"].tolist()]
    if len(set(pairs)) != len(pairs) or any(
        layer not in layers or not 0 <= head < num_heads for layer, head in pairs
    ):
        raise ValueError("ITI selected head indices are invalid")
    if not bool(torch.allclose(artifact["head_directions"].norm(dim=1), torch.ones(top_k), atol=1e-5)):
        raise ValueError("ITI head directions are not unit norm")
    if not bool((artifact["projection_stds"] > 0).all()):
        raise ValueError("ITI projection scales must be positive")
    tensor_names = set(expected_shapes)
    metadata = {
        key: value
        for key, value in artifact.items()
        if key != "metadata_fingerprint"
        and key not in tensor_names
        and not key.endswith("_fingerprint")
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("ITI artifact metadata fingerprint mismatch")
    return artifact


def iti_heads_by_layer(
    artifact: dict[str, Any], *, top_k: int | None = None
) -> dict[int, tuple[tuple[int, Any, float], ...]]:
    validate_iti_artifact(artifact)
    count = int(artifact["top_k"]) if top_k is None else int(top_k)
    if count <= 0 or count > int(artifact["top_k"]):
        raise ValueError("ITI requested top_k is outside the selected artifact")
    grouped: dict[int, list[tuple[int, Any, float]]] = {}
    for index, (layer, head) in enumerate(artifact["selected_heads"][:count].tolist()):
        grouped.setdefault(int(layer), []).append(
            (
                int(head),
                artifact["head_directions"][index],
                float(artifact["projection_stds"][index]),
            )
        )
    return {layer: tuple(values) for layer, values in grouped.items()}


def save_iti_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_iti_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_iti_artifact(
    torch: Any,
    path: Path,
    *,
    expected_model_id: str | None = None,
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("ITI artifact must be a dictionary")
    return validate_iti_artifact(artifact, expected_model_id=expected_model_id)


def austeer_consistency_scores(torch: Any, correct: Any, failure: Any) -> Any:
    """Return AUSteer's signed majority consistency beta for every scalar AU."""
    correct = _as_sample_matrix(torch, correct, label="AUSteer correct")
    failure = _as_sample_matrix(torch, failure, label="AUSteer failure")
    if correct.shape != failure.shape:
        raise ValueError("AUSteer correct/failure matrices must be paired")
    differences = correct - failure
    positive = (differences > 0).sum(dim=0)
    negative = (differences < 0).sum(dim=0)
    beta = torch.maximum(positive, negative).float() / differences.shape[0]
    return torch.where(positive < negative, -beta, beta)


def build_austeer_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    train_correct_by_layer: dict[int, Any],
    train_failure_by_layer: dict[int, Any],
    validation_correct_by_layer: dict[int, Any],
    validation_failure_by_layer: dict[int, Any],
    train_pair_ids: Sequence[str],
    validation_pair_ids: Sequence[str],
    top_k: int,
    benchmark: str,
    calibration_split: dict[str, Any],
    site: str,
    source: dict[str, str],
) -> dict[str, Any]:
    layers = sorted(int(value) for value in train_correct_by_layer)
    mappings = (
        train_failure_by_layer,
        validation_correct_by_layer,
        validation_failure_by_layer,
    )
    if not layers or any(sorted(int(value) for value in mapping) != layers for mapping in mappings):
        raise ValueError("AUSteer activation mappings must contain identical layers")
    train_correct = {
        layer: _as_sample_matrix(torch, train_correct_by_layer[layer], label=f"train_correct_l{layer}")
        for layer in layers
    }
    train_failure = {
        layer: _as_sample_matrix(torch, train_failure_by_layer[layer], label=f"train_failure_l{layer}")
        for layer in layers
    }
    validation_correct = {
        layer: _as_sample_matrix(
            torch, validation_correct_by_layer[layer], label=f"validation_correct_l{layer}"
        )
        for layer in layers
    }
    validation_failure = {
        layer: _as_sample_matrix(
            torch, validation_failure_by_layer[layer], label=f"validation_failure_l{layer}"
        )
        for layer in layers
    }
    train_shapes = {tuple(value.shape) for value in train_correct.values()}
    train_shapes.update(tuple(value.shape) for value in train_failure.values())
    validation_shapes = {tuple(value.shape) for value in validation_correct.values()}
    validation_shapes.update(tuple(value.shape) for value in validation_failure.values())
    if len(train_shapes) != 1 or len(validation_shapes) != 1:
        raise ValueError("AUSteer class matrices must share shapes within each split")
    train_count, d_model = next(iter(train_shapes))
    validation_count, validation_width = next(iter(validation_shapes))
    if validation_width != d_model:
        raise ValueError("AUSteer validation width must match training")
    train_ids = [str(value) for value in train_pair_ids]
    validation_ids = [str(value) for value in validation_pair_ids]
    if len(train_ids) != train_count or len(set(train_ids)) != len(train_ids):
        raise ValueError("AUSteer train IDs must uniquely match pairs")
    if len(validation_ids) != validation_count or len(set(validation_ids)) != len(
        validation_ids
    ):
        raise ValueError("AUSteer validation IDs must uniquely match pairs")
    if set(train_ids).intersection(validation_ids):
        raise ValueError("AUSteer train and validation IDs must be disjoint")
    if int(top_k) <= 0 or int(top_k) > len(layers) * d_model:
        raise ValueError("AUSteer top_k is outside the available scalar AUs")
    train_betas = torch.stack(
        [austeer_consistency_scores(torch, train_correct[layer], train_failure[layer]) for layer in layers]
    )
    validation_betas = torch.stack(
        [
            austeer_consistency_scores(
                torch, validation_correct[layer], validation_failure[layer]
            )
            for layer in layers
        ]
    )
    order = torch.argsort(train_betas.abs().flatten(), descending=True, stable=True)
    selected_flat = order[: int(top_k)]
    layer_offsets = selected_flat // d_model
    dimensions = selected_flat % d_model
    selected_units = torch.stack(
        (
            torch.tensor([layers[int(offset)] for offset in layer_offsets]),
            dimensions,
        ),
        dim=1,
    ).to(dtype=torch.int64)
    selected_betas = train_betas[layer_offsets, dimensions].float().cpu()
    selected_validation_betas = validation_betas[layer_offsets, dimensions].float().cpu()
    metadata = {
        "schema_version": AUSTEER_ARTIFACT_SCHEMA_VERSION,
        "method": "austeer",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layers": layers,
        "d_model": int(d_model),
        "top_k": int(top_k),
        "window_size": 1,
        "train_pair_ids": train_ids,
        "train_pair_count": int(train_count),
        "validation_pair_ids": validation_ids,
        "validation_pair_count": int(validation_count),
        "selection": "global_top_absolute_signed_pair_consistency",
        "application": "activation_times_one_plus_alpha_beta",
        "validation_sign_agreement_count": int(
            ((selected_betas * selected_validation_betas) > 0).sum()
        ),
        "benchmark": str(benchmark),
        "calibration_split": calibration_split,
        "site": str(site),
        "source": {str(key): str(value) for key, value in source.items()},
    }
    tensors = {
        "selected_units": selected_units,
        "selected_betas": selected_betas,
        "validation_betas": selected_validation_betas,
    }
    return {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        **{f"{name}_fingerprint": _tensor_sha256(value) for name, value in tensors.items()},
        **tensors,
    }


def validate_austeer_artifact(
    artifact: dict[str, Any], *, expected_model_id: str | None = None
) -> dict[str, Any]:
    import torch

    if artifact.get("schema_version") != AUSTEER_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported AUSteer artifact schema")
    if artifact.get("method") != "austeer":
        raise ValueError("artifact is not AUSteer")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("AUSteer artifact model does not match")
    top_k = int(artifact.get("top_k", -1))
    expected_shapes = {
        "selected_units": (top_k, 2),
        "selected_betas": (top_k,),
        "validation_betas": (top_k,),
    }
    for name, shape in expected_shapes.items():
        tensor = artifact.get(name)
        if tensor is None or tuple(tensor.shape) != shape:
            raise ValueError(f"AUSteer {name} is missing or malformed")
        if name == "selected_units":
            if tensor.dtype != torch.int64:
                raise ValueError("AUSteer selected units must be int64")
        elif not bool(torch.isfinite(tensor).all()) or bool((tensor.abs() > 1.0).any()):
            raise ValueError(f"AUSteer {name} has invalid beta values")
        if _tensor_sha256(tensor) != artifact.get(f"{name}_fingerprint"):
            raise ValueError(f"AUSteer {name} fingerprint mismatch")
    layers = {int(value) for value in artifact.get("layers", [])}
    d_model = int(artifact.get("d_model", -1))
    pairs = [(int(layer), int(dimension)) for layer, dimension in artifact["selected_units"].tolist()]
    if len(set(pairs)) != len(pairs) or any(
        layer not in layers or not 0 <= dimension < d_model for layer, dimension in pairs
    ):
        raise ValueError("AUSteer selected unit indices are invalid")
    tensor_names = set(expected_shapes)
    metadata = {
        key: value
        for key, value in artifact.items()
        if key != "metadata_fingerprint"
        and key not in tensor_names
        and not key.endswith("_fingerprint")
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("AUSteer artifact metadata fingerprint mismatch")
    return artifact


def austeer_units_by_layer(
    artifact: dict[str, Any], *, top_k: int | None = None
) -> dict[int, tuple[tuple[int, float], ...]]:
    validate_austeer_artifact(artifact)
    count = int(artifact["top_k"]) if top_k is None else int(top_k)
    if count <= 0 or count > int(artifact["top_k"]):
        raise ValueError("AUSteer requested top_k is outside the artifact")
    grouped: dict[int, list[tuple[int, float]]] = {}
    for index, (layer, dimension) in enumerate(artifact["selected_units"][:count].tolist()):
        grouped.setdefault(int(layer), []).append(
            (int(dimension), float(artifact["selected_betas"][index]))
        )
    return {layer: tuple(values) for layer, values in grouped.items()}


def save_austeer_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_austeer_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_austeer_artifact(
    torch: Any, path: Path, *, expected_model_id: str | None = None
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("AUSteer artifact must be a dictionary")
    return validate_austeer_artifact(artifact, expected_model_id=expected_model_id)


def loreft_transform(
    torch: Any,
    hidden: Any,
    *,
    rotate: Any,
    learned_weight: Any,
    learned_bias: Any,
    scale: float = 1.0,
) -> Any:
    """Apply LoReFT's exact low-rank residual replacement formula."""
    if hidden.shape[-1] != rotate.shape[0]:
        raise ValueError("LoReFT hidden width and rotation width do not match")
    rank = int(rotate.shape[1])
    if tuple(learned_weight.shape) != (rank, int(rotate.shape[0])) or tuple(
        learned_bias.shape
    ) != (rank,):
        raise ValueError("LoReFT learned source tensors have incompatible shapes")
    if not math.isfinite(float(scale)):
        raise ValueError("LoReFT scale must be finite")
    work = hidden.float()
    rotation = rotate.to(device=hidden.device, dtype=torch.float32)
    weight = learned_weight.to(device=hidden.device, dtype=torch.float32)
    bias = learned_bias.to(device=hidden.device, dtype=torch.float32)
    rotated_base = work @ rotation
    learned_source = work @ weight.T + bias
    output = work + float(scale) * ((learned_source - rotated_base) @ rotation.T)
    return output.to(dtype=hidden.dtype)


def build_loreft_artifact(
    torch: Any,
    *,
    model_id: str,
    model_revision: str | None,
    layers: Sequence[int],
    rotate_by_layer: dict[int, Any],
    learned_weight_by_layer: dict[int, Any],
    learned_bias_by_layer: dict[int, Any],
    train_example_ids: Sequence[str],
    validation_example_ids: Sequence[str],
    rank: int,
    benchmark: str,
    training: dict[str, Any],
    validation_loss: float,
    site: str,
    position: str,
    source: dict[str, str],
) -> dict[str, Any]:
    normalized_layers = [int(value) for value in layers]
    if not normalized_layers or len(set(normalized_layers)) != len(normalized_layers):
        raise ValueError("LoReFT layers must be non-empty and unique")
    if int(rank) <= 0:
        raise ValueError("LoReFT rank must be positive")
    mappings = (rotate_by_layer, learned_weight_by_layer, learned_bias_by_layer)
    if any(set(int(key) for key in mapping) != set(normalized_layers) for mapping in mappings):
        raise ValueError("LoReFT parameter mappings must match configured layers")
    rotations = torch.stack(
        [rotate_by_layer[layer].detach().float().cpu() for layer in normalized_layers]
    )
    weights = torch.stack(
        [learned_weight_by_layer[layer].detach().float().cpu() for layer in normalized_layers]
    )
    biases = torch.stack(
        [learned_bias_by_layer[layer].detach().float().cpu() for layer in normalized_layers]
    )
    if rotations.ndim != 3 or int(rotations.shape[2]) != int(rank):
        raise ValueError("LoReFT rotations must have shape [layers, d_model, rank]")
    d_model = int(rotations.shape[1])
    if tuple(weights.shape) != (len(normalized_layers), int(rank), d_model):
        raise ValueError("LoReFT learned weights have the wrong shape")
    if tuple(biases.shape) != (len(normalized_layers), int(rank)):
        raise ValueError("LoReFT learned biases have the wrong shape")
    if not all(bool(torch.isfinite(value).all()) for value in (rotations, weights, biases)):
        raise ValueError("LoReFT tensors contain non-finite values")
    gram = rotations.transpose(1, 2) @ rotations
    identity = torch.eye(int(rank), dtype=torch.float32).expand_as(gram)
    if not bool(torch.allclose(gram, identity, atol=1e-4, rtol=1e-4)):
        raise ValueError("LoReFT rotation columns must be orthonormal")
    train_ids = [str(value) for value in train_example_ids]
    validation_ids = [str(value) for value in validation_example_ids]
    if (
        not train_ids
        or not validation_ids
        or len(set(train_ids)) != len(train_ids)
        or len(set(validation_ids)) != len(validation_ids)
        or set(train_ids).intersection(validation_ids)
    ):
        raise ValueError("LoReFT train/validation IDs must be non-empty, unique, and disjoint")
    if not math.isfinite(float(validation_loss)):
        raise ValueError("LoReFT validation loss must be finite")
    metadata = {
        "schema_version": LOREFT_ARTIFACT_SCHEMA_VERSION,
        "method": "loreft",
        "model_id": str(model_id),
        "model_revision": model_revision,
        "layers": normalized_layers,
        "d_model": d_model,
        "rank": int(rank),
        "train_example_ids": train_ids,
        "train_example_count": len(train_ids),
        "validation_example_ids": validation_ids,
        "validation_example_count": len(validation_ids),
        "formula": "h_plus_learned_source_minus_projection_times_rotation_transpose",
        "benchmark": str(benchmark),
        "training": training,
        "validation_loss": float(validation_loss),
        "site": str(site),
        "position": str(position),
        "source": {str(key): str(value) for key, value in source.items()},
    }
    tensors = {
        "rotations": rotations,
        "learned_weights": weights,
        "learned_biases": biases,
    }
    return {
        **metadata,
        "metadata_fingerprint": _metadata_sha256(metadata),
        **{f"{name}_fingerprint": _tensor_sha256(value) for name, value in tensors.items()},
        **tensors,
    }


def validate_loreft_artifact(
    artifact: dict[str, Any], *, expected_model_id: str | None = None
) -> dict[str, Any]:
    import torch

    if artifact.get("schema_version") != LOREFT_ARTIFACT_SCHEMA_VERSION:
        raise ValueError("unsupported LoReFT artifact schema")
    if artifact.get("method") != "loreft":
        raise ValueError("artifact is not LoReFT")
    if expected_model_id is not None and artifact.get("model_id") != expected_model_id:
        raise ValueError("LoReFT artifact model does not match")
    layers = [int(value) for value in artifact.get("layers", [])]
    d_model = int(artifact.get("d_model", -1))
    rank = int(artifact.get("rank", -1))
    expected_shapes = {
        "rotations": (len(layers), d_model, rank),
        "learned_weights": (len(layers), rank, d_model),
        "learned_biases": (len(layers), rank),
    }
    for name, shape in expected_shapes.items():
        tensor = artifact.get(name)
        if tensor is None or tuple(tensor.shape) != shape or not bool(torch.isfinite(tensor).all()):
            raise ValueError(f"LoReFT {name} is missing, malformed, or non-finite")
        if _tensor_sha256(tensor) != artifact.get(f"{name}_fingerprint"):
            raise ValueError(f"LoReFT {name} fingerprint mismatch")
    gram = artifact["rotations"].transpose(1, 2) @ artifact["rotations"]
    identity = torch.eye(rank, dtype=torch.float32).expand_as(gram)
    if not bool(torch.allclose(gram.float(), identity, atol=1e-4, rtol=1e-4)):
        raise ValueError("LoReFT rotations are not orthonormal")
    tensor_names = set(expected_shapes)
    metadata = {
        key: value
        for key, value in artifact.items()
        if key != "metadata_fingerprint"
        and key not in tensor_names
        and not key.endswith("_fingerprint")
    }
    if _metadata_sha256(metadata) != artifact.get("metadata_fingerprint"):
        raise ValueError("LoReFT artifact metadata fingerprint mismatch")
    return artifact


def loreft_parameters_by_layer(
    artifact: dict[str, Any]
) -> dict[int, tuple[Any, Any, Any]]:
    validate_loreft_artifact(artifact)
    return {
        int(layer): (
            artifact["rotations"][index],
            artifact["learned_weights"][index],
            artifact["learned_biases"][index],
        )
        for index, layer in enumerate(artifact["layers"])
    }


def save_loreft_artifact(torch: Any, artifact: dict[str, Any], path: Path) -> Path:
    validate_loreft_artifact(artifact)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(path)
    return path


def load_loreft_artifact(
    torch: Any, path: Path, *, expected_model_id: str | None = None
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict):
        raise ValueError("LoReFT artifact must be a dictionary")
    return validate_loreft_artifact(artifact, expected_model_id=expected_model_id)
