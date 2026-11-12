"""Locate decoder parts on Qwen3.5 (hybrid) and plain decoder-only checkpoints.

The upstream baselines hard-code ``model.model.layers[i].self_attn`` and assume
every layer has softmax attention.  Qwen3.5 interleaves Gated DeltaNet layers
(``linear_attn``) with full-attention layers (``self_attn``), and the
multimodal class nests the text stack under ``language_model``.  These helpers
resolve the real modules so adapters never guess.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


def text_config(model: Any) -> Any:
    config = model.config
    return getattr(config, "text_config", None) or config


def decoder_layers(model: Any) -> Any:
    """Return the ``ModuleList`` of decoder blocks."""
    candidates = (
        ("model", "layers"),
        ("model", "language_model", "layers"),
        ("language_model", "layers"),
        ("layers",),
    )
    for path in candidates:
        current = model
        for name in path:
            current = getattr(current, name, None)
            if current is None:
                break
        if current is not None and hasattr(current, "__len__") and len(current) > 0:
            return current
    raise AttributeError(f"cannot locate decoder layers on {type(model).__name__}")


def decoder_layers_prefix(model: Any) -> str:
    """Dotted module name of the decoder ``ModuleList`` (e.g. ``model.layers``)."""
    layers = decoder_layers(model)
    for name, module in model.named_modules():
        if module is layers:
            return name
    raise AttributeError("decoder layers are not registered under the model")


def layer_types(model: Any) -> list[str]:
    config = text_config(model)
    n_layers = len(decoder_layers(model))
    types = getattr(config, "layer_types", None)
    if types is None:
        return ["full_attention"] * n_layers
    types = list(types)[:n_layers]
    if len(types) != n_layers:
        raise ValueError("config.layer_types does not cover every decoder layer")
    return types


def full_attention_layers(model: Any) -> list[int]:
    """Indices of decoder layers whose token mixer is softmax attention with o_proj."""
    layers = decoder_layers(model)
    indices = [
        index
        for index, kind in enumerate(layer_types(model))
        if kind == "full_attention" and hasattr(getattr(layers[index], "self_attn", None), "o_proj")
    ]
    if not indices:
        raise ValueError("model has no full-attention layers with self_attn.o_proj")
    return indices


def attention_shape(model: Any) -> tuple[int, int]:
    """(num_attention_heads, head_dim) of the o_proj input."""
    config = text_config(model)
    heads = int(config.num_attention_heads)
    head_dim = getattr(config, "head_dim", None)
    head_dim = int(head_dim) if head_dim else int(config.hidden_size) // heads
    return heads, head_dim


def hidden_size(model: Any) -> int:
    return int(text_config(model).hidden_size)


def model_device(model: Any) -> Any:
    device = getattr(model, "device", None)
    if device is not None:
        return device
    return next(model.parameters()).device


def first_tensor(value: Any) -> Any:
    return value[0] if isinstance(value, tuple) else value


def replace_first(value: Any, tensor: Any) -> Any:
    if isinstance(value, tuple):
        return (tensor, *value[1:])
    return tensor


@contextmanager
def hooks(handles: list[Any]) -> Iterator[None]:
    try:
        yield
    finally:
        for handle in handles:
            handle.remove()


class ForwardCounter:
    """Absolute token positions of successive forward calls inside one generate().

    Batch size is 1 throughout this protocol, so position == token index.
    The first call is the prefill; every later call is one decode step.
    """

    def __init__(self) -> None:
        self.calls = 0
        self.seen = 0

    def advance(self, seq_len: int) -> tuple[int, int]:
        start = self.seen
        self.seen += int(seq_len)
        self.calls += 1
        return start, self.seen

    @property
    def is_prefill(self) -> bool:
        return self.calls == 1
