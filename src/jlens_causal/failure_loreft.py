"""Generic LoReFT training from validated Tau2 failure-repair pairs."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from jlens_causal.baselines import load_loreft_artifact, save_loreft_artifact
from jlens_causal.failure_caa import tau_messages_for_hf, template_ids_and_offsets
from jlens_causal.failure_core_extractors import select_failure_pairs
from jlens_causal.loreft import LoReFTExample, train_loreft_artifact
from jlens_causal.modeling import ModelRuntime

_SOURCE = {
    "repository": "stanfordnlp/pyreft",
    "revision": "dafd0995a366d7b47160a337dcc388eda7431821",
}


def response_suffix_positions(
    prompt_token_ids: Sequence[int], full_token_ids: Sequence[int]
) -> tuple[int, tuple[int, ...]]:
    """Locate the response after an exact chat-template generation prefix."""
    prompt = [int(value) for value in prompt_token_ids]
    full = [int(value) for value in full_token_ids]
    if not prompt or len(full) <= len(prompt) or full[: len(prompt)] != prompt:
        raise ValueError(
            "positive action is not an exact continuation of the rendered generation prompt"
        )
    return len(prompt) - 1, tuple(range(len(prompt), len(full)))


def failure_loreft_example(
    runtime: ModelRuntime,
    pair: dict[str, Any],
    *,
    tools: list[dict[str, Any]],
) -> LoReFTExample:
    """Render one repair as the supervised continuation of its pre-failure context."""
    context = tau_messages_for_hf(pair["context_messages"])
    repaired = tau_messages_for_hf([pair["positive_repaired_message"]])
    prompt_ids, _, _ = template_ids_and_offsets(
        runtime,
        context,
        tools=tools,
        add_generation_prompt=True,
    )
    full_ids, _, _ = template_ids_and_offsets(
        runtime,
        [*context, *repaired],
        tools=tools,
        add_generation_prompt=False,
    )
    prompt_values = prompt_ids.detach().cpu().tolist()[0]
    full_values = full_ids.detach().cpu().tolist()[0]
    boundary, positions = response_suffix_positions(prompt_values, full_values)
    attention_mask = runtime.torch.ones_like(full_ids)
    return LoReFTExample(
        example_id=str(pair["pair_id"]),
        input_ids=full_ids,
        attention_mask=attention_mask,
        response_positions=positions,
        boundary_position=boundary,
    )


def train_failure_loreft(
    runtime: ModelRuntime,
    pairs: Iterable[dict[str, Any]],
    *,
    model_id: str,
    model_revision: str,
    failure_category: str,
    layers: Iterable[int],
    ranks: Iterable[int],
    output_dir: str | Path,
    tools: list[dict[str, Any]],
    epochs: int = 8,
    learning_rate: float = 1e-3,
    weight_decay: float = 0.0,
    max_grad_norm: float = 1.0,
    seed: int = 42,
    force: bool = False,
) -> dict[str, Any]:
    """Train repair-only LoReFT parameters with task-disjoint validation."""
    if not tools:
        raise ValueError("exact TauBench LoReFT training requires airline tool schemas")
    train_pairs, validation_pairs = select_failure_pairs(pairs, failure_category)
    layer_tuple = tuple(sorted(set(int(layer) for layer in layers)))
    rank_tuple = tuple(sorted(set(int(rank) for rank in ranks)))
    if not layer_tuple or not rank_tuple or min(rank_tuple) <= 0:
        raise ValueError("LoReFT layers and positive ranks must be non-empty")
    train_examples = [failure_loreft_example(runtime, pair, tools=tools) for pair in train_pairs]
    validation_examples = [
        failure_loreft_example(runtime, pair, tools=tools) for pair in validation_pairs
    ]
    output = Path(output_dir).expanduser().resolve()
    completed: list[dict[str, Any]] = []
    for rank in rank_tuple:
        path = output / f"loreft-rank-{rank}.pt"
        if path.is_file() and not force:
            artifact = load_loreft_artifact(runtime.torch, path, expected_model_id=model_id)
            completed.append(
                {
                    "rank": rank,
                    "path": str(path),
                    "validation_loss": float(artifact["validation_loss"]),
                    "status": "already_complete",
                }
            )
            continue
        artifact = train_loreft_artifact(
            runtime,
            model_id=model_id,
            model_revision=model_revision,
            layers=layer_tuple,
            rank=rank,
            train_examples=train_examples,
            validation_examples=validation_examples,
            epochs=int(epochs),
            learning_rate=float(learning_rate),
            weight_decay=float(weight_decay),
            max_grad_norm=float(max_grad_norm),
            seed=int(seed) + rank,
            benchmark="taubench-airline-failure-modes",
            site="block_output",
            source=_SOURCE,
        )
        save_loreft_artifact(runtime.torch, artifact, path)
        completed.append(
            {
                "rank": rank,
                "path": str(path),
                "validation_loss": float(artifact["validation_loss"]),
                "status": "trained",
            }
        )
    return {
        "failure_category": failure_category,
        "train_examples": len(train_examples),
        "validation_examples": len(validation_examples),
        "artifacts": completed,
    }
