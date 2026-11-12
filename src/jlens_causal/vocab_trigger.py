"""Vocabulary-triggered J-lens steering.

Detect: at the decision point of an agent turn, read the residual at an
observation layer through the Jacobian lens (``W_U · Norm(J_l h)``, the same
readout the J-lens exports use) and score a mined *risk* vocabulary against a
*safe* vocabulary::

    score = logsumexp(z[risk]) - logsumexp(z[safe])

Steer: if ``score > threshold`` the turn is latched and, for every position the
model processes for the rest of that turn, the residual at a control layer is
moved along the J-lens concept direction of the safe vocabulary::

    d = normalize(J_c^T (mean W_U[safe] - mean W_U[risk]))
    h <- h + alpha * ||h|| * d

``mode`` selects the condition: ``off`` (detect only), ``trigger``,
``always`` (steer every turn, no detection) or ``random`` (trigger timing and
dose, random direction).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import torch

READ_PREFIXES = ("get_", "search_", "list_", "calculate", "think")
# Tools whose only argument is free text: judged by name, never by exact arguments.
FREE_TEXT_TOOLS = ("transfer_to_human_agents",)


# --------------------------------------------------------------------------- readout


@dataclass
class ReadoutHead:
    """Final norm + unembedding of a Qwen3.5 checkpoint, float32 on CPU."""

    norm_weight: torch.Tensor
    eps: float
    unembed: torch.Tensor  # [vocab, d_model]
    zero_centered: bool = True  # Qwen3_5RMSNorm scales by (1 + w)

    def norm(self, x: torch.Tensor) -> torch.Tensor:
        x = x.float()
        x = x * torch.rsqrt(x.pow(2).mean(-1, keepdim=True) + self.eps)
        weight = self.norm_weight.to(x.device)
        return x * ((1.0 + weight) if self.zero_centered else weight)

    def logits(self, transported: torch.Tensor) -> torch.Tensor:
        return self.norm(transported) @ self.unembed.to(transported.device).T


def load_readout_head(model_dir: str | Path) -> ReadoutHead:
    """Read only the final norm and the (tied) embedding from the safetensors shards."""
    from safetensors import safe_open

    model_dir = Path(model_dir)
    index = json.loads((model_dir / "model.safetensors.index.json").read_text())["weight_map"]
    config = json.loads((model_dir / "config.json").read_text())
    text_config = config.get("text_config", config)
    prefix = "model.language_model." if "model.language_model.norm.weight" in index else "model."
    names = {"norm": f"{prefix}norm.weight", "embed": f"{prefix}embed_tokens.weight"}
    if not text_config.get("tie_word_embeddings", True) and "lm_head.weight" in index:
        names["embed"] = "lm_head.weight"
    tensors = {}
    for key, name in names.items():
        with safe_open(model_dir / index[name], framework="pt") as handle:
            tensors[key] = handle.get_tensor(name).float()
    return ReadoutHead(
        norm_weight=tensors["norm"],
        eps=float(text_config.get("rms_norm_eps", 1e-6)),
        unembed=tensors["embed"],
    )


def lens_logits(lens: Any, head: ReadoutHead, residual: torch.Tensor, layer: int) -> torch.Tensor:
    """J-lens readout of a residual (block output) at ``layer``."""
    return head.logits(lens.transport(residual.float(), layer))


# --------------------------------------------------------------------------- trigger


@dataclass
class TriggerSpec:
    observe_layer: int
    site: str
    risk_ids: list[int]
    safe_ids: list[int]
    threshold: float
    risk_tokens: list[str]
    safe_tokens: list[str]

    def score(self, logits: torch.Tensor) -> float:
        z = logits.float().reshape(-1)
        return float(torch.logsumexp(z[self.risk_ids], 0) - torch.logsumexp(z[self.safe_ids], 0))

    def score_hidden(self, lens: Any, head: ReadoutHead, hidden: torch.Tensor) -> float:
        """Same score from a residual, computing only the vocabulary's logits."""
        normed = head.norm(lens.transport(hidden.float(), self.observe_layer)).reshape(-1)
        ids = [*self.risk_ids, *self.safe_ids]
        z = head.unembed[ids].to(device=normed.device, dtype=torch.float32) @ normed
        risk, safe = z[: len(self.risk_ids)], z[len(self.risk_ids) :]
        return float(torch.logsumexp(risk, 0) - torch.logsumexp(safe, 0))

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> TriggerSpec:
        return cls(**json.loads(Path(path).read_text(encoding="utf-8")))


def concept_direction(lens: Any, head: ReadoutHead, spec: TriggerSpec, control_layer: int) -> torch.Tensor:
    """normalize(J_c^T (mean W_U[safe] - mean W_U[risk])) in the control layer's basis."""
    target = head.unembed[spec.safe_ids].float().mean(0) - head.unembed[spec.risk_ids].float().mean(0)
    direction = lens.jacobians[control_layer].float().T @ target
    return direction / direction.norm()


def random_direction(like: torch.Tensor, seed: int) -> torch.Tensor:
    generator = torch.Generator().manual_seed(seed)
    vector = torch.randn(like.shape, generator=generator)
    return vector / vector.norm()


# --------------------------------------------------------------------------- tool-call labels


def is_write(name: str) -> bool:
    return not name.startswith(READ_PREFIXES)


def label_calls(calls: Sequence[dict[str, Any]], gold: Sequence[dict[str, Any]]) -> str:
    """Turn label from its tool calls: bad_write / good_write / read / no_call."""
    if not calls:
        return "no_call"
    kinds = []
    for call in calls:
        if not is_write(call["name"]):
            kinds.append("read")
            continue
        same = [action for action in gold if action["name"] == call["name"]]
        if call["name"] in FREE_TEXT_TOOLS:
            match = bool(same)
        else:
            match = any(
                json.dumps(action.get("arguments") or {}, sort_keys=True)
                == json.dumps(call.get("arguments") or {}, sort_keys=True)
                for action in same
            )
        kinds.append("good_write" if match else "bad_write")
    if "bad_write" in kinds:
        return "bad_write"
    if "good_write" in kinds:
        return "good_write"
    return "read"


# --------------------------------------------------------------------------- generation hooks


def _blocks(model: Any) -> Any:
    for path in (("model", "layers"), ("model", "language_model", "layers")):
        current = model
        for name in path:
            current = getattr(current, name, None)
        if current is not None:
            return current
    raise AttributeError("decoder layers not found")


@contextmanager
def vocab_trigger_steering(
    model: Any,
    lens: Any,
    head: ReadoutHead,
    spec: TriggerSpec,
    *,
    mode: str,
    control_layer: int,
    direction: torch.Tensor,
    alpha: float,
) -> Iterator[dict[str, Any]]:
    """Detect on the first forward call of a turn (the decision point), then latch.

    The first forward of ``generate`` must process the last prompt token (use a
    prefix cache of ``prompt[:-1]``) so detection sees the decision position.
    """
    if mode not in {"off", "trigger", "always", "random"}:
        raise ValueError(f"unknown mode {mode!r}")
    if control_layer <= spec.observe_layer and mode in {"trigger", "random"}:
        raise ValueError("control layer must come after the observation layer")
    blocks = _blocks(model)
    trace: dict[str, Any] = {"mode": mode, "alpha": alpha, "observe_layer": spec.observe_layer,
                             "control_layer": control_layer, "score": None, "triggered": False,
                             "steered_positions": 0, "calls": 0}
    state = {"active": mode == "always"}

    def observe(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
        if trace["score"] is not None:
            return
        hidden = output if torch.is_tensor(output) else output[0]
        score = spec.score_hidden(lens, head, hidden[0, -1].detach())
        trace["score"] = score
        trace["triggered"] = score > spec.threshold
        if mode in {"trigger", "random"} and trace["triggered"]:
            state["active"] = True

    def control(module: Any, args: Any, output: Any) -> Any:  # noqa: ARG001
        trace["calls"] += 1
        if not state["active"] or alpha == 0.0:
            return output
        hidden = output if torch.is_tensor(output) else output[0]
        d = direction.to(device=hidden.device, dtype=hidden.dtype)
        hidden = hidden + alpha * hidden.norm(dim=-1, keepdim=True) * d
        trace["steered_positions"] += int(hidden.shape[1])
        return hidden if torch.is_tensor(output) else (hidden, *output[1:])

    handles = [blocks[spec.observe_layer].register_forward_hook(observe),
               blocks[control_layer].register_forward_hook(control)]
    try:
        yield trace
    finally:
        for handle in handles:
            handle.remove()
