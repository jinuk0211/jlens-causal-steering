from types import SimpleNamespace

import pytest

from jlens_causal.failure_core_extractors import (
    _attention_shape,
    _modules,
    select_failure_pairs,
)


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


def test_attention_modules_only_require_requested_full_attention_layers():
    projection = object()
    runtime = SimpleNamespace(
        lens_model=SimpleNamespace(
            layers=[
                SimpleNamespace(linear_attn=object()),
                SimpleNamespace(self_attn=SimpleNamespace(o_proj=projection)),
            ]
        )
    )

    assert _modules(runtime, "attention_o_proj_input", [1]) == {1: projection}
    with pytest.raises(ValueError, match="layer 0 lacks site"):
        _modules(runtime, "attention_o_proj_input", [0])


def test_attention_shape_prefers_explicit_head_dimension_for_wide_qwen_heads():
    runtime = SimpleNamespace(
        hf_model=SimpleNamespace(
            config=SimpleNamespace(
                text_config=SimpleNamespace(num_attention_heads=16, head_dim=256)
            )
        ),
        lens_model=SimpleNamespace(d_model=2560),
    )

    assert _attention_shape(runtime) == (16, 256)
