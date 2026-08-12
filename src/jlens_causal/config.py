"""Configuration loading and validation for reproducible pilot sweeps."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "jlens-causal-pilot-v2"
VALID_METHODS = frozenset({"jlens", "contrastive", "random"})
VALID_DIRECTIONS = frozenset({"a_to_b", "b_to_a"})
VALID_POSITIONS = frozenset({"user_span", "system_matched", "prompt_first", "prompt_last"})


def _require(mapping: dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise ValueError(f"{key!r} must be {expected.__name__}")
    return value


def _resolve_from(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base / path
    return path.resolve()


@dataclass(frozen=True)
class PilotConfig:
    """Validated JSON configuration with paths resolved from its own directory."""

    path: Path
    raw: dict[str, Any]
    toolalign_root: Path
    output_dir: Path

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def data(self) -> dict[str, Any]:
        return self.raw["data"]

    @property
    def directions(self) -> dict[str, Any]:
        return self.raw["directions"]

    @property
    def sweep(self) -> dict[str, Any]:
        return self.raw["sweep"]

    @property
    def generation(self) -> dict[str, Any]:
        return self.raw["generation"]

    @property
    def direction_artifact(self) -> Path:
        return self.output_dir / "directions.pt"

    @property
    def target_selection_path(self) -> Path:
        return self.output_dir / "target_selection.json"

    @property
    def records_path(self) -> Path:
        return self.output_dir / "runs.jsonl"

    @property
    def direction_fingerprint(self) -> str:
        payload = {
            "config_schema_version": SCHEMA_VERSION,
            "direction_algorithm": "cross-domain-thought-axis-v1",
            "model": self.model,
            "calibration": {
                key: self.data[key]
                for key in (
                    "scenario_a",
                    "scenario_b",
                    "calibration_domains",
                    "calibration_documents",
                    "conditions",
                )
            },
            "directions": self.directions,
            "layers": self.sweep["layers"],
            "coordinate_swap_layers": self.sweep["coordinate_swap_layers"],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    @property
    def run_fingerprint(self) -> str:
        """Hash every semantic input that can change a generation result."""
        payload = {
            "config_schema_version": SCHEMA_VERSION,
            "record_semantics": "thought-steering-v3",
            "direction_fingerprint": self.direction_fingerprint,
            "model": self.model,
            "evaluation": {
                key: self.data[key]
                for key in (
                    "scenario_a",
                    "scenario_b",
                    "evaluation_domains",
                    "evaluation_documents",
                    "conditions",
                )
            },
            "directions": self.directions,
            "sweep": self.sweep,
            "generation": self.generation,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def estimated_generations(self) -> dict[str, int]:
        """Return exact planned generation counts before resume de-duplication."""
        pairs = (
            len(self.data["evaluation_domains"])
            * len(self.data["evaluation_documents"])
            * len(self.data["conditions"])
        )
        directions = len(self.sweep["directions"])
        layers = len(self.sweep["layers"])
        nonzero_alphas = [value for value in self.sweep["alphas"] if value != 0]
        variants = sum(
            len(self.directions["random_seeds"]) if method == "random" else 1
            for method in self.sweep["methods"]
        )
        site_variants = sum(
            len(self.directions["random_seeds"]) if method == "random" else 1
            for method in self.sweep["site_control_methods"]
        )
        counts = {
            "baseline": pairs * 2,
            "main_additive": pairs * directions * layers * len(nonzero_alphas) * variants,
            "site_controls": pairs
            * directions
            * layers
            * len(self.sweep["site_control_alphas"])
            * site_variants
            * 2,
            "paper_swap": 0,
        }
        if self.sweep["include_paper_coordinate_swap"]:
            counts["paper_swap"] = (
                pairs * directions * len(self.sweep["coordinate_swap_alphas"]) * 3
            )
        counts["total"] = sum(counts.values())
        return counts

    def public_dict(self) -> dict[str, Any]:
        output = json.loads(json.dumps(self.raw))
        output["data"]["toolalign_root"] = str(self.toolalign_root)
        output["output_dir"] = str(self.output_dir)
        return output


def load_config(value: str | Path) -> PilotConfig:
    """Load a pilot config and reject ambiguous or scientifically unsafe grids."""
    path = Path(value).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("configuration root must be an object")
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")

    model = _require(raw, "model", dict)
    data = _require(raw, "data", dict)
    directions = _require(raw, "directions", dict)
    sweep = _require(raw, "sweep", dict)
    generation = _require(raw, "generation", dict)
    for key in ("model_id", "model_revision", "lens_repo", "lens_revision", "lens_file"):
        _require(model, key, str)
    for key in (
        "scenario_a",
        "scenario_b",
    ):
        _require(data, key, str)
    if data["scenario_a"] == data["scenario_b"]:
        raise ValueError("scenario_a and scenario_b must differ")
    for key in (
        "calibration_domains",
        "evaluation_domains",
        "calibration_documents",
        "evaluation_documents",
        "conditions",
    ):
        values = _require(data, key, list)
        if not values:
            raise ValueError(f"{key} cannot be empty")
    overlap = set(data["calibration_domains"]) & set(data["evaluation_domains"])
    if overlap:
        raise ValueError(f"calibration/evaluation domains overlap: {sorted(overlap)}")

    values = _require(directions, "random_seeds", list)
    if not values:
        raise ValueError("random_seeds cannot be empty")
    if len(values) != len(set(values)):
        raise ValueError("random_seeds must contain unique values")
    if any(not isinstance(seed, int) for seed in directions["random_seeds"]):
        raise ValueError("random_seeds must contain integers")
    if directions.get("scale") != "mean_residual_norm":
        raise ValueError("directions.scale must be 'mean_residual_norm'")
    target_selection = _require(directions, "target_selection", dict)
    for key in ("top_k", "min_domain_consistency", "candidate_per_fold", "readout_layer"):
        value = target_selection.get(key)
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"directions.target_selection.{key} must be a positive integer")
    if target_selection["min_domain_consistency"] > len(data["calibration_domains"]):
        raise ValueError("target-selection consistency exceeds calibration domain count")

    layers = _require(sweep, "layers", list)
    coordinate_swap_layers = _require(sweep, "coordinate_swap_layers", list)
    alphas = _require(sweep, "alphas", list)
    methods = _require(sweep, "methods", list)
    transitions = _require(sweep, "directions", list)
    if not layers or any(not isinstance(layer, int) or layer < 0 for layer in layers):
        raise ValueError("layers must be non-negative integers")
    if len(layers) != len(set(layers)):
        raise ValueError("layers must be unique")
    if (
        not coordinate_swap_layers
        or any(not isinstance(layer, int) or layer < 0 for layer in coordinate_swap_layers)
        or len(coordinate_swap_layers) != len(set(coordinate_swap_layers))
    ):
        raise ValueError("coordinate_swap_layers must be unique non-negative integers")
    if not set(layers) <= set(coordinate_swap_layers):
        raise ValueError("coordinate_swap_layers must include every additive candidate layer")
    try:
        numeric_alphas = [float(alpha) for alpha in alphas]
    except (TypeError, ValueError) as exc:
        raise ValueError("alphas must be numeric") from exc
    if len(numeric_alphas) != len(set(numeric_alphas)):
        raise ValueError("alphas must be unique")
    if 0.0 not in alphas:
        raise ValueError("alphas must include the shared alpha=0 baseline")
    if any(float(alpha) < 0 for alpha in alphas):
        raise ValueError("alphas must be non-negative")
    unknown_methods = set(methods) - VALID_METHODS
    if unknown_methods:
        raise ValueError(f"unknown methods: {sorted(unknown_methods)}")
    if set(transitions) != VALID_DIRECTIONS:
        raise ValueError("directions must contain both a_to_b and b_to_a")
    position_policy = sweep.get("position_policy")
    if position_policy not in VALID_POSITIONS:
        raise ValueError(f"position_policy must be one of {sorted(VALID_POSITIONS)}")
    wrong_position_policy = sweep.get("wrong_position_policy", "prompt_first")
    if wrong_position_policy not in VALID_POSITIONS or wrong_position_policy == position_policy:
        raise ValueError(
            "wrong_position_policy must be a valid policy different from position_policy"
        )
    wrong_layer = sweep.get("wrong_layer")
    if not isinstance(wrong_layer, int) or wrong_layer < 0 or wrong_layer in layers:
        raise ValueError("wrong_layer must be a non-candidate non-negative layer")
    wrong_layer_band = _require(sweep, "wrong_layer_band", list)
    if (
        len(wrong_layer_band) != len(coordinate_swap_layers)
        or any(not isinstance(layer, int) or layer < 0 for layer in wrong_layer_band)
        or set(wrong_layer_band) & set(layers)
    ):
        raise ValueError(
            "wrong_layer_band must match coordinate-swap band width and not overlap it"
        )
    for key in ("site_control_methods", "site_control_alphas", "coordinate_swap_alphas"):
        values = _require(sweep, key, list)
        if len(values) != len(set(values)):
            raise ValueError(f"{key} must contain unique values")
    if set(sweep["site_control_methods"]) - set(methods):
        raise ValueError("site_control_methods must be a subset of methods")
    nonzero = {float(alpha) for alpha in alphas if float(alpha) != 0.0}
    if not {float(value) for value in sweep["site_control_alphas"]} <= nonzero:
        raise ValueError("site_control_alphas must be non-zero members of alphas")
    if any(float(value) <= 0 for value in sweep["coordinate_swap_alphas"]):
        raise ValueError("coordinate_swap_alphas must be positive")
    observation_layer = sweep.get("thought_observation_layer")
    if not isinstance(observation_layer, int) or observation_layer <= max(layers):
        raise ValueError("thought_observation_layer must be after every intervention layer")
    trace_tokens = sweep.get("thought_trace_tokens")
    if not isinstance(trace_tokens, int) or trace_tokens <= 0:
        raise ValueError("thought_trace_tokens must be a positive integer")
    if target_selection["readout_layer"] != observation_layer:
        raise ValueError("target-selection and thought-observation layers must match")

    if int(generation.get("max_new_tokens", 0)) <= 0:
        raise ValueError("generation.max_new_tokens must be positive")
    if not isinstance(generation.get("seed"), int):
        raise ValueError("generation.seed must be an integer")

    base = path.parent
    toolalign_root = _resolve_from(base, _require(data, "toolalign_root", str))
    if not (toolalign_root / "benchmark" / "tools" / "domains.ts").is_file():
        raise FileNotFoundError(f"invalid ToolAlignBench checkout: {toolalign_root}")
    output_dir = _resolve_from(base, _require(raw, "output_dir", str))
    return PilotConfig(
        path=path,
        raw=raw,
        toolalign_root=toolalign_root,
        output_dir=output_dir,
    )
