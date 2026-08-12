"""Command-line entry point for the causal steering pilot."""

from __future__ import annotations

import argparse
import json
from typing import Any

from jlens_causal.config import PilotConfig, load_config
from jlens_causal.directions import extract_directions
from jlens_causal.experiment import (
    reset_output_artifacts,
    run_sweep,
    validate_output_compatibility,
)
from jlens_causal.metrics import analyze_runs
from jlens_causal.modeling import load_runtime
from jlens_causal.toolalign import load_cases


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _validate_data(config: PilotConfig) -> dict[str, Any]:
    selections: dict[str, int] = {}
    for split, domains, documents in (
        (
            "calibration",
            config.data["calibration_domains"],
            config.data["calibration_documents"],
        ),
        (
            "evaluation",
            config.data["evaluation_domains"],
            config.data["evaluation_documents"],
        ),
    ):
        _, cases = load_cases(
            config.toolalign_root,
            domains=domains,
            documents=documents,
            scenario_types=[config.data["scenario_a"], config.data["scenario_b"]],
        )
        selections[split] = len(cases)
    return {
        "config": str(config.path),
        "toolalign_root": str(config.toolalign_root),
        "output_dir": str(config.output_dir),
        "selected_cases": selections,
        "calibration_pairs": selections["calibration"] // 2,
        "estimated_generations": config.estimated_generations(),
        "direction_fingerprint": config.direction_fingerprint,
        "run_fingerprint": config.run_fingerprint,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jlens-causal",
        description="Run paired J-lens/contrastive/random causal steering pilots.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name in ("validate", "plan"):
        child = subparsers.add_parser(name)
        child.add_argument("config")

    extract = subparsers.add_parser("extract-directions")
    extract.add_argument("config")
    extract.add_argument("--force", action="store_true")

    run = subparsers.add_parser("run")
    run.add_argument("config")
    run.add_argument("--limit", type=int)

    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("config")
    analyze.add_argument("--bootstrap-samples", type=int, default=2_000)

    all_command = subparsers.add_parser("all")
    all_command.add_argument("config")
    all_command.add_argument("--force-directions", action="store_true")
    all_command.add_argument(
        "--fresh",
        action="store_true",
        help="remove this runner's known artifacts before starting",
    )
    all_command.add_argument("--limit", type=int)
    all_command.add_argument("--bootstrap-samples", type=int, default=2_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_config(args.config)
    if args.command in {"validate", "plan"}:
        _print(_validate_data(config))
        return 0
    if args.command == "analyze":
        _print(analyze_runs(config, bootstrap_samples=args.bootstrap_samples))
        return 0

    fresh_removed: list[str] = []
    if args.command == "all" and args.fresh:
        fresh_removed = reset_output_artifacts(config)
    elif args.command in {"run", "all"}:
        validate_output_compatibility(config)

    runtime = load_runtime(config.model)
    if args.command == "extract-directions":
        path = extract_directions(config, runtime, force=args.force)
        _print({"direction_artifact": str(path)})
        return 0
    if args.command == "run":
        _print(run_sweep(config, runtime, limit=args.limit))
        return 0
    if args.command == "all":
        path = extract_directions(
            config,
            runtime,
            force=args.force_directions or args.fresh,
        )
        run_stats = run_sweep(config, runtime, limit=args.limit)
        result: dict[str, Any] = {
            "direction_artifact": str(path),
            "fresh_removed": fresh_removed,
            "run": run_stats,
        }
        if (
            args.limit is None
            and run_stats["already_complete"] + run_stats["written"] == run_stats["planned"]
        ):
            result["analysis"] = analyze_runs(config, bootstrap_samples=args.bootstrap_samples)
        else:
            result["analysis"] = "skipped because the sweep is incomplete"
        _print(result)
        return 0
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
