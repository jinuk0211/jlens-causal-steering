"""Pinned Hugging Face/Jacobian-lens runtime helpers."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any


@dataclass
class ModelRuntime:
    torch: Any
    tokenizer: Any
    hf_model: Any
    lens_model: Any
    lens: Any
    device: Any


@dataclass(frozen=True)
class RenderedPrompt:
    """Tokenized chat prompt with exact semantic segment positions."""

    input_ids: Any
    attention_mask: Any
    user_positions: tuple[int, ...]
    system_positions: tuple[int, ...]

    def __iter__(self):
        """Keep two-value unpacking compatibility with the v1 helper."""
        yield self.input_ids
        yield self.attention_mask


@dataclass(frozen=True)
class RenderedConversation:
    """Tokenized multi-turn chat with exact template-rendered message spans."""

    input_ids: Any
    attention_mask: Any
    message_positions: dict[int, tuple[int, ...]]


@dataclass(frozen=True)
class GenerationResult:
    text: str
    completion_ids: list[int]
    terminated_by_eos: bool
    hit_token_limit: bool
    termination_reason: str


def _resolve_dtype(torch: Any, value: str) -> Any:
    if value == "auto":
        return "auto"
    dtype = getattr(torch, value, None)
    if dtype is None:
        raise ValueError(f"unknown torch dtype {value!r}")
    return dtype


def load_runtime(model_config: dict[str, Any]) -> ModelRuntime:
    """Load one pinned model/tokenizer/lens bundle onto a single device."""
    import jlens
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    requested_device = str(model_config.get("device", "auto"))
    device = (
        "cuda" if requested_device == "auto" and torch.cuda.is_available() else requested_device
    )
    if device == "auto":
        device = "cpu"
    dtype = _resolve_dtype(torch, str(model_config.get("dtype", "auto")))
    tokenizer = AutoTokenizer.from_pretrained(
        model_config["model_id"],
        revision=model_config["model_revision"],
        trust_remote_code=bool(model_config.get("trust_remote_code", False)),
    )
    kwargs: dict[str, Any] = {
        "revision": model_config["model_revision"],
        "dtype": dtype,
        "trust_remote_code": bool(model_config.get("trust_remote_code", False)),
    }
    attention = str(model_config.get("attention", "auto"))
    if attention != "auto":
        kwargs["attn_implementation"] = attention
    hf_model = AutoModelForCausalLM.from_pretrained(model_config["model_id"], **kwargs)
    hf_model.to(device)
    hf_model.eval()
    lens_model = jlens.from_hf(hf_model, tokenizer, force_bos=False)
    lens = jlens.JacobianLens.from_pretrained(
        model_config["lens_repo"],
        filename=model_config["lens_file"],
        revision=model_config["lens_revision"],
    )
    if lens.d_model != lens_model.d_model:
        raise ValueError(
            f"lens width {lens.d_model} does not match model width {lens_model.d_model}"
        )
    return ModelRuntime(
        torch=torch,
        tokenizer=tokenizer,
        hf_model=hf_model,
        lens_model=lens_model,
        lens=lens,
        device=lens_model.input_device,
    )


def _content_positions(offsets: list[tuple[int, int]], *, start: int, end: int) -> tuple[int, ...]:
    return tuple(
        index
        for index, (left, right) in enumerate(offsets)
        if right > left and right > start and left < end
    )


def _render_chat_text(tokenizer: Any, messages: list[dict[str, str]]) -> str:
    rendered = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(rendered, str):
        raise TypeError("chat template did not return text")
    return rendered


def _rendered_message_span(
    tokenizer: Any,
    messages: list[dict[str, str]],
    *,
    message_index: int,
    rendered_text: str,
) -> tuple[int, int]:
    """Locate content after the chat template has transformed it.

    Qwen's template trims message content, so searching for the source document
    verbatim fails whenever a benchmark file ends in a newline.  Render a
    sentinel variant through the same template instead; the unchanged prefix
    and suffix delimit exactly the content emitted by the template without
    making assumptions about whitespace or role-marker tokenization.
    """
    marker = f"\ue000JLENS_MESSAGE_{message_index}\ue001"
    while marker in rendered_text or any(
        marker in str(item.get("content", "")) for item in messages
    ):
        marker += "_"
    variant = [dict(item) for item in messages]
    variant[message_index]["content"] = marker
    sentinel_text = _render_chat_text(tokenizer, variant)
    if sentinel_text.count(marker) != 1:
        raise ValueError(
            f"chat template did not preserve the message-{message_index} span sentinel exactly once"
        )
    marker_start = sentinel_text.index(marker)
    marker_end = marker_start + len(marker)
    prefix = sentinel_text[:marker_start]
    suffix = sentinel_text[marker_end:]
    if not rendered_text.startswith(prefix) or not rendered_text.endswith(suffix):
        raise ValueError(
            f"chat template changes structure when rendering message {message_index} content"
        )
    start = len(prefix)
    end = len(rendered_text) - len(suffix)
    if start >= end:
        raise ValueError(f"chat template rendered an empty message-{message_index} content span")
    return start, end


def render_conversation(
    runtime: ModelRuntime,
    messages: list[dict[str, str]],
    *,
    message_indices: Iterable[int],
) -> RenderedConversation:
    """Render an arbitrary chat and retain selected message-content token spans."""
    indices = tuple(sorted(set(int(index) for index in message_indices)))
    if not messages or not indices:
        raise ValueError("messages and message_indices cannot be empty")
    if indices[0] < 0 or indices[-1] >= len(messages):
        raise ValueError("message index is outside the conversation")
    rendered_text = _render_chat_text(runtime.tokenizer, messages)
    character_spans = {
        index: _rendered_message_span(
            runtime.tokenizer,
            messages,
            message_index=index,
            rendered_text=rendered_text,
        )
        for index in indices
    }
    with_offsets = runtime.tokenizer(
        rendered_text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    offset_ids = with_offsets["input_ids"]
    offsets_value = with_offsets["offset_mapping"]
    offsets = [tuple(map(int, pair)) for pair in offsets_value[0].tolist()]
    encoded = runtime.tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_tensors="pt",
    )
    if hasattr(encoded, "input_ids"):
        input_ids = encoded.input_ids
        attention_mask = getattr(encoded, "attention_mask", None)
    elif isinstance(encoded, dict):
        input_ids = encoded["input_ids"]
        attention_mask = encoded.get("attention_mask")
    else:
        input_ids = encoded
        attention_mask = None
    if input_ids.ndim == 1:
        input_ids = input_ids.unsqueeze(0)
    if offset_ids.ndim == 1:
        offset_ids = offset_ids.unsqueeze(0)
    if input_ids.detach().cpu().tolist() != offset_ids.detach().cpu().tolist():
        special_id = getattr(runtime.tokenizer, "bos_token_id", None)
        offset_values = offset_ids.detach().cpu().tolist()
        input_values = input_ids.detach().cpu().tolist()
        if (
            special_id is not None
            and len(input_values[0]) == len(offset_values[0]) + 1
            and input_values[0][0] == int(special_id)
            and input_values[0][1:] == offset_values[0]
        ):
            offsets.insert(0, (0, 0))
        else:
            raise ValueError("chat-template tokens disagree with offset-mapped tokenizer output")
    positions = {
        index: _content_positions(offsets, start=span[0], end=span[1])
        for index, span in character_spans.items()
    }
    if any(not value for value in positions.values()):
        raise ValueError("rendered conversation has an empty selected message span")
    input_ids = input_ids.to(runtime.device)
    if attention_mask is None:
        attention_mask = runtime.torch.ones_like(input_ids)
    elif attention_mask.ndim == 1:
        attention_mask = attention_mask.unsqueeze(0)
    return RenderedConversation(
        input_ids=input_ids,
        attention_mask=attention_mask.to(runtime.device),
        message_positions=positions,
    )


def render_messages(runtime: ModelRuntime, messages: list[dict[str, str]]) -> RenderedPrompt:
    """Render once and retain exact system/user token spans.

    Segment-aware intervention masks are derived from character offsets in the
    rendered chat template. The token IDs are checked against the template's
    native tokenized form so a tokenizer/template drift fails loudly.
    """
    if len(messages) != 2 or [item.get("role") for item in messages] != ["system", "user"]:
        raise ValueError("the isolated pilot requires exactly one system and one user message")
    rendered_text = _render_chat_text(runtime.tokenizer, messages)
    system_start, system_end = _rendered_message_span(
        runtime.tokenizer,
        messages,
        message_index=0,
        rendered_text=rendered_text,
    )
    user_start, user_end = _rendered_message_span(
        runtime.tokenizer,
        messages,
        message_index=1,
        rendered_text=rendered_text,
    )
    if system_end > user_start:
        raise ValueError("rendered system and user content spans overlap or are out of order")

    with_offsets = runtime.tokenizer(
        rendered_text,
        add_special_tokens=False,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    offset_ids = with_offsets["input_ids"]
    offsets_value = with_offsets["offset_mapping"]
    offsets = [tuple(map(int, pair)) for pair in offsets_value[0].tolist()]
    encoded = runtime.tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=True,
        enable_thinking=False,
        return_tensors="pt",
    )
    if hasattr(encoded, "input_ids"):
        input_ids = encoded.input_ids
        attention_mask = getattr(encoded, "attention_mask", None)
    elif isinstance(encoded, dict):
        input_ids = encoded["input_ids"]
        attention_mask = encoded.get("attention_mask")
    else:
        input_ids = encoded
        attention_mask = None
    if input_ids.ndim == 1:
        input_ids = input_ids.unsqueeze(0)
    if offset_ids.ndim == 1:
        offset_ids = offset_ids.unsqueeze(0)
    if input_ids.detach().cpu().tolist() != offset_ids.detach().cpu().tolist():
        special_id = getattr(runtime.tokenizer, "bos_token_id", None)
        offset_values = offset_ids.detach().cpu().tolist()
        input_values = input_ids.detach().cpu().tolist()
        if (
            special_id is not None
            and len(input_values[0]) == len(offset_values[0]) + 1
            and input_values[0][0] == int(special_id)
            and input_values[0][1:] == offset_values[0]
        ):
            offsets.insert(0, (0, 0))
        else:
            raise ValueError("chat-template tokens disagree with offset-mapped tokenizer output")
    user_positions = _content_positions(
        offsets,
        start=user_start,
        end=user_end,
    )
    system_positions = _content_positions(
        offsets,
        start=system_start,
        end=system_end,
    )
    if not user_positions or not system_positions:
        raise ValueError("rendered prompt has an empty system or user token span")
    input_ids = input_ids.to(runtime.device)
    if attention_mask is None:
        attention_mask = runtime.torch.ones_like(input_ids)
    elif attention_mask.ndim == 1:
        attention_mask = attention_mask.unsqueeze(0)
    return RenderedPrompt(
        input_ids=input_ids,
        attention_mask=attention_mask.to(runtime.device),
        user_positions=user_positions,
        system_positions=system_positions,
    )


def token_ids_sha256(input_ids: Any) -> str:
    values = [int(value) for value in input_ids.detach().cpu().reshape(-1).tolist()]
    return hashlib.sha256(",".join(map(str, values)).encode()).hexdigest()


def completion_status(
    completion_ids: list[int],
    *,
    max_new_tokens: int,
    eos_token_ids: set[int],
) -> tuple[bool, bool, str]:
    """Classify termination without trusting backend-specific finish strings."""
    terminated_by_eos = bool(completion_ids and completion_ids[-1] in eos_token_ids)
    hit_token_limit = len(completion_ids) >= max_new_tokens and not terminated_by_eos
    if terminated_by_eos:
        reason = "eos"
    elif hit_token_limit:
        reason = "length"
    else:
        reason = "other_stop"
    return terminated_by_eos, hit_token_limit, reason


def _eos_token_ids(runtime: ModelRuntime) -> set[int]:
    values: set[int] = set()
    candidates = (
        getattr(runtime.tokenizer, "eos_token_id", None),
        getattr(getattr(runtime.hf_model, "generation_config", None), "eos_token_id", None),
    )
    for candidate in candidates:
        if candidate is None:
            continue
        if isinstance(candidate, (list, tuple, set)):
            values.update(int(value) for value in candidate)
        else:
            values.add(int(candidate))
    return values


@contextmanager
def capture_block_outputs(blocks: Any, layers: Iterable[int]):
    """Capture block outputs without modifying them."""
    activations: dict[int, Any] = {}
    handles = []

    def make_hook(index: int):
        def hook(_module: Any, _inputs: Any, output: Any) -> None:
            activations[index] = output if hasattr(output, "shape") else output[0]

        return hook

    try:
        for layer in sorted(set(layers)):
            handles.append(blocks[layer].register_forward_hook(make_hook(layer)))
        yield activations
    finally:
        for handle in handles:
            handle.remove()


def generate_text(
    runtime: ModelRuntime,
    *,
    input_ids: Any,
    attention_mask: Any,
    generation_config: dict[str, Any],
) -> GenerationResult:
    """Generate deterministically under the caller's active intervention hooks."""
    torch = runtime.torch
    seed = int(generation_config["seed"])
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    kwargs = {
        "max_new_tokens": int(generation_config["max_new_tokens"]),
        "do_sample": bool(generation_config.get("do_sample", False)),
        "use_cache": bool(generation_config.get("use_cache", True)),
    }
    for key in ("temperature", "top_p", "top_k"):
        if key in generation_config:
            kwargs[key] = generation_config[key]
    if runtime.tokenizer.pad_token_id is None:
        kwargs["pad_token_id"] = runtime.tokenizer.eos_token_id
    with torch.inference_mode():
        output = runtime.hf_model.generate(
            input_ids=input_ids,
            attention_mask=attention_mask,
            **kwargs,
        )
    sequences = output.sequences if hasattr(output, "sequences") else output
    completion = [int(item) for item in sequences[0, input_ids.shape[1] :].detach().cpu().tolist()]
    text = runtime.tokenizer.decode(
        completion,
        skip_special_tokens=False,
        clean_up_tokenization_spaces=False,
    )
    terminated_by_eos, hit_token_limit, termination_reason = completion_status(
        completion,
        max_new_tokens=int(generation_config["max_new_tokens"]),
        eos_token_ids=_eos_token_ids(runtime),
    )
    return GenerationResult(
        text=text,
        completion_ids=completion,
        terminated_by_eos=terminated_by_eos,
        hit_token_limit=hit_token_limit,
        termination_reason=termination_reason,
    )
