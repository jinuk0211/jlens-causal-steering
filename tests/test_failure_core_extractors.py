import pytest

from jlens_causal.failure_core_extractors import select_failure_pairs


def _pair(pair_id, split, category="retry_without_state_change"):
    return {"pair_id": pair_id, "split": split, "failure_category": category}


def test_select_failure_pairs_keeps_train_and_validation_disjoint():
    train, validation = select_failure_pairs(
        [
            _pair("t1", "train"),
            _pair("t2", "train"),
            _pair("v1", "validation"),
            _pair("v2", "validation"),
            _pair("other", "train", "short_tool_cycle"),
        ],
        "retry_without_state_change",
    )
    assert [item["pair_id"] for item in train] == ["t1", "t2"]
    assert [item["pair_id"] for item in validation] == ["v1", "v2"]


def test_select_failure_pairs_rejects_missing_validation_and_duplicate_ids():
    with pytest.raises(ValueError, match="at least two train"):
        select_failure_pairs(
            [_pair("t1", "train"), _pair("t2", "train")],
            "retry_without_state_change",
        )
    with pytest.raises(ValueError, match="must be unique"):
        select_failure_pairs(
            [
                _pair("same", "train"),
                _pair("t2", "train"),
                _pair("same", "validation"),
                _pair("v2", "validation"),
            ],
            "retry_without_state_change",
        )
