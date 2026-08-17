"""Generic CAA extraction from validated failed-versus-repaired Tau2 actions."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from jlens_causal.baselines import build_caa_artifact, save_caa_artifact
from jlens_causal.modeling import ModelRuntime, capture_block_outputs


def read_failure_pairs(path: str | Path) -> list[dict[str, Any]]:
    pairs: list[dict[str, Any]] = []
    with Path(path).expanduser().resolve().open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                value = json.loads(line)
                if value.get("schema_version") != "agent-failure-repair-pair-v1":
                    raise ValueError("unsupported failure repair pair schema")
                pairs.append(value)
    return pairs


def tau_messages_for_hf(messages: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Match Tau2's local backend chat representation and omit generated call IDs."""
    converted: list[dict[str, Any]] = []
    for message in messages:
        role = message.get("role")
        if role in {"system", "user"}:
            converted.append({"role": role, "content": message.get("content")})
        elif role == "assistant":
            item: dict[str, Any] = {
                "role": "assistant",
                "content": message.get("content"),
            }
            calls = message.get("tool_calls")
            if calls:
                item["tool_calls"] = [
                    {
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": call.get("arguments") or {},
                        },
                    }
                    for call in calls
                ]
            converted.append(item)
        elif role == "tool":
            nested = message.get("tool_messages")
            candidates = nested if isinstance(nested, list) else [message]
            converted.extend(
                {
                    "role": "tool",
                    "content": candidate.get("content"),
                    "tool_call_id": candidate.get("id", ""),
                }
                for candidate in candidates
            )
        else:
            raise ValueError(f"unsupported Tau2 role {role!r}")
    return converted


def divergent_character_spans(left: str, right: str) -> tuple[tuple[int, int], tuple[int, int]]:
    """Return the minimal non-common action region in two rendered conversations."""
    prefix = 0
    limit = min(len(left), len(right))
    while prefix < limit and left[prefix] == right[prefix]:
        prefix += 1
    suffix = 0
    left_remaining = len(left) - prefix
    right_remaining = len(right) - prefix
    while (
        suffix < left_remaining
        and suffix < right_remaining
        and left[len(left) - suffix - 1] == right[len(right) - suffix - 1]
    ):
        suffix += 1
    left_end = len(left) - suffix
    right_end = len(right) - suffix
    if prefix >= left_end or prefix >= right_end:
        raise ValueError("paired rendered actions do not contain two non-empty divergent spans")
    return (prefix, left_end), (prefix, right_end)


def template_ids_and_offsets(
    runtime: ModelRuntime,
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
    add_generation_prompt: bool = False,
) -> tuple[Any, list[tuple[int, int]], str]:
    template_kwargs: dict[str, Any] = {
        "add_generation_prompt": bool(add_generation_prompt),
        "enable_thinking": False,
    }
    if tools:
        template_kwargs["tools"] = tools
    rendered = runtime.tokenizer.apply_chat_template(messages, tokenize=False, **template_kwargs)
    encoded = runtime.tokenizer(
        rendered,
        add_special_tokens=False,
        return_offsets_mapping=True,
        return_tensors="pt",
    )
    offsets = [tuple(map(int, pair)) for pair in encoded["offset_mapping"][0].tolist()]
    template = runtime.tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        return_tensors="pt",
        **template_kwargs,
    )
    if hasattr(template, "input_ids"):
        input_ids = template.input_ids
    elif isinstance(template, dict):
        input_ids = template["input_ids"]
    else:
        input_ids = template
    if input_ids.ndim == 1:
        input_ids = input_ids.unsqueeze(0)
    offset_ids = encoded["input_ids"]
    template_values = input_ids.detach().cpu().tolist()[0]
    offset_values = offset_ids.detach().cpu().tolist()[0]
    if template_values != offset_values:
        bos = getattr(runtime.tokenizer, "bos_token_id", None)
        if (
            bos is not None
            and template_values[:1] == [int(bos)]
            and template_values[1:] == offset_values
        ):
            offsets.insert(0, (0, 0))
        else:
            raise ValueError("chat-template token IDs disagree with offset tokenization")
    return input_ids.to(runtime.device), offsets, rendered


def _last_span_position(offsets: list[tuple[int, int]], span: tuple[int, int]) -> int:
    start, end = span
    positions = [
        index
        for index, (left, right) in enumerate(offsets)
        if right > left and right > start and left < end
    ]
    if not positions:
        raise ValueError("divergent action span has no token positions")
    return positions[-1]


def paired_action_activations(
    runtime: ModelRuntime,
    *,
    context_messages: list[dict[str, Any]],
    positive_message: dict[str, Any],
    negative_message: dict[str, Any],
    layers: Iterable[int],
    tools: list[dict[str, Any]] | None = None,
) -> tuple[dict[int, Any], dict[int, Any]]:
    """Capture the last token that differs between repaired and failed actions."""
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    (positive_ids, positive_position), (negative_ids, negative_position) = paired_action_inputs(
        runtime,
        context_messages=context_messages,
        positive_message=positive_message,
        negative_message=negative_message,
        tools=tools,
    )

    def capture(input_ids: Any, position: int) -> dict[int, Any]:
        with (
            runtime.torch.inference_mode(),
            capture_block_outputs(runtime.lens_model.layers, layer_tuple) as activations,
        ):
            runtime.lens_model.forward(input_ids)
        return {
            layer: activations[layer][0, position].detach().float().cpu() for layer in layer_tuple
        }

    return capture(positive_ids, positive_position), capture(negative_ids, negative_position)


def paired_action_inputs(
    runtime: ModelRuntime,
    *,
    context_messages: list[dict[str, Any]],
    positive_message: dict[str, Any],
    negative_message: dict[str, Any],
    tools: list[dict[str, Any]] | None = None,
) -> tuple[tuple[Any, int], tuple[Any, int]]:
    """Render a pair once and return exact IDs plus divergent token positions."""
    context = tau_messages_for_hf(context_messages)
    positive_messages = [*context, *tau_messages_for_hf([positive_message])]
    negative_messages = [*context, *tau_messages_for_hf([negative_message])]
    positive_ids, positive_offsets, positive_text = template_ids_and_offsets(
        runtime, positive_messages, tools=tools
    )
    negative_ids, negative_offsets, negative_text = template_ids_and_offsets(
        runtime, negative_messages, tools=tools
    )
    positive_span, negative_span = divergent_character_spans(positive_text, negative_text)
    positive_position = _last_span_position(positive_offsets, positive_span)
    negative_position = _last_span_position(negative_offsets, negative_span)
    return (positive_ids, positive_position), (negative_ids, negative_position)


def extract_failure_caa(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    output_dir: str | Path,
    tools: list[dict[str, Any]] | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Build one repair-minus-failure CAA artifact per requested model layer."""
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    selected = [
        pair
        for pair in pairs
        if pair.get("split") == "train" and pair.get("failure_category") == failure_category
    ]
    if len(selected) < 2:
        raise ValueError("CAA extraction requires at least two training repair pairs")
    output = Path(output_dir).expanduser().resolve()
    paths = {layer: output / f"caa-layer-{layer}.pt" for layer in layer_tuple}
    if not force and all(path.is_file() for path in paths.values()):
        return {"pair_count": len(selected), "paths": [str(path) for path in paths.values()]}
    positive: dict[int, list[Any]] = {layer: [] for layer in layer_tuple}
    negative: dict[int, list[Any]] = {layer: [] for layer in layer_tuple}
    for pair in selected:
        positive_values, negative_values = paired_action_activations(
            runtime,
            context_messages=pair["context_messages"],
            positive_message=pair["positive_repaired_message"],
            negative_message=pair["negative_failed_message"],
            layers=layer_tuple,
            tools=tools,
        )
        for layer in layer_tuple:
            positive[layer].append(positive_values[layer])
            negative[layer].append(negative_values[layer])
    written: list[str] = []
    for layer in layer_tuple:
        artifact = build_caa_artifact(
            runtime.torch,
            model_id=model_id,
            model_revision=model_revision,
            layer=layer,
            positive=positive[layer],
            negative=negative[layer],
            pair_ids=[str(pair["pair_id"]) for pair in selected],
            positive_label="validated_repaired_agent_action",
            negative_label="observed_failed_agent_action",
            extraction_site="last_token_of_pairwise_divergent_rendered_action_span",
            benchmark="taubench-airline-failure-modes",
            calibration_split={
                "failure_category": failure_category,
                "split": "train",
                "future_messages_excluded": True,
                "pair_schema": "agent-failure-repair-pair-v1",
                "tool_schema_sha256": (
                    hashlib.sha256(
                        json.dumps(
                            tools,
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest()
                    if tools
                    else None
                ),
            },
        )
        written.append(str(save_caa_artifact(runtime.torch, artifact, paths[layer])))
    return {"pair_count": len(selected), "paths": written}
