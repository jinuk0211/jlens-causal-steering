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


def render_messages(runtime: ModelRuntime, messages: list[dict[str, str]]) -> RenderedPrompt:
    """Render once and retain exact system/user token spans.

    Segment-aware intervention masks are derived from character offsets in the
    rendered chat template. The token IDs are checked against the template's
    native tokenized form so a tokenizer/template drift fails loudly.
    """
    if len(messages) != 2 or [item.get("role") for item in messages] != ["system", "user"]:
        raise ValueError("the isolated pilot requires exactly one system and one user message")
    rendered_text = runtime.tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )
    if not isinstance(rendered_text, str):
        raise TypeError("chat template did not return text")
    system_text = str(messages[0]["content"])
    user_text = str(messages[1]["content"])
    system_start = rendered_text.find(system_text)
    user_start = rendered_text.rfind(user_text)
    if system_start < 0 or user_start < 0 or user_start <= system_start:
        raise ValueError("could not locate system/user content in the rendered chat template")

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
        end=user_start + len(user_text),
    )
    system_positions = _content_positions(
        offsets,
        start=system_start,
        end=system_start + len(system_text),
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
