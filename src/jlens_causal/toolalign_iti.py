"""ITI head-probe extraction and ToolAlign trajectory evaluation."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from contextlib import contextmanager
from typing import Any

from jlens_causal.baselines import (
    build_iti_artifact,
    iti_heads_by_layer,
    load_iti_artifact,
    save_iti_artifact,
)
from jlens_causal.modeling import ModelRuntime, render_conversation
from jlens_causal.steering_config import ToolAlignITIConfig
from jlens_causal.toolalign import ScenarioCase, messages_for_case
from jlens_causal.toolalign_caa import (
    ItiRolloutIntervention,
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


def _attention_shape(runtime: ModelRuntime) -> tuple[int, int]:
    config = runtime.hf_model.config
    text_config = getattr(config, "text_config", config)
    num_heads = int(text_config.num_attention_heads)
    d_model = int(runtime.lens_model.d_model)
    if d_model % num_heads:
        raise ValueError("model width is not divisible by its query attention heads")
    return num_heads, d_model // num_heads


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
        for layer in layers:
            layer = int(layer)

            def hook(_module: Any, inputs: Any, *, selected_layer: int = layer) -> None:
                captured[selected_layer] = inputs[0].detach()
                return None

            handles.append(modules[layer].register_forward_pre_hook(hook))
        yield captured
    finally:
        for handle in reversed(handles):
            handle.remove()


def _teacher_forced_iti_activations(
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
    num_heads, head_dim = _attention_shape(runtime)
    with (
        runtime.torch.inference_mode(),
        _capture_projection_inputs(_output_projections(runtime), layers) as activations,
    ):
        runtime.lens_model.forward(rendered.input_ids)
    return {
        int(layer): activations[int(layer)][0, position]
        .reshape(num_heads, head_dim)
        .detach()
        .float()
        .cpu()
        for layer in layers
    }


def _pair_activations(
    config: ToolAlignITIConfig,
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
        correct_values = _teacher_forced_iti_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["positive_response"]}],
            layers=layers,
        )
        failure_values = _teacher_forced_iti_activations(
            runtime,
            messages=[*prompt, {"role": "assistant", "content": pair["negative_response"]}],
            layers=layers,
        )
        for layer in layers:
            correct[layer].append(correct_values[layer])
            failure[layer].append(failure_values[layer])
    return correct, failure


def extract_toolalign_iti(
    config: ToolAlignITIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    train_pairs = divergent_response_pairs(config, split="calibration")
    validation_pairs = divergent_response_pairs(config, split="head_validation")
    if len(train_pairs) < int(config.extraction["minimum_train_pairs"]):
        raise ValueError("too few divergent ITI training response pairs")
    if len(validation_pairs) < int(config.extraction["minimum_validation_pairs"]):
        raise ValueError("too few divergent ITI head-validation response pairs")
    path = config.artifact_path(role)
    if path.is_file() and not force:
        artifact = load_iti_artifact(
            runtime.torch,
            path,
            expected_model_id=config.models[role]["model_id"],
        )
        return {
            "train_pair_count": len(train_pairs),
            "validation_pair_count": len(validation_pairs),
            "selected_heads": artifact["selected_heads"].tolist(),
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
        split="head_validation",
        pairs=validation_pairs,
        layers=layers,
    )
    model = config.models[role]
    artifact = build_iti_artifact(
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
        regularization_c=float(config.extraction["regularization_c"]),
        benchmark="toolalign",
        calibration_split={
            "train_domains": config.data["calibration_domains"],
            "head_validation_domains": config.data["head_validation_domains"],
            "evaluation_domains": config.data["evaluation_domains"],
            "condition": config.condition,
            "pair_selection": "strict_aligned_vs_abliterated_divergence",
            "alpha_selection": "preregistered_grid_not_evaluation_tuned",
            "config_fingerprint": config.config_fingerprint,
        },
        site=config.extraction["site"],
        source=config.raw["source"],
    )
    save_iti_artifact(runtime.torch, artifact, path)
    return {
        "train_pair_count": len(train_pairs),
        "validation_pair_count": len(validation_pairs),
        "selected_heads": artifact["selected_heads"].tolist(),
        "selected_validation_accuracies": [
            float(
                artifact["validation_accuracies"][artifact["layers"].index(int(layer)), int(head)]
            )
            for layer, head in artifact["selected_heads"].tolist()
        ],
        "path": str(path),
    }


def _fingerprint_entries(torch: Any, entries: dict[int, tuple[tuple[int, Any, float], ...]]) -> str:
    flattened = []
    for layer, values in sorted(entries.items()):
        for head, direction, scale in values:
            flattened.extend([float(layer), float(head), float(scale), *direction.float().tolist()])
    tensor = torch.tensor(flattened, dtype=torch.float32)
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def _random_head_entries(
    torch: Any,
    artifact: dict[str, Any],
    *,
    count: int,
    seed: int,
) -> dict[int, tuple[tuple[int, Any, float], ...]]:
    selected = {tuple(value) for value in artifact["selected_heads"].tolist()}
    candidates = [
        (int(layer), head)
        for layer in artifact["layers"]
        for head in range(int(artifact["num_attention_heads"]))
        if (int(layer), head) not in selected
    ]
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    chosen = torch.randperm(len(candidates), generator=generator)[:count].tolist()
    grouped: dict[int, list[tuple[int, Any, float]]] = {}
    scales = artifact["projection_stds"][:count]
    for index, candidate_index in enumerate(chosen):
        layer, head = candidates[candidate_index]
        direction = torch.randn(int(artifact["head_dim"]), generator=generator, dtype=torch.float32)
        direction = direction / direction.norm()
        grouped.setdefault(layer, []).append((head, direction, float(scales[index])))
    return {layer: tuple(values) for layer, values in grouped.items()}


def _iti_interventions(
    config: ToolAlignITIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, ItiRolloutIntervention | None]]:
    artifact = load_iti_artifact(
        runtime.torch,
        config.artifact_path(role),
        expected_model_id=config.models[role]["model_id"],
    )
    common = {
        "num_attention_heads": int(artifact["num_attention_heads"]),
        "head_dim": int(artifact["head_dim"]),
    }
    specs: list[tuple[str, int | None, float, ItiRolloutIntervention | None]] = [
        ("baseline", None, 0.0, None)
    ]
    for top_k in config.sweep["top_k_values"]:
        top_k = int(top_k)
        entries = iti_heads_by_layer(artifact, top_k=top_k)
        fingerprint = _fingerprint_entries(runtime.torch, entries)
        for alpha in config.sweep["alphas"]:
            alpha = float(alpha)
            specs.append(
                (
                    "iti",
                    top_k,
                    alpha,
                    ItiRolloutIntervention(
                        method="iti",
                        heads_by_layer=entries,
                        alpha=alpha,
                        top_k=top_k,
                        vector_fingerprint=fingerprint,
                        **common,
                    ),
                )
            )
    primary_top_k = int(config.sweep["primary_top_k"])
    primary_alpha = float(config.sweep["primary_alpha"])
    primary_entries = iti_heads_by_layer(artifact, top_k=primary_top_k)
    primary_fingerprint = _fingerprint_entries(runtime.torch, primary_entries)
    specs.extend(
        [
            (
                "iti_negative",
                primary_top_k,
                -primary_alpha,
                ItiRolloutIntervention(
                    method="iti_negative",
                    heads_by_layer=primary_entries,
                    alpha=-primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                    **common,
                ),
            ),
            (
                "iti_prefill_only",
                primary_top_k,
                primary_alpha,
                ItiRolloutIntervention(
                    method="iti_prefill_only",
                    heads_by_layer=primary_entries,
                    alpha=primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=primary_fingerprint,
                    apply_decode=False,
                    **common,
                ),
            ),
        ]
    )
    for seed in config.sweep["random_seeds"]:
        entries = _random_head_entries(runtime.torch, artifact, count=primary_top_k, seed=int(seed))
        specs.append(
            (
                "iti_random_heads",
                primary_top_k,
                primary_alpha,
                ItiRolloutIntervention(
                    method="iti_random_heads",
                    heads_by_layer=entries,
                    alpha=primary_alpha,
                    top_k=primary_top_k,
                    vector_fingerprint=_fingerprint_entries(runtime.torch, entries),
                    control_seed=int(seed),
                    **common,
                ),
            )
        )
    return specs


def run_toolalign_iti_sweep(
    config: ToolAlignITIConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    common, cases = _selected_cases(config, split="evaluation")
    specs = _iti_interventions(config, runtime, role=role)
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


def analyze_toolalign_iti(config: ToolAlignITIConfig, *, role: str) -> dict[str, Any]:
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
                "applied_head_count": sum(
                    int(trace.get("applied_prefill_heads", 0))
                    + int(trace.get("applied_decode_heads", 0))
                    for trace in traces
                ),
                "transitions_from_baseline": transitions,
            }
        )
    result = {
        "schema_version": "toolalign-iti-analysis-v1",
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
