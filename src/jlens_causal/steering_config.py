"""Validated configuration for benchmark-level steering baselines."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

STEERING_CONFIG_SCHEMA = "agent-steering-experiment-v1"


def _fingerprint(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ToolAlignCAAConfig:
    """One preregistered aligned/abliterated CAA experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def direction_path(self, role: str, layer: int) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "directions" / role / f"caa-layer-{layer}.pt"

    def sweep_path(self, role: str) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "sweeps" / f"{role}.jsonl"


@dataclass(frozen=True)
class ToolAlignCASTConfig:
    """One preregistered conditional activation-steering experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def artifact_path(self, role: str, behavior_layer: int) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "artifacts" / role / f"cast-layer-{behavior_layer}.pt"

    def sweep_path(self, role: str) -> Path:
        if role not in self.models:
            raise ValueError(f"unknown model role {role!r}")
        return self.output_dir / "sweeps" / f"{role}.jsonl"


@dataclass(frozen=True)
class ToolAlignMERAConfig:
    """One preregistered MERA error-reduction experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def artifact_path(self, role: str, layer: int) -> Path:
        return self.output_dir / "artifacts" / role / f"mera-layer-{int(layer)}.pt"

    def sweep_path(self, role: str) -> Path:
        return self.output_dir / "sweeps" / f"{role}.jsonl"


@dataclass(frozen=True)
class ToolAlignSADIConfig:
    """One preregistered SADI sparse dynamic-unit experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def artifact_path(self, role: str) -> Path:
        return self.output_dir / "artifacts" / role / "sadi-hidden-units.pt"

    def sweep_path(self, role: str) -> Path:
        return self.output_dir / "sweeps" / f"{role}.jsonl"


@dataclass(frozen=True)
class ToolAlignITIConfig:
    """One preregistered ITI head-probe experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def artifact_path(self, role: str) -> Path:
        return self.output_dir / "artifacts" / role / "iti-heads.pt"

    def sweep_path(self, role: str) -> Path:
        return self.output_dir / "sweeps" / f"{role}.jsonl"


@dataclass(frozen=True)
class ToolAlignAUSteerConfig:
    """One preregistered AUSteer atomic-unit experiment."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def models(self) -> dict[str, dict[str, Any]]:
        return self.raw["models"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def extraction(self) -> dict[str, Any]:
        return self.raw["extraction"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def condition(self) -> str:
        return str(self.data["condition"])

    @property
    def config_fingerprint(self) -> str:
        return _fingerprint(self.raw)

    def baseline_path(self, role: str) -> Path:
        return self.output_dir / "baselines" / f"{role}.jsonl"

    def artifact_path(self, role: str) -> Path:
        return self.output_dir / "artifacts" / role / "austeer-attention-aus.pt"

    def sweep_path(self, role: str) -> Path:
        return self.output_dir / "sweeps" / f"{role}.jsonl"


def _require_string_list(value: Any, *, label: str) -> list[str]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty string list")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains duplicates")
    return value


def _require_int_list(value: Any, *, label: str, minimum: int = 0) -> list[int]:
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, int) and item >= minimum for item in value)
    ):
        raise ValueError(f"{label} must be a non-empty integer list >= {minimum}")
    if len(set(value)) != len(value):
        raise ValueError(f"{label} contains duplicates")
    return value


def load_toolalign_caa_config(path: str | Path) -> ToolAlignCAAConfig:
    """Read and reject incomplete, overlapping, or unpinned experiment plans."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign":
        raise ValueError("this config must target benchmark='toolalign'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        revision = model.get("model_revision")
        if not isinstance(revision, str) or len(revision) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    calibration_domains = _require_string_list(
        data.get("calibration_domains"), label="data.calibration_domains"
    )
    evaluation_domains = _require_string_list(
        data.get("evaluation_domains"), label="data.evaluation_domains"
    )
    if set(calibration_domains).intersection(evaluation_domains):
        raise ValueError("calibration and evaluation domains must be disjoint")
    _require_int_list(
        data.get("calibration_documents"),
        label="data.calibration_documents",
        minimum=1,
    )
    _require_int_list(
        data.get("evaluation_documents"),
        label="data.evaluation_documents",
        minimum=1,
    )
    scenario_types = _require_string_list(
        data.get("evaluation_scenario_types"),
        label="data.evaluation_scenario_types",
    )
    if not set(scenario_types).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    if data.get("condition") not in {
        "boldly-with-reasoning",
        "boldly-without-reasoning",
        "tamely-with-reasoning",
        "tamely-without-reasoning",
    }:
        raise ValueError("unknown ToolAlign condition")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("layers"), label="extraction.layers")
    if extraction.get("site") != "assistant_response_last_content":
        raise ValueError("CAA extraction site must be assistant_response_last_content")
    if int(extraction.get("minimum_pairs", 0)) <= 0:
        raise ValueError("extraction.minimum_pairs must be positive")
    generation = raw.get("generation")
    if not isinstance(generation, dict):
        raise ValueError("generation section is required")
    if int(generation.get("max_new_tokens", 0)) <= 0:
        raise ValueError("generation.max_new_tokens must be positive")
    if int(generation.get("max_steps", 0)) <= 0:
        raise ValueError("generation.max_steps must be positive")
    if bool(generation.get("do_sample", False)):
        raise ValueError("the confirmatory CAA experiment requires deterministic decoding")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    alphas = sweep.get("alphas")
    if not isinstance(alphas, list) or 0.0 not in {float(value) for value in alphas}:
        raise ValueError("sweep.alphas must include the alpha=0 baseline")
    if int(sweep.get("wrong_layer", -1)) < 0:
        raise ValueError("sweep.wrong_layer must be non-negative")
    random_seeds = _require_int_list(sweep.get("random_seeds"), label="sweep.random_seeds")
    if len(random_seeds) < 3:
        raise ValueError("at least three random controls are required")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else (path.parent / root_value)
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else (path.parent / output_value)
    ).resolve()
    return ToolAlignCAAConfig(
        path=path,
        raw=raw,
        toolalign_root=toolalign_root,
        output_dir=output_dir,
    )


def load_toolalign_cast_config(path: str | Path) -> ToolAlignCASTConfig:
    """Read a disjoint behavior-train/gate-validation CAST plan."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign" or raw.get("method") != "cast":
        raise ValueError("this config must target ToolAlign with method='cast'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        revision = model.get("model_revision")
        if not isinstance(revision, str) or len(revision) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    behavior_domains = _require_string_list(
        data.get("calibration_domains"), label="data.calibration_domains"
    )
    gate_domains = _require_string_list(
        data.get("gate_validation_domains"), label="data.gate_validation_domains"
    )
    evaluation_domains = _require_string_list(
        data.get("evaluation_domains"), label="data.evaluation_domains"
    )
    if (
        set(behavior_domains).intersection(gate_domains)
        or set(behavior_domains).intersection(evaluation_domains)
        or set(gate_domains).intersection(evaluation_domains)
    ):
        raise ValueError("CAST behavior, gate-validation, and evaluation domains must be disjoint")
    _require_int_list(
        data.get("calibration_documents"), label="data.calibration_documents", minimum=1
    )
    _require_int_list(
        data.get("gate_validation_documents"),
        label="data.gate_validation_documents",
        minimum=1,
    )
    _require_int_list(
        data.get("evaluation_documents"), label="data.evaluation_documents", minimum=1
    )
    scenario_types = _require_string_list(
        data.get("evaluation_scenario_types"), label="data.evaluation_scenario_types"
    )
    if not set(scenario_types).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    if data.get("condition") not in {
        "boldly-with-reasoning",
        "boldly-without-reasoning",
        "tamely-with-reasoning",
        "tamely-without-reasoning",
    }:
        raise ValueError("unknown ToolAlign condition")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("behavior_layers"), label="extraction.behavior_layers")
    _require_int_list(extraction.get("condition_layers"), label="extraction.condition_layers")
    expected_sites = {
        "behavior_extraction": "block_output_assistant_content_mean",
        "condition_extraction": "block_output_prompt_mean",
        "gate_measurement": "block_input_prompt",
        "behavior_application": "block_input",
    }
    if extraction.get("sites") != expected_sites:
        raise ValueError("CAST extraction.sites must explicitly match the official layer sites")
    if extraction.get("comparison_mode") not in {"mean", "last"}:
        raise ValueError("CAST comparison_mode must be mean or last")
    if int(extraction.get("minimum_behavior_pairs", 0)) <= 0:
        raise ValueError("extraction.minimum_behavior_pairs must be positive")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "IBM/activation-steering"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("CAST source must pin IBM/activation-steering to a commit")
    generation = raw.get("generation")
    if not isinstance(generation, dict) or int(generation.get("max_new_tokens", 0)) <= 0:
        raise ValueError("generation with positive max_new_tokens is required")
    if int(generation.get("max_steps", 0)) <= 0:
        raise ValueError("generation.max_steps must be positive")
    if bool(generation.get("do_sample", False)):
        raise ValueError("the confirmatory CAST experiment requires deterministic decoding")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    alphas = sweep.get("alphas")
    if not isinstance(alphas, list) or 0.0 not in {float(value) for value in alphas}:
        raise ValueError("sweep.alphas must include the alpha=0 baseline")
    modes = _require_string_list(sweep.get("prefill_modes"), label="sweep.prefill_modes")
    if set(modes) != {"all_tokens", "decision_only"}:
        raise ValueError("CAST sweep must include official and decision-only prefill modes")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else (path.parent / root_value)
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else (path.parent / output_value)
    ).resolve()
    return ToolAlignCASTConfig(
        path=path,
        raw=raw,
        toolalign_root=toolalign_root,
        output_dir=output_dir,
    )


def load_toolalign_mera_config(path: str | Path) -> ToolAlignMERAConfig:
    """Read a disjoint MERA probe-train/validation/evaluation plan."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign" or raw.get("method") != "mera":
        raise ValueError("this config must target ToolAlign with method='mera'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "annahedstroem/MERA-steering"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("MERA source must pin annahedstroem/MERA-steering to a commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    split_domains = {
        name: _require_string_list(data.get(name), label=f"data.{name}")
        for name in (
            "calibration_domains",
            "probe_validation_domains",
            "evaluation_domains",
        )
    }
    domain_sets = [set(value) for value in split_domains.values()]
    if any(
        domain_sets[left].intersection(domain_sets[right])
        for left in range(len(domain_sets))
        for right in range(left + 1, len(domain_sets))
    ):
        raise ValueError("MERA train, validation, and evaluation domains must be disjoint")
    for key in (
        "calibration_documents",
        "probe_validation_documents",
        "evaluation_documents",
    ):
        _require_int_list(data.get(key), label=f"data.{key}", minimum=1)
    scenarios = _require_string_list(
        data.get("evaluation_scenario_types"), label="data.evaluation_scenario_types"
    )
    if not set(scenarios).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("layers"), label="extraction.layers")
    if extraction.get("site") != "post_attention_layernorm_output_last_assistant_content":
        raise ValueError("MERA extraction site must match the official hook module")
    if int(extraction.get("minimum_train_pairs", 0)) <= 0 or int(
        extraction.get("minimum_validation_pairs", 0)
    ) <= 0:
        raise ValueError("MERA minimum train/validation pairs must be positive")
    alpha_grid = extraction.get("alpha_grid")
    if (
        not isinstance(alpha_grid, list)
        or not alpha_grid
        or any(not 0.0 < float(value) <= 1.0 for value in alpha_grid)
    ):
        raise ValueError("MERA alpha_grid values must be in (0, 1]")
    generation = raw.get("generation")
    if not isinstance(generation, dict) or int(generation.get("max_new_tokens", 0)) <= 0:
        raise ValueError("generation with positive max_new_tokens is required")
    if int(generation.get("max_steps", 0)) <= 0 or bool(
        generation.get("do_sample", False)
    ):
        raise ValueError("MERA confirmatory generation must be deterministic")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    modes = _require_string_list(sweep.get("prefill_modes"), label="sweep.prefill_modes")
    if set(modes) != {"all_tokens", "decision_only"}:
        raise ValueError("MERA sweep must include all_tokens and decision_only")
    seeds = _require_int_list(sweep.get("random_seeds"), label="sweep.random_seeds")
    if len(seeds) < 3:
        raise ValueError("MERA requires at least three random-probe controls")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else path.parent / root_value
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else path.parent / output_value
    ).resolve()
    return ToolAlignMERAConfig(path, raw, toolalign_root, output_dir)


def load_toolalign_sadi_config(path: str | Path) -> ToolAlignSADIConfig:
    """Read a disjoint SADI unit-train/validation/evaluation plan."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign" or raw.get("method") != "sadi":
        raise ValueError("this config must target ToolAlign with method='sadi'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "weixuan-wang123/SADI"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("SADI source must pin weixuan-wang123/SADI to a commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    split_domains = {
        name: _require_string_list(data.get(name), label=f"data.{name}")
        for name in (
            "calibration_domains",
            "unit_validation_domains",
            "evaluation_domains",
        )
    }
    domain_sets = [set(value) for value in split_domains.values()]
    if any(
        domain_sets[left].intersection(domain_sets[right])
        for left in range(len(domain_sets))
        for right in range(left + 1, len(domain_sets))
    ):
        raise ValueError("SADI train, validation, and evaluation domains must be disjoint")
    for key in (
        "calibration_documents",
        "unit_validation_documents",
        "evaluation_documents",
    ):
        _require_int_list(data.get(key), label=f"data.{key}", minimum=1)
    scenarios = _require_string_list(
        data.get("evaluation_scenario_types"), label="data.evaluation_scenario_types"
    )
    if not set(scenarios).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("layers"), label="extraction.layers")
    if extraction.get("site") != "mlp_output_last_assistant_content":
        raise ValueError("SADI extraction site must be the official hidden-output MLP site")
    if int(extraction.get("minimum_train_pairs", 0)) <= 0 or int(
        extraction.get("minimum_validation_pairs", 0)
    ) <= 0:
        raise ValueError("SADI minimum train/validation pairs must be positive")
    if int(extraction.get("max_top_k", 0)) <= 0:
        raise ValueError("SADI max_top_k must be positive")
    generation = raw.get("generation")
    if (
        not isinstance(generation, dict)
        or int(generation.get("max_new_tokens", 0)) <= 0
        or int(generation.get("max_steps", 0)) <= 0
        or bool(generation.get("do_sample", False))
    ):
        raise ValueError("SADI confirmatory generation must be positive and deterministic")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    top_k_values = _require_int_list(sweep.get("top_k_values"), label="sweep.top_k_values", minimum=1)
    if max(top_k_values) != int(extraction["max_top_k"]):
        raise ValueError("SADI max_top_k must equal the largest sweep top_k")
    strengths = sweep.get("strengths")
    if (
        not isinstance(strengths, list)
        or not strengths
        or any(float(value) < 0.0 for value in strengths)
        or float(sweep.get("primary_strength", -1.0)) not in {float(value) for value in strengths}
    ):
        raise ValueError("SADI strengths must be non-negative and contain primary_strength")
    if int(sweep.get("primary_top_k", 0)) not in top_k_values:
        raise ValueError("SADI primary_top_k must occur in top_k_values")
    seeds = _require_int_list(sweep.get("random_seeds"), label="sweep.random_seeds")
    if len(seeds) < 3:
        raise ValueError("SADI requires at least three random-unit controls")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else path.parent / root_value
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else path.parent / output_value
    ).resolve()
    return ToolAlignSADIConfig(path, raw, toolalign_root, output_dir)


def load_toolalign_iti_config(path: str | Path) -> ToolAlignITIConfig:
    """Read a disjoint ITI probe-train/head-validation/evaluation plan."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign" or raw.get("method") != "iti":
        raise ValueError("this config must target ToolAlign with method='iti'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "likenneth/honest_llama"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("ITI source must pin likenneth/honest_llama to a commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    domain_values = [
        _require_string_list(data.get(name), label=f"data.{name}")
        for name in (
            "calibration_domains",
            "head_validation_domains",
            "evaluation_domains",
        )
    ]
    domain_sets = [set(values) for values in domain_values]
    if any(
        domain_sets[left].intersection(domain_sets[right])
        for left in range(3)
        for right in range(left + 1, 3)
    ):
        raise ValueError("ITI train, head-validation, and evaluation domains must be disjoint")
    for key in (
        "calibration_documents",
        "head_validation_documents",
        "evaluation_documents",
    ):
        _require_int_list(data.get(key), label=f"data.{key}", minimum=1)
    scenarios = _require_string_list(
        data.get("evaluation_scenario_types"), label="data.evaluation_scenario_types"
    )
    if not set(scenarios).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("layers"), label="extraction.layers")
    if extraction.get("site") != "self_attn_o_proj_input_last_assistant_content":
        raise ValueError("ITI extraction site must match the official attention-head site")
    if int(extraction.get("minimum_train_pairs", 0)) <= 0 or int(
        extraction.get("minimum_validation_pairs", 0)
    ) <= 0:
        raise ValueError("ITI minimum train/validation pairs must be positive")
    if int(extraction.get("max_top_k", 0)) <= 0 or float(
        extraction.get("regularization_c", 0.0)
    ) <= 0.0:
        raise ValueError("ITI max_top_k and regularization_c must be positive")
    generation = raw.get("generation")
    if (
        not isinstance(generation, dict)
        or int(generation.get("max_new_tokens", 0)) <= 0
        or int(generation.get("max_steps", 0)) <= 0
        or bool(generation.get("do_sample", False))
    ):
        raise ValueError("ITI confirmatory generation must be positive and deterministic")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    top_k_values = _require_int_list(sweep.get("top_k_values"), label="sweep.top_k_values", minimum=1)
    if max(top_k_values) != int(extraction["max_top_k"]):
        raise ValueError("ITI max_top_k must equal the largest sweep top_k")
    alphas = sweep.get("alphas")
    if (
        not isinstance(alphas, list)
        or not alphas
        or any(float(value) <= 0.0 for value in alphas)
        or float(sweep.get("primary_alpha", 0.0)) not in {float(value) for value in alphas}
    ):
        raise ValueError("ITI alphas must be positive and contain primary_alpha")
    if int(sweep.get("primary_top_k", 0)) not in top_k_values:
        raise ValueError("ITI primary_top_k must occur in top_k_values")
    seeds = _require_int_list(sweep.get("random_seeds"), label="sweep.random_seeds")
    if len(seeds) < 3:
        raise ValueError("ITI requires at least three random-head controls")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else path.parent / root_value
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else path.parent / output_value
    ).resolve()
    return ToolAlignITIConfig(path, raw, toolalign_root, output_dir)


def load_toolalign_austeer_config(path: str | Path) -> ToolAlignAUSteerConfig:
    """Read a disjoint AUSteer AU-train/validation/evaluation plan."""
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != STEERING_CONFIG_SCHEMA:
        raise ValueError("unsupported steering experiment config schema")
    if raw.get("benchmark") != "toolalign" or raw.get("method") != "austeer":
        raise ValueError("this config must target ToolAlign with method='austeer'")
    models = raw.get("models")
    if not isinstance(models, dict) or set(models) != {"aligned", "abliterated"}:
        raise ValueError("models must contain exactly aligned and abliterated")
    for role, model in models.items():
        if not isinstance(model, dict) or not model.get("model_id"):
            raise ValueError(f"models.{role}.model_id is required")
        if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
            raise ValueError(f"models.{role}.model_revision must be a 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "zijian678/AUSteer"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("AUSteer source must pin zijian678/AUSteer to a commit")
    data = raw.get("data")
    if not isinstance(data, dict):
        raise ValueError("data section is required")
    domain_values = [
        _require_string_list(data.get(name), label=f"data.{name}")
        for name in ("calibration_domains", "au_validation_domains", "evaluation_domains")
    ]
    domain_sets = [set(values) for values in domain_values]
    if any(
        domain_sets[left].intersection(domain_sets[right])
        for left in range(3)
        for right in range(left + 1, 3)
    ):
        raise ValueError("AUSteer train, AU-validation, and evaluation domains must be disjoint")
    for key in (
        "calibration_documents",
        "au_validation_documents",
        "evaluation_documents",
    ):
        _require_int_list(data.get(key), label=f"data.{key}", minimum=1)
    scenarios = _require_string_list(
        data.get("evaluation_scenario_types"), label="data.evaluation_scenario_types"
    )
    if not set(scenarios).issubset({"safe", "wrongdoing"}):
        raise ValueError("evaluation scenario types must be safe/wrongdoing")
    extraction = raw.get("extraction")
    if not isinstance(extraction, dict):
        raise ValueError("extraction section is required")
    _require_int_list(extraction.get("layers"), label="extraction.layers")
    if extraction.get("site") != "self_attn_o_proj_input_last_assistant_content":
        raise ValueError("AUSteer extraction site must match its attention AU site")
    if int(extraction.get("window_size", 0)) != 1:
        raise ValueError("confirmatory AUSteer requires scalar window_size=1")
    if int(extraction.get("minimum_train_pairs", 0)) <= 0 or int(
        extraction.get("minimum_validation_pairs", 0)
    ) <= 0:
        raise ValueError("AUSteer minimum train/validation pairs must be positive")
    if int(extraction.get("max_top_k", 0)) <= 0:
        raise ValueError("AUSteer max_top_k must be positive")
    generation = raw.get("generation")
    if (
        not isinstance(generation, dict)
        or int(generation.get("max_new_tokens", 0)) <= 0
        or int(generation.get("max_steps", 0)) <= 0
        or bool(generation.get("do_sample", False))
    ):
        raise ValueError("AUSteer confirmatory generation must be positive and deterministic")
    sweep = raw.get("sweep")
    if not isinstance(sweep, dict):
        raise ValueError("sweep section is required")
    top_k_values = _require_int_list(sweep.get("top_k_values"), label="sweep.top_k_values", minimum=1)
    if max(top_k_values) != int(extraction["max_top_k"]):
        raise ValueError("AUSteer max_top_k must equal the largest sweep top_k")
    alphas = sweep.get("alphas")
    if (
        not isinstance(alphas, list)
        or not alphas
        or any(float(value) <= 0.0 for value in alphas)
        or float(sweep.get("primary_alpha", 0.0)) not in {float(value) for value in alphas}
        or int(sweep.get("primary_top_k", 0)) not in top_k_values
    ):
        raise ValueError("AUSteer primary alpha/top_k must occur in the positive grid")
    seeds = _require_int_list(sweep.get("random_seeds"), label="sweep.random_seeds")
    if len(seeds) < 3:
        raise ValueError("AUSteer requires at least three random-AU controls")
    root_value = Path(data["toolalign_root"]).expanduser()
    output_value = Path(raw["output_dir"]).expanduser()
    toolalign_root = (
        root_value if root_value.is_absolute() else path.parent / root_value
    ).resolve()
    output_dir = (
        output_value if output_value.is_absolute() else path.parent / output_value
    ).resolve()
    return ToolAlignAUSteerConfig(path, raw, toolalign_root, output_dir)
