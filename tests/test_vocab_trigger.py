import torch

from jlens_causal.vocab_trigger import ReadoutHead, TriggerSpec, label_calls, vocab_trigger_steering


class _Lens:
    def __init__(self, layers: int, width: int):
        self.jacobians = {layer: torch.eye(width) for layer in range(layers)}

    def transport(self, hidden: torch.Tensor, layer: int) -> torch.Tensor:
        return hidden @ self.jacobians[layer].T


class _Model(torch.nn.Module):
    def __init__(self, layers: int, width: int):
        super().__init__()
        self.model = torch.nn.Module()
        self.model.layers = torch.nn.ModuleList(torch.nn.Identity() for _ in range(layers))

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        for block in self.model.layers:
            hidden = block(hidden)
        return hidden


def _setup(threshold: float):
    width, layers = 8, 6
    head = ReadoutHead(norm_weight=torch.zeros(width), eps=1e-6, unembed=torch.eye(width))
    spec = TriggerSpec(observe_layer=1, site="initial_decision", risk_ids=[0], safe_ids=[1],
                       threshold=threshold, risk_tokens=["r"], safe_tokens=["s"])
    direction = torch.zeros(width)
    direction[1] = 1.0  # toward the safe token
    hidden = torch.zeros(1, 2, width)
    hidden[0, -1, 0] = 2.0  # risk-leaning decision point
    return _Model(layers, width), _Lens(layers, width), head, spec, direction, hidden


def _run(mode: str, alpha: float, threshold: float = 0.0):
    model, lens, head, spec, direction, hidden = _setup(threshold)
    with vocab_trigger_steering(model, lens, head, spec, mode=mode, control_layer=3,
                                direction=direction, alpha=alpha, probe_layers=[3, 5]) as trace:
        model(hidden)
        model(hidden[:, -1:])  # a decode step: detection must not re-run
    return trace


def test_trigger_latches_and_probe_sees_signed_edit():
    off = _run("off", 0.0)
    plus = _run("trigger", 0.5)
    minus = _run("trigger", -0.5)
    assert off["triggered"] and plus["triggered"]
    assert off["steered_positions"] == 0 and plus["steered_positions"] == 3
    # Observation (layer 1) precedes the edit (layer 3): identical scores.
    assert off["score"] == plus["score"] == minus["score"]
    # The probe at the control layer runs after the edit and keeps the sign.
    for layer in (3, 5):
        assert plus["probe"][layer] < off["probe"][layer] < minus["probe"][layer]


def test_trigger_below_threshold_does_not_steer():
    trace = _run("trigger", 0.5, threshold=100.0)
    assert not trace["triggered"] and trace["steered_positions"] == 0
    assert trace["probe"][3] == _run("off", 0.0, threshold=100.0)["probe"][3]


def test_label_calls_free_text_transfer_and_args():
    gold = [{"name": "cancel_reservation", "arguments": {"reservation_id": "A1"}},
            {"name": "transfer_to_human_agents", "arguments": {"summary": "x"}}]
    assert label_calls([], gold) == "no_call"
    assert label_calls([{"name": "get_user_details", "arguments": {}}], gold) == "read"
    assert label_calls([{"name": "cancel_reservation", "arguments": {"reservation_id": "A1"}}], gold) == "good_write"
    assert label_calls([{"name": "cancel_reservation", "arguments": {"reservation_id": "B2"}}], gold) == "bad_write"
    assert label_calls([{"name": "transfer_to_human_agents", "arguments": {"summary": "other"}}], gold) == "good_write"
