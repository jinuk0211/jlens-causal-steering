"""CLI for generalized TauBench failure localization and replay planning."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jlens_causal.failure_cast import (
    build_failure_cast_condition_pairs,
    write_failure_cast_condition_pairs,
)
from jlens_causal.failure_events import (
    build_replay_plan,
    detect_failures,
    load_results,
    merge_results,
    read_events,
    summarize_failures,
    write_events,
)
from jlens_causal.failure_pairs import (
    build_failure_response_pairs,
    read_repairs,
    write_failure_response_pairs,
)
from jlens_causal.failure_repairs import (
    Tau2AirlineRepairRuntime,
    generate_validated_repairs,
)
from jlens_causal.failure_steering import (
    compile_failure_steering_matrix,
    load_failure_steering_manifest,
    write_failure_steering_matrix,
)


def _write_json(path: str | Path, value: Any) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jlens-failures",
        description=(
            "Normalize Tau2 review labels and deterministic trajectory failures without "
            "task- or turn-specific configuration."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)

    detect = commands.add_parser("detect", help="create failure events from results JSON")
    detect.add_argument("results")
    detect.add_argument("--output", required=True)
    detect.add_argument("--summary")

    plan = commands.add_parser("plan", help="create paired replay/control conditions")
    plan.add_argument("results")
    plan.add_argument("events")
    plan.add_argument("--output", required=True)
    plan.add_argument("--seed", type=int, default=42)
    plan.add_argument("--minimum-confidence", type=float, default=0.5)

    audit = commands.add_parser("audit", help="detect failures and build a replay plan")
    audit.add_argument("results")
    audit.add_argument("--output-dir", required=True)
    audit.add_argument("--seed", type=int, default=42)
    audit.add_argument("--minimum-confidence", type=float, default=0.5)
    compile_command = commands.add_parser(
        "compile", help="compile a remote-only Core-7 failure steering matrix"
    )
    compile_command.add_argument("manifest")
    compile_command.add_argument("--output", required=True)
    pairs = commands.add_parser(
        "pairs", help="join validated counterfactual repairs to train/validation failures"
    )
    pairs.add_argument("results")
    pairs.add_argument("events")
    pairs.add_argument("repairs")
    pairs.add_argument("manifest")
    pairs.add_argument("--output", required=True)
    pairs.add_argument("--output-category")
    repairs = commands.add_parser(
        "repairs",
        help="generate counterfactual repairs and validate them with Tau2 replay",
    )
    repairs.add_argument("results")
    repairs.add_argument("events")
    repairs.add_argument("manifest")
    repairs.add_argument("--output", required=True)
    repairs.add_argument("--report")
    repairs.add_argument("--pairs-output")
    repairs.add_argument("--category", default="retry_without_state_change")
    repairs.add_argument(
        "--categories",
        nargs="+",
        help="source failure categories to pool; defaults to --category",
    )
    repairs.add_argument(
        "--output-category",
        help="category label written to pooled repair pairs; defaults to --category",
    )
    repairs.add_argument(
        "--seed-repairs",
        action="append",
        default=[],
        help="reuse validated repair checkpoints from an earlier compatible run",
    )
    repairs.add_argument("--proposal-model", default="gpt-5.2")
    repairs.add_argument("--review-model", default="gpt-4.1-2025-04-14")
    repairs.add_argument("--reasoning-effort", default="low")
    repairs.add_argument("--minimum-confidence", type=float, default=0.5)
    repairs.add_argument("--max-attempts", type=int, default=3)
    repairs.add_argument("--minimum-per-split", type=int, default=2)
    repairs.add_argument("--maximum-per-split", type=int, default=0)
    repairs.add_argument("--review-tpm", type=int, default=27_000)
    repairs.add_argument("--api-retries", type=int, default=6)
    repairs.add_argument("--overwrite", action="store_true")
    cast_conditions = commands.add_parser(
        "cast-conditions",
        help="build prospective CAST risk/control contexts at the same boundary",
    )
    cast_conditions.add_argument("results")
    cast_conditions.add_argument("events")
    cast_conditions.add_argument("manifest")
    cast_conditions.add_argument("--category", required=True)
    cast_conditions.add_argument("--output", required=True)
    merge = commands.add_parser(
        "merge", help="merge reviewed train/validation result shards losslessly"
    )
    merge.add_argument("results", nargs="+")
    merge.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "compile":
        manifest = load_failure_steering_manifest(args.manifest)
        matrix = compile_failure_steering_matrix(manifest)
        output = write_failure_steering_matrix(args.output, matrix)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "manifest_fingerprint": manifest.fingerprint,
                    "matrix_fingerprint": matrix["matrix_fingerprint"],
                    "conditions": len(matrix["conditions"]),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "merge":
        merged = merge_results([load_results(path) for path in args.results])
        output = _write_json(args.output, merged)
        print(
            json.dumps(
                {"output": str(output), "simulations": len(merged["simulations"])},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    results = load_results(args.results)
    if args.command == "repairs":
        manifest = load_failure_steering_manifest(args.manifest)
        events = read_events(args.events)
        report_path = args.report or str(Path(args.output).with_suffix(".report.json"))
        runtime = Tau2AirlineRepairRuntime(
            results,
            proposal_model=args.proposal_model,
            review_model=args.review_model,
            reasoning_effort=args.reasoning_effort,
            review_tpm=args.review_tpm,
            api_retries=args.api_retries,
        )
        report = generate_validated_repairs(
            results,
            events,
            runtime,
            output=args.output,
            report=report_path,
            category=args.category,
            categories=args.categories,
            output_category=args.output_category,
            train_task_ids=manifest.train_task_ids,
            validation_task_ids=manifest.validation_task_ids,
            evaluation_task_ids=manifest.evaluation_task_ids,
            minimum_confidence=args.minimum_confidence,
            max_attempts=args.max_attempts,
            minimum_per_split=args.minimum_per_split,
            maximum_per_split=args.maximum_per_split,
            overwrite=args.overwrite,
            seed_repairs=[repair for path in args.seed_repairs for repair in read_repairs(path)],
        )
        summary: dict[str, Any] = {
            "output": str(Path(args.output).expanduser().resolve()),
            "report": str(Path(report_path).expanduser().resolve()),
            "accepted": report["accepted"],
            "complete": report["complete"],
        }
        if args.pairs_output:
            pairs = build_failure_response_pairs(
                results,
                events,
                read_repairs(args.output),
                train_task_ids=manifest.train_task_ids,
                validation_task_ids=manifest.validation_task_ids,
                evaluation_task_ids=manifest.evaluation_task_ids,
                failure_category=args.output_category,
            )
            output = write_failure_response_pairs(args.pairs_output, pairs)
            summary["pairs_output"] = str(output)
            summary["pairs"] = len(pairs)
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "cast-conditions":
        manifest = load_failure_steering_manifest(args.manifest)
        cast_pairs = build_failure_cast_condition_pairs(
            results,
            read_events(args.events),
            failure_category=args.category,
            train_task_ids=manifest.train_task_ids,
            validation_task_ids=manifest.validation_task_ids,
            evaluation_task_ids=manifest.evaluation_task_ids,
        )
        output = write_failure_cast_condition_pairs(args.output, cast_pairs)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "pairs": len(cast_pairs),
                    "train_pairs": sum(pair["split"] == "train" for pair in cast_pairs),
                    "validation_pairs": sum(pair["split"] == "validation" for pair in cast_pairs),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "pairs":
        manifest = load_failure_steering_manifest(args.manifest)
        pairs = build_failure_response_pairs(
            results,
            read_events(args.events),
            read_repairs(args.repairs),
            train_task_ids=manifest.train_task_ids,
            validation_task_ids=manifest.validation_task_ids,
            evaluation_task_ids=manifest.evaluation_task_ids,
            failure_category=args.output_category,
        )
        output = write_failure_response_pairs(args.output, pairs)
        print(
            json.dumps(
                {
                    "output": str(output),
                    "pairs": len(pairs),
                    "train_pairs": sum(pair["split"] == "train" for pair in pairs),
                    "validation_pairs": sum(pair["split"] == "validation" for pair in pairs),
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.command == "detect":
        events = detect_failures(results)
        event_path = write_events(args.output, events)
        summary = summarize_failures(events)
        summary["events_path"] = str(event_path)
        if args.summary:
            summary["summary_path"] = str(_write_json(args.summary, summary))
        print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    if args.command == "plan":
        plan = build_replay_plan(
            results,
            read_events(args.events),
            seed=args.seed,
            minimum_confidence=args.minimum_confidence,
        )
        output = _write_json(args.output, plan)
        print(
            json.dumps({"output": str(output), "simulations": len(plan["simulations"])}, indent=2)
        )
        return 0
    if args.command == "audit":
        output_dir = Path(args.output_dir).expanduser().resolve()
        events = detect_failures(results)
        event_path = write_events(output_dir / "failure-events.jsonl", events)
        summary = summarize_failures(events)
        summary_path = _write_json(output_dir / "failure-summary.json", summary)
        plan = build_replay_plan(
            results,
            events,
            seed=args.seed,
            minimum_confidence=args.minimum_confidence,
        )
        plan_path = _write_json(output_dir / "replay-plan.json", plan)
        print(
            json.dumps(
                {
                    "events": str(event_path),
                    "summary": str(summary_path),
                    "plan": str(plan_path),
                    **summary,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
