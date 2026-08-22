"""Failure-risk CAST condition data and generic TauBench artifact extraction."""

from __future__ import annotations

import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_cast_artifact,
    cast_condition_similarity,
    cast_pca_pairwise,
    save_cast_artifact,
    select_cast_gate,
)
from jlens_causal.failure_caa import (
    paired_action_activations,
    tau_messages_for_hf,
    template_ids_and_offsets,
)
from jlens_causal.failure_core_extractors import select_failure_pairs
from jlens_causal.failure_events import FailureEvent
from jlens_causal.modeling import (
    ModelRuntime,
    capture_block_inputs,
    capture_block_outputs,
)

FAILURE_CAST_CONDITION_SCHEMA = "agent-failure-cast-condition-pair-v1"
_SOURCE = {
    "repository": "IBM/activation-steering",
    "revision": "52be60235ee309b46c49d6d5877f36e20c52e6ab",
}


def _tool_outcome(message: dict[str, Any]) -> str | None:
    if message.get("role") != "tool":
        return None
    nested = message.get("tool_messages")
    candidates = nested if isinstance(nested, list) else [message]
    errors = [bool(item.get("error")) for item in candidates if isinstance(item, dict)]
    if not errors:
        return None
    return "error" if any(errors) else "success"


def _is_opportunity(messages: list[dict[str, Any]], index: int, failure_category: str) -> bool:
    message = messages[index]
    if message.get("role") != "assistant":
        return False
    previous = _tool_outcome(messages[index - 1]) if index else None
    if failure_category == "retry_without_state_change":
        return previous == "error"
    if failure_category in {"repeated_tool_call", "completion_not_released"}:
        return previous == "success"
    if failure_category == "short_tool_cycle":
        return previous in {"error", "success"}
    if failure_category == "tool_call_error":
        return bool(message.get("tool_calls"))
    raise ValueError(f"unsupported CAST failure category {failure_category!r}")


def build_failure_cast_condition_pairs(
    results: dict[str, Any],
    events: Iterable[FailureEvent],
    *,
    failure_category: str,
    train_task_ids: Iterable[str],
    validation_task_ids: Iterable[str],
    evaluation_task_ids: Iterable[str],
    minimum_pairs_per_split: int = 2,
) -> list[dict[str, Any]]:
    """Match observed failure-risk contexts to same-boundary clean contexts."""
    split_by_task = {
        **{str(task_id): "train" for task_id in train_task_ids},
        **{str(task_id): "validation" for task_id in validation_task_ids},
    }
    evaluation = {str(task_id) for task_id in evaluation_task_ids}
    positives = {
        (event.simulation_id, int(event.first_bad_message_index))
        for event in events
        if event.actor == "agent"
        and event.category == failure_category
        and event.first_bad_message_index is not None
        and event.task_id not in evaluation
    }
    candidates: dict[str, list[dict[str, Any]]] = {"train": [], "validation": []}
    for simulation in results.get("simulations") or []:
        if not isinstance(simulation, dict):
            continue
        task_id = str(simulation.get("task_id", ""))
        split = split_by_task.get(task_id)
        if split is None:
            continue
        simulation_id = str(simulation.get("id", ""))
        messages = simulation.get("messages") or []
        for index in range(len(messages)):
            if not _is_opportunity(messages, index, failure_category):
                continue
            candidate_id = f"{simulation_id}:{index}"
            candidates[split].append(
                {
                    "candidate_id": candidate_id,
                    "simulation_id": simulation_id,
                    "task_id": task_id,
                    "message_index": index,
                    "context_messages": messages[:index],
                    "positive": (simulation_id, index) in positives,
                }
            )

    pairs: list[dict[str, Any]] = []
    for split in ("train", "validation"):
        positive = sorted(
            (item for item in candidates[split] if item["positive"]),
            key=lambda item: item["candidate_id"],
        )
        negative = [item for item in candidates[split] if not item["positive"]]
        if len(positive) < int(minimum_pairs_per_split) or len(negative) < len(positive):
            raise ValueError(
                f"CAST {split} requires at least {minimum_pairs_per_split} failure-risk "
                "contexts and one unused matched control per risk context"
            )
        unused = list(negative)
        for positive_item in positive:
            negative_item = min(
                unused,
                key=lambda item: (
                    item["simulation_id"] != positive_item["simulation_id"],
                    abs(int(item["message_index"]) - int(positive_item["message_index"])),
                    item["candidate_id"],
                ),
            )
            unused.remove(negative_item)
            pair_id = f"{failure_category}:{split}:{positive_item['candidate_id']}"
            pairs.append(
                {
                    "schema_version": FAILURE_CAST_CONDITION_SCHEMA,
                    "pair_id": pair_id,
                    "split": split,
                    "failure_category": failure_category,
                    "positive_candidate_id": positive_item["candidate_id"],
                    "negative_candidate_id": negative_item["candidate_id"],
                    "positive_context_messages": positive_item["context_messages"],
                    "negative_context_messages": negative_item["context_messages"],
                    "matching": "same_opportunity_boundary_nearest_message_index",
                    "future_messages_excluded": True,
                }
            )
    return pairs


def write_failure_cast_condition_pairs(path: str | Path, pairs: Iterable[dict[str, Any]]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(output)
    return output


def read_failure_cast_condition_pairs(path: str | Path) -> list[dict[str, Any]]:
    pairs = []
    for line_number, line in enumerate(
        Path(path).expanduser().resolve().read_text(encoding="utf-8").splitlines(), 1
    ):
        if not line.strip():
            continue
        value = json.loads(line)
        if value.get("schema_version") != FAILURE_CAST_CONDITION_SCHEMA:
            raise ValueError(f"unsupported CAST condition schema on line {line_number}")
        pairs.append(value)
    return pairs


def _prompt_captures(
    runtime: ModelRuntime,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]],
    output_layers: tuple[int, ...] = (),
    input_layers: tuple[int, ...] = (),
) -> tuple[dict[int, Any], dict[int, Any]]:
    input_ids, _, _ = template_ids_and_offsets(
        runtime,
        tau_messages_for_hf(messages),
        tools=tools,
        add_generation_prompt=True,
    )
    with (
        runtime.torch.inference_mode(),
        capture_block_outputs(runtime.lens_model.layers, output_layers) as outputs,
        capture_block_inputs(runtime.lens_model.layers, input_layers) as inputs,
    ):
        runtime.lens_model.forward(input_ids)
    return (
        {layer: value[0].detach().float().cpu() for layer, value in outputs.items()},
        {layer: value[0].detach().float().cpu() for layer, value in inputs.items()},
    )


def extract_failure_cast(
    runtime: ModelRuntime,
    repair_pairs: Iterable[dict[str, Any]],
    condition_pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    behavior_layers: Iterable[int],
    condition_layers: Iterable[int],
    output_dir: str | Path,
    tools: list[dict[str, Any]],
    comparison_mode: str = "mean",
    force: bool = False,
) -> dict[str, Any]:
    """Fit CAST behavior and prospective failure-risk gate on disjoint tasks."""
    if not tools:
        raise ValueError("exact TauBench CAST extraction requires airline tool schemas")
    if comparison_mode not in {"mean", "last"}:
        raise ValueError("CAST comparison_mode must be mean or last")
    train_repairs, _ = select_failure_pairs(repair_pairs, failure_category)
    selected_conditions = [
        pair for pair in condition_pairs if pair.get("failure_category") == failure_category
    ]
    train_conditions = [pair for pair in selected_conditions if pair.get("split") == "train"]
    validation_conditions = [
        pair for pair in selected_conditions if pair.get("split") == "validation"
    ]
    if len(train_conditions) < 2 or len(validation_conditions) < 2:
        raise ValueError("CAST requires at least two train and two validation condition pairs")
    behavior_layer_tuple = tuple(sorted(set(int(layer) for layer in behavior_layers)))
    condition_layer_tuple = tuple(sorted(set(int(layer) for layer in condition_layers)))
    output = Path(output_dir).expanduser().resolve()
    expected = [output / f"cast-layer-{layer}.pt" for layer in behavior_layer_tuple]
    if not force and all(path.is_file() for path in expected):
        return {"paths": [str(path) for path in expected], "status": "already_complete"}

    behavior_positive = {layer: [] for layer in behavior_layer_tuple}
    behavior_negative = {layer: [] for layer in behavior_layer_tuple}
    for pair in train_repairs:
        positive, negative = paired_action_activations(
            runtime,
            context_messages=pair["context_messages"],
            positive_message=pair["positive_repaired_message"],
            negative_message=pair["negative_failed_message"],
            layers=behavior_layer_tuple,
            tools=tools,
        )
        for layer in behavior_layer_tuple:
            behavior_positive[layer].append(positive[layer])
            behavior_negative[layer].append(negative[layer])

    condition_positive = {layer: [] for layer in condition_layer_tuple}
    condition_negative = {layer: [] for layer in condition_layer_tuple}
    for pair in train_conditions:
        positive, _ = _prompt_captures(
            runtime,
            pair["positive_context_messages"],
            tools=tools,
            output_layers=condition_layer_tuple,
        )
        negative, _ = _prompt_captures(
            runtime,
            pair["negative_context_messages"],
            tools=tools,
            output_layers=condition_layer_tuple,
        )
        for layer in condition_layer_tuple:
            condition_positive[layer].append(positive[layer].mean(dim=0))
            condition_negative[layer].append(negative[layer].mean(dim=0))
    condition_results = {
        layer: cast_pca_pairwise(
            runtime.torch,
            positive=condition_positive[layer],
            negative=condition_negative[layer],
        )
        for layer in condition_layer_tuple
    }

    positive_scores = {layer: [] for layer in condition_layer_tuple}
    negative_scores = {layer: [] for layer in condition_layer_tuple}
    for pair in validation_conditions:
        _, positive = _prompt_captures(
            runtime,
            pair["positive_context_messages"],
            tools=tools,
            input_layers=condition_layer_tuple,
        )
        _, negative = _prompt_captures(
            runtime,
            pair["negative_context_messages"],
            tools=tools,
            input_layers=condition_layer_tuple,
        )
        for layer in condition_layer_tuple:
            direction = condition_results[layer]["direction"]
            positive_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        positive[layer],
                        direction,
                        comparison_mode=comparison_mode,
                    )
                )
            )
            negative_scores[layer].append(
                float(
                    cast_condition_similarity(
                        runtime.torch,
                        negative[layer],
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
    sites = {
        "behavior_extraction": "block_output_last_divergent_action_token",
        "condition_extraction": "block_output_prompt_mean",
        "gate_measurement": "block_input_prompt",
        "behavior_application": "block_input",
    }
    saved = []
    for behavior_layer in behavior_layer_tuple:
        artifact = build_cast_artifact(
            runtime.torch,
            model_id=model_id,
            model_revision=model_revision,
            behavior_layer=behavior_layer,
            condition_layer=condition_layer,
            behavior_positive=behavior_positive[behavior_layer],
            behavior_negative=behavior_negative[behavior_layer],
            condition_positive=condition_positive[condition_layer],
            condition_negative=condition_negative[condition_layer],
            behavior_pair_ids=[str(pair["pair_id"]) for pair in train_repairs],
            condition_pair_ids=[str(pair["pair_id"]) for pair in train_conditions],
            gate_positive_ids=[f"{pair['pair_id']}:risk" for pair in validation_conditions],
            gate_negative_ids=[f"{pair['pair_id']}:control" for pair in validation_conditions],
            gate_positive_scores=positive_scores[condition_layer],
            gate_negative_scores=negative_scores[condition_layer],
            gate=gate,
            comparison_mode=comparison_mode,
            benchmark="taubench-airline-failure-modes",
            calibration_split={
                "failure_category": failure_category,
                "repair_pair_schema": "agent-failure-repair-pair-v1",
                "condition_pair_schema": FAILURE_CAST_CONDITION_SCHEMA,
                "future_messages_excluded": True,
                "prospective_gate": True,
            },
            sites=sites,
            source=_SOURCE,
        )
        path = output / f"cast-layer-{behavior_layer}.pt"
        saved.append(str(save_cast_artifact(runtime.torch, artifact, path)))
    return {
        "paths": saved,
        "behavior_pairs": len(train_repairs),
        "condition_train_pairs": len(train_conditions),
        "condition_validation_pairs": len(validation_conditions),
        "selected_gate": gate,
    }
