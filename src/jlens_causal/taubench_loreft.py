"""LoReFT training for TauBench airline Task 18."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jlens_causal.baselines import (
    build_loreft_artifact,
    load_loreft_artifact,
    save_loreft_artifact,
)
from jlens_causal.loreft import LoReFTExample, train_loreft_artifact
from jlens_causal.modeling import ModelRuntime
from jlens_causal.taubench_caa import (
    TauBenchCAAConfig,
    _failure_prompt_prefix,
    load_taubench_caa_config,
)

TAUBENCH_LOREFT_SCHEMA = "taubench-failure-loreft-v1"


@dataclass(frozen=True)
class TauBenchLoReFTConfig:
    path: Path
    raw: dict[str, Any]
    source_meta_path: Path
    behavior_config: TauBenchCAAConfig
    output_dir: Path

    @property
    def model(self) -> dict[str, Any]:
        return self.raw["model"]

    @property
    def training(self) -> dict[str, Any]:
        return self.raw["training"]

    def artifact_path(self, rank: int) -> Path:
        return self.output_dir / "artifacts" / f"loreft-rank-{int(rank)}.pt"

    def random_artifact_path(self, seed: int) -> Path:
        return self.output_dir / "artifacts" / f"loreft-random-seed-{int(seed)}.pt"


def load_taubench_loreft_config(path: str | Path) -> TauBenchLoReFTConfig:
    path = Path(path).expanduser().resolve()
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != TAUBENCH_LOREFT_SCHEMA:
        raise ValueError("unsupported TauBench LoReFT config schema")
    if raw.get("benchmark") != "taubench-airline" or str(raw.get("task_id")) != "18":
        raise ValueError("the failure-specific LoReFT pilot must target airline task 18")
    model = raw.get("model")
    if not isinstance(model, dict) or not model.get("model_id"):
        raise ValueError("model.model_id is required")
    if not isinstance(model.get("model_revision"), str) or len(model["model_revision"]) != 40:
        raise ValueError("model.model_revision must be a pinned 40-character commit")
    source = raw.get("source")
    if (
        not isinstance(source, dict)
        or source.get("repository") != "stanfordnlp/pyreft"
        or not isinstance(source.get("revision"), str)
        or len(source["revision"]) != 40
    ):
        raise ValueError("LoReFT source must pin its official repository to a commit")
    training = raw.get("training")
    if not isinstance(training, dict):
        raise ValueError("LoReFT training section is required")
    layers = training.get("layers")
    ranks = training.get("ranks")
    train_indices = training.get("train_pair_indices")
    validation_indices = training.get("validation_pair_indices")
    if (
        not isinstance(layers, list)
        or not layers
        or not all(isinstance(value, int) and value >= 0 for value in layers)
        or len(set(layers)) != len(layers)
    ):
        raise ValueError("LoReFT layers must be unique non-negative integers")
    if (
        not isinstance(ranks, list)
        or not ranks
        or not all(isinstance(value, int) and value > 0 for value in ranks)
        or int(training.get("primary_rank", 0)) not in ranks
    ):
        raise ValueError("LoReFT ranks must be positive and include primary_rank")
    if (
        not isinstance(train_indices, list)
        or not isinstance(validation_indices, list)
        or not train_indices
        or not validation_indices
        or not all(isinstance(value, int) and value >= 0 for value in train_indices + validation_indices)
        or set(train_indices).intersection(validation_indices)
    ):
        raise ValueError("LoReFT train and validation indices must be non-empty and disjoint")
    if training.get("site") != "block_output" or training.get("position") != "last_prompt_token":
        raise ValueError("LoReFT must target block_output at last_prompt_token")
    if (
        int(training.get("epochs", 0)) <= 0
        or float(training.get("learning_rate", 0.0)) <= 0.0
        or float(training.get("weight_decay", -1.0)) < 0.0
        or float(training.get("max_grad_norm", 0.0)) <= 0.0
    ):
        raise ValueError("LoReFT training hyperparameters are invalid")
    seeds = training.get("random_seeds")
    if not isinstance(seeds, list) or len(seeds) < 3 or len(set(seeds)) != len(seeds):
        raise ValueError("LoReFT requires three unique random controls")
    source_meta = Path(raw["source_meta_path"]).expanduser()
    behavior_path = Path(raw["behavior_source_config"]).expanduser()
    output = Path(raw["output_dir"]).expanduser()
    source_meta = (
        source_meta if source_meta.is_absolute() else path.parent / source_meta
    ).resolve()
    behavior_path = (
        behavior_path if behavior_path.is_absolute() else path.parent / behavior_path
    ).resolve()
    output = (output if output.is_absolute() else path.parent / output).resolve()
    if not source_meta.is_file():
        raise FileNotFoundError(f"Task 18 source metadata is missing: {source_meta}")
    behavior_config = load_taubench_caa_config(behavior_path)
    pair_count = len(behavior_config.extraction["positive_responses"])
    if set(train_indices + validation_indices) != set(range(pair_count)):
        raise ValueError("LoReFT train/validation indices must partition all behavior pairs")
    if behavior_config.source_meta_path != source_meta:
        raise ValueError("LoReFT and behavior configs do not share the source prompt")
    return TauBenchLoReFTConfig(path, raw, source_meta, behavior_config, output)


def _examples(config: TauBenchLoReFTConfig, runtime: ModelRuntime) -> list[LoReFTExample]:
    prefix = _failure_prompt_prefix(config.behavior_config)
    closing = str(config.training["assistant_closing_text"])
    examples = []
    for index, response in enumerate(
        config.behavior_config.extraction["positive_responses"]
    ):
        full_text = prefix + response + closing
        encoded = runtime.tokenizer(
            full_text,
            add_special_tokens=False,
            return_offsets_mapping=True,
            return_tensors="pt",
        )
        input_ids = encoded["input_ids"].to(runtime.device)
        attention_mask = encoded.get("attention_mask")
        if attention_mask is None:
            attention_mask = runtime.torch.ones_like(input_ids)
        else:
            attention_mask = attention_mask.to(runtime.device)
        offsets = [tuple(map(int, item)) for item in encoded["offset_mapping"][0].tolist()]
        start = len(prefix)
        end = start + len(response)
        positions = tuple(
            token_index
            for token_index, (left, right) in enumerate(offsets)
            if right > left and right > start and left < end
        )
        if not positions or positions[0] == 0:
            raise ValueError("LoReFT response has no prompt boundary")
        examples.append(
            LoReFTExample(
                example_id=f"task18-binding-pair-{index:02d}",
                input_ids=input_ids,
                attention_mask=attention_mask,
                response_positions=positions,
                boundary_position=positions[0] - 1,
            )
        )
    return examples


def train_taubench_task18_loreft(
    config: TauBenchLoReFTConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> dict[str, Any]:
    examples = _examples(config, runtime)
    train_indices = [int(value) for value in config.training["train_pair_indices"]]
    validation_indices = [
        int(value) for value in config.training["validation_pair_indices"]
    ]
    completed = []
    layers = tuple(int(value) for value in config.training["layers"])
    for rank_value in config.training["ranks"]:
        rank = int(rank_value)
        path = config.artifact_path(rank)
        if path.is_file() and not force:
            artifact = load_loreft_artifact(
                runtime.torch, path, expected_model_id=config.model["model_id"]
            )
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
            model_id=config.model["model_id"],
            model_revision=config.model["model_revision"],
            layers=layers,
            rank=rank,
            train_examples=[examples[index] for index in train_indices],
            validation_examples=[examples[index] for index in validation_indices],
            epochs=int(config.training["epochs"]),
            learning_rate=float(config.training["learning_rate"]),
            weight_decay=float(config.training["weight_decay"]),
            max_grad_norm=float(config.training["max_grad_norm"]),
            seed=int(config.training["seed"]) + rank,
            benchmark="taubench-airline-task18",
            site=config.training["site"],
            source=config.raw["source"],
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
    primary_rank = int(config.training["primary_rank"])
    d_model = int(runtime.lens_model.d_model)
    for seed_value in config.training["random_seeds"]:
        seed = int(seed_value)
        path = config.random_artifact_path(seed)
        if path.is_file() and not force:
            completed.append(
                {
                    "rank": primary_rank,
                    "path": str(path),
                    "status": "random_control_already_complete",
                }
            )
            continue
        generator = runtime.torch.Generator(device="cpu")
        generator.manual_seed(seed)
        rotations = {}
        weights = {}
        biases = {}
        bound = d_model**-0.5
        for layer in layers:
            rotations[layer] = runtime.torch.linalg.qr(
                runtime.torch.randn(d_model, primary_rank, generator=generator),
                mode="reduced",
            ).Q
            weights[layer] = runtime.torch.empty(primary_rank, d_model).uniform_(
                -bound, bound, generator=generator
            )
            biases[layer] = runtime.torch.empty(primary_rank).uniform_(
                -bound, bound, generator=generator
            )
        artifact = build_loreft_artifact(
            runtime.torch,
            model_id=config.model["model_id"],
            model_revision=config.model["model_revision"],
            layers=layers,
            rotate_by_layer=rotations,
            learned_weight_by_layer=weights,
            learned_bias_by_layer=biases,
            train_example_ids=[examples[index].example_id for index in train_indices],
            validation_example_ids=[
                examples[index].example_id for index in validation_indices
            ],
            rank=primary_rank,
            benchmark="taubench-airline-task18-random-control",
            training={"kind": "untrained_random_initialization", "seed": seed},
            validation_loss=0.0,
            site=config.training["site"],
            position=config.training["position"],
            source=config.raw["source"],
        )
        save_loreft_artifact(runtime.torch, artifact, path)
        completed.append(
            {
                "rank": primary_rank,
                "path": str(path),
                "status": "random_control_created",
            }
        )
    return {"artifacts": completed}
