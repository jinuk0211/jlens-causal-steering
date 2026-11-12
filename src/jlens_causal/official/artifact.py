"""Versioned, tensor-only artifacts for the official baselines."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

OFFICIAL_ARTIFACT_SCHEMA = "official-baseline-artifact-v1"
ADAPTER_VERSION = "official-adapters-v1"
METHODS = ("caa", "cast", "mera", "sadi", "iti", "austeer")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def metadata_fingerprint(artifact: dict[str, Any]) -> str:
    """Hash every JSON field except the tensor state."""
    metadata = {key: value for key, value in artifact.items() if key not in {"state", "fingerprint"}}
    return hashlib.sha256(_canonical(metadata).encode()).hexdigest()


def build_artifact(
    *,
    method: str,
    model_id: str,
    model_revision: str,
    upstream: dict[str, Any],
    fit: dict[str, Any],
    deviations: list[str],
    state: dict[str, Any],
) -> dict[str, Any]:
    if method not in METHODS:
        raise ValueError(f"unknown official baseline {method!r}")
    artifact = {
        "schema_version": OFFICIAL_ARTIFACT_SCHEMA,
        "implementation": "official",
        "method": method,
        "adapter_version": ADAPTER_VERSION,
        "model": {"model_id": model_id, "model_revision": model_revision},
        "upstream": upstream,
        "fit": fit,
        "deviations": list(deviations),
        "state": state,
    }
    _canonical({key: value for key, value in artifact.items() if key != "state"})
    artifact["fingerprint"] = metadata_fingerprint(artifact)
    return artifact


def save_artifact(torch: Any, artifact: dict[str, Any], path: str | Path) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    torch.save(artifact, temporary)
    temporary.replace(output)
    sidecar = output.with_suffix(output.suffix + ".json")
    sidecar.write_text(
        json.dumps(
            {key: value for key, value in artifact.items() if key != "state"},
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output


def load_artifact(
    torch: Any,
    path: str | Path,
    *,
    expected_model_id: str | None = None,
    expected_method: str | None = None,
) -> dict[str, Any]:
    artifact = torch.load(Path(path), map_location="cpu", weights_only=True)
    if not isinstance(artifact, dict) or artifact.get("schema_version") != OFFICIAL_ARTIFACT_SCHEMA:
        raise ValueError(f"{path} is not an official baseline artifact")
    if artifact.get("fingerprint") != metadata_fingerprint(artifact):
        raise ValueError(f"{path} metadata fingerprint mismatch")
    if expected_method is not None and artifact.get("method") != expected_method:
        raise ValueError(f"{path} holds {artifact.get('method')!r}, expected {expected_method!r}")
    if expected_model_id is not None and artifact["model"]["model_id"] != expected_model_id:
        raise ValueError(
            f"{path} was fit on {artifact['model']['model_id']!r}, not {expected_model_id!r}"
        )
    return artifact
