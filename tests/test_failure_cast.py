from jlens_causal.failure_cast import build_failure_cast_condition_pairs
from jlens_causal.failure_events import FailureEvent


def _simulation(simulation_id, task_id, repeat):
    first = {
        "role": "assistant",
        "turn_idx": 0,
        "tool_calls": [{"name": "lookup", "arguments": {"id": "bad"}}],
    }
    second = {
        "role": "assistant",
        "turn_idx": 1,
        "tool_calls": [{"name": "lookup", "arguments": {"id": "bad" if repeat else "fixed"}}],
    }
    return {
        "id": simulation_id,
        "task_id": task_id,
        "messages": [
            {"role": "system", "content": "policy"},
            first,
            {"role": "tool", "id": "x", "content": "bad id", "error": True},
            second,
        ],
    }


def _event(simulation_id, task_id):
    return FailureEvent(
        event_id=f"event-{simulation_id}",
        simulation_id=simulation_id,
        task_id=task_id,
        trial=0,
        actor="agent",
        category="retry_without_state_change",
        severity="critical",
        first_bad_turn=1,
        first_bad_message_index=3,
        trigger_turn=0,
        evidence_message_indices=(1, 2, 3),
        reasoning="repeat",
        correct_behavior="revise",
        sources=("structural",),
        confidence=1.0,
    )


def test_cast_condition_pairs_match_failure_to_same_pre_action_boundary():
    results = {
        "simulations": [
            _simulation("tp", "train", True),
            _simulation("tn", "train", False),
            _simulation("vp", "validation", True),
            _simulation("vn", "validation", False),
        ]
    }
    pairs = build_failure_cast_condition_pairs(
        results,
        [_event("tp", "train"), _event("vp", "validation")],
        failure_category="retry_without_state_change",
        train_task_ids=["train"],
        validation_task_ids=["validation"],
        evaluation_task_ids=["evaluation"],
        minimum_pairs_per_split=1,
    )
    assert [pair["split"] for pair in pairs] == ["train", "validation"]
    assert all(pair["future_messages_excluded"] for pair in pairs)
    assert all(len(pair["positive_context_messages"]) == 3 for pair in pairs)
    assert all(pair["positive_context_messages"][-1]["error"] for pair in pairs)
    assert all(pair["negative_context_messages"][-1]["error"] for pair in pairs)
