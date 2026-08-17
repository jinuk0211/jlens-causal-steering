import pytest

from jlens_causal.failure_loreft import response_suffix_positions


def test_response_suffix_positions_uses_exact_generation_boundary():
    boundary, positions = response_suffix_positions([1, 2, 3], [1, 2, 3, 7, 8])
    assert boundary == 2
    assert positions == (3, 4)


@pytest.mark.parametrize(
    ("prompt", "full"),
    [([], [1]), ([1, 2], [1, 3]), ([1, 2], [1, 2])],
)
def test_response_suffix_positions_rejects_inexact_or_empty_continuations(prompt, full):
    with pytest.raises(ValueError, match="exact continuation"):
        response_suffix_positions(prompt, full)
