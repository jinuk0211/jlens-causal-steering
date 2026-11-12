"""Fit official-baseline artifacts for the Tau2 airline failure-mode protocol.

    python -m jlens_causal.official.fit_cli all \
        configs/taubench_airline_official_baselines_qwen35_4b.json \
        outputs/taubench-airline-repair-pairs.jsonl \
        --condition-pairs outputs/taubench-airline-cast-conditions.jsonl

Every artifact is written next to a JSON sidecar recording the upstream
commit, the hashes of the upstream files used, the fit settings and the
documented deviations.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jlens_causal.failure_steering import load_failure_steering_manifest
from jlens_causal.official import austeer, caa, cast, iti, mera, sadi
from jlens_causal.official.artifact import METHODS
from jlens_causal.official.data import (
    RenderSettings,
    load_rendered_condition_pairs,
    load_rendered_pairs,
)


def _tools(path: Path) -> list[dict[str, Any]]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("tools")
    if not isinstance(value, list) or not value:
        raise ValueError("tool schema JSON must be a non-empty list or {'tools': [...]}")
    return value


def _official_settings(manifest_raw: dict[str, Any]) -> dict[str, Any]:
    settings = manifest_raw.get("official_fit")
    if not isinstance(settings, dict):
        raise ValueError("manifest.official_fit is required for official baselines")
    return settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("method", choices=[*METHODS, "all"])
    parser.add_argument("manifest", type=Path)
    parser.add_argument("pairs", type=Path, help="agent-failure-repair-pair-v1 JSONL")
    parser.add_argument("--condition-pairs", type=Path, help="CAST condition pairs JSONL")
    parser.add_argument("--category", default="tool_call_error")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    from jlens_causal.modeling import load_hf_runtime

    manifest = load_failure_steering_manifest(args.manifest)
    fit_settings = _official_settings(manifest.raw)
    output_dir = (args.output_dir or Path(fit_settings["output_dir"])).expanduser().resolve()
    methods = list(METHODS) if args.method == "all" else [args.method]
    if "cast" in methods and args.condition_pairs is None:
        parser.error("CAST requires --condition-pairs")
    if manifest.tool_schema_path is None:
        parser.error("the manifest must pin tool_schema for exact Tau2 rendering")

    model_config = {**manifest.raw["model"], "device": "auto"}
    runtime = load_hf_runtime(model_config)
    if not runtime.torch.cuda.is_available():
        raise RuntimeError("official baseline fitting expects a CUDA host")
    generation = manifest.raw.get("generation", {})
    settings = RenderSettings(
        tools=_tools(manifest.tool_schema_path),
        chat_template_kwargs=dict(generation.get("hf_chat_template_kwargs", {})),
    )
    pairs = load_rendered_pairs(
        runtime.tokenizer, args.pairs, settings,
        failure_category=args.category, splits=("train", "validation"),
    )
    common = {
        "model_id": manifest.raw["model"]["model_id"],
        "model_revision": manifest.raw["model"]["model_revision"],
    }
    results: dict[str, str] = {}
    for method in methods:
        method_settings = dict(fit_settings.get(method, {}))
        output_path = output_dir / f"{method}-official.pt"
        if output_path.is_file() and not args.force:
            results[method] = f"{output_path} (exists)"
            continue
        if method == "caa":
            path = caa.fit(
                runtime, pairs, settings=settings,
                layers=[int(layer) for layer in method_settings.get("layers", [12, 16, 20, 24])],
                behavior=args.category, output_path=output_path, **common,
            )
        elif method == "cast":
            condition_pairs = load_rendered_condition_pairs(
                runtime.tokenizer, args.condition_pairs, settings,
                failure_category=args.category, splits=("train", "validation"),
            )
            path = cast.fit(
                runtime, pairs, condition_pairs,
                behavior_layers=[int(layer) for layer in method_settings.get("behavior_layers", list(range(15, 24)))],
                condition_layer_range=tuple(method_settings.get("condition_layer_range", [1, 16])),
                max_response_tokens=int(method_settings.get("max_response_tokens", 64)),
                threshold_range=tuple(method_settings.get("threshold_range", [0.0, 0.1])),
                threshold_step=float(method_settings.get("threshold_step", 1e-4)),
                output_path=output_path, **common,
            )
        elif method == "mera":
            path = mera.fit(runtime, pairs, seed=int(method_settings.get("seed", 42)),
                            output_path=output_path, **common)
        elif method == "sadi":
            path = sadi.fit(runtime, pairs, max_tokens=method_settings.get("max_tokens"),
                            output_path=output_path, **common)
        elif method == "iti":
            path = iti.fit(
                runtime, pairs,
                num_heads_to_intervene=int(method_settings.get("num_heads", 6)),
                seed=int(method_settings.get("seed", 42)),
                val_ratio=float(method_settings.get("val_ratio", 0.2)),
                output_path=output_path, **common,
            )
        elif method == "austeer":
            path = austeer.fit(runtime, pairs, output_path=output_path, **common)
        else:  # pragma: no cover
            raise AssertionError(method)
        results[method] = str(path)
        print(json.dumps({method: str(path)}), flush=True)
    print(json.dumps({"completed": results}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
