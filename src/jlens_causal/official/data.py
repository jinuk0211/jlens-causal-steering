"""Turn Tau2 repair pairs into the prompt/response strings the upstreams expect.

Every upstream baseline consumes some variant of ``(prompt, positive answer,
negative answer)``.  Here the prompt is the exact chat-template rendering the
Tau2 backend feeds to ``model.generate`` (same tools, same template kwargs, a
trailing generation header) and the answers are the rendered repaired versus
failed assistant actions that follow it.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.failure_caa import read_failure_pairs, tau_messages_for_hf
from jlens_causal.failure_cast import read_failure_cast_condition_pairs

ASSISTANT_END = "<|im_end|>"


@dataclass(frozen=True)
class RenderedPair:
    pair_id: str
    split: str
    task_id: str
    failure_category: str
    prompt: str
    positive: str
    negative: str
    positive_message: dict[str, Any]
    negative_message: dict[str, Any]
    context: list[dict[str, Any]]


@dataclass(frozen=True)
class RenderedConditionPair:
    pair_id: str
    split: str
    failure_category: str
    positive_prompt: str
    negative_prompt: str


@dataclass(frozen=True)
class RenderSettings:
    tools: list[dict[str, Any]]
    chat_template_kwargs: dict[str, Any]
    assistant_end: str = ASSISTANT_END


def render(
    tokenizer: Any,
    messages: list[dict[str, Any]],
    settings: RenderSettings,
    *,
    add_generation_prompt: bool,
) -> str:
    kwargs: dict[str, Any] = {
        "tokenize": False,
        "add_generation_prompt": add_generation_prompt,
        **settings.chat_template_kwargs,
    }
    if settings.tools:
        kwargs["tools"] = settings.tools
    return tokenizer.apply_chat_template(messages, **kwargs)


def _continuation(prompt: str, full: str, assistant_end: str) -> str:
    if not full.startswith(prompt):
        raise ValueError(
            "the rendered assistant turn does not extend the generation prompt; "
            "the chat template renders history differently from generation"
        )
    body = full[len(prompt) :].rstrip()
    if body.endswith(assistant_end):
        body = body[: -len(assistant_end)]
    if not body.strip():
        raise ValueError("rendered assistant action is empty")
    return body


def render_pair(tokenizer: Any, pair: dict[str, Any], settings: RenderSettings) -> RenderedPair:
    context = tau_messages_for_hf(pair["context_messages"])
    prompt = render(tokenizer, context, settings, add_generation_prompt=True)
    positive_full = render(
        tokenizer,
        [*context, *tau_messages_for_hf([pair["positive_repaired_message"]])],
        settings,
        add_generation_prompt=False,
    )
    negative_full = render(
        tokenizer,
        [*context, *tau_messages_for_hf([pair["negative_failed_message"]])],
        settings,
        add_generation_prompt=False,
    )
    positive = _continuation(prompt, positive_full, settings.assistant_end)
    negative = _continuation(prompt, negative_full, settings.assistant_end)
    if positive == negative:
        raise ValueError(f"pair {pair.get('pair_id')} renders identical actions")
    return RenderedPair(
        pair_id=str(pair["pair_id"]),
        split=str(pair["split"]),
        task_id=str(pair.get("task_id", "")),
        failure_category=str(pair["failure_category"]),
        prompt=prompt,
        positive=positive,
        negative=negative,
        positive_message=pair["positive_repaired_message"],
        negative_message=pair["negative_failed_message"],
        context=context,
    )


def load_rendered_pairs(
    tokenizer: Any,
    path: str | Path,
    settings: RenderSettings,
    *,
    failure_category: str,
    splits: Iterable[str],
) -> list[RenderedPair]:
    wanted = set(splits)
    return [
        render_pair(tokenizer, pair, settings)
        for pair in read_failure_pairs(path)
        if pair.get("failure_category") == failure_category and pair.get("split") in wanted
    ]


def load_rendered_condition_pairs(
    tokenizer: Any,
    path: str | Path,
    settings: RenderSettings,
    *,
    failure_category: str,
    splits: Iterable[str],
) -> list[RenderedConditionPair]:
    wanted = set(splits)
    rendered: list[RenderedConditionPair] = []
    for pair in read_failure_cast_condition_pairs(path):
        if pair.get("failure_category") != failure_category or pair.get("split") not in wanted:
            continue
        rendered.append(
            RenderedConditionPair(
                pair_id=str(pair["pair_id"]),
                split=str(pair["split"]),
                failure_category=failure_category,
                positive_prompt=render(
                    tokenizer,
                    tau_messages_for_hf(pair["positive_context_messages"]),
                    settings,
                    add_generation_prompt=True,
                ),
                negative_prompt=render(
                    tokenizer,
                    tau_messages_for_hf(pair["negative_context_messages"]),
                    settings,
                    add_generation_prompt=True,
                ),
            )
        )
    return rendered


def encode(tokenizer: Any, text: str) -> list[int]:
    """Tokenize rendered chat text exactly as the backend's template path does."""
    return list(tokenizer(text, add_special_tokens=False)["input_ids"])


def response_token_count(tokenizer: Any, prompt: str, response: str) -> int:
    """Tokens contributed by ``response`` when appended to ``prompt``."""
    return len(encode(tokenizer, prompt + response)) - len(encode(tokenizer, prompt))


def action_text(message: dict[str, Any]) -> str:
    """Human-readable assistant action for multiple-choice formats (CAA)."""
    parts: list[str] = []
    content = message.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(content.strip())
    for call in message.get("tool_calls") or []:
        arguments = json.dumps(call.get("arguments") or {}, ensure_ascii=False, sort_keys=True)
        parts.append(f"{call['name']}({arguments})")
    if not parts:
        raise ValueError("assistant action has neither content nor tool calls")
    return "\n".join(parts)


def pair_summary(pairs: Iterable[RenderedPair]) -> dict[str, Any]:
    items = list(pairs)
    return {
        "pair_ids": [pair.pair_id for pair in items],
        "splits": sorted({pair.split for pair in items}),
        "task_ids": sorted({pair.task_id for pair in items}),
        "count": len(items),
    }
