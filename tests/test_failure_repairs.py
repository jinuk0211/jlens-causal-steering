import json

import pytest

from jlens_causal.failure_events import FailureEvent
from jlens_causal.failure_repairs import (
    _interleave_events,
    generate_validated_repairs,
    validate_repaired_message,
)


def _event(
    event_id: str,
    task_id: str,
    simulation_id: str,
    category: str = "retry_without_state_change",
) -> FailureEvent:
    return FailureEvent(
        event_id=event_id,
        simulation_id=simulation_id,
        task_id=task_id,
        trial=0,
        actor="agent",
        category=category,
        severity="major_error",
        first_bad_turn=3,
        first_bad_message_index=1,
        trigger_turn=3,
        evidence_message_indices=(1,),
        reasoning="The agent repeated a failed lookup without new state.",
        correct_behavior="Ask for the missing identifier.",
        sources=("structural",),
        confidence=1.0,
    )


def _results():
    failed = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "old", "name": "lookup", "arguments": {"id": ""}}],
    }
    return {
        "simulations": [
            {
                "id": "train-sim",
                "task_id": "1",
                "messages": [{"role": "user", "content": "x"}, failed],
            },
            {
                "id": "val-sim",
                "task_id": "2",
                "messages": [{"role": "user", "content": "x"}, failed],
            },
        ]
    }


class _Runtime:
    def propose(self, event, attempt):
        return {"role": "assistant", "content": "What is the identifier?", "tool_calls": None}

    def validate_tool_schema(self, message):
        return True, []

    def replay(self, event, message):
        return {"valid": True, "errors": [], "tool_results": []}

    def review(self, event, failed_message, repaired_message, replay):
        return {"passed": True, "reason": "This obtains the missing argument."}


def test_validate_repaired_message_rejects_identical_action():
    failed = {
        "role": "assistant",
        "content": None,
        "tool_calls": [{"id": "old", "name": "lookup", "arguments": {"id": ""}}],
    }
    valid, errors = validate_repaired_message(dict(failed), failed)
    assert not valid
    assert "identical" in errors[0]


def test_generate_repairs_checkpoints_both_splits(tmp_path):
    events = [_event("train", "1", "train-sim"), _event("val", "2", "val-sim")]
    output = tmp_path / "repairs.jsonl"
    report = tmp_path / "report.json"
    summary = generate_validated_repairs(
        _results(),
        events,
        _Runtime(),
        output=output,
        report=report,
        category="retry_without_state_change",
        train_task_ids=["1"],
        validation_task_ids=["2"],
        evaluation_task_ids=["3"],
        minimum_per_split=1,
    )
    records = [json.loads(line) for line in output.read_text().splitlines()]
    assert summary["complete"]
    assert summary["accepted"] == {"train": 1, "validation": 1}
    assert len(records) == 2
    assert all(all(record["validation"].values()) for record in records)

    resumed = generate_validated_repairs(
        _results(),
        events,
        _Runtime(),
        output=output,
        report=report,
        category="retry_without_state_change",
        train_task_ids=["1"],
        validation_task_ids=["2"],
        evaluation_task_ids=["3"],
        minimum_per_split=1,
    )
    assert resumed["accepted"] == {"train": 1, "validation": 1}


def test_generate_repairs_refuses_insufficient_split_before_model_calls(tmp_path):
    with pytest.raises(ValueError, match="eligible validation events"):
        generate_validated_repairs(
            _results(),
            [_event("train", "1", "train-sim")],
            _Runtime(),
            output=tmp_path / "repairs.jsonl",
            report=tmp_path / "report.json",
            category="retry_without_state_change",
            train_task_ids=["1"],
            validation_task_ids=["2"],
            evaluation_task_ids=["3"],
            minimum_per_split=1,
        )


def test_generate_repairs_pools_categories_and_reuses_seed_checkpoint(tmp_path):
    train = _event("train", "1", "train-sim", "tool_call_error")
    validation = _event("val", "2", "val-sim", "missed_required_action")
    seed = {
        "event_id": train.event_id,
        "failure_category": "tool_call_error",
        "repaired_message": {
            "role": "assistant",
            "content": "What is the identifier?",
            "tool_calls": None,
        },
        "validation": {
            "protocol_valid": True,
            "tool_schema_valid_or_not_applicable": True,
            "environment_replay_valid": True,
            "review_passed": True,
        },
    }
    output = tmp_path / "repairs.jsonl"
    report = tmp_path / "report.json"
    summary = generate_validated_repairs(
        _results(),
        [train, validation],
        _Runtime(),
        output=output,
        report=report,
        category="agent_behavior_error",
        categories=["missed_required_action", "tool_call_error"],
        output_category="agent_behavior_error",
        train_task_ids=["1"],
        validation_task_ids=["2"],
        evaluation_task_ids=["3"],
        minimum_per_split=1,
        maximum_per_split=1,
        seed_repairs=[seed],
    )
    records = [json.loads(line) for line in output.read_text().splitlines()]

    assert summary["complete"]
    assert summary["source_categories"] == [
        "missed_required_action",
        "tool_call_error",
    ]
    assert {record["event_id"] for record in records} == {"train", "val"}
    generated = next(record for record in records if record["event_id"] == "val")
    assert generated["failure_category"] == "agent_behavior_error"
    assert generated["source_failure_category"] == "missed_required_action"


def test_pooled_event_order_round_robins_categories_and_tasks():
    events = [
        _event("a1", "1", "a1", "guideline_violation"),
        _event("a2", "1", "a2", "guideline_violation"),
        _event("a3", "2", "a3", "guideline_violation"),
        _event("b1", "1", "b1", "missed_required_action"),
        _event("b2", "2", "b2", "missed_required_action"),
    ]

    ordered = _interleave_events(events, {"1": "validation", "2": "validation"})

    assert [event.category for event in ordered[:4]] == [
        "guideline_violation",
        "missed_required_action",
        "guideline_violation",
        "missed_required_action",
    ]
    assert [event.task_id for event in ordered if event.category == "guideline_violation"] == [
        "1",
        "2",
        "1",
    ]
