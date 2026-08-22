"""Resumable command line entry point for the ToolAlign J-Servo experiment."""

from __future__ import annotations

import argparse
import json
from typing import Any

from jlens_causal.modeling import load_hf_runtime
from jlens_causal.steering_config import load_toolalign_caa_config
from jlens_causal.toolalign_caa import (
    divergent_response_pairs,
    run_baseline_rollouts,
)
from jlens_causal.toolalign_jservo import (
    analyze_toolalign_jservo,
    extract_toolalign_jservo,
    run_toolalign_jservo_sweep,
)


def emit(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def main() -> None:
    parser = argparse.ArgumentParser(prog="run-toolalign-jservo")
    parser.add_argument(
        "action",
        choices=("validate", "baseline", "pairs", "extract", "sweep", "analyze", "all"),
    )
    parser.add_argument("config")
    parser.add_argument("--role", choices=("aligned", "abliterated"))
    parser.add_argument("--limit", type=int)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    config = load_toolalign_caa_config(args.config)
    if args.action == "validate":
        emit(
            {
                "config_fingerprint": config.config_fingerprint,
                "toolalign_root": str(config.toolalign_root),
                "output_dir": str(config.output_dir),
                "models": config.models,
                "jservo": config.raw.get("jservo"),
            }
        )
        return
    if args.action == "pairs":
        emit(
            {
                "train": divergent_response_pairs(config, split="calibration"),
                "validation": divergent_response_pairs(
                    config, split="probe_validation"
                ),
            }
        )
        return
    if args.role is None:
        parser.error("--role is required for this action")
    if args.action == "analyze":
        emit(analyze_toolalign_jservo(config, role=args.role))
        return
    runtime = load_hf_runtime(config.models[args.role])
    outputs: dict[str, Any] = {}
    if args.action in {"baseline", "all"}:
        outputs["baseline"] = run_baseline_rollouts(
            config, runtime, role=args.role, limit=args.limit
        )
    if args.action in {"extract", "all"}:
        outputs["extract"] = extract_toolalign_jservo(
            config, runtime, role=args.role, force=args.force
        )
    if args.action in {"sweep", "all"}:
        outputs["sweep"] = run_toolalign_jservo_sweep(
            config, runtime, role=args.role, limit=args.limit
        )
    if args.action == "all" and args.limit is None:
        outputs["analysis"] = analyze_toolalign_jservo(config, role=args.role)
    emit(outputs)


if __name__ == "__main__":
    main()
