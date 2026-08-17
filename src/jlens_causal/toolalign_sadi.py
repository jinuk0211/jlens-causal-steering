"""SADI hidden-unit extraction and ToolAlign trajectory evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from jlens_causal.baselines import (
    build_sadi_artifact,
    load_sadi_artifact,
    sadi_units_by_layer,
    save_sadi_artifact,
)
from jlens_causal.modeling import ModelRuntime, capture_block_outputs, render_conversation
from jlens_causal.steering_config import ToolAlignSADIConfig
from jlens_causal.toolalign import ScenarioCase, messages_for_case
from jlens_causal.toolalign_caa import (
    SadiRolloutIntervention,
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


def _sadi_modules(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        module = getattr(block, "mlp", None)
        if module is None:
            raise ValueError(f"model layer {index} has no MLP module for SADI")
        modules.append(module)
    return modules


def _teacher_forced_sadi_activations(
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
    modules = _sadi_modules(runtime)
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(modules, layers) as activations,
    ):
        runtime.lens_model.forward(rendered.input_ids)
    return {
        int(layer): activations[int(layer)][0, position].detach().float().cpu() for layer in layers
    }


def _pair_activations(
    config: ToolAlignSADIConfig,
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
        correct_values = _teacher_forced_sadi_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["positive_response"]}],
            layers=layers,
        )
        failure_values = _teacher_forced_sadi_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["negative_response"]}],
            layers=layers,
        )
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    return correct, failure


def extract_toolalign_sadi(
    config: ToolAlignSADIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    """Select checkpoint-specific SADI units without tuning on evaluation data."""
    train_pairs = divergent_response_pairs(config, split="calibration")
    validation_pairs = divergent_response_pairs(config, split="unit_validation")
    if len(train_pairs) < int(config.extraction["minimum_train_pairs"]):
        raise ValueError("too few divergent SADI training response pairs")
    if len(validation_pairs) < int(config.extraction["minimum_validation_pairs"]):
        raise ValueError("too few divergent SADI validation response pairs")
    path = config.artifact_path(role)
    if path.is_file() and not force:
        artifact = load_sadi_artifact(
            runtime.torch,
            path,
            expected_model_id=config.models[role]["model_id"],
        )
        return {
            "train_pair_count": len(train_pairs),
            "validation_pair_count": len(validation_pairs),
            "validation_positive_selected_count": artifact["validation_positive_selected_count"],
            "path": str(path),
        }
    layers = tuple(int(value) for value in config.extraction["layers"])
    train_correct, train_failure = _pair_activations(
        config,
        runtime,
        split="calibration",
        pairs=train_pairs,
        layers=layers,
    )
    validation_correct, validation_failure = _pair_activations(
        config,
        runtime,
        split="unit_validation",
        pairs=validation_pairs,
        layers=layers,
    )
    model = config.models[role]
    artifact = build_sadi_artifact(
        runtime.torch,
        model_id=model["model_id"],
        model_revision=model["model_revision"],
        correct_by_layer=train_correct,
        failure_by_layer=train_failure,
        pair_ids=[pair["pair_id"] for pair in train_pairs],
        top_k=int(config.extraction["max_top_k"]),
        benchmark="toolalign",
        calibration_split={
            "train_domains": config.data["calibration_domains"],
            "unit_validation_domains": config.data["unit_validation_domains"],
            "evaluation_domains": config.data["evaluation_domains"],
            "condition": config.condition,
            "pair_selection": "strict_aligned_vs_abliterated_divergence",
            "strength_selection": "preregistered_grid_not_evaluation_tuned",
            "config_fingerprint": config.config_fingerprint,
        },
        site=config.extraction["site"],
        source=config.raw["source"],
        validation_correct_by_layer=validation_correct,
        validation_failure_by_layer=validation_failure,
        validation_pair_ids=[pair["pair_id"] for pair in validation_pairs],
    )
    save_sadi_artifact(runtime.torch, artifact, path)
    return {
        "train_pair_count": len(train_pairs),
        "validation_pair_count": len(validation_pairs),
        "selected_unit_count": artifact["top_k"],
        "validation_positive_selected_count": artifact["validation_positive_selected_count"],
        "path": str(path),
    }


def _tensor_fingerprint(tensor: Any) -> str:
    payload = tensor.detach().contiguous().cpu().numpy().tobytes()
    return hashlib.sha256(payload).hexdigest()


def _units_tensor_to_groups(units: Any) -> dict[int, tuple[int, ...]]:
    grouped: dict[int, list[int]] = {}
    for layer, dimension in units.tolist():
        grouped.setdefault(int(layer), []).append(int(dimension))
    return {layer: tuple(values) for layer, values in grouped.items()}


def _random_units(torch: Any, artifact: dict[str, Any], *, count: int, seed: int) -> Any:
    layers = [int(value) for value in artifact["layers"]]
    d_model = int(artifact["d_model"])
    selected = {tuple(value) for value in artifact["selected_units"].tolist()}
    available = [
        (layer, dimension)
        for layer in layers
        for dimension in range(d_model)
        if (layer, dimension) not in selected
    ]
    if count > len(available):
        raise ValueError("not enough non-SADI units for the random control")
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    indices = torch.randperm(len(available), generator=generator)[:count].tolist()
    return torch.tensor([available[index] for index in indices], dtype=torch.int64)


def _sadi_interventions(
    config: ToolAlignSADIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, SadiRolloutIntervention | None]]:
    artifact = load_sadi_artifact(
        runtime.torch,
        config.artifact_path(role),
        expected_model_id=config.models[role]["model_id"],
    )
    specs: list[tuple[str, int | None, float, SadiRolloutIntervention | None]] = [
        ("baseline", None, 1.0, None)
    ]
    for top_k in config.sweep["top_k_values"]:
        top_k = int(top_k)
        groups = sadi_units_by_layer(artifact, top_k=top_k)
        selected_fingerprint = _tensor_fingerprint(artifact["selected_units"][:top_k])
        for strength in config.sweep["strengths"]:
            strength = float(strength)
            specs.append(
                (
                    "sadi",
                    top_k,
                    strength,
                    SadiRolloutIntervention(
                        method="sadi",
                        units_by_layer=groups,
                        strength=strength,
                        top_k=top_k,
                        vector_fingerprint=selected_fingerprint,
                    ),
                )
            )
    primary_top_k = int(config.sweep["primary_top_k"])
    primary_strength = float(config.sweep["primary_strength"])
    primary_groups = sadi_units_by_layer(artifact, top_k=primary_top_k)
    primary_fingerprint = _tensor_fingerprint(artifact["selected_units"][:primary_top_k])
    specs.extend(
        [
            (
                "sadi_selected_ablation",
                primary_top_k,
                0.0,
                SadiRolloutIntervention(
                    method="sadi_selected_ablation",
                    units_by_layer=primary_groups,
                    strength=0.0,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                ),
            ),
            (
                "sadi_decode_dynamic_extension",
                primary_top_k,
                primary_strength,
                SadiRolloutIntervention(
                    method="sadi_decode_dynamic_extension",
                    units_by_layer=primary_groups,
                    strength=primary_strength,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                    apply_decode=True,
                ),
            ),
        ]
    )
    for seed in config.sweep["random_seeds"]:
        units = _random_units(runtime.torch, artifact, count=primary_top_k, seed=int(seed))
        specs.append(
            (
                "sadi_random_units",
                primary_top_k,
                primary_strength,
                SadiRolloutIntervention(
                    method="sadi_random_units",
                    units_by_layer=_units_tensor_to_groups(units),
                    strength=primary_strength,
                    top_k=primary_top_k,
                    vector_fingerprint=_tensor_fingerprint(units),
                    control_seed=int(seed),
                ),
            )
        )
    return specs


def run_toolalign_sadi_sweep(
    config: ToolAlignSADIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    common, cases = _selected_cases(config, split="evaluation")
    specs = _sadi_interventions(config, runtime, role=role)
    path = config.sweep_path(role)
    existing = read_jsonl(path)
    if any(record.get("config_fingerprint") != config.config_fingerprint for record in existing):
        raise ValueError(f"stale sweep records in {path}; move or remove the file")
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, top_k, strength, intervention in specs:
            seed = intervention.control_seed if intervention else None
            run_id = f"sweep:{role}:{_case_id(case)}:{method}:{top_k}:{strength:g}:{seed}"
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
                    "strength": strength,
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


def analyze_toolalign_sadi(
    config: ToolAlignSADIConfig,
    *,
    role: str,
) -> dict[str, Any]:
    records = read_jsonl(config.sweep_path(role))

    def case_key(value: dict[str, Any]) -> tuple[str, int, str]:
        return (
            str(value["domain"]),
            int(value["document"]),
            str(value["scenario_type"]),
        )

    baselines = {
        case_key(record): record for record in records if record.get("method") == "baseline"
    }
    grouped: dict[tuple[str, int | None, float, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            str(record["method"]),
            int(record["top_k"]) if record.get("top_k") is not None else None,
            float(record["strength"]),
            str(record["scenario_type"]),
        )
        grouped.setdefault(key, []).append(record)
    rows = []
    for (method, top_k, strength, scenario), values in sorted(
        grouped.items(), key=lambda item: str(item[0])
    ):
        valid = [value for value in values if value["behavior"].get("valid_for_pairing")]
        transition_counts: dict[str, int] = {}
        for value in values:
            baseline = baselines.get(case_key(value))
            if baseline is None:
                continue
            transition = (
                f"{baseline['behavior']['behavior_class']}->{value['behavior']['behavior_class']}"
            )
            transition_counts[transition] = transition_counts.get(transition, 0) + 1
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
                "strength": strength,
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
                "transitions_from_baseline": transition_counts,
            }
        )
    result = {
        "schema_version": "toolalign-sadi-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "role": role,
        "source_path": str(config.sweep_path(role)),
        "rows": rows,
        "paired_transitions": paired_toolalign_transitions(
            records, role=role, parameter_fields=("top_k", "strength", "random_seed")
        ),
    }
    result["output_path"] = str(
        write_toolalign_analysis(config.output_dir / "analysis" / f"{role}.json", result)
    )
    return result
