"""Residual-stream interventions with explicit layer and position controls."""

from __future__ import annotations

from contextlib import contextmanager
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
    """Swap the two J-lens coordinates while preserving the orthogonal residual."""

    concept_a: Any
    concept_b: Any
    alpha: float
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
        delta = (coordinates.flip(-1) - coordinates) @ self._basis.T
        return current + float(self.alpha) * delta.to(dtype=current.dtype)


def _replace_output(original: Any, tensor: Any) -> Any:
    if hasattr(original, "shape"):
        return tensor
    if isinstance(original, tuple):
        return (tensor, *original[1:])
    if isinstance(original, list):
        return [tensor, *original[1:]]
    raise TypeError(f"unsupported transformer block output {type(original).__name__}")


def _selected_positions(tensor: Any, policy: str, call_index: int) -> Any | None:
    """Return a writable [batch, selected_positions, d_model] view or None."""
    if policy == "all":
        return tensor
    if policy == "last":
        return tensor[:, -1:, :]
    if policy == "prompt_all":
        return tensor if call_index == 0 else None
    if policy == "prompt_first":
        return tensor[:, :1, :] if call_index == 0 else None
    if policy == "prompt_last":
        return tensor[:, -1:, :] if call_index == 0 else None
    if policy == "decode":
        return tensor if call_index > 0 else None
    raise ValueError(f"unknown position policy {policy!r}")


@contextmanager
def intervention_hook(
    blocks: Any,
    *,
    layer: int,
    position_policy: str,
    operator: Operator,
):
    """Install one generation-scoped hook and always remove it afterward."""
    call_index = 0

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        nonlocal call_index
        tensor = output if hasattr(output, "shape") else output[0]
        selected = _selected_positions(tensor, position_policy, call_index)
        call_index += 1
        if selected is None:
            return output
        modified = tensor.clone()
        target = _selected_positions(modified, position_policy, call_index - 1)
        if target is None:
            return output
        target.copy_(operator(target))
        return _replace_output(output, modified)

    handle = blocks[int(layer)].register_forward_hook(hook)
    try:
        yield
    finally:
        handle.remove()
