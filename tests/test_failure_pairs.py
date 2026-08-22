import pytest

from jlens_causal.failure_events import structural_failure_events
from jlens_causal.failure_pairs import build_failure_response_pairs


def _fixture(task_id="1"):
    messages = [
        {"role": "user", "content": "find x", "turn_idx": 0},
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "bad", "name": "lookup", "arguments": {"id": ""}}],
            "turn_idx": 1,
        },
        {
            "role": "tool",
            "id": "bad",
            "content": "id is required",
            "error": True,
            "requestor": "assistant",
            "turn_idx": 2,
        },
    ]
    simulation = {
        "id": "sim-1",
        "task_id": task_id,
        "trial": 0,
        "messages": messages,
        "termination_reason": "agent_error",
        "reward_info": {"reward": 0},
    }
    event = next(
        item for item in structural_failure_events(simulation) if item.category == "tool_call_error"
    )
    repair = {
        "event_id": event.event_id,
        "source": "llm_then_replay_and_review",
        "repaired_message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "new", "name": "lookup", "arguments": {"id": "x"}}],
        },
        "validation": {
            "protocol_valid": True,
            "tool_schema_valid_or_not_applicable": True,
            "environment_replay_valid": True,
            "review_passed": True,
        },
    }
    return {"simulations": [simulation]}, event, repair


def test_pair_builder_excludes_future_messages_and_assigns_train_split():
    results, event, repair = _fixture()
    pairs = build_failure_response_pairs(
        results,
        [event],
        [repair],
        train_task_ids=["1"],
        validation_task_ids=["2"],
        evaluation_task_ids=["3"],
    )
    pair = pairs[0]
    assert pair["split"] == "train"
    assert pair["context_messages"] == [results["simulations"][0]["messages"][0]]
    assert pair["future_messages_excluded"]
    assert pair["negative_failed_message"]["tool_calls"][0]["arguments"] == {"id": ""}
    assert pair["positive_repaired_message"]["tool_calls"][0]["arguments"] == {"id": "x"}


def test_pair_builder_can_pool_source_failures_under_one_output_category():
    results, event, repair = _fixture()
    pairs = build_failure_response_pairs(
        results,
        [event],
        [repair],
        train_task_ids=["1"],
        validation_task_ids=["2"],
        evaluation_task_ids=["3"],
        failure_category="agent_behavior_error",
    )

    assert pairs[0]["failure_category"] == "agent_behavior_error"
    assert pairs[0]["source_failure_category"] == "tool_call_error"


def test_pair_builder_rejects_evaluation_leakage_and_unvalidated_repairs():
    results, event, repair = _fixture(task_id="3")
    with pytest.raises(ValueError, match="may not supply repair pairs"):
        build_failure_response_pairs(
            results,
            [event],
            [repair],
            train_task_ids=["1"],
            validation_task_ids=["2"],
            evaluation_task_ids=["3"],
        )

    results, event, repair = _fixture()
    repair["validation"]["review_passed"] = False
    with pytest.raises(ValueError, match="must pass"):
        build_failure_response_pairs(
            results,
            [event],
            [repair],
            train_task_ids=["1"],
            validation_task_ids=["2"],
            evaluation_task_ids=["3"],
        )
