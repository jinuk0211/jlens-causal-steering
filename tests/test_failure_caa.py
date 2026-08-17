import pytest

from jlens_causal.failure_caa import (
    divergent_character_spans,
    tau_messages_for_hf,
)


def test_tau_messages_drop_call_ids_but_keep_tool_arguments():
    converted = tau_messages_for_hf(
        [
            {
                "role": "assistant",
                "tool_calls": [
                    {
                        "id": "generated-id",
                        "name": "lookup",
                        "arguments": {"id": "x"},
                    }
                ],
            },
            {
                "role": "tool",
                "id": "generated-id",
                "content": "found",
            },
        ]
    )
    function = converted[0]["tool_calls"][0]["function"]
    assert function == {"name": "lookup", "arguments": {"id": "x"}}
    assert "id" not in converted[0]["tool_calls"][0]
    assert converted[1]["tool_call_id"] == "generated-id"


def test_divergent_span_targets_changed_argument_not_shared_template():
    left = 'prefix<tool>{"id":"correct"}</tool>suffix'
    right = 'prefix<tool>{"id":"wrong"}</tool>suffix'
    left_span, right_span = divergent_character_spans(left, right)
    assert left[left_span[0] : left_span[1]] == "correct"
    assert right[right_span[0] : right_span[1]] == "wrong"


def test_divergent_span_rejects_identical_actions():
    with pytest.raises(ValueError, match="non-empty divergent"):
        divergent_character_spans("same", "same")
