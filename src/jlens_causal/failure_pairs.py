"""Build leakage-controlled failed-versus-repaired response pairs."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jlens_causal.failure_events import FailureEvent

FAILURE_PAIR_SCHEMA = "agent-failure-repair-pair-v1"
_REQUIRED_CHECKS = (
    "protocol_valid",
    "tool_schema_valid_or_not_applicable",
    "environment_replay_valid",
    "review_passed",
)


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_repairs(path: str | Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with Path(path).expanduser().resolve().open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"repair line {line_number} is not an object")
            records.append(value)
    return records


def _valid_assistant_message(message: Any) -> bool:
    if not isinstance(message, dict) or message.get("role") != "assistant":
        return False
    content = message.get("content")
    has_content = isinstance(content, str) and bool(content.strip())
    calls = message.get("tool_calls")
    has_calls = isinstance(calls, list) and bool(calls)
    return has_content != has_calls


def build_failure_response_pairs(
    results: dict[str, Any],
    events: Iterable[FailureEvent],
    repairs: Iterable[dict[str, Any]],
    *,
    train_task_ids: Iterable[str],
    validation_task_ids: Iterable[str],
    evaluation_task_ids: Iterable[str],
) -> list[dict[str, Any]]:
    """Join externally validated repairs to localized train/validation failures."""
    split_by_task = {
        **{str(task_id): "train" for task_id in train_task_ids},
        **{str(task_id): "validation" for task_id in validation_task_ids},
    }
    evaluation = {str(task_id) for task_id in evaluation_task_ids}
    simulations = {
        str(simulation.get("id", "")): simulation
        for simulation in results.get("simulations") or []
        if isinstance(simulation, dict)
    }
    events_by_id = {event.event_id: event for event in events}
    repairs_by_id: dict[str, dict[str, Any]] = {}
    for repair in repairs:
        event_id = str(repair.get("event_id", ""))
        if not event_id or event_id in repairs_by_id:
            raise ValueError("repairs require unique non-empty event_id values")
        repairs_by_id[event_id] = repair

    pairs: list[dict[str, Any]] = []
    for event_id, repair in sorted(repairs_by_id.items()):
        event = events_by_id.get(event_id)
        if event is None:
            raise ValueError(f"repair references unknown event {event_id}")
        if not event.steerable or event.first_bad_message_index is None:
            raise ValueError(f"repair event {event_id} is not an agent decision")
        if event.task_id in evaluation:
            raise ValueError(f"evaluation task {event.task_id} may not supply repair pairs")
        split = split_by_task.get(event.task_id)
        if split is None:
            raise ValueError(f"repair task {event.task_id} is outside train/validation splits")
        checks = repair.get("validation")
        if not isinstance(checks, dict) or not all(
            checks.get(name) is True for name in _REQUIRED_CHECKS
        ):
            raise ValueError(f"repair {event_id} must pass {', '.join(_REQUIRED_CHECKS)}")
        repaired = repair.get("repaired_message")
        if not _valid_assistant_message(repaired):
            raise ValueError(f"repair {event_id} is not one valid assistant action")
        simulation = simulations.get(event.simulation_id)
        if simulation is None:
            raise ValueError(f"simulation {event.simulation_id} is missing")
        messages = simulation.get("messages") or []
        index = event.first_bad_message_index
        if not 0 <= index < len(messages):
            raise ValueError(f"event {event_id} message index is outside its trajectory")
        failed = messages[index]
        if not _valid_assistant_message(failed):
            raise ValueError(f"event {event_id} does not point to an assistant action")
        if _hash(failed) == _hash(repaired):
            raise ValueError(f"repair {event_id} is identical to the failed action")
        context = messages[:index]
        pair_id = _hash(
            {
                "schema": FAILURE_PAIR_SCHEMA,
                "event_id": event_id,
                "failed": failed,
                "repaired": repaired,
            }
        )[:24]
        pairs.append(
            {
                "schema_version": FAILURE_PAIR_SCHEMA,
                "pair_id": pair_id,
                "event_id": event_id,
                "simulation_id": event.simulation_id,
                "task_id": event.task_id,
                "split": split,
                "failure_category": event.category,
                "failure_confidence": event.confidence,
                "context_messages": context,
                "negative_failed_message": failed,
                "positive_repaired_message": repaired,
                "validation": {name: True for name in _REQUIRED_CHECKS},
                "repair_source": str(repair.get("source", "unspecified")),
                "review_correct_behavior": event.correct_behavior,
                "future_messages_excluded": True,
            }
        )
    return pairs


def write_failure_response_pairs(path: str | Path, pairs: Iterable[dict[str, Any]]) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for pair in pairs:
            handle.write(json.dumps(pair, ensure_ascii=False, sort_keys=True) + "\n")
    temporary.replace(output)
    return output
