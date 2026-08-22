from jlens_causal.toolalign_transition_analysis import (
    exact_mcnemar_p,
    paired_toolalign_transitions,
)


def _record(method, behavior, *, alpha=0.0, applied=0):
    return {
        "run_id": f"{method}:{behavior}:{alpha}",
        "domain": "cars",
        "document": 1,
        "scenario_type": "wrongdoing",
        "method": method,
        "alpha": alpha,
        "behavior": {
            "behavior_class": behavior,
            "valid_for_pairing": True,
            "tool_signature": [behavior],
        },
        "steps": [
            {"intervention": {"active": method != "baseline", "applied_prefill_positions": applied}}
        ],
    }


def test_paired_transition_analysis_counts_role_specific_flips_and_dose():
    records = [
        _record("baseline", "misaligned"),
        _record("caa", "aligned", alpha=1.0, applied=2),
        _record("control", "misaligned", alpha=-1.0, applied=2),
        _record("zero", "misaligned", alpha=0.0, applied=20),
    ]

    result = paired_toolalign_transitions(records, role="abliterated", parameter_fields=["alpha"])

    caa = next(item for item in result["summary"] if item["method"] == "caa")
    assert result["role_target"] == "misaligned_to_aligned"
    assert caa["role_target_flip_rate"] == 1.0
    assert caa["verified_nonzero_dose_rate"] == 1.0
    assert caa["mcnemar_exact_p"] == 1.0
    control = next(item for item in result["summary"] if item["method"] == "control")
    assert control["role_target_flip_rate"] == 0.0
    zero = next(item for item in result["summary"] if item["method"] == "zero")
    assert zero["verified_nonzero_dose_rate"] == 0.0


def test_exact_mcnemar_p_uses_only_discordant_pairs():
    assert exact_mcnemar_p(5, 0) == 0.0625
    assert exact_mcnemar_p(0, 0) is None
