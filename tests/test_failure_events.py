from __future__ import annotations

import json

import pytest

from jlens_causal.failure_events import (
    FAILURE_EVENT_SCHEMA,
    FAILURE_REPLAY_SCHEMA,
    build_replay_plan,
    detect_failures,
    merge_results,
    read_events,
    review_failure_events,
    structural_failure_events,
    summarize_failures,
    write_events,
)


def _assistant(turn: int, *, name: str | None = None, arguments=None, call_id=None):
    calls = None
    if name is not None:
        calls = [
            {
                "id": call_id or f"call-{turn}",
                "name": name,
                "arguments": arguments or {},
                "requestor": "assistant",
            }
        ]
    return {
        "role": "assistant",
        "content": None if calls else "ok",
        "tool_calls": calls,
        "turn_idx": turn,
    }


def _tool(turn: int, call_id: str, *, error: bool, content: str):
    return {
        "role": "tool",
        "id": call_id,
        "requestor": "assistant",
        "error": error,
        "content": content,
        "turn_idx": turn,
    }


def _simulation(messages, **overrides):
    value = {
        "id": "sim-1",
        "task_id": "task-any",
        "trial": 2,
        "messages": messages,
        "termination_reason": "agent_stop",
        "reward_info": {"reward": 1.0},
        "review": None,
    }
    value.update(overrides)
    return value


def test_official_review_imports_actor_turn_reason_and_correct_behavior():
    simulation = _simulation(
        [
            _assistant(0),
            {"role": "user", "content": "please continue", "turn_idx": 1},
            _assistant(2, name="mutate", arguments={"value": 1}),
        ],
        review={
            "has_errors": True,
            "errors": [
                {
                    "source": "agent",
                    "error_tags": ["wrong_sequence", "guideline_violation"],
                    "severity": "critical",
                    "turn_idx": 2,
                    "reasoning": "Mutation happened before confirmation.",
                    "correct_behavior": "Ask for confirmation first.",
                },
                {
                    "source": "user",
                    "error_tags": ["hallucination"],
                    "severity": "critical_hindered",
                    "turn_idx": 1,
                    "reasoning": "The user invented a value.",
                    "correct_behavior": "Say the value is unknown.",
                },
            ],
        },
    )

    agent, user = review_failure_events(simulation)

    assert agent.category == "wrong_sequence"
    assert agent.first_bad_message_index == 2
    assert agent.correct_behavior == "Ask for confirmation first."
    assert agent.confidence == 0.65
    assert agent.steerable
    assert user.actor == "user"
    assert not user.steerable


def test_structural_detector_localizes_error_retry_and_short_cycle():
    messages = [
        _assistant(0, name="lookup", arguments={"id": "x"}, call_id="a0"),
        _tool(1, "a0", error=False, content="found"),
        _assistant(2, name="mutate", arguments={"items": "[1]"}, call_id="a1"),
        _tool(3, "a1", error=True, content="items must be an array"),
        _assistant(4, name="mutate", arguments={"items": "[1]"}, call_id="a2"),
        _tool(5, "a2", error=True, content="items must be an array"),
        _assistant(6, name="lookup", arguments={"id": "x"}, call_id="a3"),
        _tool(7, "a3", error=False, content="found"),
        _assistant(8, name="mutate", arguments={"items": "[1]"}, call_id="a4"),
        _tool(9, "a4", error=True, content="items must be an array"),
        _assistant(10, name="lookup", arguments={"id": "x"}, call_id="a5"),
        _tool(11, "a5", error=False, content="found"),
        _assistant(12, name="mutate", arguments={"items": "[1]"}, call_id="a6"),
        _tool(13, "a6", error=False, content="updated"),
    ]

    events = structural_failure_events(_simulation(messages))
    categories = [event.category for event in events]

    assert categories.count("tool_call_error") == 3
    retry = next(event for event in events if event.category == "retry_without_state_change")
    assert retry.first_bad_turn == 4
    assert retry.trigger_turn == 2
    cycles = [event for event in events if event.category == "short_tool_cycle"]
    assert {event.first_bad_turn for event in cycles} == {10, 12}
    cycle = next(event for event in cycles if event.first_bad_turn == 12)
    assert cycle.first_bad_turn == 12
    assert cycle.evidence_message_indices == (6, 8, 10, 12)


def test_detector_keeps_reward_failure_unlocalized_and_ignores_reference_actions():
    results = {
        "tasks": [
            {
                "id": "task-any",
                "evaluation_criteria": {
                    "actions": [
                        {"name": "one_possible_path", "arguments": {"not": "a requirement"}}
                    ]
                },
            }
        ],
        "simulations": [
            _simulation(
                [_assistant(0)],
                reward_info={"reward": 0.0},
            )
        ],
    }

    events = detect_failures(results)

    assert [event.category for event in events] == ["task_failure_unlocalized"]
    assert events[0].actor == "unknown"
    assert not events[0].steerable


def test_replay_plan_excludes_user_errors_and_adds_matched_controls():
    simulation = _simulation(
        [
            _assistant(0),
            {"role": "user", "content": "invented", "turn_idx": 1},
            _assistant(2, name="bad", arguments={"x": 1}, call_id="bad"),
            _tool(3, "bad", error=True, content="bad argument"),
            _assistant(4),
        ],
        review={
            "has_errors": True,
            "errors": [
                {
                    "source": "user",
                    "error_tags": ["hallucination"],
                    "severity": "critical_hindered",
                    "turn_idx": 1,
                    "reasoning": "invented",
                    "correct_behavior": "do not invent",
                }
            ],
        },
    )
    results = {"timestamp": "now", "info": {"git_commit": "abc"}, "simulations": [simulation]}
    events = detect_failures(results)

    plan = build_replay_plan(results, events, seed=7)

    assert plan["schema_version"] == FAILURE_REPLAY_SCHEMA
    assert len(plan["simulations"]) == 1
    entry = plan["simulations"][0]
    assert [item["turn_idx"] for item in entry["oracle_interventions"]] == [2]
    assert entry["count_matched_random_turns"][0] in {0, 4}
    assert entry["random_intervention_count_matched"]
    assert entry["random_overlap_with_oracle"] == []
    assert "learned_gate" in entry["conditions"]
    assert all("hallucination" not in item["categories"] for item in entry["oracle_interventions"])


def test_event_round_trip_and_summary(tmp_path):
    results = {
        "simulations": [
            _simulation(
                [
                    _assistant(0, name="bad", arguments={"x": 1}, call_id="bad"),
                    _tool(1, "bad", error=True, content="error"),
                ],
                reward_info={"reward": 0.0},
            )
        ]
    }
    events = detect_failures(results)
    path = write_events(tmp_path / "events.jsonl", events)

    loaded = read_events(path)
    summary = summarize_failures(loaded)
    first_json = json.loads(path.read_text(encoding="utf-8").splitlines()[0])

    assert loaded == events
    assert summary["event_count"] == len(events)
    assert summary["steerable_event_count"] >= 1
    assert first_json["schema_version"] == FAILURE_EVENT_SCHEMA


def test_merge_results_preserves_reviews_and_rejects_duplicate_simulations():
    left = {"info": {}, "simulations": [{"id": "train", "review": {"errors": []}}]}
    right = {"info": {}, "simulations": [{"id": "validation", "review": {"errors": [1]}}]}

    merged = merge_results([left, right])

    assert [item["id"] for item in merged["simulations"]] == ["train", "validation"]
    assert merged["simulations"][1]["review"] == {"errors": [1]}
    assert merged["info"]["jlens_merged_result_shards"] == 2
    with pytest.raises(ValueError, match="unique non-empty IDs"):
        merge_results([left, left])
