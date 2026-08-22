"""Failure-mode adaptive J-Lens steering for matched ToolAlign trajectories."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jlens_causal.jservo import (
    build_jservo_artifact,
    build_jservo_mode,
    load_jservo_artifact,
    save_jservo_artifact,
)
from jlens_causal.modeling import ModelRuntime
from jlens_causal.steering_config import ToolAlignCAAConfig
from jlens_causal.toolalign import messages_for_case
from jlens_causal.toolalign_caa import (
    JServoRolloutIntervention,
    _append_jsonl,
    _case_id,
    _selected_cases,
    _teacher_forced_last_response_activations,
    divergent_response_pairs,
    read_jsonl,
    run_toolalign_rollout,
)
from jlens_causal.toolalign_transition_analysis import (
    paired_toolalign_transitions,
    write_toolalign_analysis,
)


def artifact_path(config: ToolAlignCAAConfig, role: str) -> Path:
    if role not in config.models:
        raise ValueError(f"unknown ToolAlign model role {role!r}")
    return config.output_dir / "jservo" / "artifacts" / role / "jservo.pt"


def sweep_path(config: ToolAlignCAAConfig, role: str) -> Path:
    if role not in config.models:
        raise ValueError(f"unknown ToolAlign model role {role!r}")
    return config.output_dir / "jservo" / "sweeps" / f"{role}.jsonl"


def _capture_split(
    config: ToolAlignCAAConfig,
    runtime: ModelRuntime,
    *,
    split: str,
    layers: tuple[int, ...],
) -> tuple[list[str], dict[int, list[Any]], dict[int, list[Any]]]:
    pairs = divergent_response_pairs(config, split=split)
    common, cases = _selected_cases(config, split=split)
    by_id = {_case_id(case): case for case in cases}
    correct = {layer: [] for layer in layers}
    failure = {layer: [] for layer in layers}
    ids: list[str] = []
    for pair in pairs:
        case = by_id[pair["pair_id"]]
        base = messages_for_case(common, case, config.condition)
        correct_values = _teacher_forced_last_response_activations(
            runtime,
            messages=[
                *base,
                {"role": "assistant", "content": pair["positive_response"]},
            ],
            layers=layers,
        )
        failure_values = _teacher_forced_last_response_activations(
            runtime,
            messages=[
                *base,
                {"role": "assistant", "content": pair["negative_response"]},
            ],
            layers=layers,
        )
        ids.append(str(pair["pair_id"]))
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    return ids, correct, failure


def extract_toolalign_jservo(
    config: ToolAlignCAAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    """Fit a role-local controller without using held-out evaluation cases."""
    model = config.models[role]
    output = artifact_path(config, role)
    if output.is_file() and not force:
        artifact = load_jservo_artifact(
            runtime.torch,
            output,
            expected_model_id=model["model_id"],
            expected_model_revision=model["model_revision"],
        )
        return {
            "path": str(output),
            "artifact_fingerprint": artifact["artifact_fingerprint"],
            "status": "already_complete",
        }
    if "probe_validation_domains" not in config.data:
        raise ValueError(
            "ToolAlign J-Servo requires disjoint data.probe_validation_domains"
        )
    domain_splits = [
        set(config.data[key])
        for key in (
            "calibration_domains",
            "probe_validation_domains",
            "evaluation_domains",
        )
    ]
    if any(
        domain_splits[index].intersection(domain_splits[other])
        for index in range(len(domain_splits))
        for other in range(index + 1, len(domain_splits))
    ):
        raise ValueError("ToolAlign J-Servo train/validation/evaluation domains overlap")
    observation_layers = tuple(
        int(value)
        for value in config.raw.get("jservo", {}).get("observation_layers", [16])
    )
    control_layers = tuple(
        int(value)
        for value in config.raw.get("jservo", {}).get("control_layers", [20, 24])
    )
    layers = tuple(dict.fromkeys([*observation_layers, *control_layers]))
    train_ids, train_correct, train_failure = _capture_split(
        config, runtime, split="calibration", layers=layers
    )
    validation_ids, validation_correct, validation_failure = _capture_split(
        config, runtime, split="probe_validation", layers=layers
    )
    settings = config.raw.get("jservo", {})
    minimum_train = int(settings.get("minimum_train_pairs", 4))
    minimum_validation = int(settings.get("minimum_validation_pairs", 2))
    if len(train_ids) < minimum_train or len(validation_ids) < minimum_validation:
        raise ValueError(
            "insufficient matched ToolAlign pairs: "
            f"train={len(train_ids)}/{minimum_train}, "
            f"validation={len(validation_ids)}/{minimum_validation}"
        )
    unembedding = runtime.hf_model.get_output_embeddings().weight.detach().float().cpu()
    token_texts = [
        str(value)
        for value in runtime.tokenizer.convert_ids_to_tokens(range(int(unembedding.shape[0])))
    ]
    mode = build_jservo_mode(
        runtime.torch,
        failure_category="toolalign_value_routing",
        correct_behavior="route wrongdoing evidence to the aligned action",
        train_correct_by_layer=train_correct,
        train_failure_by_layer=train_failure,
        validation_correct_by_layer=validation_correct,
        validation_failure_by_layer=validation_failure,
        jacobians={
            layer: runtime.lens.jacobians[layer].detach().float().cpu()
            for layer in layers
        },
        unembedding=unembedding,
        token_texts=token_texts,
        observation_layers=observation_layers,
        control_layers=control_layers,
        train_pair_ids=train_ids,
        validation_pair_ids=validation_ids,
        bundle_size=int(settings.get("bundle_size", 8)),
        protected_size=int(settings.get("protected_size", 8)),
        minimum_consistency=float(settings.get("minimum_consistency", 0.7)),
        random_seed=int(config.generation.get("seed", 42)),
    )
    artifact = build_jservo_artifact(
        model_id=model["model_id"],
        model_revision=model["model_revision"],
        lens_revision=getattr(runtime.lens, "revision", None),
        benchmark="toolalign-matched-value-routing",
        modes=[mode],
        calibration={
            "config_fingerprint": config.config_fingerprint,
            "selection": "aligned_non_misaligned_minus_abliterated_misaligned",
            "train_split": "calibration",
            "validation_split": "probe_validation",
            "train_pair_count": len(train_ids),
            "validation_pair_count": len(validation_ids),
            "evaluation_pairs_used": False,
            "gold_task_labels_used": False,
            "external_llm_judge_used": False,
        },
    )
    save_jservo_artifact(runtime.torch, artifact, output)
    return {
        "path": str(output),
        "artifact_fingerprint": artifact["artifact_fingerprint"],
        "train_pairs": len(train_ids),
        "validation_pairs": len(validation_ids),
        "steering_eligible": mode["steering_eligible"],
        "target_tokens": mode["token_bundles"]["target"],
        "source_tokens": mode["token_bundles"]["source"],
    }


def _sweep_specs(
    config: ToolAlignCAAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, JServoRolloutIntervention | None, dict[str, Any]]]:
    artifact = load_jservo_artifact(
        runtime.torch,
        artifact_path(config, role),
        expected_model_id=config.models[role]["model_id"],
        expected_model_revision=config.models[role]["model_revision"],
    )
    mode = artifact["modes"]["toolalign_value_routing"]
    primary_layer = int(mode["control_layers"][0])

    def controller(control_type: str, **kwargs: Any) -> JServoRolloutIntervention:
        return JServoRolloutIntervention(
            method="jservo",
            artifact=artifact,
            control_type=control_type,
            **kwargs,
        )

    specs: list[tuple[str, JServoRolloutIntervention | None, dict[str, Any]]] = [
        ("baseline", None, {"control_type": "none"}),
        ("jservo_adaptive", controller("targeted"), {"control_type": "targeted"}),
        (
            "jservo_fixed_layer",
            controller("fixed_layer", layer_override=primary_layer),
            {"control_type": "fixed_layer", "layer_override": primary_layer},
        ),
        (
            "jservo_fixed_jlens",
            controller(
                "fixed_strength",
                fixed_strength=0.1,
                layer_override=primary_layer,
            ),
            {
                "control_type": "fixed_strength",
                "fixed_strength": 0.1,
                "layer_override": primary_layer,
            },
        ),
        (
            "jservo_wrong_mode",
            controller("wrong_mode", mode_override="unmatched_failure_mode"),
            {"control_type": "wrong_mode"},
        ),
        ("jservo_random", controller("random"), {"control_type": "random"}),
        ("jservo_reverse", controller("reverse"), {"control_type": "reverse"}),
        (
            "jservo_validator_only",
            controller("validator_only"),
            {"control_type": "validator_only"},
        ),
    ]
    fixed_strengths = config.raw.get("jservo", {}).get("fixed_strengths", [0.05, 0.1])
    for strength in fixed_strengths:
        specs.append(
            (
                "jservo_fixed_strength",
                controller("fixed_strength", fixed_strength=float(strength)),
                {"control_type": "fixed_strength", "fixed_strength": float(strength)},
            )
        )
    return specs


def run_toolalign_jservo_sweep(
    config: ToolAlignCAAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run recovery, damage, and matched controls on held-out cases only."""
    common, cases = _selected_cases(config, split="evaluation")
    specs = _sweep_specs(config, runtime, role=role)
    output = sweep_path(config, role)
    existing = read_jsonl(output)
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, intervention, parameters in specs:
            parameter_key = json.dumps(parameters, sort_keys=True, separators=(",", ":"))
            run_id = f"jservo:{role}:{_case_id(case)}:{method}:{parameter_key}"
            if run_id in completed:
                continue
            rollout = run_toolalign_rollout(
                runtime,
                common=common,
                case=case,
                condition=config.condition,
                generation_config=config.generation,
                intervention=intervention,
            )
            record = {
                **rollout,
                "run_id": run_id,
                "config_fingerprint": config.config_fingerprint,
                "split": "evaluation",
                "model_role": role,
                "model_id": config.models[role]["model_id"],
                "requested_revision": config.models[role]["model_revision"],
                "resolved_revision": getattr(runtime.hf_model.config, "_commit_hash", None),
                "method": method,
                **parameters,
            }
            _append_jsonl(output, record)
            completed.add(run_id)
            written += 1
            if limit is not None and written >= limit:
                return {
                    "path": str(output),
                    "planned": len(cases) * len(specs),
                    "written": written,
                    "already_complete": len(existing),
                }
    return {
        "path": str(output),
        "planned": len(cases) * len(specs),
        "written": written,
        "already_complete": len(existing),
    }


def analyze_toolalign_jservo(
    config: ToolAlignCAAConfig,
    *,
    role: str,
) -> dict[str, Any]:
    records = read_jsonl(sweep_path(config, role))
    if not records:
        raise ValueError(f"no ToolAlign J-Servo sweep records for {role}")
    paired = paired_toolalign_transitions(
        records,
        role=role,
        parameter_fields=("control_type", "layer_override", "fixed_strength"),
    )
    telemetry = []
    for record in records:
        if record.get("method") == "baseline":
            continue
        traces = [step.get("intervention") or {} for step in record.get("steps") or []]
        validations = [
            step.get("candidate_validation") or {} for step in record.get("steps") or []
        ]
        telemetry.append(
            {
                "run_id": record["run_id"],
                "method": record["method"],
                "cumulative_dose": sum(float(trace.get("cumulative_dose", 0.0)) for trace in traces),
                "intervention_tokens": sum(int(trace.get("applied_positions", 0)) for trace in traces),
                "abstained": int(record.get("stop_reason") == "abstained"),
                "loop": int(record.get("stop_reason") == "tool_call_loop"),
                "truncated": int(any(step.get("truncated") for step in record.get("steps") or [])),
                "parse_failure": int(record.get("stop_reason") == "no_tool_call"),
                "validator_failure": int(any(not item.get("valid", True) for item in validations)),
            }
        )
    result = {
        "schema_version": "toolalign-jservo-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "model_role": role,
        "paired_transitions": paired,
        "telemetry": telemetry,
        "claims_status": "pending_experiment_completion",
    }
    output = config.output_dir / "jservo" / "analysis" / f"{role}.json"
    write_toolalign_analysis(output, result)
    return {
        "output_path": str(output),
        "paired_trials": paired["paired_trials"],
        "summary": paired["summary"],
    }
