"""Extract generic failure-mode steering artifacts on a remote GPU host."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jlens_causal.failure_caa import extract_failure_caa, read_failure_pairs
from jlens_causal.failure_cast import (
    extract_failure_cast,
    read_failure_cast_condition_pairs,
)
from jlens_causal.failure_core_extractors import (
    extract_failure_austeer,
    extract_failure_iti,
    extract_failure_mera,
    extract_failure_sadi,
)
from jlens_causal.failure_steering import load_failure_steering_manifest
from jlens_causal.jservo import extract_failure_jservo
from jlens_causal.modeling import load_hf_runtime


def _read_tool_schemas(path: Path) -> list[dict]:
    value = json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("tools")
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, dict) for item in value)
    ):
        raise ValueError("tools JSON must be a non-empty list or an object with a tools list")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "method",
        choices=[
            "caa",
            "cast",
            "mera",
            "sadi",
            "iti",
            "austeer",
            "jservo",
            "all",
        ],
    )
    parser.add_argument("manifest", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--category", default="retry_without_state_change")
    parser.add_argument(
        "--categories",
        nargs="+",
        help="J-Servo failure categories; defaults to --category",
    )
    parser.add_argument("--layers", nargs="+", type=int, default=[20, 24])
    parser.add_argument(
        "--attention-layers",
        nargs="+",
        type=int,
        help="full-attention layers for ITI/AUSteer; defaults to --layers",
    )
    parser.add_argument("--condition-layers", nargs="+", type=int, default=[16, 20, 24])
    parser.add_argument("--observation-layers", nargs="+", type=int, default=[16])
    parser.add_argument("--condition-pairs", type=Path)
    parser.add_argument("--tools-json", type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/workspace/jlens-artifacts/taubench-airline/retry"),
    )
    parser.add_argument("--top-k", type=int)
    parser.add_argument("--protected-k", type=int, default=8)
    parser.add_argument("--minimum-consistency", type=float, default=0.7)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = load_failure_steering_manifest(args.manifest)
    model = dict(manifest.raw["model"])
    model["device"] = "auto"
    runtime = load_hf_runtime(model)
    if not runtime.torch.cuda.is_available():
        raise RuntimeError("failure artifact extraction must run on a remote CUDA host")
    pairs = read_failure_pairs(args.pairs)
    tools_path = args.tools_json or manifest.tool_schema_path
    if tools_path is None:
        parser.error("--tools-json is required when the manifest does not pin tool_schema")
    tools = _read_tool_schemas(tools_path)
    common = {
        "runtime": runtime,
        "pairs": pairs,
        "model_id": model["model_id"],
        "model_revision": model["model_revision"],
        "failure_category": args.category,
        "layers": args.layers,
        "output_dir": args.output_dir,
        "tools": tools,
    }
    attention_common = {
        **common,
        "layers": args.attention_layers or args.layers,
    }
    methods = list(manifest.enabled_methods) if args.method == "all" else [args.method]
    disabled = set(methods) - set(manifest.enabled_methods)
    if disabled:
        parser.error(f"methods are disabled by the manifest: {sorted(disabled)}")
    if "cast" in methods and args.condition_pairs is None:
        parser.error("cast and all require --condition-pairs")
    condition_pairs = (
        read_failure_cast_condition_pairs(args.condition_pairs)
        if args.condition_pairs is not None
        else None
    )
    results = {}
    for method in methods:
        if method == "jservo":
            result = extract_failure_jservo(
                runtime,
                pairs,
                model_id=model["model_id"],
                model_revision=model["model_revision"],
                failure_categories=args.categories or [args.category],
                observation_layers=args.observation_layers,
                control_layers=args.layers,
                output_path=args.output_dir / "jservo.pt",
                tools=tools,
                bundle_size=args.top_k or 8,
                protected_size=args.protected_k,
                minimum_consistency=args.minimum_consistency,
                force=args.force,
            )
        elif method == "caa":
            result = extract_failure_caa(**common, force=args.force)
        elif method == "cast":
            assert condition_pairs is not None
            result = extract_failure_cast(
                runtime,
                pairs,
                condition_pairs,
                model_id=model["model_id"],
                model_revision=model["model_revision"],
                failure_category=args.category,
                behavior_layers=args.layers,
                condition_layers=args.condition_layers,
                output_dir=args.output_dir,
                tools=tools,
                force=args.force,
            )
        elif method == "mera":
            result = extract_failure_mera(**common, force=args.force)
        elif method == "sadi":
            result = extract_failure_sadi(
                **common, top_k=args.top_k or 20, force=args.force
            )
        elif method == "iti":
            result = extract_failure_iti(
                **attention_common, top_k=args.top_k or 8, force=args.force
            )
        elif method == "austeer":
            result = extract_failure_austeer(
                **attention_common, top_k=args.top_k or 100, force=args.force
            )
        else:
            raise AssertionError(f"unhandled artifact method {method}")
        results[method] = result
        print(json.dumps({method: result}, ensure_ascii=False, indent=2, sort_keys=True))
    if len(results) > 1:
        print(json.dumps({"completed": list(results)}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
