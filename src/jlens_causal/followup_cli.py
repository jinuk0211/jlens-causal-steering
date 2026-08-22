"""CLI for post-tool stop/repeat causal steering."""

from __future__ import annotations

import argparse
import json
from typing import Any

from jlens_causal.followup import (
    analyze_followup,
    extract_followup_directions,
    reset_followup_artifacts,
    run_followup_sweep,
    validate_followup_outputs,
)
from jlens_causal.followup_config import load_followup_config
from jlens_causal.modeling import load_runtime
from jlens_causal.toolalign import load_cases


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _validate(config: Any) -> dict[str, Any]:
    selected = {}
    for split in ("calibration", "evaluation"):
        _, cases = load_cases(
            config.toolalign_root,
            domains=config.data[f"{split}_domains"],
            documents=config.data[f"{split}_documents"],
            scenario_types=config.data["scenario_types"],
        )
        selected[split] = len(cases) * len(config.data["conditions"])
    return {
        "config": str(config.path),
        "toolalign_root": str(config.toolalign_root),
        "output_dir": str(config.output_dir),
        "selected_cases": selected,
        "estimated_generations": config.estimated_generations(),
        "direction_fingerprint": config.direction_fingerprint,
        "run_fingerprint": config.run_fingerprint,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jlens-followup")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("validate", "plan"):
        child = sub.add_parser(name)
        child.add_argument("config")
    extract = sub.add_parser("extract-directions")
    extract.add_argument("config")
    extract.add_argument("--force", action="store_true")
    run = sub.add_parser("run")
    run.add_argument("config")
    run.add_argument("--limit", type=int)
    analyze = sub.add_parser("analyze")
    analyze.add_argument("config")
    all_command = sub.add_parser("all")
    all_command.add_argument("config")
    all_command.add_argument("--fresh", action="store_true")
    all_command.add_argument("--force-directions", action="store_true")
    all_command.add_argument("--limit", type=int)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    config = load_followup_config(args.config)
    if args.command in {"validate", "plan"}:
        _print(_validate(config))
        return 0
    if args.command == "analyze":
        _print(analyze_followup(config))
        return 0
    removed: list[str] = []
    if args.command == "all" and args.fresh:
        removed = reset_followup_artifacts(config)
    else:
        validate_followup_outputs(config)
    runtime = load_runtime(config.model)
    if args.command == "extract-directions":
        _print(
            {
                "direction_artifact": str(
                    extract_followup_directions(config, runtime, force=args.force)
                )
            }
        )
        return 0
    if args.command == "run":
        _print(run_followup_sweep(config, runtime, limit=args.limit))
        return 0
    if args.command == "all":
        path = extract_followup_directions(
            config, runtime, force=args.fresh or args.force_directions
        )
        stats = run_followup_sweep(config, runtime, limit=args.limit)
        result: dict[str, Any] = {
            "direction_artifact": str(path),
            "fresh_removed": removed,
            "run": stats,
        }
        if args.limit is None and stats["already_complete"] + stats["written"] == stats["planned"]:
            result["analysis"] = analyze_followup(config)
        else:
            result["analysis"] = "skipped because the sweep is incomplete"
        _print(result)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
