"""MERA error-probe extraction and ToolAlign trajectory evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from jlens_causal.baselines import (
    build_mera_artifact,
    load_mera_artifact,
    save_mera_artifact,
)
from jlens_causal.modeling import ModelRuntime, capture_block_outputs, render_conversation
from jlens_causal.steering_config import ToolAlignMERAConfig
from jlens_causal.toolalign import ScenarioCase, messages_for_case
from jlens_causal.toolalign_caa import (
    MeraRolloutIntervention,
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


def _mera_modules(runtime: ModelRuntime) -> list[Any]:
    modules = []
    for index, block in enumerate(runtime.lens_model.layers):
        module = getattr(block, "post_attention_layernorm", None)
        if module is None:
            raise ValueError(f"model layer {index} has no post_attention_layernorm for MERA")
        modules.append(module)
    return modules


def _teacher_forced_mera_activations(
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
    modules = _mera_modules(runtime)
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(modules, layers) as activations,
    ):
        runtime.lens_model.forward(rendered.input_ids)
    return {
        int(layer): activations[int(layer)][0, position].detach().float().cpu() for layer in layers
    }


def _pair_activations(
    config: ToolAlignMERAConfig,
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
        correct_values = _teacher_forced_mera_activations(
            runtime,
            messages=[
                *prompt,
                {"role": "assistant", "content": pair["positive_response"]},
            ],
            layers=layers,
        )
        failure_values = _teacher_forced_mera_activations(
            runtime,
            messages=[
                *prompt,
                {"role": "assistant", "content": pair["negative_response"]},
            ],
            layers=layers,
        )
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    return correct, failure


def extract_toolalign_mera(
    config: ToolAlignMERAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    """Fit and held-out-calibrate checkpoint-specific MERA probes."""
    train_pairs = divergent_response_pairs(config, split="calibration")
    validation_pairs = divergent_response_pairs(config, split="probe_validation")
    if len(train_pairs) < int(config.extraction["minimum_train_pairs"]):
        raise ValueError("too few divergent MERA training response pairs")
    if len(validation_pairs) < int(config.extraction["minimum_validation_pairs"]):
        raise ValueError("too few divergent MERA validation response pairs")
    layers = tuple(int(value) for value in config.extraction["layers"])
    paths = [config.artifact_path(role, layer) for layer in layers]
    if not force and all(path.is_file() for path in paths):
        return {
            "train_pair_count": len(train_pairs),
            "validation_pair_count": len(validation_pairs),
            "paths": [str(path) for path in paths],
        }
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
        split="probe_validation",
        pairs=validation_pairs,
        layers=layers,
    )
    model = config.models[role]
    saved = []
    selections = {}
    for layer in layers:
        artifact = build_mera_artifact(
            runtime.torch,
            model_id=model["model_id"],
            model_revision=model["model_revision"],
            layer=layer,
            train_correct=train_correct[layer],
            train_failure=train_failure[layer],
            validation_correct=validation_correct[layer],
            validation_failure=validation_failure[layer],
            train_pair_ids=[pair["pair_id"] for pair in train_pairs],
            validation_correct_ids=[f"{pair['pair_id']}:correct" for pair in validation_pairs],
            validation_failure_ids=[f"{pair['pair_id']}:failure" for pair in validation_pairs],
            alpha_grid=config.extraction["alpha_grid"],
            benchmark="toolalign",
            calibration_split={
                "train_domains": config.data["calibration_domains"],
                "probe_validation_domains": config.data["probe_validation_domains"],
                "evaluation_domains": config.data["evaluation_domains"],
                "condition": config.condition,
                "pair_selection": "strict_aligned_vs_abliterated_divergence",
                "config_fingerprint": config.config_fingerprint,
            },
            site=config.extraction["site"],
            source=config.raw["source"],
            target_epsilon=float(config.extraction["target_epsilon"]),
        )
        saved.append(
            str(
                save_mera_artifact(
                    runtime.torch,
                    artifact,
                    config.artifact_path(role, layer),
                )
            )
        )
        selections[str(layer)] = {
            "selected_alpha": artifact["selected_alpha"],
            "selection_metrics": artifact["selection_metrics"],
        }
    return {
        "train_pair_count": len(train_pairs),
        "validation_pair_count": len(validation_pairs),
        "selections": selections,
        "paths": saved,
    }


def _random_matched_probe(torch: Any, vector: Any, *, seed: int) -> Any:
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    random = torch.randn(vector.shape, generator=generator, dtype=torch.float32)
    return random / random.norm() * vector.float().norm()


def _fingerprint(tensor: Any) -> str:
    value = tensor.detach().contiguous().float().cpu().numpy().tobytes()
    return hashlib.sha256(value).hexdigest()


def _mera_interventions(
    config: ToolAlignMERAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, MeraRolloutIntervention | None]]:
    specs: list[tuple[str, int | None, float, MeraRolloutIntervention | None]] = [
        ("baseline", None, 1.0, None)
    ]
    for layer in config.extraction["layers"]:
        artifact = load_mera_artifact(
            runtime.torch,
            config.artifact_path(role, int(layer)),
            expected_model_id=config.models[role]["model_id"],
            expected_layer=int(layer),
        )
        alpha = float(artifact["selected_alpha"])
        common = {
            "layer": int(layer),
            "probe_vector": artifact["probe_vector"],
            "vector_fingerprint": artifact["probe_vector_fingerprint"],
        }
        specs.extend(
            [
                (
                    "mera",
                    int(layer),
                    alpha,
                    MeraRolloutIntervention(
                        method="mera",
                        alpha=alpha,
                        prefill_mode="all_tokens",
                        **common,
                    ),
                ),
                (
                    "mera_decision_only",
                    int(layer),
                    alpha,
                    MeraRolloutIntervention(
                        method="mera_decision_only",
                        alpha=alpha,
                        prefill_mode="decision_only",
                        **common,
                    ),
                ),
                (
                    "mera_abstain",
                    int(layer),
                    1.0,
                    MeraRolloutIntervention(
                        method="mera_abstain",
                        alpha=1.0,
                        prefill_mode="all_tokens",
                        **common,
                    ),
                ),
            ]
        )
        for control_alpha in config.sweep["uncalibrated_alphas"]:
            control_alpha = float(control_alpha)
            if control_alpha == alpha:
                continue
            specs.append(
                (
                    "mera_uncalibrated",
                    int(layer),
                    control_alpha,
                    MeraRolloutIntervention(
                        method="mera_uncalibrated",
                        alpha=control_alpha,
                        prefill_mode="all_tokens",
                        **common,
                    ),
                )
            )
        for seed in config.sweep["random_seeds"]:
            random = _random_matched_probe(runtime.torch, artifact["probe_vector"], seed=int(seed))
            specs.append(
                (
                    "mera_random_probe",
                    int(layer),
                    alpha,
                    MeraRolloutIntervention(
                        method="mera_random_probe",
                        layer=int(layer),
                        probe_vector=random,
                        alpha=alpha,
                        prefill_mode="all_tokens",
                        vector_fingerprint=_fingerprint(random),
                        control_seed=int(seed),
                    ),
                )
            )
    return specs


def run_toolalign_mera_sweep(
    config: ToolAlignMERAConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    common, cases = _selected_cases(config, split="evaluation")
    specs = _mera_interventions(config, runtime, role=role)
    path = config.sweep_path(role)
    existing = read_jsonl(path)
    if any(record.get("config_fingerprint") != config.config_fingerprint for record in existing):
        raise ValueError(f"stale sweep records in {path}; move or remove the file")
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, layer, alpha, intervention in specs:
            seed = intervention.control_seed if intervention else None
            run_id = f"sweep:{role}:{_case_id(case)}:{method}:{layer}:{alpha:g}:{seed}"
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
                    "layer": layer,
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


def analyze_toolalign_mera(
    config: ToolAlignMERAConfig,
    *,
    role: str,
) -> dict[str, Any]:
    records = read_jsonl(config.sweep_path(role))
    grouped: dict[tuple[str, float, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            str(record["method"]),
            float(record["alpha"]),
            str(record["scenario_type"]),
        )
        grouped.setdefault(key, []).append(record)
    rows = []
    for (method, alpha, scenario), values in sorted(grouped.items()):
        valid = [value for value in values if value["behavior"].get("valid_for_pairing")]
        traces = [
            step["intervention"]
            for value in values
            for step in value.get("steps", [])
            if step["intervention"].get("active")
        ]
        applied = sum(
            int(trace.get("applied_prefill_positions", 0))
            + int(trace.get("applied_decode_positions", 0))
            for trace in traces
        )
        eligible = sum(
            int(trace.get("eligible_prefill_positions", 0))
            + int(trace.get("eligible_decode_positions", 0))
            for trace in traces
        )
        rows.append(
            {
                "method": method,
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
                "intervention_position_rate": applied / eligible if eligible else 0.0,
            }
        )
    result = {
        "schema_version": "toolalign-mera-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "role": role,
        "source_path": str(config.sweep_path(role)),
        "rows": rows,
        "paired_transitions": paired_toolalign_transitions(
            records, role=role, parameter_fields=("layer", "alpha", "random_seed")
        ),
    }
    result["output_path"] = str(
        write_toolalign_analysis(config.output_dir / "analysis" / f"{role}.json", result)
    )
    return result
