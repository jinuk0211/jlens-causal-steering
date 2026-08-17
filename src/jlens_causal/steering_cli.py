"""CLI for sequential published-baseline integration."""

from __future__ import annotations

import argparse
import json
from typing import Any

from jlens_causal.modeling import load_hf_runtime
from jlens_causal.steering_config import (
    load_toolalign_austeer_config,
    load_toolalign_caa_config,
    load_toolalign_cast_config,
    load_toolalign_iti_config,
    load_toolalign_loreft_config,
    load_toolalign_mera_config,
    load_toolalign_sadi_config,
)
from jlens_causal.taubench_austeer import (
    extract_taubench_task18_austeer,
    load_taubench_austeer_config,
)
from jlens_causal.taubench_caa import (
    extract_taubench_task18_caa,
    load_taubench_caa_config,
)
from jlens_causal.taubench_cast import (
    extract_taubench_task18_cast,
    load_taubench_cast_config,
)
from jlens_causal.taubench_iti import (
    extract_taubench_task18_iti,
    load_taubench_iti_config,
)
from jlens_causal.taubench_loreft import (
    load_taubench_loreft_config,
    train_taubench_task18_loreft,
)
from jlens_causal.taubench_mera import (
    extract_taubench_task18_mera,
    load_taubench_mera_config,
)
from jlens_causal.taubench_sadi import (
    extract_taubench_task18_sadi,
    load_taubench_sadi_config,
)
from jlens_causal.toolalign_austeer import (
    analyze_toolalign_austeer,
    extract_toolalign_austeer,
    run_toolalign_austeer_sweep,
)
from jlens_causal.toolalign_caa import (
    _selected_cases,
    analyze_caa_sweep,
    divergent_calibration_pairs,
    divergent_response_pairs,
    extract_caa_directions,
    run_baseline_rollouts,
    run_caa_sweep,
)
from jlens_causal.toolalign_cast import (
    analyze_toolalign_cast,
    extract_toolalign_cast,
    run_toolalign_cast_sweep,
)
from jlens_causal.toolalign_iti import (
    analyze_toolalign_iti,
    extract_toolalign_iti,
    run_toolalign_iti_sweep,
)
from jlens_causal.toolalign_loreft import (
    analyze_toolalign_loreft,
    run_toolalign_loreft_sweep,
    train_toolalign_loreft,
)
from jlens_causal.toolalign_mera import (
    analyze_toolalign_mera,
    extract_toolalign_mera,
    run_toolalign_mera_sweep,
)
from jlens_causal.toolalign_sadi import (
    analyze_toolalign_sadi,
    extract_toolalign_sadi,
    run_toolalign_sadi_sweep,
)


def _print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agent-steering",
        description="Run CAA and later Core-7 baselines on agent benchmarks.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate-toolalign-caa")
    validate.add_argument("config")
    baseline = commands.add_parser("toolalign-baseline")
    baseline.add_argument("config")
    baseline.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    baseline.add_argument("--limit", type=int)
    pairs = commands.add_parser("toolalign-pairs")
    pairs.add_argument("config")
    extract = commands.add_parser("toolalign-extract-caa")
    extract.add_argument("config")
    extract.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    extract.add_argument("--force", action="store_true")
    sweep = commands.add_parser("toolalign-sweep-caa")
    sweep.add_argument("config")
    sweep.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    sweep.add_argument("--limit", type=int)
    analyze = commands.add_parser("toolalign-analyze-caa")
    analyze.add_argument("config")
    analyze.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    validate_cast = commands.add_parser("validate-toolalign-cast")
    validate_cast.add_argument("config")
    baseline_cast = commands.add_parser("toolalign-baseline-cast")
    baseline_cast.add_argument("config")
    baseline_cast.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    baseline_cast.add_argument("--limit", type=int)
    pairs_cast = commands.add_parser("toolalign-pairs-cast")
    pairs_cast.add_argument("config")
    extract_cast = commands.add_parser("toolalign-extract-cast")
    extract_cast.add_argument("config")
    extract_cast.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    extract_cast.add_argument("--force", action="store_true")
    sweep_cast = commands.add_parser("toolalign-sweep-cast")
    sweep_cast.add_argument("config")
    sweep_cast.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    sweep_cast.add_argument("--limit", type=int)
    analyze_cast = commands.add_parser("toolalign-analyze-cast")
    analyze_cast.add_argument("config")
    analyze_cast.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    validate_mera = commands.add_parser("validate-toolalign-mera")
    validate_mera.add_argument("config")
    baseline_mera = commands.add_parser("toolalign-baseline-mera")
    baseline_mera.add_argument("config")
    baseline_mera.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    baseline_mera.add_argument("--limit", type=int)
    pairs_mera = commands.add_parser("toolalign-pairs-mera")
    pairs_mera.add_argument("config")
    extract_mera = commands.add_parser("toolalign-extract-mera")
    extract_mera.add_argument("config")
    extract_mera.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    extract_mera.add_argument("--force", action="store_true")
    sweep_mera = commands.add_parser("toolalign-sweep-mera")
    sweep_mera.add_argument("config")
    sweep_mera.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    sweep_mera.add_argument("--limit", type=int)
    analyze_mera = commands.add_parser("toolalign-analyze-mera")
    analyze_mera.add_argument("config")
    analyze_mera.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    validate_sadi = commands.add_parser("validate-toolalign-sadi")
    validate_sadi.add_argument("config")
    baseline_sadi = commands.add_parser("toolalign-baseline-sadi")
    baseline_sadi.add_argument("config")
    baseline_sadi.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    baseline_sadi.add_argument("--limit", type=int)
    pairs_sadi = commands.add_parser("toolalign-pairs-sadi")
    pairs_sadi.add_argument("config")
    extract_sadi = commands.add_parser("toolalign-extract-sadi")
    extract_sadi.add_argument("config")
    extract_sadi.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    extract_sadi.add_argument("--force", action="store_true")
    sweep_sadi = commands.add_parser("toolalign-sweep-sadi")
    sweep_sadi.add_argument("config")
    sweep_sadi.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    sweep_sadi.add_argument("--limit", type=int)
    analyze_sadi = commands.add_parser("toolalign-analyze-sadi")
    analyze_sadi.add_argument("config")
    analyze_sadi.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    validate_iti = commands.add_parser("validate-toolalign-iti")
    validate_iti.add_argument("config")
    baseline_iti = commands.add_parser("toolalign-baseline-iti")
    baseline_iti.add_argument("config")
    baseline_iti.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    baseline_iti.add_argument("--limit", type=int)
    pairs_iti = commands.add_parser("toolalign-pairs-iti")
    pairs_iti.add_argument("config")
    extract_iti = commands.add_parser("toolalign-extract-iti")
    extract_iti.add_argument("config")
    extract_iti.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    extract_iti.add_argument("--force", action="store_true")
    sweep_iti = commands.add_parser("toolalign-sweep-iti")
    sweep_iti.add_argument("config")
    sweep_iti.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    sweep_iti.add_argument("--limit", type=int)
    analyze_iti = commands.add_parser("toolalign-analyze-iti")
    analyze_iti.add_argument("config")
    analyze_iti.add_argument("--role", required=True, choices=["aligned", "abliterated"])
    validate_austeer = commands.add_parser("validate-toolalign-austeer")
    validate_austeer.add_argument("config")
    baseline_austeer = commands.add_parser("toolalign-baseline-austeer")
    baseline_austeer.add_argument("config")
    baseline_austeer.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    baseline_austeer.add_argument("--limit", type=int)
    pairs_austeer = commands.add_parser("toolalign-pairs-austeer")
    pairs_austeer.add_argument("config")
    extract_austeer = commands.add_parser("toolalign-extract-austeer")
    extract_austeer.add_argument("config")
    extract_austeer.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    extract_austeer.add_argument("--force", action="store_true")
    sweep_austeer = commands.add_parser("toolalign-sweep-austeer")
    sweep_austeer.add_argument("config")
    sweep_austeer.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    sweep_austeer.add_argument("--limit", type=int)
    analyze_austeer = commands.add_parser("toolalign-analyze-austeer")
    analyze_austeer.add_argument("config")
    analyze_austeer.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    validate_loreft = commands.add_parser("validate-toolalign-loreft")
    validate_loreft.add_argument("config")
    baseline_loreft = commands.add_parser("toolalign-baseline-loreft")
    baseline_loreft.add_argument("config")
    baseline_loreft.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    baseline_loreft.add_argument("--limit", type=int)
    pairs_loreft = commands.add_parser("toolalign-pairs-loreft")
    pairs_loreft.add_argument("config")
    train_loreft = commands.add_parser("toolalign-train-loreft")
    train_loreft.add_argument("config")
    train_loreft.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    train_loreft.add_argument("--force", action="store_true")
    sweep_loreft = commands.add_parser("toolalign-sweep-loreft")
    sweep_loreft.add_argument("config")
    sweep_loreft.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    sweep_loreft.add_argument("--limit", type=int)
    analyze_loreft = commands.add_parser("toolalign-analyze-loreft")
    analyze_loreft.add_argument("config")
    analyze_loreft.add_argument(
        "--role", required=True, choices=["aligned", "abliterated"]
    )
    validate_tau = commands.add_parser("validate-taubench-caa")
    validate_tau.add_argument("config")
    extract_tau = commands.add_parser("taubench-extract-caa")
    extract_tau.add_argument("config")
    extract_tau.add_argument("--force", action="store_true")
    validate_tau_cast = commands.add_parser("validate-taubench-cast")
    validate_tau_cast.add_argument("config")
    extract_tau_cast = commands.add_parser("taubench-extract-cast")
    extract_tau_cast.add_argument("config")
    extract_tau_cast.add_argument("--force", action="store_true")
    validate_tau_mera = commands.add_parser("validate-taubench-mera")
    validate_tau_mera.add_argument("config")
    extract_tau_mera = commands.add_parser("taubench-extract-mera")
    extract_tau_mera.add_argument("config")
    extract_tau_mera.add_argument("--force", action="store_true")
    validate_tau_sadi = commands.add_parser("validate-taubench-sadi")
    validate_tau_sadi.add_argument("config")
    extract_tau_sadi = commands.add_parser("taubench-extract-sadi")
    extract_tau_sadi.add_argument("config")
    extract_tau_sadi.add_argument("--force", action="store_true")
    validate_tau_iti = commands.add_parser("validate-taubench-iti")
    validate_tau_iti.add_argument("config")
    extract_tau_iti = commands.add_parser("taubench-extract-iti")
    extract_tau_iti.add_argument("config")
    extract_tau_iti.add_argument("--force", action="store_true")
    validate_tau_austeer = commands.add_parser("validate-taubench-austeer")
    validate_tau_austeer.add_argument("config")
    extract_tau_austeer = commands.add_parser("taubench-extract-austeer")
    extract_tau_austeer.add_argument("config")
    extract_tau_austeer.add_argument("--force", action="store_true")
    validate_tau_loreft = commands.add_parser("validate-taubench-loreft")
    validate_tau_loreft.add_argument("config")
    train_tau_loreft = commands.add_parser("taubench-train-loreft")
    train_tau_loreft.add_argument("config")
    train_tau_loreft.add_argument("--force", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command in {"validate-taubench-loreft", "taubench-train-loreft"}:
        tau_loreft_config = load_taubench_loreft_config(args.config)
        if args.command == "validate-taubench-loreft":
            _print(
                {
                    "config": str(tau_loreft_config.path),
                    "model": tau_loreft_config.model,
                    "source_meta_path": str(tau_loreft_config.source_meta_path),
                    "behavior_source_config": str(
                        tau_loreft_config.behavior_config.path
                    ),
                    "task_id": tau_loreft_config.raw["task_id"],
                    "causal_turn_index": tau_loreft_config.raw[
                        "causal_turn_index"
                    ],
                    "causal_boundary": tau_loreft_config.raw["causal_boundary"],
                    "layers": tau_loreft_config.training["layers"],
                    "ranks": tau_loreft_config.training["ranks"],
                    "train_pair_indices": tau_loreft_config.training[
                        "train_pair_indices"
                    ],
                    "validation_pair_indices": tau_loreft_config.training[
                        "validation_pair_indices"
                    ],
                    "output_dir": str(tau_loreft_config.output_dir),
                    "source": tau_loreft_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_loreft_config.model)
        _print(
            train_taubench_task18_loreft(
                tau_loreft_config, runtime, force=args.force
            )
        )
        return 0
    if args.command in {
        "validate-toolalign-loreft",
        "toolalign-baseline-loreft",
        "toolalign-pairs-loreft",
        "toolalign-train-loreft",
        "toolalign-sweep-loreft",
        "toolalign-analyze-loreft",
    }:
        loreft_config = load_toolalign_loreft_config(args.config)
        if args.command == "validate-toolalign-loreft":
            selections = {}
            for split in ("calibration", "reft_validation", "evaluation"):
                _, cases = _selected_cases(loreft_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(loreft_config.path),
                    "config_fingerprint": loreft_config.config_fingerprint,
                    "toolalign_root": str(loreft_config.toolalign_root),
                    "output_dir": str(loreft_config.output_dir),
                    "selected_cases": selections,
                    "layers": loreft_config.training["layers"],
                    "ranks": loreft_config.training["ranks"],
                    "source": loreft_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-loreft":
            _print(
                {
                    split: divergent_response_pairs(loreft_config, split=split)
                    for split in ("calibration", "reft_validation")
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-loreft":
            _print(analyze_toolalign_loreft(loreft_config, role=role))
            return 0
        runtime = load_hf_runtime(loreft_config.models[role])
        if args.command == "toolalign-baseline-loreft":
            _print(
                run_baseline_rollouts(
                    loreft_config, runtime, role=role, limit=args.limit
                )
            )
            return 0
        if args.command == "toolalign-train-loreft":
            _print(
                train_toolalign_loreft(
                    loreft_config, runtime, role=role, force=args.force
                )
            )
            return 0
        if args.command == "toolalign-sweep-loreft":
            _print(
                run_toolalign_loreft_sweep(
                    loreft_config, runtime, role=role, limit=args.limit
                )
            )
            return 0
        raise AssertionError(f"unhandled LoReFT command {args.command}")
    if args.command in {"validate-taubench-austeer", "taubench-extract-austeer"}:
        tau_austeer_config = load_taubench_austeer_config(args.config)
        if args.command == "validate-taubench-austeer":
            _print(
                {
                    "config": str(tau_austeer_config.path),
                    "model": tau_austeer_config.model,
                    "source_meta_path": str(tau_austeer_config.source_meta_path),
                    "behavior_source_config": str(
                        tau_austeer_config.behavior_config.path
                    ),
                    "task_id": tau_austeer_config.raw["task_id"],
                    "causal_turn_index": tau_austeer_config.raw[
                        "causal_turn_index"
                    ],
                    "causal_boundary": tau_austeer_config.raw["causal_boundary"],
                    "layers": tau_austeer_config.extraction["layers"],
                    "train_pair_indices": tau_austeer_config.extraction[
                        "train_pair_indices"
                    ],
                    "validation_pair_indices": tau_austeer_config.extraction[
                        "validation_pair_indices"
                    ],
                    "top_k_values": tau_austeer_config.raw["sweep"][
                        "top_k_values"
                    ],
                    "alphas": tau_austeer_config.raw["sweep"]["alphas"],
                    "output_dir": str(tau_austeer_config.output_dir),
                    "source": tau_austeer_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_austeer_config.model)
        _print(
            extract_taubench_task18_austeer(
                tau_austeer_config, runtime, force=args.force
            )
        )
        return 0
    if args.command in {
        "validate-toolalign-austeer",
        "toolalign-baseline-austeer",
        "toolalign-pairs-austeer",
        "toolalign-extract-austeer",
        "toolalign-sweep-austeer",
        "toolalign-analyze-austeer",
    }:
        austeer_config = load_toolalign_austeer_config(args.config)
        if args.command == "validate-toolalign-austeer":
            selections = {}
            for split in ("calibration", "au_validation", "evaluation"):
                _, cases = _selected_cases(austeer_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(austeer_config.path),
                    "config_fingerprint": austeer_config.config_fingerprint,
                    "toolalign_root": str(austeer_config.toolalign_root),
                    "output_dir": str(austeer_config.output_dir),
                    "selected_cases": selections,
                    "layers": austeer_config.extraction["layers"],
                    "top_k_values": austeer_config.sweep["top_k_values"],
                    "alphas": austeer_config.sweep["alphas"],
                    "source": austeer_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-austeer":
            _print(
                {
                    split: divergent_response_pairs(austeer_config, split=split)
                    for split in ("calibration", "au_validation")
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-austeer":
            _print(analyze_toolalign_austeer(austeer_config, role=role))
            return 0
        runtime = load_hf_runtime(austeer_config.models[role])
        if args.command == "toolalign-baseline-austeer":
            _print(
                run_baseline_rollouts(
                    austeer_config, runtime, role=role, limit=args.limit
                )
            )
            return 0
        if args.command == "toolalign-extract-austeer":
            _print(
                extract_toolalign_austeer(
                    austeer_config, runtime, role=role, force=args.force
                )
            )
            return 0
        if args.command == "toolalign-sweep-austeer":
            _print(
                run_toolalign_austeer_sweep(
                    austeer_config, runtime, role=role, limit=args.limit
                )
            )
            return 0
        raise AssertionError(f"unhandled AUSteer command {args.command}")
    if args.command in {
        "validate-toolalign-iti",
        "toolalign-baseline-iti",
        "toolalign-pairs-iti",
        "toolalign-extract-iti",
        "toolalign-sweep-iti",
        "toolalign-analyze-iti",
    }:
        iti_config = load_toolalign_iti_config(args.config)
        if args.command == "validate-toolalign-iti":
            selections = {}
            for split in ("calibration", "head_validation", "evaluation"):
                _, cases = _selected_cases(iti_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(iti_config.path),
                    "config_fingerprint": iti_config.config_fingerprint,
                    "toolalign_root": str(iti_config.toolalign_root),
                    "output_dir": str(iti_config.output_dir),
                    "selected_cases": selections,
                    "layers": iti_config.extraction["layers"],
                    "top_k_values": iti_config.sweep["top_k_values"],
                    "alphas": iti_config.sweep["alphas"],
                    "source": iti_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-iti":
            _print(
                {
                    split: divergent_response_pairs(iti_config, split=split)
                    for split in ("calibration", "head_validation")
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-iti":
            _print(analyze_toolalign_iti(iti_config, role=role))
            return 0
        runtime = load_hf_runtime(iti_config.models[role])
        if args.command == "toolalign-baseline-iti":
            _print(run_baseline_rollouts(iti_config, runtime, role=role, limit=args.limit))
            return 0
        if args.command == "toolalign-extract-iti":
            _print(extract_toolalign_iti(iti_config, runtime, role=role, force=args.force))
            return 0
        if args.command == "toolalign-sweep-iti":
            _print(run_toolalign_iti_sweep(iti_config, runtime, role=role, limit=args.limit))
            return 0
        raise AssertionError(f"unhandled ITI command {args.command}")
    if args.command in {"validate-taubench-iti", "taubench-extract-iti"}:
        tau_iti_config = load_taubench_iti_config(args.config)
        if args.command == "validate-taubench-iti":
            _print(
                {
                    "config": str(tau_iti_config.path),
                    "model": tau_iti_config.model,
                    "source_meta_path": str(tau_iti_config.source_meta_path),
                    "behavior_source_config": str(tau_iti_config.behavior_config.path),
                    "task_id": tau_iti_config.raw["task_id"],
                    "causal_turn_index": tau_iti_config.raw["causal_turn_index"],
                    "causal_boundary": tau_iti_config.raw["causal_boundary"],
                    "layers": tau_iti_config.extraction["layers"],
                    "train_pair_indices": tau_iti_config.extraction["train_pair_indices"],
                    "validation_pair_indices": tau_iti_config.extraction[
                        "validation_pair_indices"
                    ],
                    "top_k_values": tau_iti_config.raw["sweep"]["top_k_values"],
                    "alphas": tau_iti_config.raw["sweep"]["alphas"],
                    "output_dir": str(tau_iti_config.output_dir),
                    "source": tau_iti_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_iti_config.model)
        _print(
            extract_taubench_task18_iti(
                tau_iti_config,
                runtime,
                force=args.force,
            )
        )
        return 0
    if args.command in {
        "validate-toolalign-sadi",
        "toolalign-baseline-sadi",
        "toolalign-pairs-sadi",
        "toolalign-extract-sadi",
        "toolalign-sweep-sadi",
        "toolalign-analyze-sadi",
    }:
        sadi_config = load_toolalign_sadi_config(args.config)
        if args.command == "validate-toolalign-sadi":
            selections = {}
            for split in ("calibration", "unit_validation", "evaluation"):
                _, cases = _selected_cases(sadi_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(sadi_config.path),
                    "config_fingerprint": sadi_config.config_fingerprint,
                    "toolalign_root": str(sadi_config.toolalign_root),
                    "output_dir": str(sadi_config.output_dir),
                    "selected_cases": selections,
                    "layers": sadi_config.extraction["layers"],
                    "top_k_values": sadi_config.sweep["top_k_values"],
                    "strengths": sadi_config.sweep["strengths"],
                    "source": sadi_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-sadi":
            _print(
                {
                    split: divergent_response_pairs(sadi_config, split=split)
                    for split in ("calibration", "unit_validation")
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-sadi":
            _print(analyze_toolalign_sadi(sadi_config, role=role))
            return 0
        runtime = load_hf_runtime(sadi_config.models[role])
        if args.command == "toolalign-baseline-sadi":
            _print(run_baseline_rollouts(sadi_config, runtime, role=role, limit=args.limit))
            return 0
        if args.command == "toolalign-extract-sadi":
            _print(extract_toolalign_sadi(sadi_config, runtime, role=role, force=args.force))
            return 0
        if args.command == "toolalign-sweep-sadi":
            _print(run_toolalign_sadi_sweep(sadi_config, runtime, role=role, limit=args.limit))
            return 0
        raise AssertionError(f"unhandled SADI command {args.command}")
    if args.command in {"validate-taubench-sadi", "taubench-extract-sadi"}:
        tau_sadi_config = load_taubench_sadi_config(args.config)
        if args.command == "validate-taubench-sadi":
            _print(
                {
                    "config": str(tau_sadi_config.path),
                    "model": tau_sadi_config.model,
                    "source_meta_path": str(tau_sadi_config.source_meta_path),
                    "behavior_source_config": str(tau_sadi_config.behavior_config.path),
                    "task_id": tau_sadi_config.raw["task_id"],
                    "causal_turn_index": tau_sadi_config.raw["causal_turn_index"],
                    "causal_boundary": tau_sadi_config.raw["causal_boundary"],
                    "layers": tau_sadi_config.extraction["layers"],
                    "train_pair_indices": tau_sadi_config.extraction["train_pair_indices"],
                    "validation_pair_indices": tau_sadi_config.extraction[
                        "validation_pair_indices"
                    ],
                    "top_k_values": tau_sadi_config.raw["sweep"]["top_k_values"],
                    "strengths": tau_sadi_config.raw["sweep"]["strengths"],
                    "output_dir": str(tau_sadi_config.output_dir),
                    "source": tau_sadi_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_sadi_config.model)
        _print(
            extract_taubench_task18_sadi(
                tau_sadi_config,
                runtime,
                force=args.force,
            )
        )
        return 0
    if args.command in {"validate-taubench-mera", "taubench-extract-mera"}:
        tau_mera_config = load_taubench_mera_config(args.config)
        if args.command == "validate-taubench-mera":
            _print(
                {
                    "config": str(tau_mera_config.path),
                    "model": tau_mera_config.model,
                    "source_meta_path": str(tau_mera_config.source_meta_path),
                    "behavior_source_config": str(
                        tau_mera_config.behavior_config.path
                    ),
                    "task_id": tau_mera_config.raw["task_id"],
                    "causal_turn_index": tau_mera_config.raw["causal_turn_index"],
                    "causal_boundary": tau_mera_config.raw["causal_boundary"],
                    "layers": tau_mera_config.extraction["layers"],
                    "train_pair_indices": tau_mera_config.extraction[
                        "train_pair_indices"
                    ],
                    "validation_pair_indices": tau_mera_config.extraction[
                        "validation_pair_indices"
                    ],
                    "alpha_grid": tau_mera_config.extraction["alpha_grid"],
                    "output_dir": str(tau_mera_config.output_dir),
                    "source": tau_mera_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_mera_config.model)
        _print(
            extract_taubench_task18_mera(
                tau_mera_config,
                runtime,
                force=args.force,
            )
        )
        return 0
    if args.command in {"validate-taubench-cast", "taubench-extract-cast"}:
        tau_cast_config = load_taubench_cast_config(args.config)
        if args.command == "validate-taubench-cast":
            _print(
                {
                    "config": str(tau_cast_config.path),
                    "model": tau_cast_config.model,
                    "source_meta_path": str(tau_cast_config.source_meta_path),
                    "behavior_source_config": str(
                        tau_cast_config.behavior_config.path
                    ),
                    "task_id": tau_cast_config.raw["task_id"],
                    "causal_turn_index": tau_cast_config.raw["causal_turn_index"],
                    "causal_boundary": tau_cast_config.raw["causal_boundary"],
                    "behavior_layers": tau_cast_config.extraction["behavior_layers"],
                    "condition_layers": tau_cast_config.extraction["condition_layers"],
                    "condition_pair_count": len(
                        tau_cast_config.extraction["condition_train"]["positive"]
                    ),
                    "gate_pair_count": len(
                        tau_cast_config.extraction["gate_validation"]["positive"]
                    ),
                    "output_dir": str(tau_cast_config.output_dir),
                    "source": tau_cast_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_cast_config.model)
        _print(
            extract_taubench_task18_cast(
                tau_cast_config,
                runtime,
                force=args.force,
            )
        )
        return 0
    if args.command in {"validate-taubench-caa", "taubench-extract-caa"}:
        tau_config = load_taubench_caa_config(args.config)
        if args.command == "validate-taubench-caa":
            _print(
                {
                    "config": str(tau_config.path),
                    "model": tau_config.model,
                    "source_meta_path": str(tau_config.source_meta_path),
                    "task_id": tau_config.raw["task_id"],
                    "causal_turn_index": tau_config.raw["causal_turn_index"],
                    "causal_boundary": tau_config.raw["causal_boundary"],
                    "layers": tau_config.extraction["layers"],
                    "pair_count": len(tau_config.extraction["positive_responses"]),
                    "output_dir": str(tau_config.output_dir),
                    "status": "valid",
                }
            )
            return 0
        runtime = load_hf_runtime(tau_config.model)
        _print(
            extract_taubench_task18_caa(
                tau_config,
                runtime,
                force=args.force,
            )
        )
        return 0
    if args.command in {
        "validate-toolalign-cast",
        "toolalign-baseline-cast",
        "toolalign-pairs-cast",
        "toolalign-extract-cast",
        "toolalign-sweep-cast",
        "toolalign-analyze-cast",
    }:
        cast_config = load_toolalign_cast_config(args.config)
        if args.command == "validate-toolalign-cast":
            selections = {}
            for split in ("calibration", "evaluation"):
                _, cases = _selected_cases(cast_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(cast_config.path),
                    "config_fingerprint": cast_config.config_fingerprint,
                    "toolalign_root": str(cast_config.toolalign_root),
                    "output_dir": str(cast_config.output_dir),
                    "selected_cases": selections,
                    "behavior_layers": cast_config.extraction["behavior_layers"],
                    "condition_layers": cast_config.extraction["condition_layers"],
                    "gate_validation_domains": cast_config.data["gate_validation_domains"],
                    "source": cast_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-cast":
            pairs = divergent_calibration_pairs(cast_config)
            _print(
                {
                    "pair_count": len(pairs),
                    "minimum_required": cast_config.extraction["minimum_behavior_pairs"],
                    "pairs": pairs,
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-cast":
            _print(analyze_toolalign_cast(cast_config, role=role))
            return 0
        runtime = load_hf_runtime(cast_config.models[role])
        if args.command == "toolalign-baseline-cast":
            _print(run_baseline_rollouts(cast_config, runtime, role=role, limit=args.limit))
            return 0
        if args.command == "toolalign-extract-cast":
            _print(extract_toolalign_cast(cast_config, runtime, role=role, force=args.force))
            return 0
        if args.command == "toolalign-sweep-cast":
            _print(run_toolalign_cast_sweep(cast_config, runtime, role=role, limit=args.limit))
            return 0
        raise AssertionError(f"unhandled CAST command {args.command}")
    if args.command in {
        "validate-toolalign-mera",
        "toolalign-baseline-mera",
        "toolalign-pairs-mera",
        "toolalign-extract-mera",
        "toolalign-sweep-mera",
        "toolalign-analyze-mera",
    }:
        mera_config = load_toolalign_mera_config(args.config)
        if args.command == "validate-toolalign-mera":
            selections = {}
            for split in ("calibration", "probe_validation", "evaluation"):
                _, cases = _selected_cases(mera_config, split=split)
                selections[split] = len(cases)
            _print(
                {
                    "config": str(mera_config.path),
                    "config_fingerprint": mera_config.config_fingerprint,
                    "toolalign_root": str(mera_config.toolalign_root),
                    "output_dir": str(mera_config.output_dir),
                    "selected_cases": selections,
                    "layers": mera_config.extraction["layers"],
                    "alpha_grid": mera_config.extraction["alpha_grid"],
                    "source": mera_config.raw["source"],
                    "status": "valid",
                }
            )
            return 0
        if args.command == "toolalign-pairs-mera":
            _print(
                {
                    split: divergent_response_pairs(mera_config, split=split)
                    for split in ("calibration", "probe_validation")
                }
            )
            return 0
        role = args.role
        if args.command == "toolalign-analyze-mera":
            _print(analyze_toolalign_mera(mera_config, role=role))
            return 0
        runtime = load_hf_runtime(mera_config.models[role])
        if args.command == "toolalign-baseline-mera":
            _print(run_baseline_rollouts(mera_config, runtime, role=role, limit=args.limit))
            return 0
        if args.command == "toolalign-extract-mera":
            _print(extract_toolalign_mera(mera_config, runtime, role=role, force=args.force))
            return 0
        if args.command == "toolalign-sweep-mera":
            _print(run_toolalign_mera_sweep(mera_config, runtime, role=role, limit=args.limit))
            return 0
        raise AssertionError(f"unhandled MERA command {args.command}")
    config = load_toolalign_caa_config(args.config)
    if args.command == "validate-toolalign-caa":
        selections = {}
        for split in ("calibration", "evaluation"):
            _, cases = _selected_cases(config, split=split)
            selections[split] = len(cases)
        _print(
            {
                "config": str(config.path),
                "config_fingerprint": config.config_fingerprint,
                "toolalign_root": str(config.toolalign_root),
                "output_dir": str(config.output_dir),
                "models": config.models,
                "selected_cases": selections,
                "extraction_layers": config.extraction["layers"],
                "status": "valid",
            }
        )
        return 0
    if args.command == "toolalign-pairs":
        pairs = divergent_calibration_pairs(config)
        _print(
            {
                "pair_count": len(pairs),
                "minimum_required": config.extraction["minimum_pairs"],
                "pairs": pairs,
            }
        )
        return 0
    role = args.role
    if args.command == "toolalign-analyze-caa":
        _print(analyze_caa_sweep(config, role=role))
        return 0
    runtime = load_hf_runtime(config.models[role])
    if args.command == "toolalign-baseline":
        _print(run_baseline_rollouts(config, runtime, role=role, limit=args.limit))
        return 0
    if args.command == "toolalign-extract-caa":
        _print(extract_caa_directions(config, runtime, role=role, force=args.force))
        return 0
    if args.command == "toolalign-sweep-caa":
        _print(run_caa_sweep(config, runtime, role=role, limit=args.limit))
        return 0
    raise AssertionError(f"unhandled command {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
