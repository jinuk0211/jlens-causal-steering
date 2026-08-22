from __future__ import annotations

import pytest
import torch

from jlens_causal.jservo import (
    JSERVO_ARTIFACT_SCHEMA,
    JSERVO_CONTROLLER_VERSION,
    canonical_failure_mode,
    jservo_generation_hooks,
    minimum_state_edit,
    mode_layer_policy,
    project_away,
    select_concept_bundles,
    validate_jservo_artifact,
)


def test_failure_categories_map_to_analyzed_mechanisms():
    assert canonical_failure_mode("repeated_tool_call") == "completion_not_released"
    assert canonical_failure_mode("missed_required_action") == "skipped_evidence_acquisition"
    assert (
        canonical_failure_mode("tool_call_argument_error", "Use the returned payment ID")
        == "argument_binding_error"
    )
    assert mode_layer_policy("malformed_serialization") == ((28,), (28, 30))
    assert mode_layer_policy("argument_binding_error") == ((20,), (24, 28))


def test_minimum_edit_reaches_margin_and_zero_error_has_zero_dose():
    current = torch.tensor([0.0, 1.0, 0.0])
    read = torch.tensor([1.0, 0.0, 0.0])
    result = minimum_state_edit(
        current,
        margin_direction=read,
        projected_direction=read,
        target_margin=2.0,
        dose_cap=3.0,
    )
    assert result["feasible"]
    assert result["dose_norm"] == pytest.approx(2.0)
    assert result["predicted_post_margin"] == pytest.approx(2.0)
    reached = minimum_state_edit(
        current + result["delta"],
        margin_direction=read,
        projected_direction=read,
        target_margin=2.0,
        dose_cap=3.0,
    )
    assert reached["dose_norm"] == 0.0
    assert reached["reason"] == "target_already_reached"


def test_protected_projection_and_caps_request_abstention():
    protected = torch.tensor([[0.0], [1.0], [0.0]])
    projected = project_away(torch.tensor([1.0, 1.0, 0.0]), protected)
    assert float(projected @ protected[:, 0]) == pytest.approx(0.0, abs=1e-5)
    result = minimum_state_edit(
        torch.zeros(3),
        margin_direction=torch.tensor([1.0, 1.0, 0.0]),
        projected_direction=projected,
        target_margin=2.0,
        dose_cap=1.0,
    )
    assert not result["feasible"]
    assert result["reason"] == "layer_dose_cap_exceeded"


def test_bundle_selection_requires_train_and_validation_consistency():
    # Token 0 is repair-positive, token 1 failure-positive, token 2 stable.
    train_correct = torch.tensor([[4.0, 0.0, 3.0], [5.0, 0.0, 3.0]])
    train_failure = torch.tensor([[0.0, 4.0, 3.0], [0.0, 5.0, 3.0]])
    val_correct = torch.tensor([[4.0, 0.0, 3.0], [4.0, 0.0, 3.0]])
    val_failure = torch.tensor([[0.0, 4.0, 3.0], [0.0, 4.0, 3.0]])
    selected = select_concept_bundles(
        train_correct,
        train_failure,
        val_correct,
        val_failure,
        [" repair", " repeat", " task"],
        bundle_size=1,
        protected_size=1,
        minimum_consistency=1.0,
    )
    assert selected["target"][0]["token_id"] == 0
    assert selected["source"][0]["token_id"] == 1
    assert selected["protected"][0]["token_id"] == 2


class _Block:
    def __init__(self):
        self.hooks = []

    class _Handle:
        def __init__(self, hooks, hook):
            self.hooks = hooks
            self.hook = hook

        def remove(self):
            self.hooks.remove(self.hook)

    def register_forward_hook(self, hook):
        self.hooks.append(hook)
        return self._Handle(self.hooks, hook)

    def run(self, tensor):
        output = tensor
        for hook in list(self.hooks):
            output = hook(self, (), output)
        return output


def _artifact(dose_cap=10.0):
    layers = {}
    for layer, role in ((0, "observe"), (1, "control"), (2, "control")):
        layers[str(layer)] = {
            "layer": layer,
            "role": role,
            "margin_direction": torch.tensor([1.0, 0.0]),
            "projected_direction": torch.tensor([1.0, 0.0]),
            "random_direction": torch.tensor([0.0, 1.0]),
            "control_gain": 1.0,
            "gate_threshold": 0.5,
            "target_margin": 1.0,
            "margin_scale": 1.0,
            "dose_cap": dose_cap,
            "residual_scale": 2.0,
            "protected_rank": 0,
            "validation_false_trigger_rate": 0.0,
            "validation_failure_trigger_rate": 1.0,
            "steering_eligible": True,
        }
    mode = {
        "mode": "completion_not_released",
        "source_failure_category": "repeated_tool_call",
        "boundaries": ["after_successful_tool_result"],
        "observation_layers": [0],
        "control_layers": [1, 2],
        "max_active_layers_per_position": 2,
        "cumulative_dose_cap": 10.0,
        "steering_eligible": True,
        "fallback": "abstain_on_infeasible_edit",
        "token_bundles": {"target": [], "source": [], "protected": []},
        "layers": layers,
        "train_pair_ids": ["t"],
        "validation_pair_ids": ["v"],
    }
    return {
        "schema_version": JSERVO_ARTIFACT_SCHEMA,
        "controller_version": JSERVO_CONTROLLER_VERSION,
        "model_id": "m",
        "model_revision": "r",
        "lens_revision": "l",
        "benchmark": "test",
        "calibration": {},
        "artifact_fingerprint": "fingerprint",
        "modes": {mode["mode"]: mode},
    }


def test_sequential_feedback_stops_later_layer_after_target_reached():
    blocks = [_Block(), _Block(), _Block()]
    value = torch.tensor([[[0.0, 0.0]]])
    with jservo_generation_hooks(
        blocks,
        artifact=validate_jservo_artifact(_artifact()),
        boundaries=["after_successful_tool_result"],
        apply_decode=False,
    ) as trace:
        observed = blocks[0].run(value)
        controlled = blocks[1].run(observed)
        final = blocks[2].run(controlled)
    assert float(final[0, -1, 0]) == pytest.approx(1.0)
    assert trace["applied_positions"] == 1
    control_sites = [site for site in trace["sites"] if site.get("role") == "control"]
    assert control_sites[0]["dose_norm"] == pytest.approx(1.0)
    assert control_sites[1]["reason"] == "target_already_reached"


def test_infeasible_controller_requests_abstention_without_mutating():
    blocks = [_Block(), _Block(), _Block()]
    value = torch.tensor([[[0.0, 0.0]]])
    with jservo_generation_hooks(
        blocks,
        artifact=validate_jservo_artifact(_artifact(dose_cap=0.1)),
        boundaries=["after_successful_tool_result"],
        apply_decode=False,
    ) as trace:
        observed = blocks[0].run(value)
        controlled = blocks[1].run(observed)
    assert torch.equal(controlled, value)
    assert trace["abstain_requested"]
    assert trace["abstain_reasons"] == ["layer_dose_cap_exceeded"]


def test_reverse_control_has_its_own_source_margin_target():
    artifact = _artifact()
    for payload in artifact["modes"]["completion_not_released"]["layers"].values():
        payload["reverse_gate_threshold"] = 1.0
        payload["reverse_target_margin"] = 0.0
    blocks = [_Block(), _Block(), _Block()]
    value = torch.tensor([[[2.0, 0.0]]])
    with jservo_generation_hooks(
        blocks,
        artifact=artifact,
        boundaries=["after_successful_tool_result"],
        control_type="reverse",
        apply_decode=False,
    ) as trace:
        observed = blocks[0].run(value)
        controlled = blocks[1].run(observed)
    assert float(controlled[0, -1, 0]) == pytest.approx(0.0)
    assert trace["active"]
    assert trace["cumulative_dose"] == pytest.approx(2.0)
