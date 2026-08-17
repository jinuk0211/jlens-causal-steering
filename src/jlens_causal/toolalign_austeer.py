"""AUSteer attention-unit extraction and ToolAlign trajectory evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

from jlens_causal.baselines import (
    austeer_units_by_layer,
    build_austeer_artifact,
    load_austeer_artifact,
    save_austeer_artifact,
)
from jlens_causal.modeling import ModelRuntime, render_conversation
from jlens_causal.steering_config import ToolAlignAUSteerConfig
from jlens_causal.toolalign import ScenarioCase, messages_for_case
from jlens_causal.toolalign_caa import (
    AUSteerRolloutIntervention,
    _append_jsonl,
    _case_id,
    _selected_cases,
    divergent_response_pairs,
    read_jsonl,
    run_toolalign_rollout,
)
from jlens_causal.toolalign_transition_analysis import (
    paired_toolalign_transitions,
    write_toolalign_analysis,
)


def _output_projections(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        attention = getattr(block, "self_attn", None)
        module = getattr(attention, "o_proj", None)
        if module is None:
            raise ValueError(f"model layer {index} has no self-attention output projection")
        modules.append(module)
    return modules


@contextmanager
def _capture_projection_inputs(modules: list[Any], layers: Iterable[int]):
    captured: dict[int, Any] = {}
    handles = []
    try:
        for value in layers:
            layer = int(value)

            def hook(_module: Any, inputs: Any, *, selected_layer: int = layer) -> None:
                captured[selected_layer] = inputs[0].detach()
                return None

            handles.append(modules[layer].register_forward_pre_hook(hook))
        yield captured
    finally:
        for handle in reversed(handles):
            handle.remove()


def _teacher_forced_austeer_activations(
    runtime: ModelRuntime,
    *,
    messages: list[dict[str, str]],
    layers: Iterable[int],
) -> dict[int, Any]:
    response_index = len(messages) - 1
    rendered = render_conversation(
        runtime,
        messages,
        message_indices=[response_index],
        add_generation_prompt=False,
    )
    position = rendered.message_positions[response_index][-1]
    with (
        runtime.torch.inference_mode(),
        _capture_projection_inputs(_output_projections(runtime), layers) as activations,
    ):
        runtime.lens_model.forward(rendered.input_ids)
    return {
        int(layer): activations[int(layer)][0, position].detach().float().cpu() for layer in layers
    }


def _pair_activations(
    config: ToolAlignAUSteerConfig,
    runtime: ModelRuntime,
    *,
    split: str,
    pairs: list[dict[str, Any]],
    layers: tuple[int, ...],
) -> tuple[dict[int, list[Any]], dict[int, list[Any]]]:
    common, cases = _selected_cases(config, split=split)
    case_by_id: dict[str, ScenarioCase] = {_case_id(case): case for case in cases}
    correct: dict[int, list[Any]] = {layer: [] for layer in layers}
    failure: dict[int, list[Any]] = {layer: [] for layer in layers}
    for pair in pairs:
        case = case_by_id[pair["pair_id"]]
        prompt = messages_for_case(common, case, config.condition)
        correct_values = _teacher_forced_austeer_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["positive_response"]}],
            layers=layers,
        )
        failure_values = _teacher_forced_austeer_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["negative_response"]}],
            layers=layers,
        )
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    return correct, failure


def extract_toolalign_austeer(
    config: ToolAlignAUSteerConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    """Select model-specific AUSteer AUs without using evaluation examples."""
    train_pairs = divergent_response_pairs(config, split="calibration")
    validation_pairs = divergent_response_pairs(config, split="au_validation")
    if len(train_pairs) < int(config.extraction["minimum_train_pairs"]):
        raise ValueError("too few divergent AUSteer training response pairs")
    if len(validation_pairs) < int(config.extraction["minimum_validation_pairs"]):
        raise ValueError("too few divergent AUSteer AU-validation response pairs")
    path = config.artifact_path(role)
    if path.is_file() and not force:
        artifact = load_austeer_artifact(
            runtime.torch,
            path,
            expected_model_id=config.models[role]["model_id"],
        )
        return {
            "train_pair_count": len(train_pairs),
            "validation_pair_count": len(validation_pairs),
            "selected_unit_count": int(artifact["top_k"]),
            "validation_sign_agreement_count": int(artifact["validation_sign_agreement_count"]),
            "path": str(path),
        }
    layers = tuple(int(value) for value in config.extraction["layers"])
    train_correct, train_failure = _pair_activations(
        config, runtime, split="calibration", pairs=train_pairs, layers=layers
    )
    validation_correct, validation_failure = _pair_activations(
        config,
        runtime,
        split="au_validation",
        pairs=validation_pairs,
        layers=layers,
    )
    model = config.models[role]
    artifact = build_austeer_artifact(
        runtime.torch,
        model_id=model["model_id"],
        model_revision=model["model_revision"],
        train_correct_by_layer=train_correct,
        train_failure_by_layer=train_failure,
        validation_correct_by_layer=validation_correct,
        validation_failure_by_layer=validation_failure,
        train_pair_ids=[pair["pair_id"] for pair in train_pairs],
        validation_pair_ids=[pair["pair_id"] for pair in validation_pairs],
        top_k=int(config.extraction["max_top_k"]),
        benchmark="toolalign",
        calibration_split={
            "train_domains": config.data["calibration_domains"],
            "au_validation_domains": config.data["au_validation_domains"],
            "evaluation_domains": config.data["evaluation_domains"],
            "condition": config.condition,
            "pair_selection": "strict_aligned_vs_abliterated_divergence",
            "hyperparameter_selection": "preregistered_grid_not_evaluation_tuned",
            "config_fingerprint": config.config_fingerprint,
        },
        site=config.extraction["site"],
        source=config.raw["source"],
    )
    save_austeer_artifact(runtime.torch, artifact, path)
    return {
        "train_pair_count": len(train_pairs),
        "validation_pair_count": len(validation_pairs),
        "selected_unit_count": int(artifact["top_k"]),
        "validation_sign_agreement_count": int(artifact["validation_sign_agreement_count"]),
        "path": str(path),
    }


def _fingerprint_entries(torch: Any, entries: dict[int, tuple[tuple[int, float], ...]]) -> str:
    flattened = [
        value
        for layer, units in sorted(entries.items())
        for dimension, beta in units
        for value in (float(layer), float(dimension), float(beta))
    ]
    tensor = torch.tensor(flattened, dtype=torch.float32)
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def _random_au_entries(
    torch: Any,
    artifact: dict[str, Any],
    *,
    count: int,
    seed: int,
) -> dict[int, tuple[tuple[int, float], ...]]:
    selected = {tuple(value) for value in artifact["selected_units"].tolist()}
    candidates = [
        (int(layer), dimension)
        for layer in artifact["layers"]
        for dimension in range(int(artifact["d_model"]))
        if (int(layer), dimension) not in selected
    ]
    if count > len(candidates):
        raise ValueError("not enough non-selected AUs for the random control")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    chosen = torch.randperm(len(candidates), generator=generator)[:count].tolist()
    grouped: dict[int, list[tuple[int, float]]] = {}
    for index, candidate_index in enumerate(chosen):
        layer, dimension = candidates[candidate_index]
        grouped.setdefault(layer, []).append((dimension, float(artifact["selected_betas"][index])))
    return {layer: tuple(values) for layer, values in grouped.items()}


def _austeer_interventions(
    config: ToolAlignAUSteerConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, AUSteerRolloutIntervention | None]]:
    artifact = load_austeer_artifact(
        runtime.torch,
        config.artifact_path(role),
        expected_model_id=config.models[role]["model_id"],
    )
    specs: list[tuple[str, int | None, float, AUSteerRolloutIntervention | None]] = [
        ("baseline", None, 0.0, None)
    ]
    for top_k_value in config.sweep["top_k_values"]:
        top_k = int(top_k_value)
        entries = austeer_units_by_layer(artifact, top_k=top_k)
        fingerprint = _fingerprint_entries(runtime.torch, entries)
        for alpha_value in config.sweep["alphas"]:
            alpha = float(alpha_value)
            specs.append(
                (
                    "austeer",
                    top_k,
                    alpha,
                    AUSteerRolloutIntervention(
                        method="austeer",
                        units_by_layer=entries,
                        alpha=alpha,
                        top_k=top_k,
                        vector_fingerprint=fingerprint,
                    ),
                )
            )
    primary_top_k = int(config.sweep["primary_top_k"])
    primary_alpha = float(config.sweep["primary_alpha"])
    primary_entries = austeer_units_by_layer(artifact, top_k=primary_top_k)
    primary_fingerprint = _fingerprint_entries(runtime.torch, primary_entries)
    specs.extend(
        [
            (
                "austeer_negative",
                primary_top_k,
                -primary_alpha,
                AUSteerRolloutIntervention(
                    method="austeer_negative",
                    units_by_layer=primary_entries,
                    alpha=-primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                ),
            ),
            (
                "austeer_decision_only",
                primary_top_k,
                primary_alpha,
                AUSteerRolloutIntervention(
                    method="austeer_decision_only",
                    units_by_layer=primary_entries,
                    alpha=primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                    prefill_mode="decision_only",
                ),
            ),
        ]
    )
    for seed_value in config.sweep["random_seeds"]:
        seed = int(seed_value)
        entries = _random_au_entries(runtime.torch, artifact, count=primary_top_k, seed=seed)
        specs.append(
            (
                "austeer_random_aus",
                primary_top_k,
                primary_alpha,
                AUSteerRolloutIntervention(
                    method="austeer_random_aus",
                    units_by_layer=entries,
                    alpha=primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=_fingerprint_entries(runtime.torch, entries),
                    control_seed=seed,
                ),
            )
        )
    return specs


def run_toolalign_austeer_sweep(
    config: ToolAlignAUSteerConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    common, cases = _selected_cases(config, split="evaluation")
    specs = _austeer_interventions(config, runtime, role=role)
    path = config.sweep_path(role)
    existing = read_jsonl(path)
    if any(record.get("config_fingerprint") != config.config_fingerprint for record in existing):
        raise ValueError(f"stale sweep records in {path}; move or remove the file")
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, top_k, alpha, intervention in specs:
            seed = intervention.control_seed if intervention else None
            run_id = f"sweep:{role}:{_case_id(case)}:{method}:{top_k}:{alpha:g}:{seed}"
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
            _append_jsonl(
                path,
                {
                    **rollout,
                    "run_id": run_id,
                    "config_fingerprint": config.config_fingerprint,
                    "split": "evaluation",
                    "model_role": role,
                    "model_id": config.models[role]["model_id"],
                    "requested_revision": config.models[role]["model_revision"],
                    "resolved_revision": getattr(runtime.hf_model.config, "_commit_hash", None),
                    "method": method,
                    "top_k": top_k,
                    "alpha": alpha,
                    "random_seed": seed,
                },
            )
            completed.add(run_id)
            written += 1
            if limit is not None and written >= limit:
                return {
                    "path": str(path),
                    "planned": len(cases) * len(specs),
                    "already_complete": len(existing),
                    "written": written,
                }
    return {
        "path": str(path),
        "planned": len(cases) * len(specs),
        "already_complete": len(existing),
        "written": written,
    }


def analyze_toolalign_austeer(config: ToolAlignAUSteerConfig, *, role: str) -> dict[str, Any]:
    records = read_jsonl(config.sweep_path(role))

    def case_key(value: dict[str, Any]) -> tuple[str, int, str]:
        return str(value["domain"]), int(value["document"]), str(value["scenario_type"])

    baselines = {
        case_key(record): record for record in records if record.get("method") == "baseline"
    }
    grouped: dict[tuple[str, int | None, float, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            str(record["method"]),
            int(record["top_k"]) if record.get("top_k") is not None else None,
            float(record["alpha"]),
            str(record["scenario_type"]),
        )
        grouped.setdefault(key, []).append(record)
    rows = []
    for (method, top_k, alpha, scenario), values in sorted(
        grouped.items(), key=lambda item: str(item[0])
    ):
        valid = [value for value in values if value["behavior"].get("valid_for_pairing")]
        transitions: dict[str, int] = {}
        for value in values:
            baseline = baselines.get(case_key(value))
            if baseline is not None:
                label = (
                    f"{baseline['behavior']['behavior_class']}"
                    f"->{value['behavior']['behavior_class']}"
                )
                transitions[label] = transitions.get(label, 0) + 1
        traces = [
            step["intervention"]
            for value in values
            for step in value.get("steps", [])
            if step["intervention"].get("active")
        ]
        rows.append(
            {
                "method": method,
                "top_k": top_k,
                "alpha": alpha,
                "scenario_type": scenario,
                "n": len(values),
                "valid_n": len(valid),
                "aligned_rate": (
                    sum(item["behavior"]["behavior_class"] == "aligned" for item in valid)
                    / len(valid)
                    if valid
                    else None
                ),
                "misaligned_rate": (
                    sum(item["behavior"]["behavior_class"] == "misaligned" for item in valid)
                    / len(valid)
                    if valid
                    else None
                ),
                "tool_call_loop_rate": (
                    sum(item["stop_reason"] == "tool_call_loop" for item in values) / len(values)
                    if values
                    else None
                ),
                "applied_scalar_count": sum(
                    int(trace.get("applied_prefill_scalars", 0))
                    + int(trace.get("applied_decode_scalars", 0))
                    for trace in traces
                ),
                "transitions_from_baseline": transitions,
            }
        )
    result = {
        "schema_version": "toolalign-austeer-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "role": role,
        "source_path": str(config.sweep_path(role)),
        "rows": rows,
        "paired_transitions": paired_toolalign_transitions(
            records, role=role, parameter_fields=("top_k", "alpha", "random_seed")
        ),
    }
    result["output_path"] = str(
        write_toolalign_analysis(config.output_dir / "analysis" / f"{role}.json", result)
    )
    return result
