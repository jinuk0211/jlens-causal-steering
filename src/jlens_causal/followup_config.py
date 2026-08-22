"""Configuration and fingerprints for post-tool stop/repeat steering."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FOLLOWUP_CONFIG_SCHEMA = "jlens-followup-pilot-v1"
VALID_METHODS = frozenset({"jlens", "contrastive", "random"})
VALID_DIRECTIONS = frozenset({"repeat_to_stop", "stop_to_repeat"})


def _require(mapping: dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise ValueError(f"{key!r} must be {expected.__name__}")
    return value


def _resolve(base: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return (base / path).resolve() if not path.is_absolute() else path.resolve()


@dataclass(frozen=True)
class FollowupConfig:
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
        return self.output_dir / "followup_directions.pt"

    @property
    def target_report(self) -> Path:
        return self.output_dir / "followup_targets.json"

    @property
    def records_path(self) -> Path:
        return self.output_dir / "followup_runs.jsonl"

    @property
    def direction_fingerprint(self) -> str:
        payload = {
            "schema": FOLLOWUP_CONFIG_SCHEMA,
            "algorithm": "toolalign-success-stop-repeat-v2",
            "model": self.model,
            "calibration": {
                key: self.data[key]
                for key in (
                    "calibration_domains",
                    "calibration_documents",
                    "conditions",
                )
            },
            "directions": self.directions,
            "layers": self.sweep["layers"],
            "observation_layer": self.sweep["observation_layer"],
            "calibration_generation": self.generation,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    @property
    def run_fingerprint(self) -> str:
        payload = {
            "schema": FOLLOWUP_CONFIG_SCHEMA,
            "record_semantics": "post-success-followup-v2",
            "direction_fingerprint": self.direction_fingerprint,
            "evaluation": {
                key: self.data[key]
                for key in (
                    "evaluation_domains",
                    "evaluation_documents",
                    "scenario_types",
                    "conditions",
                )
            },
            "sweep": self.sweep,
            "generation": self.generation,
        }
        return hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()

    def selected_case_count(self, split: str) -> int:
        return (
            len(self.data[f"{split}_domains"])
            * len(self.data[f"{split}_documents"])
            * len(self.data["scenario_types"])
            * len(self.data["conditions"])
        )

    def estimated_generations(self) -> dict[str, int]:
        cases = self.selected_case_count("evaluation")
        directions = len(self.sweep["directions"])
        layers = len(self.sweep["layers"])
        alphas = sum(float(value) != 0.0 for value in self.sweep["alphas"])
        variants = sum(
            len(self.directions["random_seeds"]) if method == "random" else 1
            for method in self.sweep["methods"]
        )
        site_variants = sum(
            len(self.directions["random_seeds"]) if method == "random" else 1
            for method in self.sweep["site_control_methods"]
        )
        counts = {
            "direction_calibration": self.selected_case_count("calibration"),
            "baseline": cases,
            "candidate": cases * directions * layers * alphas * variants,
            "site_controls": cases
            * directions
            * layers
            * len(self.sweep["site_control_alphas"])
            * site_variants
            * 2,
        }
        counts["sweep_total"] = sum(
            counts[key] for key in ("baseline", "candidate", "site_controls")
        )
        counts["fresh_total"] = counts["direction_calibration"] + counts["sweep_total"]
        return counts

    def public_dict(self) -> dict[str, Any]:
        result = json.loads(json.dumps(self.raw))
        result["data"]["toolalign_root"] = str(self.toolalign_root)
        result["output_dir"] = str(self.output_dir)
        return result


def load_followup_config(value: str | Path) -> FollowupConfig:
    path = Path(value).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or raw.get("schema_version") != FOLLOWUP_CONFIG_SCHEMA:
        raise ValueError(f"schema_version must be {FOLLOWUP_CONFIG_SCHEMA!r}")
    model = _require(raw, "model", dict)
    data = _require(raw, "data", dict)
    directions = _require(raw, "directions", dict)
    sweep = _require(raw, "sweep", dict)
    generation = _require(raw, "generation", dict)
    for key in ("model_id", "model_revision", "lens_repo", "lens_revision", "lens_file"):
        _require(model, key, str)
    for key in (
        "calibration_domains",
        "evaluation_domains",
        "calibration_documents",
        "evaluation_documents",
        "scenario_types",
        "conditions",
    ):
        values = _require(data, key, list)
        if not values or len(values) != len(set(values)):
            raise ValueError(f"{key} must be non-empty and unique")
    overlap = set(data["calibration_domains"]) & set(data["evaluation_domains"])
    if overlap:
        raise ValueError(f"calibration/evaluation domains overlap: {sorted(overlap)}")
    if set(data["scenario_types"]) != {"safe", "wrongdoing"}:
        raise ValueError("scenario_types must contain safe and wrongdoing")
    seeds = _require(directions, "random_seeds", list)
    if not seeds or len(seeds) != len(set(seeds)) or any(not isinstance(x, int) for x in seeds):
        raise ValueError("random_seeds must be unique integers")
    targets = _require(directions, "concept_targets", dict)
    for key in ("stop", "repeat"):
        words = _require(targets, key, list)
        if not words or any(not isinstance(word, str) or not word for word in words):
            raise ValueError(f"concept_targets.{key} must contain words")
    for key in ("contrastive_min_samples", "contrastive_min_domains"):
        value = directions.get(key)
        if not isinstance(value, int) or value < 2:
            raise ValueError(f"directions.{key} must be an integer >= 2")
    if directions.get("scale") != "mean_residual_norm":
        raise ValueError("directions.scale must be mean_residual_norm")
    layers = _require(sweep, "layers", list)
    if (
        not layers
        or len(layers) != len(set(layers))
        or any(not isinstance(layer, int) or layer < 0 for layer in layers)
    ):
        raise ValueError("layers must be unique non-negative integers")
    observation = sweep.get("observation_layer")
    if not isinstance(observation, int) or observation <= max(layers):
        raise ValueError("observation_layer must be after candidate layers")
    wrong_layer = sweep.get("wrong_layer")
    if not isinstance(wrong_layer, int) or wrong_layer < 0 or wrong_layer in layers:
        raise ValueError("wrong_layer must be a non-candidate layer")
    alphas = _require(sweep, "alphas", list)
    numeric = [float(value) for value in alphas]
    if 0.0 not in numeric or len(numeric) != len(set(numeric)) or any(x < 0 for x in numeric):
        raise ValueError("alphas must be unique, non-negative, and include zero")
    methods = _require(sweep, "methods", list)
    if not methods or set(methods) - VALID_METHODS:
        raise ValueError("methods contain an unknown method")
    if set(_require(sweep, "directions", list)) != VALID_DIRECTIONS:
        raise ValueError("directions must contain repeat_to_stop and stop_to_repeat")
    site_methods = _require(sweep, "site_control_methods", list)
    if set(site_methods) - set(methods):
        raise ValueError("site_control_methods must be a subset of methods")
    site_alphas = _require(sweep, "site_control_alphas", list)
    nonzero = {value for value in numeric if value != 0.0}
    if not site_alphas or not {float(value) for value in site_alphas} <= nonzero:
        raise ValueError("site_control_alphas must be non-zero members of alphas")
    if int(generation.get("max_new_tokens", 0)) != 4096:
        raise ValueError("follow-up generation must use ToolAlign max_new_tokens=4096")
    if generation.get("do_sample") is not False:
        raise ValueError("follow-up generation must be deterministic")
    base = path.parent
    toolalign_root = _resolve(base, _require(data, "toolalign_root", str))
    if not (toolalign_root / "benchmark" / "tools" / "domains.ts").is_file():
        raise FileNotFoundError(f"invalid ToolAlignBench checkout: {toolalign_root}")
    return FollowupConfig(
        path=path,
        raw=raw,
        toolalign_root=toolalign_root,
        output_dir=_resolve(base, _require(raw, "output_dir", str)),
    )
