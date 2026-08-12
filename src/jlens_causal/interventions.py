"""Residual-stream interventions with explicit layer and position controls."""

from __future__ import annotations

from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, field
from typing import Any, Protocol


class Operator(Protocol):
    def __call__(self, current: Any) -> Any: ...


@dataclass
class AdditiveOperator:
    """Apply h <- h + sign * alpha * d."""

    vector: Any
    alpha: float
    sign: float = 1.0
    _cached_vector: Any = field(default=None, init=False, repr=False)

    def __call__(self, current: Any) -> Any:
        if (
            self._cached_vector is None
            or self._cached_vector.device != current.device
            or self._cached_vector.dtype != current.dtype
        ):
            self._cached_vector = self.vector.to(device=current.device, dtype=current.dtype)
        return current + float(self.sign) * float(self.alpha) * self._cached_vector


@dataclass
class CoordinateSwapOperator:
    """Move a residual from one J-lens coordinate toward the other."""

    concept_a: Any
    concept_b: Any
    alpha: float
    direction: str = "a_to_b"
    _basis: Any = field(default=None, init=False, repr=False)
    _pinv: Any = field(default=None, init=False, repr=False)

    def __call__(self, current: Any) -> Any:
        # Work in fp32 for the two-dimensional pseudoinverse, then cast the
        # reconstructed delta back to the residual dtype.
        torch = __import__("torch")
        if self._basis is None or self._basis.device != current.device:
            self._basis = torch.stack(
                [self.concept_a.detach().float(), self.concept_b.detach().float()], dim=1
            ).to(current.device)
            self._pinv = torch.linalg.pinv(self._basis)
        point = current.float()
        coordinates = point @ self._pinv.T
        target_index = 1 if self.direction == "a_to_b" else 0
        source_index = 1 - target_index
        target_coordinates = coordinates.clone()
        target_coordinates[..., target_index] = coordinates[..., source_index]
        target_coordinates[..., source_index] = coordinates[..., target_index]
        delta = (target_coordinates - coordinates) @ self._basis.T
        return current + float(self.alpha) * delta.to(dtype=current.dtype)


def _replace_output(original: Any, tensor: Any) -> Any:
    if hasattr(original, "shape"):
        return tensor
    if isinstance(original, tuple):
        return (tensor, *original[1:])
    if isinstance(original, list):
        return [tensor, *original[1:]]
    raise TypeError(f"unsupported transformer block output {type(original).__name__}")


def matched_prompt_positions(
    policy: str,
    *,
    user_positions: tuple[int, ...],
    system_positions: tuple[int, ...],
) -> tuple[int, ...]:
    """Resolve a prompt-only candidate/control mask with a matched token dose."""
    if policy == "user_span":
        return user_positions
    if policy == "system_matched":
        count = len(user_positions)
        if len(system_positions) < count:
            raise ValueError("system span is too short for a token-count-matched control")
        return system_positions[-count:]
    if policy == "prompt_last":
        return (user_positions[-1],)
    if policy == "prompt_first":
        return (user_positions[0],)
    raise ValueError(f"unknown prompt position policy {policy!r}")


@contextmanager
def intervention_hook(
    blocks: Any,
    *,
    layer: int,
    prompt_positions: tuple[int, ...],
    operator: Operator,
):
    """Apply an intervention once to exact prompt positions, never during decode."""
    call_index = 0

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        nonlocal call_index
        tensor = output if hasattr(output, "shape") else output[0]
        call_index += 1
        if call_index != 1:
            return output
        if not prompt_positions or max(prompt_positions) >= tensor.shape[1]:
            raise ValueError("intervention positions are outside the initial prompt tensor")
        modified = tensor.clone()
        indices = list(prompt_positions)
        modified[:, indices, :] = operator(modified[:, indices, :])
        return _replace_output(output, modified)

    handle = blocks[int(layer)].register_forward_hook(hook)
    try:
        yield
    finally:
        handle.remove()


@contextmanager
def intervention_band_hooks(
    blocks: Any,
    *,
    layer_operators: list[tuple[int, Operator]],
    prompt_positions: tuple[int, ...],
):
    """Install a simultaneous multi-layer prompt intervention band."""
    with ExitStack() as stack:
        for layer, operator in layer_operators:
            stack.enter_context(
                intervention_hook(
                    blocks,
                    layer=int(layer),
                    prompt_positions=prompt_positions,
                    operator=operator,
                )
            )
        yield


@contextmanager
def thought_trace_hook(
    blocks: Any,
    *,
    layer: int,
    probe_vector: Any,
    user_positions: tuple[int, ...],
    max_response_tokens: int,
):
    """Record a scalar J-lens thought margin at prompt/decode decision sites."""
    trace: dict[str, Any] = {
        "observation_layer": int(layer),
        "pre_response_last": None,
        "user_span_mean": None,
        "response_margins": [],
    }
    call_index = 0
    cached_probe: Any = None

    def hook(_module: Any, _inputs: Any, output: Any) -> None:
        nonlocal call_index, cached_probe
        tensor = output if hasattr(output, "shape") else output[0]
        if cached_probe is None or cached_probe.device != tensor.device:
            cached_probe = probe_vector.to(device=tensor.device, dtype=tensor.dtype)
        if call_index == 0:
            if not user_positions or max(user_positions) >= tensor.shape[1]:
                raise ValueError("thought-trace user positions are outside the prompt tensor")
            values = tensor[0, list(user_positions), :] @ cached_probe
            trace["user_span_mean"] = float(values.float().mean().detach().cpu())
            pre_response = float((tensor[0, -1, :] @ cached_probe).float().detach().cpu())
            trace["pre_response_last"] = pre_response
        elif len(trace["response_margins"]) < max_response_tokens:
            value = tensor[0, -1, :] @ cached_probe
            trace["response_margins"].append(float(value.float().detach().cpu()))
        call_index += 1

    handle = blocks[int(layer)].register_forward_hook(hook)
    try:
        yield trace
    finally:
        handle.remove()


def finalize_thought_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Add compact early-trajectory summaries without dropping the raw margins."""
    values = [float(value) for value in trace.get("response_margins", [])]
    output = dict(trace)
    output["response_tokens_observed"] = len(values)
    for width in (8, 32):
        selected = values[:width]
        output[f"response_first_{width}_mean"] = sum(selected) / len(selected) if selected else None
    return output
