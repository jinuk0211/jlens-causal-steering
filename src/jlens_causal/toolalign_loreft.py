"""LoReFT training and ToolAlign trajectory evaluation."""

from __future__ import annotations

import hashlib
from typing import Any

from jlens_causal.baselines import (
    load_loreft_artifact,
    loreft_parameters_by_layer,
    save_loreft_artifact,
)
from jlens_causal.loreft import LoReFTExample, train_loreft_artifact
from jlens_causal.modeling import ModelRuntime, render_conversation
from jlens_causal.steering_config import ToolAlignLoReFTConfig
from jlens_causal.toolalign import ScenarioCase, messages_for_case
from jlens_causal.toolalign_caa import (
    LoReFTRolloutIntervention,
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


def _training_examples(
    config: ToolAlignLoReFTConfig,
    runtime: ModelRuntime,
    *,
    split: str,
    pairs: list[dict[str, Any]],
) -> list[LoReFTExample]:
    common, cases = _selected_cases(config, split=split)
    case_by_id: dict[str, ScenarioCase] = {_case_id(case): case for case in cases}
    examples = []
    for pair in pairs:
        case = case_by_id[pair["pair_id"]]
        prompt = messages_for_case(common, case, config.condition)
        messages = [
            *prompt,
            {"role": "assistant", "content": pair["positive_response"]},
        ]
        response_index = len(messages) - 1
        rendered = render_conversation(
            runtime,
            messages,
            message_indices=[response_index],
            add_generation_prompt=False,
        )
        response_positions = rendered.message_positions[response_index]
        boundary = int(response_positions[0]) - 1
        if boundary < 0:
            raise ValueError("LoReFT response has no prompt boundary token")
        examples.append(
            LoReFTExample(
                example_id=pair["pair_id"],
                input_ids=rendered.input_ids,
                attention_mask=rendered.attention_mask,
                response_positions=response_positions,
                boundary_position=boundary,
            )
        )
    return examples


def train_toolalign_loreft(
    config: ToolAlignLoReFTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    force: bool = False,
) -> dict[str, Any]:
    train_pairs = divergent_response_pairs(config, split="calibration")
    validation_pairs = divergent_response_pairs(config, split="reft_validation")
    if len(train_pairs) < int(config.training["minimum_train_pairs"]):
        raise ValueError("too few divergent LoReFT training response pairs")
    if len(validation_pairs) < int(config.training["minimum_validation_pairs"]):
        raise ValueError("too few divergent LoReFT validation response pairs")
    layers = tuple(int(value) for value in config.training["layers"])
    train_examples = _training_examples(config, runtime, split="calibration", pairs=train_pairs)
    validation_examples = _training_examples(
        config, runtime, split="reft_validation", pairs=validation_pairs
    )
    model = config.models[role]
    completed = []
    for rank_value in config.training["ranks"]:
        rank = int(rank_value)
        path = config.artifact_path(role, rank)
        if path.is_file() and not force:
            artifact = load_loreft_artifact(
                runtime.torch, path, expected_model_id=model["model_id"]
            )
            completed.append(
                {
                    "rank": rank,
                    "path": str(path),
                    "validation_loss": float(artifact["validation_loss"]),
                    "status": "already_complete",
                }
            )
            continue
        artifact = train_loreft_artifact(
            runtime,
            model_id=model["model_id"],
            model_revision=model["model_revision"],
            layers=layers,
            rank=rank,
            train_examples=train_examples,
            validation_examples=validation_examples,
            epochs=int(config.training["epochs"]),
            learning_rate=float(config.training["learning_rate"]),
            weight_decay=float(config.training["weight_decay"]),
            max_grad_norm=float(config.training["max_grad_norm"]),
            seed=int(config.training["seed"]) + rank,
            benchmark="toolalign",
            site=config.training["site"],
            source=config.raw["source"],
        )
        save_loreft_artifact(runtime.torch, artifact, path)
        completed.append(
            {
                "rank": rank,
                "path": str(path),
                "validation_loss": float(artifact["validation_loss"]),
                "status": "trained",
            }
        )
    return {
        "train_pair_count": len(train_pairs),
        "validation_pair_count": len(validation_pairs),
        "artifacts": completed,
    }


def _fingerprint_parameters(torch: Any, parameters: dict[int, tuple[Any, Any, Any]]) -> str:
    flattened = []
    for layer, values in sorted(parameters.items()):
        flattened.append(torch.tensor([float(layer)]))
        flattened.extend(value.detach().float().cpu().reshape(-1) for value in values)
    tensor = torch.cat(flattened)
    return hashlib.sha256(tensor.numpy().tobytes()).hexdigest()


def _random_parameters(
    runtime: ModelRuntime, *, layers: tuple[int, ...], rank: int, seed: int
) -> dict[int, tuple[Any, Any, Any]]:
    torch = runtime.torch
    generator = torch.Generator(device="cpu")
    generator.manual_seed(int(seed))
    d_model = int(runtime.lens_model.d_model)
    parameters = {}
    for layer in layers:
        rotation = torch.linalg.qr(
            torch.randn(d_model, rank, generator=generator), mode="reduced"
        ).Q
        bound = d_model**-0.5
        weight = torch.empty(rank, d_model).uniform_(-bound, bound, generator=generator)
        bias = torch.empty(rank).uniform_(-bound, bound, generator=generator)
        parameters[layer] = (rotation, weight, bias)
    return parameters


def _loreft_interventions(
    config: ToolAlignLoReFTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
) -> list[tuple[str, int | None, float, LoReFTRolloutIntervention | None]]:
    specs: list[tuple[str, int | None, float, LoReFTRolloutIntervention | None]] = [
        ("baseline", None, 0.0, None)
    ]
    for rank_value in config.training["ranks"]:
        rank = int(rank_value)
        artifact = load_loreft_artifact(
            runtime.torch,
            config.artifact_path(role, rank),
            expected_model_id=config.models[role]["model_id"],
        )
        parameters = loreft_parameters_by_layer(artifact)
        specs.append(
            (
                "loreft",
                rank,
                1.0,
                LoReFTRolloutIntervention(
                    method="loreft",
                    parameters_by_layer=parameters,
                    rank=rank,
                    vector_fingerprint=_fingerprint_parameters(runtime.torch, parameters),
                ),
            )
        )
    primary_rank = int(config.training["primary_rank"])
    primary_artifact = load_loreft_artifact(
        runtime.torch,
        config.artifact_path(role, primary_rank),
        expected_model_id=config.models[role]["model_id"],
    )
    primary_parameters = loreft_parameters_by_layer(primary_artifact)
    specs.extend(
        [
            (
                "loreft_identity",
                primary_rank,
                0.0,
                LoReFTRolloutIntervention(
                    method="loreft_identity",
                    parameters_by_layer=primary_parameters,
                    rank=primary_rank,
                    vector_fingerprint=_fingerprint_parameters(runtime.torch, primary_parameters),
                    scale=0.0,
                ),
            ),
            (
                "loreft_decode_extension",
                primary_rank,
                1.0,
                LoReFTRolloutIntervention(
                    method="loreft_decode_extension",
                    parameters_by_layer=primary_parameters,
                    rank=primary_rank,
                    vector_fingerprint=_fingerprint_parameters(runtime.torch, primary_parameters),
                    apply_decode=True,
                ),
            ),
        ]
    )
    layers = tuple(int(value) for value in config.training["layers"])
    for seed_value in config.training["random_seeds"]:
        seed = int(seed_value)
        parameters = _random_parameters(runtime, layers=layers, rank=primary_rank, seed=seed)
        specs.append(
            (
                "loreft_random_init",
                primary_rank,
                1.0,
                LoReFTRolloutIntervention(
                    method="loreft_random_init",
                    parameters_by_layer=parameters,
                    rank=primary_rank,
                    vector_fingerprint=_fingerprint_parameters(runtime.torch, parameters),
                    control_seed=seed,
                ),
            )
        )
    return specs


def run_toolalign_loreft_sweep(
    config: ToolAlignLoReFTConfig,
    runtime: ModelRuntime,
    *,
    role: str,
    limit: int | None = None,
) -> dict[str, Any]:
    common, cases = _selected_cases(config, split="evaluation")
    specs = _loreft_interventions(config, runtime, role=role)
    path = config.sweep_path(role)
    existing = read_jsonl(path)
    if any(record.get("config_fingerprint") != config.config_fingerprint for record in existing):
        raise ValueError(f"stale sweep records in {path}; move or remove the file")
    completed = {str(record["run_id"]) for record in existing}
    written = 0
    for case in cases:
        for method, rank, scale, intervention in specs:
            seed = intervention.control_seed if intervention else None
            run_id = f"sweep:{role}:{_case_id(case)}:{method}:{rank}:{scale:g}:{seed}"
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
                    "rank": rank,
                    "scale": scale,
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


def analyze_toolalign_loreft(config: ToolAlignLoReFTConfig, *, role: str) -> dict[str, Any]:
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
            int(record["rank"]) if record.get("rank") is not None else None,
            float(record["scale"]),
            str(record["scenario_type"]),
        )
        grouped.setdefault(key, []).append(record)
    rows = []
    for (method, rank, scale, scenario), values in sorted(
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
                "rank": rank,
                "scale": scale,
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
                "applied_position_count": sum(
                    int(trace.get("applied_prefill_positions", 0))
                    + int(trace.get("applied_decode_positions", 0))
                    for trace in traces
                ),
                "transitions_from_baseline": transitions,
            }
        )
    result = {
        "schema_version": "toolalign-loreft-analysis-v1",
        "config_fingerprint": config.config_fingerprint,
        "role": role,
        "source_path": str(config.sweep_path(role)),
        "rows": rows,
        "paired_transitions": paired_toolalign_transitions(
            records, role=role, parameter_fields=("rank", "scale", "random_seed")
        ),
    }
    result["output_path"] = str(
        write_toolalign_analysis(config.output_dir / "analysis" / f"{role}.json", result)
    )
    return result
