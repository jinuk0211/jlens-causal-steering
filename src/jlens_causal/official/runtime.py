"""Generation-time entry point used by the Tau2 backend for official baselines."""

from __future__ import annotations

import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jlens_causal.official.artifact import METHODS, load_artifact

_ARTIFACT_CACHE: dict[tuple[str, str], dict[str, Any]] = {}


def _method_module(method: str) -> Any:
    if method not in METHODS:
        raise ValueError(f"unknown official baseline {method!r}")
    return importlib.import_module(f"jlens_causal.official.{method}")


def cached_artifact(path: str | Path, *, method: str, model_id: str) -> dict[str, Any]:
    import torch

    key = (str(Path(path).expanduser().resolve()), method)
    artifact = _ARTIFACT_CACHE.get(key)
    if artifact is None:
        artifact = load_artifact(torch, key[0], expected_model_id=model_id, expected_method=method)
        _ARTIFACT_CACHE[key] = artifact
    return artifact


@contextmanager
def official_steering(
    *,
    model: Any,
    tokenizer: Any,
    method: str,
    artifact_path: str | Path,
    model_id: str,
    strength: float,
    layer: int,
    prompt_ids: list[int],
    options: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Install one official baseline around a single ``model.generate`` call.

    The yielded dict is filled with method-specific telemetry and should be
    merged into the backend's intervention trace after generation.
    """
    artifact = cached_artifact(artifact_path, method=method, model_id=model_id)
    module = _method_module(method)
    with module.steer(
        model,
        tokenizer,
        artifact,
        strength=float(strength),
        layer=int(layer),
        prompt_ids=list(prompt_ids),
        options=dict(options or {}),
    ) as trace:
        trace.setdefault("implementation", "official")
        trace.setdefault("upstream", {
            "repository": artifact["upstream"]["repository"],
            "commit": artifact["upstream"]["commit"],
        })
        trace.setdefault("artifact_fingerprint", artifact["fingerprint"])
        yield trace
