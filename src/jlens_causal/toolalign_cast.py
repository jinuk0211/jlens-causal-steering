"""Official-site CAST extraction and ToolAlign trajectory evaluation."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_cast_artifact,
    cast_condition_similarity,
    cast_pca_pairwise,
    load_cast_artifact,
    save_cast_artifact,
    select_cast_gate,
)
from jlens_causal.interventions import AdditiveOperator
from jlens_causal.modeling import (
    ModelRuntime,
    capture_block_inputs,
    capture_block_outputs,
    render_conversation,
)
from jlens_causal.steering_config import ToolAlignCASTConfig
from jlens_causal.toolalign import ScenarioCase, load_cases, messages_for_case
from jlens_causal.toolalign_caa import (
    CastRolloutIntervention,
    _append_jsonl,
    _case_id,
    _selected_cases,
    divergent_calibration_pairs,
    read_jsonl,
    run_toolalign_rollout,
)
from jlens_causal.toolalign_transition_analysis import (
    paired_toolalign_transitions,
    write_toolalign_analysis,
)


def _paired_condition_cases(
    config: ToolAlignCASTConfig,
    *,
    split: str,
) -> tuple[Any, list[tuple[str, ScenarioCase, ScenarioCase]]]:
    if split == "train":
        domains = config.data["calibration_domains"]
        documents = config.data["calibration_documents"]
    elif split == "gate_validation":
        domains = config.data["gate_validation_domains"]
        documents = config.data["gate_validation_documents"]
    else:
        raise ValueError(f"unknown CAST condition split {split!r}")
    common, cases = load_cases(
        config.toolalign_root,
        domains=domains,
        documents=documents,
        scenario_types=["safe", "wrongdoing"],
    )
    indexed = {(case.domain, int(case.document), case.scenario_type): case for case in cases}
    pairs: list[tuple[str, ScenarioCase, ScenarioCase]] = []
    for domain in domains:
        for document in documents:
            safe = indexed.get((domain, int(document), "safe"))
            wrongdoing = indexed.get((domain, int(document), "wrongdoing"))
            if safe is None or wrongdoing is None:
                continue
            pairs.append((f"{domain}:{document}", wrongdoing, safe))
    if not pairs:
        raise ValueError(f"no paired safe/wrongdoing prompts found for CAST {split}")
    return common, pairs


def _forward_captures(
    runtime: ModelRuntime,
    *,
    messages: list[dict[str, str]],
    output_layers: Iterable[int] = (),
    input_layers: Iterable[int] = (),
    add_generation_prompt: bool = True,
) -> tuple[Any, dict[int, Any], dict[int, Any]]:
    rendered = render_conversation(
        runtime,
        messages,
        message_indices=[len(messages) - 1],
        add_generation_prompt=add_generation_prompt,
    )
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, output_layers) as outputs,
        capture_block_inputs(runtime.lens_model.layers, input_layers) as inputs,
    ):
        runtime.lens_model.forward(rendered.input_ids)
    copied_outputs = {int(layer): value.detach().float().cpu() for layer, value in outputs.items()}
    copied_inputs = {int(layer): value.detach().float().cpu() for layer, value in inputs.items()}
    return rendered, copied_outputs, copied_inputs


def _condition_output_means(
    runtime: ModelRuntime,
    *,
    messages: list[dict[str, str]],
    layers: Iterable[int],
) -> dict[int, Any]:
    _rendered, outputs, _inputs = _forward_captures(
        runtime,
        messages=messages,
        output_layers=layers,
    )
    return {layer: value[0].mean(dim=0) for layer, value in outputs.items()}


def _gate_input_states(
    runtime: ModelRuntime,
    *,
    messages: list[dict[str, str]],
    layers: Iterable[int],
) -> dict[int, Any]:
    _rendered, _outputs, inputs = _forward_captures(
        runtime,
        messages=messages,
        input_layers=layers,
    )
    return {layer: value[0] for layer, value in inputs.items()}


def _behavior_output_means(
    runtime: ModelRuntime,
    *,
    messages: list[dict[str, str]],
    layers: Iterable[int],
) -> dict[int, Any]:
    response_index = len(messages) - 1
    rendered, outputs, _inputs = _forward_captures(
        runtime,
        messages=messages,
        output_layers=layers,
        add_generation_prompt=False,
    )
    positions = list(rendered.message_positions[response_index])
    return {layer: value[0, positions, :].mean(dim=0) for layer, value in outputs.items()}


def extract_toolalign_cast(
    config: ToolAlignCASTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    """Extract behavior/condition PCA vectors and tune the gate out of domain."""
    behavior_pairs = divergent_calibration_pairs(config)
    minimum = int(config.extraction["minimum_behavior_pairs"])
    if len(behavior_pairs) < minimum:
        raise ValueError(
            f"only {len(behavior_pairs)} divergent behavior pairs; need at least {minimum}"
        )
    behavior_layers = tuple(int(value) for value in config.extraction["behavior_layers"])
    condition_layers = tuple(int(value) for value in config.extraction["condition_layers"])
    paths = [config.artifact_path(role, layer) for layer in behavior_layers]
    if not force and all(path.is_file() for path in paths):
        return {"behavior_pair_count": len(behavior_pairs), "paths": [str(p) for p in paths]}

    common, calibration_cases = _selected_cases(config, split="calibration")
    cases_by_id = {_case_id(case): case for case in calibration_cases}
    behavior_positive: dict[int, list[Any]] = {layer: [] for layer in behavior_layers}
    behavior_negative: dict[int, list[Any]] = {layer: [] for layer in behavior_layers}
    for pair in behavior_pairs:
        case = cases_by_id[pair["pair_id"]]
        prompt = messages_for_case(common, case, config.condition)
        positive = _behavior_output_means(
            runtime,
            messages=[
                *prompt,
                {"role": "assistant", "content": pair["positive_response"]},
            ],
            layers=behavior_layers,
        )
        negative = _behavior_output_means(
            runtime,
            messages=[
                *prompt,
                {"role": "assistant", "content": pair["negative_response"]},
            ],
            layers=behavior_layers,
        )
        for layer in behavior_layers:
            behavior_positive[layer].append(positive[layer])
            behavior_negative[layer].append(negative[layer])

    condition_common, condition_pairs = _paired_condition_cases(config, split="train")
    condition_positive: dict[int, list[Any]] = {layer: [] for layer in condition_layers}
    condition_negative: dict[int, list[Any]] = {layer: [] for layer in condition_layers}
    for _pair_id, wrongdoing, safe in condition_pairs:
        wrongdoing_values = _condition_output_means(
            runtime,
            messages=messages_for_case(condition_common, wrongdoing, config.condition),
            layers=condition_layers,
        )
        safe_values = _condition_output_means(
            runtime,
            messages=messages_for_case(condition_common, safe, config.condition),
            layers=condition_layers,
        )
        for layer in condition_layers:
            condition_positive[layer].append(wrongdoing_values[layer])
            condition_negative[layer].append(safe_values[layer])
    condition_results = {
        layer: cast_pca_pairwise(
            runtime.torch,
            positive=condition_positive[layer],
            negative=condition_negative[layer],
        )
        for layer in condition_layers
    }

    gate_common, gate_pairs = _paired_condition_cases(config, split="gate_validation")
    positive_scores: dict[int, list[float]] = {layer: [] for layer in condition_layers}
    negative_scores: dict[int, list[float]] = {layer: [] for layer in condition_layers}
    comparison_mode = str(config.extraction["comparison_mode"])
    for _pair_id, wrongdoing, safe in gate_pairs:
        wrongdoing_inputs = _gate_input_states(
            runtime,
            messages=messages_for_case(gate_common, wrongdoing, config.condition),
            layers=condition_layers,
        )
        safe_inputs = _gate_input_states(
            runtime,
            messages=messages_for_case(gate_common, safe, config.condition),
            layers=condition_layers,
        )
        for layer in condition_layers:
            direction = condition_results[layer]["direction"]
            positive_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        wrongdoing_inputs[layer],
                        direction,
                        comparison_mode=comparison_mode,
                    )
                )
            )
            negative_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        safe_inputs[layer],
                        direction,
                        comparison_mode=comparison_mode,
                    )
                )
            )
    gate = select_cast_gate(
        positive_scores=positive_scores,
        negative_scores=negative_scores,
    )
    condition_layer = int(gate["condition_layer"])
    condition_ids = [item[0] for item in condition_pairs]
    gate_ids = [item[0] for item in gate_pairs]
    model = config.models[role]
    saved: list[str] = []
    for behavior_layer in behavior_layers:
        artifact = build_cast_artifact(
            runtime.torch,
            model_id=model["model_id"],
            model_revision=model["model_revision"],
            behavior_layer=behavior_layer,
            condition_layer=condition_layer,
            behavior_positive=behavior_positive[behavior_layer],
            behavior_negative=behavior_negative[behavior_layer],
            condition_positive=condition_positive[condition_layer],
            condition_negative=condition_negative[condition_layer],
            behavior_pair_ids=[pair["pair_id"] for pair in behavior_pairs],
            condition_pair_ids=condition_ids,
            gate_positive_ids=[f"{pair_id}:wrongdoing" for pair_id in gate_ids],
            gate_negative_ids=[f"{pair_id}:safe" for pair_id in gate_ids],
            gate_positive_scores=positive_scores[condition_layer],
            gate_negative_scores=negative_scores[condition_layer],
            gate=gate,
            comparison_mode=comparison_mode,
            benchmark="toolalign",
            calibration_split={
                "behavior_domains": config.data["calibration_domains"],
                "gate_validation_domains": config.data["gate_validation_domains"],
                "evaluation_domains": config.data["evaluation_domains"],
                "documents": config.data["calibration_documents"],
                "condition": config.condition,
                "behavior_selection": ("aligned_non_misaligned_and_abliterated_misaligned"),
                "config_fingerprint": config.config_fingerprint,
            },
            sites=config.extraction["sites"],
            source=config.raw["source"],
        )
        saved.append(
            str(
                save_cast_artifact(
                    runtime.torch,
                    artifact,
                    config.artifact_path(role, behavior_layer),
                )
            )
        )
    return {
        "behavior_pair_count": len(behavior_pairs),
        "condition_pair_count": len(condition_pairs),
        "gate_positive_count": len(gate_pairs),
        "gate_negative_count": len(gate_pairs),
        "selected_gate": gate,
        "paths": saved,
    }


def _cast_interventions(
    config: ToolAlignCASTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, CastRolloutIntervention | None]]:
    specs: list[tuple[str, int | None, float, CastRolloutIntervention | None]] = [
        ("baseline", None, 0.0, None)
    ]
    primary_sign = 1.0 if role == "abliterated" else -1.0
    primary_label = "restore_alignment" if role == "abliterated" else "erode_alignment"
    for behavior_layer in config.extraction["behavior_layers"]:
        artifact = load_cast_artifact(
            runtime.torch,
            config.artifact_path(role, int(behavior_layer)),
            expected_model_id=config.models[role]["model_id"],
            expected_behavior_layer=int(behavior_layer),
        )
        common = {
            "condition_layer": int(artifact["condition_layer"]),
            "behavior_layer": int(behavior_layer),
            "condition_direction": artifact["condition_direction"],
            "threshold": float(artifact["condition_threshold"]),
            "comparator": str(artifact["condition_comparator"]),
            "comparison_mode": str(artifact["condition_comparison_mode"]),
            "vector_fingerprint": str(artifact["behavior_vector_fingerprint"]),
            "condition_vector_fingerprint": str(artifact["condition_vector_fingerprint"]),
        }
        for alpha_value in config.sweep["alphas"]:
            alpha = float(alpha_value)
            if alpha == 0.0:
                continue
            for sign, label in ((1.0, "toward_aligned"), (-1.0, "toward_abliterated")):
                specs.append(
                    (
                        "cast",
                        int(behavior_layer),
                        sign * alpha,
                        CastRolloutIntervention(
                            method="cast",
                            operator=AdditiveOperator(
                                vector=artifact["behavior_direction"], alpha=sign * alpha
                            ),
                            prefill_mode="all_tokens",
                            direction_label=label,
                            **common,
                        ),
                    )
                )
            specs.append(
                (
                    "cast_decision_only",
                    int(behavior_layer),
                    primary_sign * alpha,
                    CastRolloutIntervention(
                        method="cast_decision_only",
                        operator=AdditiveOperator(
                            vector=artifact["behavior_direction"],
                            alpha=primary_sign * alpha,
                        ),
                        prefill_mode="decision_only",
                        direction_label=primary_label,
                        **common,
                    ),
                )
            )
            if config.sweep.get("include_ungated_control", False):
                specs.append(
                    (
                        "cast_ungated",
                        int(behavior_layer),
                        primary_sign * alpha,
                        CastRolloutIntervention(
                            method="cast_ungated",
                            operator=AdditiveOperator(
                                vector=artifact["behavior_direction"],
                                alpha=primary_sign * alpha,
                            ),
                            prefill_mode="all_tokens",
                            direction_label=primary_label,
                            gate_override=True,
                            **common,
                        ),
                    )
                )
            if config.sweep.get("include_complement_gate_control", False):
                complement = "less" if common["comparator"] == "greater" else "greater"
                complement_common = dict(common, comparator=complement)
                specs.append(
                    (
                        "cast_complement_gate",
                        int(behavior_layer),
                        primary_sign * alpha,
                        CastRolloutIntervention(
                            method="cast_complement_gate",
                            operator=AdditiveOperator(
                                vector=artifact["behavior_direction"],
                                alpha=primary_sign * alpha,
                            ),
                            prefill_mode="all_tokens",
                            direction_label=primary_label,
                            **complement_common,
                        ),
                    )
                )
    return specs


def run_toolalign_cast_sweep(
    config: ToolAlignCASTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run held-out full trajectories with CAST and gate/site controls."""
    common, cases = _selected_cases(config, split="evaluation")
    specs = _cast_interventions(config, runtime, role=role)
    path = config.sweep_path(role)
    existing = read_jsonl(path)
    if any(record.get("config_fingerprint") != config.config_fingerprint for record in existing):
        raise ValueError(f"stale sweep records in {path}; move or remove the file")
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, behavior_layer, signed_alpha, intervention in specs:
            condition_layer = intervention.condition_layer if intervention else None
            run_id = (
                f"sweep:{role}:{_case_id(case)}:{method}:{condition_layer}:"
                f"{behavior_layer}:{signed_alpha:g}"
            )
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
                "condition_layer": condition_layer,
                "behavior_layer": behavior_layer,
                "signed_alpha": signed_alpha,
            }
            _append_jsonl(path, record)
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


def analyze_toolalign_cast(
    config: ToolAlignCASTConfig,
    *,
    role: str,
) -> dict[str, Any]:
    """Summarize outcome changes and the observed CAST gate rate."""
    records = read_jsonl(config.sweep_path(role))
    grouped: dict[tuple[str, float, str], list[dict[str, Any]]] = {}
    for record in records:
        key = (
            str(record["method"]),
            float(record["signed_alpha"]),
            str(record["scenario_type"]),
        )
        grouped.setdefault(key, []).append(record)
    rows = []
    for (method, alpha, scenario), values in sorted(grouped.items()):
        valid = [value for value in values if value["behavior"].get("valid_for_pairing")]
        gates = [
            bool(step["intervention"].get("gate_triggered"))
            for value in values
            for step in value.get("steps", [])
            if step["intervention"].get("active")
            and step["intervention"].get("gate_triggered") is not None
        ]
        rows.append(
            {
                "method": method,
                "signed_alpha": alpha,
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
                "gate_trigger_rate": sum(gates) / len(gates) if gates else None,
            }
        )
    result = {
        "schema_version": "toolalign-cast-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "role": role,
        "source_path": str(config.sweep_path(role)),
        "rows": rows,
        "paired_transitions": paired_toolalign_transitions(
            records,
            role=role,
            parameter_fields=("condition_layer", "behavior_layer", "signed_alpha"),
        ),
    }
    result["output_path"] = str(
        write_toolalign_analysis(config.output_dir / "analysis" / f"{role}.json", result)
    )
    return result


def expected_toolalign_cast_outputs(config: ToolAlignCASTConfig) -> list[Path]:
    """Expose owned outputs for orchestration without broad filesystem scans."""
    outputs: list[Path] = []
    for role in config.models:
        outputs.append(config.baseline_path(role))
        outputs.append(config.sweep_path(role))
        outputs.extend(
            config.artifact_path(role, int(layer)) for layer in config.extraction["behavior_layers"]
        )
    return outputs
