"""Pinned upstream baseline checkouts and isolated imports.

The official baselines call code from each paper's own repository.  Three of
those repositories carry no license, so their code is never copied into this
repository: ``scripts/fetch_official_upstreams.sh`` clones every source at the
commit pinned below into ``third_party/upstream`` (git-ignored), and the
adapters import it from there at runtime.

Several upstreams use generic top-level module names (``utils``, ``steering``,
``tasks`` ...).  Imports therefore run with the checkout first on ``sys.path``
and with those names purged from ``sys.modules`` before and after, so two
baselines never see each other's modules.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import os
import subprocess
import sys
import types
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

UPSTREAM_ROOT_ENV = "JLENS_UPSTREAM_ROOT"
COMMIT_MARKER = ".jlens-upstream-commit"


@dataclass(frozen=True)
class UpstreamSource:
    method: str
    repository: str
    commit: str
    license: str
    directory: str
    package_root: str = ""
    # Top-level module names that collide across checkouts or with this project.
    generic_modules: tuple[str, ...] = ()


UPSTREAMS: dict[str, UpstreamSource] = {
    "caa": UpstreamSource(
        method="caa",
        repository="nrimsky/CAA",
        commit="5dabbbd9a0bca5f25e174501e959de378806aa48",
        license="MIT",
        directory="CAA",
        generic_modules=("utils", "behaviors", "llama_wrapper", "generate_vectors"),
    ),
    "cast": UpstreamSource(
        method="cast",
        repository="IBM/activation-steering",
        commit="52be60235ee309b46c49d6d5877f36e20c52e6ab",
        license="Apache-2.0",
        directory="activation-steering",
    ),
    "mera": UpstreamSource(
        method="mera",
        repository="annahedstroem/MERA-steering",
        commit="1a1e6880e885ef9905815baed065e0cbbeed70c7",
        license="none published (fetched at runtime, never vendored)",
        directory="MERA-steering",
        package_root="src",
        generic_modules=("utils", "steering", "tasks", "cache", "probes", "plotting"),
    ),
    "sadi": UpstreamSource(
        method="sadi",
        repository="weixuan-wang123/SADI",
        commit="47b11e4f0818ce4ca625f0c86e59f882ddb0656b",
        license="none published (fetched at runtime, never vendored)",
        directory="SADI",
        generic_modules=("util",),
    ),
    "iti": UpstreamSource(
        method="iti",
        repository="likenneth/honest_llama",
        commit="2c6b2179be7b5aa8f0a171688cf9e01b812ca327",
        license="MIT",
        directory="honest_llama",
        generic_modules=("utils", "interveners"),
    ),
    "austeer": UpstreamSource(
        method="austeer",
        repository="zijian678/AUSteer",
        commit="d6573876734f662824062a69c5b9dee31ae57f81",
        license="none published (fetched at runtime, never vendored)",
        directory="AUSteer",
        generic_modules=("steer", "utils", "rmodels"),
    ),
}


def upstream_root() -> Path:
    """Directory holding the pinned checkouts."""
    configured = os.environ.get(UPSTREAM_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    # src/jlens_causal/official/upstream.py -> repository root
    return Path(__file__).resolve().parents[3] / "third_party" / "upstream"


def _checkout_commit(path: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        marker = path / COMMIT_MARKER
        return marker.read_text(encoding="utf-8").strip() if marker.is_file() else None


def checkout(method: str) -> Path:
    """Return the verified checkout for ``method`` or explain how to fetch it."""
    source = UPSTREAMS[method]
    path = upstream_root() / source.directory
    if not path.is_dir():
        raise FileNotFoundError(
            f"{source.repository} is not checked out at {path}; run "
            "scripts/fetch_official_upstreams.sh (or set "
            f"{UPSTREAM_ROOT_ENV})"
        )
    commit = _checkout_commit(path)
    if commit != source.commit:
        raise RuntimeError(
            f"{source.repository} checkout is at {commit!r}, expected the pinned "
            f"commit {source.commit}"
        )
    return path


def package_root(method: str) -> Path:
    source = UPSTREAMS[method]
    root = checkout(method)
    return root / source.package_root if source.package_root else root


def file_sha256(method: str, relative_path: str) -> str:
    path = checkout(method) / relative_path
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(method: str, files: tuple[str, ...]) -> dict[str, Any]:
    """Record exactly which upstream files an artifact was produced with."""
    source = UPSTREAMS[method]
    return {
        "repository": source.repository,
        "commit": source.commit,
        "license": source.license,
        "files": {name: file_sha256(method, name) for name in files},
    }


def read_source(method: str, relative_path: str) -> str:
    return (checkout(method) / relative_path).read_text(encoding="utf-8")


def _matches(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)


@contextlib.contextmanager
def _isolated_path(root: Path, purge: tuple[str, ...]) -> Iterator[None]:
    saved_path = list(sys.path)
    saved_modules = {
        name: sys.modules.pop(name) for name in list(sys.modules) if _matches(name, purge)
    }
    sys.path.insert(0, str(root))
    try:
        yield
    finally:
        sys.path[:] = saved_path
        for name in list(sys.modules):
            if _matches(name, purge):
                sys.modules.pop(name, None)
        sys.modules.update(saved_modules)


@contextlib.contextmanager
def _stubbed(stubs: Mapping[str, types.ModuleType]) -> Iterator[None]:
    """Install stand-ins only for modules that are genuinely unavailable."""
    installed: list[str] = []
    for name, module in stubs.items():
        if name in sys.modules:
            continue
        try:
            importlib.import_module(name)
            continue
        except Exception:  # missing, or incompatible with this transformers/torch
            for loaded in list(sys.modules):
                if _matches(loaded, (name,)):
                    sys.modules.pop(loaded, None)
        sys.modules[name] = module
        installed.append(name)
    try:
        yield
    finally:
        for name in installed:
            sys.modules.pop(name, None)


def stub_module(name: str, **attributes: Any) -> types.ModuleType:
    module = types.ModuleType(name)
    module.__dict__.update(attributes)
    module.__path__ = []  # allow "from name.sub import x" against nested stubs
    return module


_IMPORT_CACHE: dict[tuple[str, str], types.ModuleType] = {}


def _transformers_compat() -> None:
    """Expose names that transformers 5 renamed but the upstreams still import.

    Only aliases are added; no upstream file is edited.
    """
    try:
        import transformers
    except ImportError:
        return
    if not hasattr(transformers, "PretrainedConfig") and hasattr(transformers, "PreTrainedConfig"):
        transformers.PretrainedConfig = transformers.PreTrainedConfig


def import_upstream(
    method: str,
    module_name: str,
    *,
    stubs: Mapping[str, types.ModuleType] | None = None,
) -> types.ModuleType:
    """Import ``module_name`` from the pinned checkout of ``method``.

    The returned module keeps working after the generic names are purged from
    ``sys.modules`` because its functions hold their own globals.
    """
    key = (method, module_name)
    cached = _IMPORT_CACHE.get(key)
    if cached is not None:
        return cached
    source = UPSTREAMS[method]
    purge = tuple(dict.fromkeys((*source.generic_modules, module_name.split(".")[0])))
    os.environ.setdefault("MPLBACKEND", "Agg")
    _transformers_compat()
    with _stubbed(stubs or {}), _isolated_path(package_root(method), purge):
        module = importlib.import_module(module_name)
    _IMPORT_CACHE[key] = module
    return module


def import_package(method: str, package: str) -> types.ModuleType:
    """Import a uniquely named upstream package that may stay in ``sys.modules``."""
    key = (method, package)
    cached = _IMPORT_CACHE.get(key)
    if cached is not None:
        return cached
    os.environ.setdefault("MPLBACKEND", "Agg")
    _transformers_compat()
    root = str(package_root(method))
    if root not in sys.path:
        sys.path.insert(0, root)
    module = importlib.import_module(package)
    location = Path(getattr(module, "__file__", "") or "").resolve()
    if Path(root).resolve() not in location.parents:
        raise RuntimeError(
            f"{package} resolved to {location}, not the pinned checkout under {root}; "
            "uninstall the conflicting copy"
        )
    _IMPORT_CACHE[key] = module
    return module
