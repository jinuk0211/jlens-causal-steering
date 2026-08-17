"""Extract generic TauBench repair-minus-failure CAA artifacts on a GPU host."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jlens_causal.failure_caa import extract_failure_caa, read_failure_pairs
from jlens_causal.failure_steering import load_failure_steering_manifest
from jlens_causal.modeling import load_hf_runtime


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("pairs", type=Path)
    parser.add_argument("--category", default="retry_without_state_change")
    parser.add_argument("--layers", nargs="+", type=int, default=[20, 24])
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("/workspace/jlens-artifacts/taubench-airline/retry"),
    )
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    manifest = load_failure_steering_manifest(args.manifest)
    model = dict(manifest.raw["model"])
    model["device"] = "auto"
    runtime = load_hf_runtime(model)
    if not runtime.torch.cuda.is_available():
        raise RuntimeError("failure CAA extraction must run on a remote CUDA host")
    result = extract_failure_caa(
        runtime,
        read_failure_pairs(args.pairs),
        model_id=model["model_id"],
        model_revision=model["model_revision"],
        failure_category=args.category,
        layers=args.layers,
        output_dir=args.output_dir,
        force=args.force,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
