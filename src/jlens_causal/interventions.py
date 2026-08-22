"""Residual-stream interventions with explicit layer and position controls."""

from __future__ import annotations

import math
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
def generation_intervention_hook(
    blocks: Any,
    *,
    layer: int,
    operator: Operator,
    apply_prefill_decision: bool = True,
    apply_decode: bool = True,
):
    """Apply a published generation-time intervention at assistant positions.

    The first block call is prompt prefill.  Only its final residual, which
    predicts the first assistant token, is modified.  Cached decode calls then
    contain the current generated token and are modified one at a time.  This
    reproduces CAA's "after the instruction" site without altering the system,
    tool schema, user document, or earlier trajectory tokens.

    The yielded trace is written into experiment records so a run can verify
    the exact intervention dose rather than inferring it from configuration.
    """
    call_index = 0
    trace: dict[str, Any] = {
        "layer": int(layer),
        "prefill_calls": 0,
        "decode_calls": 0,
        "applied_prefill_positions": 0,
        "applied_decode_positions": 0,
    }

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        nonlocal call_index
        tensor = output if hasattr(output, "shape") else output[0]
        is_prefill = call_index == 0
        call_index += 1
        if is_prefill:
            trace["prefill_calls"] += 1
            should_apply = apply_prefill_decision
        else:
            trace["decode_calls"] += 1
            should_apply = apply_decode
        if not should_apply:
            return output
        modified = tensor.clone()
        modified[:, -1, :] = operator(modified[:, -1, :])
        if is_prefill:
            trace["applied_prefill_positions"] += int(modified.shape[0])
        else:
            trace["applied_decode_positions"] += int(modified.shape[0])
        return _replace_output(output, modified)

    handle = blocks[int(layer)].register_forward_hook(hook)
    try:
        yield trace
    finally:
        handle.remove()


@contextmanager
def cast_generation_hook(
    blocks: Any,
    *,
    condition_layer: int,
    behavior_layer: int,
    condition_direction: Any,
    threshold: float,
    comparator: str,
    comparison_mode: str,
    operator: Operator,
    prefill_mode: str = "all_tokens",
    apply_decode: bool = True,
    gate_override: bool | None = None,
):
    """Apply CAST's behavior vector only when its prompt condition fires.

    Both measurements and additions are pre-layer, matching the official
    ``LeashLayer`` wrapper.  ``all_tokens`` is the official first-call dose;
    ``decision_only`` is the site-matched control used beside CAA.
    """
    from jlens_causal.baselines import cast_condition_similarity

    condition_layer = int(condition_layer)
    behavior_layer = int(behavior_layer)
    if condition_layer > behavior_layer:
        raise ValueError("CAST condition layer must not follow its behavior layer")
    if comparator not in {"greater", "less"}:
        raise ValueError("CAST comparator must be 'greater' or 'less'")
    if comparison_mode not in {"mean", "last"}:
        raise ValueError("CAST comparison_mode must be 'mean' or 'last'")
    if prefill_mode not in {"all_tokens", "decision_only"}:
        raise ValueError("CAST prefill_mode must be 'all_tokens' or 'decision_only'")

    condition_calls = 0
    behavior_calls = 0
    gate_triggered: bool | None = None
    trace: dict[str, Any] = {
        "condition_layer": condition_layer,
        "behavior_layer": behavior_layer,
        "condition_threshold": float(threshold),
        "condition_comparator": comparator,
        "condition_comparison_mode": comparison_mode,
        "prefill_mode": prefill_mode,
        "condition_score": None,
        "natural_gate_triggered": None,
        "gate_override": gate_override,
        "gate_triggered": None,
        "condition_calls": 0,
        "behavior_prefill_calls": 0,
        "behavior_decode_calls": 0,
        "applied_prefill_positions": 0,
        "applied_decode_positions": 0,
    }

    def condition_hook(_module: Any, inputs: Any) -> None:
        nonlocal condition_calls, gate_triggered
        condition_calls += 1
        trace["condition_calls"] = condition_calls
        if condition_calls != 1:
            return None
        hidden = inputs[0]
        if hidden.ndim != 3 or hidden.shape[0] != 1:
            raise ValueError("CAST generation currently requires one rank-3 prompt batch")
        score = cast_condition_similarity(
            __import__("torch"),
            hidden[0],
            condition_direction,
            comparison_mode=comparison_mode,
        )
        numeric_score = float(score.detach().float().cpu())
        natural_gate = (
            numeric_score > float(threshold)
            if comparator == "greater"
            else numeric_score < float(threshold)
        )
        gate_triggered = natural_gate if gate_override is None else bool(gate_override)
        trace["condition_score"] = numeric_score
        trace["natural_gate_triggered"] = natural_gate
        trace["gate_triggered"] = gate_triggered
        return None

    def behavior_hook(_module: Any, inputs: Any) -> Any:
        nonlocal behavior_calls
        is_prefill = behavior_calls == 0
        behavior_calls += 1
        if is_prefill:
            trace["behavior_prefill_calls"] += 1
        else:
            trace["behavior_decode_calls"] += 1
        if gate_triggered is None:
            raise RuntimeError("CAST behavior layer ran before its condition gate")
        if not gate_triggered or (not is_prefill and not apply_decode):
            return None
        hidden = inputs[0]
        if hidden.ndim != 3:
            raise ValueError("CAST behavior input must have shape [batch, tokens, d_model]")
        modified = hidden.clone()
        if is_prefill and prefill_mode == "decision_only":
            modified[:, -1, :] = operator(modified[:, -1, :])
            applied = int(modified.shape[0])
        else:
            modified = operator(modified)
            applied = int(modified.shape[0] * modified.shape[1])
        key = "applied_prefill_positions" if is_prefill else "applied_decode_positions"
        trace[key] += applied
        return (modified, *inputs[1:])

    condition_handle = blocks[condition_layer].register_forward_pre_hook(condition_hook)
    behavior_handle = blocks[behavior_layer].register_forward_pre_hook(behavior_hook)
    try:
        yield trace
    finally:
        behavior_handle.remove()
        condition_handle.remove()


@contextmanager
def mera_generation_hook(
    modules: Any,
    *,
    layer: int,
    probe_vector: Any,
    alpha: float,
    prefill_mode: str = "all_tokens",
    apply_decode: bool = True,
):
    """Apply MERA's closed-form error reduction at each selected position."""
    from jlens_causal.baselines import mera_closed_form_delta

    if prefill_mode not in {"all_tokens", "decision_only"}:
        raise ValueError("MERA prefill_mode must be all_tokens or decision_only")
    call_index = 0
    trace: dict[str, Any] = {
        "layer": int(layer),
        "alpha": float(alpha),
        "prefill_mode": prefill_mode,
        "prefill_calls": 0,
        "decode_calls": 0,
        "eligible_prefill_positions": 0,
        "eligible_decode_positions": 0,
        "applied_prefill_positions": 0,
        "applied_decode_positions": 0,
        "prefill_error_probability_mean": None,
        "prefill_error_probability_max": None,
        "decode_error_probability_mean": [],
        "decode_error_probability_max": [],
    }

    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        nonlocal call_index
        tensor = output if hasattr(output, "shape") else output[0]
        is_prefill = call_index == 0
        call_index += 1
        call_key = "prefill_calls" if is_prefill else "decode_calls"
        trace[call_key] += 1
        if not is_prefill and not apply_decode:
            return output
        modified = tensor.clone()
        if is_prefill and prefill_mode == "decision_only":
            selected = modified[:, -1:, :]
        else:
            selected = modified
        delta, condition, scores = mera_closed_form_delta(
            __import__("torch"),
            selected,
            probe_vector,
            alpha=float(alpha),
        )
        if is_prefill and prefill_mode == "decision_only":
            modified[:, -1:, :] = selected + delta
        else:
            modified = selected + delta
        eligible_key = (
            "eligible_prefill_positions" if is_prefill else "eligible_decode_positions"
        )
        applied_key = (
            "applied_prefill_positions" if is_prefill else "applied_decode_positions"
        )
        trace[eligible_key] += int(condition.numel())
        trace[applied_key] += int(condition.sum().detach().cpu())
        mean_score = float(scores.mean().detach().float().cpu())
        max_score = float(scores.max().detach().float().cpu())
        if is_prefill:
            trace["prefill_error_probability_mean"] = mean_score
            trace["prefill_error_probability_max"] = max_score
        else:
            trace["decode_error_probability_mean"].append(mean_score)
            trace["decode_error_probability_max"].append(max_score)
        return _replace_output(output, modified)

    handle = modules[int(layer)].register_forward_hook(hook)
    try:
        yield trace
    finally:
        handle.remove()


@contextmanager
def sadi_generation_hooks(
    modules: Any,
    *,
    units_by_layer: dict[int, tuple[int, ...] | list[int]],
    strength: float,
    apply_decode: bool = False,
):
    """Scale SADI-selected MLP output coordinates at generation decisions.

    The default reproduces the hidden-output intervention in the reference
    implementation: selected coordinates at the final prompt position are
    replaced by ``strength * current_activation``.  Applying the same dynamic
    scaling during autoregressive decode is exposed only as a labelled agent
    extension.
    """
    import torch

    if not units_by_layer:
        raise ValueError("SADI requires at least one selected unit")
    if not float(strength) >= 0.0:
        raise ValueError("SADI strength must be non-negative")
    normalized: dict[int, tuple[int, ...]] = {}
    for layer, dimensions in units_by_layer.items():
        layer = int(layer)
        values = tuple(int(value) for value in dimensions)
        if not values or len(values) != len(set(values)) or any(value < 0 for value in values):
            raise ValueError("SADI unit dimensions must be unique non-negative integers")
        if layer < 0 or layer >= len(modules):
            raise ValueError("SADI layer is outside the supplied modules")
        normalized[layer] = values

    calls = {layer: 0 for layer in normalized}
    trace: dict[str, Any] = {
        "strength": float(strength),
        "apply_decode": bool(apply_decode),
        "selected_unit_count": sum(len(values) for values in normalized.values()),
        "units_by_layer": {str(layer): list(values) for layer, values in normalized.items()},
        "prefill_calls": 0,
        "decode_calls": 0,
        "applied_prefill_scalars": 0,
        "applied_decode_scalars": 0,
        "mean_absolute_before": [],
        "mean_absolute_after": [],
    }
    handles: list[Any] = []

    def make_hook(layer: int, dimensions: tuple[int, ...]):
        def hook(_module: Any, _inputs: Any, output: Any) -> Any:
            tensor = output if hasattr(output, "shape") else output[0]
            if tensor.ndim != 3:
                raise ValueError("SADI MLP output must have shape [batch, tokens, d_model]")
            if dimensions[-1] >= int(tensor.shape[-1]):
                raise ValueError("SADI selected dimension exceeds the MLP output width")
            is_prefill = calls[layer] == 0
            calls[layer] += 1
            if layer == min(normalized):
                trace["prefill_calls" if is_prefill else "decode_calls"] += 1
            if not is_prefill and not apply_decode:
                return output
            modified = tensor.clone()
            index = torch.as_tensor(dimensions, device=tensor.device, dtype=torch.long)
            before = modified[:, -1, :].index_select(-1, index)
            after = before * float(strength)
            modified[:, -1, :].index_copy_(-1, index, after)
            scalar_count = int(before.numel())
            key = "applied_prefill_scalars" if is_prefill else "applied_decode_scalars"
            trace[key] += scalar_count
            trace["mean_absolute_before"].append(float(before.detach().float().abs().mean().cpu()))
            trace["mean_absolute_after"].append(float(after.detach().float().abs().mean().cpu()))
            return _replace_output(output, modified)

        return hook

    try:
        for layer, dimensions in normalized.items():
            handles.append(modules[layer].register_forward_hook(make_hook(layer, dimensions)))
        yield trace
    finally:
        for handle in reversed(handles):
            handle.remove()


@contextmanager
def iti_generation_hooks(
    output_projections: Any,
    *,
    heads_by_layer: dict[int, tuple[tuple[int, Any, float], ...]],
    num_attention_heads: int,
    head_dim: int,
    alpha: float,
    apply_decode: bool = True,
):
    """Add ITI's std-scaled COM directions at attention output heads."""
    if not heads_by_layer:
        raise ValueError("ITI requires at least one selected head")
    if not math.isfinite(float(alpha)):
        raise ValueError("ITI alpha must be finite")
    calls = {int(layer): 0 for layer in heads_by_layer}
    trace: dict[str, Any] = {
        "alpha": float(alpha),
        "num_attention_heads": int(num_attention_heads),
        "head_dim": int(head_dim),
        "apply_decode": bool(apply_decode),
        "selected_head_count": sum(len(values) for values in heads_by_layer.values()),
        "heads_by_layer": {
            str(layer): [int(head) for head, _direction, _scale in values]
            for layer, values in heads_by_layer.items()
        },
        "prefill_calls": 0,
        "decode_calls": 0,
        "applied_prefill_heads": 0,
        "applied_decode_heads": 0,
    }
    handles = []
    sentinel = min(heads_by_layer)

    def make_hook(layer: int, entries: tuple[tuple[int, Any, float], ...]):
        def hook(_module: Any, inputs: Any) -> Any:
            hidden = inputs[0]
            if hidden.ndim != 3 or int(hidden.shape[-1]) != num_attention_heads * head_dim:
                raise ValueError("ITI o_proj input has an incompatible attention-head shape")
            is_prefill = calls[layer] == 0
            calls[layer] += 1
            if layer == sentinel:
                trace["prefill_calls" if is_prefill else "decode_calls"] += 1
            if not is_prefill and not apply_decode:
                return None
            modified = hidden.clone()
            for head, direction, scale in entries:
                start = int(head) * head_dim
                end = start + head_dim
                vector = direction.to(device=hidden.device, dtype=hidden.dtype)
                modified[:, -1, start:end] += float(alpha) * float(scale) * vector
            key = "applied_prefill_heads" if is_prefill else "applied_decode_heads"
            trace[key] += int(modified.shape[0]) * len(entries)
            return (modified, *inputs[1:])

        return hook

    try:
        for layer, entries in heads_by_layer.items():
            handles.append(
                output_projections[int(layer)].register_forward_pre_hook(
                    make_hook(int(layer), entries)
                )
            )
        yield trace
    finally:
        for handle in reversed(handles):
            handle.remove()


@contextmanager
def austeer_generation_hooks(
    output_projections: Any,
    *,
    units_by_layer: dict[int, tuple[tuple[int, float], ...]],
    alpha: float,
    prefill_mode: str = "all_tokens",
    apply_decode: bool = True,
):
    """Apply AUSteer's multiplicative signed-consistency mask."""
    if not units_by_layer or not math.isfinite(float(alpha)):
        raise ValueError("AUSteer requires units and a finite alpha")
    if prefill_mode not in {"all_tokens", "decision_only"}:
        raise ValueError("AUSteer prefill mode must be all_tokens or decision_only")
    calls = {int(layer): 0 for layer in units_by_layer}
    sentinel = min(units_by_layer)
    trace: dict[str, Any] = {
        "alpha": float(alpha),
        "prefill_mode": prefill_mode,
        "apply_decode": bool(apply_decode),
        "selected_unit_count": sum(len(values) for values in units_by_layer.values()),
        "prefill_calls": 0,
        "decode_calls": 0,
        "applied_prefill_scalars": 0,
        "applied_decode_scalars": 0,
    }
    handles = []

    def make_hook(layer: int, entries: tuple[tuple[int, float], ...]):
        def hook(_module: Any, inputs: Any) -> Any:
            import torch

            hidden = inputs[0]
            if hidden.ndim != 3:
                raise ValueError("AUSteer attention output must be rank 3")
            is_prefill = calls[layer] == 0
            calls[layer] += 1
            if layer == sentinel:
                trace["prefill_calls" if is_prefill else "decode_calls"] += 1
            if not is_prefill and not apply_decode:
                return None
            modified = hidden.clone()
            dimensions = torch.tensor(
                [dimension for dimension, _beta in entries],
                dtype=torch.long,
                device=hidden.device,
            )
            betas = torch.tensor(
                [beta for _dimension, beta in entries],
                dtype=hidden.dtype,
                device=hidden.device,
            )
            if is_prefill and prefill_mode == "decision_only":
                selected = modified[:, -1:, :].index_select(-1, dimensions)
                modified[:, -1:, :].index_copy_(
                    -1, dimensions, selected * (1.0 + float(alpha) * betas)
                )
                positions = int(modified.shape[0])
            else:
                selected = modified.index_select(-1, dimensions)
                modified.index_copy_(
                    -1, dimensions, selected * (1.0 + float(alpha) * betas)
                )
                positions = int(modified.shape[0] * modified.shape[1])
            key = "applied_prefill_scalars" if is_prefill else "applied_decode_scalars"
            trace[key] += positions * len(entries)
            return (modified, *inputs[1:])

        return hook

    try:
        for layer, entries in units_by_layer.items():
            handles.append(
                output_projections[int(layer)].register_forward_pre_hook(
                    make_hook(int(layer), entries)
                )
            )
        yield trace
    finally:
        for handle in reversed(handles):
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
