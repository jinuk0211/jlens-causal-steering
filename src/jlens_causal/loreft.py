"""Small, dependency-free LoReFT training loop for frozen agent models."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from jlens_causal.baselines import build_loreft_artifact, loreft_transform
from jlens_causal.modeling import ModelRuntime


@dataclass(frozen=True)
class LoReFTExample:
    example_id: str
    input_ids: Any
    attention_mask: Any
    response_positions: tuple[int, ...]
    boundary_position: int


def _replace_output(output: Any, tensor: Any) -> Any:
    if hasattr(output, "shape"):
        return tensor
    return (tensor, *output[1:])


def _effective_rotation(torch: Any, raw: Any) -> Any:
    return torch.linalg.qr(raw.float(), mode="reduced").Q


def _initialize_parameters(
    runtime: ModelRuntime, *, layers: tuple[int, ...], rank: int, seed: int
) -> tuple[dict[int, Any], dict[int, Any], dict[int, Any]]:
    torch = runtime.torch
    torch.manual_seed(int(seed))
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(int(seed))
    d_model = int(runtime.lens_model.d_model)
    rotations: dict[int, Any] = {}
    weights: dict[int, Any] = {}
    biases: dict[int, Any] = {}
    for layer in layers:
        raw = torch.randn(d_model, int(rank), device=runtime.device, dtype=torch.float32)
        rotations[layer] = torch.nn.Parameter(_effective_rotation(torch, raw))
        linear = torch.nn.Linear(d_model, int(rank), bias=True, device=runtime.device)
        weights[layer] = torch.nn.Parameter(linear.weight.detach().float())
        biases[layer] = torch.nn.Parameter(linear.bias.detach().float())
    return rotations, weights, biases


@contextmanager
def _training_hooks(
    runtime: ModelRuntime,
    *,
    layers: tuple[int, ...],
    rotations: dict[int, Any],
    weights: dict[int, Any],
    biases: dict[int, Any],
    position: int,
):
    handles = []

    def make_hook(layer: int):
        def hook(_module: Any, _inputs: Any, output: Any) -> Any:
            tensor = output if hasattr(output, "shape") else output[0]
            if not 0 <= int(position) < int(tensor.shape[1]):
                raise ValueError("LoReFT training position is outside the sequence")
            rotation = _effective_rotation(runtime.torch, rotations[layer])
            transformed = loreft_transform(
                runtime.torch,
                tensor[:, position : position + 1, :],
                rotate=rotation,
                learned_weight=weights[layer],
                learned_bias=biases[layer],
            )
            modified = runtime.torch.cat(
                (tensor[:, :position, :], transformed, tensor[:, position + 1 :, :]),
                dim=1,
            )
            return _replace_output(output, modified)

        return hook

    try:
        for layer in layers:
            handles.append(
                runtime.lens_model.layers[layer].register_forward_hook(make_hook(layer))
            )
        yield
    finally:
        for handle in reversed(handles):
            handle.remove()


def _example_loss(
    runtime: ModelRuntime,
    example: LoReFTExample,
    *,
    layers: tuple[int, ...],
    rotations: dict[int, Any],
    weights: dict[int, Any],
    biases: dict[int, Any],
) -> Any:
    labels = runtime.torch.full_like(example.input_ids, -100)
    labels[:, list(example.response_positions)] = example.input_ids[
        :, list(example.response_positions)
    ]
    with _training_hooks(
        runtime,
        layers=layers,
        rotations=rotations,
        weights=weights,
        biases=biases,
        position=example.boundary_position,
    ):
        output = runtime.hf_model(
            input_ids=example.input_ids,
            attention_mask=example.attention_mask,
            labels=labels,
            use_cache=False,
        )
    return output.loss


def train_loreft_artifact(
    runtime: ModelRuntime,
    *,
    model_id: str,
    model_revision: str | None,
    layers: tuple[int, ...],
    rank: int,
    train_examples: list[LoReFTExample],
    validation_examples: list[LoReFTExample],
    epochs: int,
    learning_rate: float,
    weight_decay: float,
    max_grad_norm: float,
    seed: int,
    benchmark: str,
    site: str,
    source: dict[str, str],
) -> dict[str, Any]:
    """Fit only LoReFT parameters and select the epoch on held-out LM loss."""
    if not train_examples or not validation_examples:
        raise ValueError("LoReFT requires non-empty train and validation examples")
    if int(epochs) <= 0 or float(learning_rate) <= 0.0 or float(max_grad_norm) <= 0.0:
        raise ValueError("LoReFT training hyperparameters must be positive")
    rotations, weights, biases = _initialize_parameters(
        runtime, layers=layers, rank=int(rank), seed=int(seed)
    )
    parameters = [
        value
        for mapping in (rotations, weights, biases)
        for value in mapping.values()
    ]
    optimizer = runtime.torch.optim.AdamW(
        parameters,
        lr=float(learning_rate),
        weight_decay=float(weight_decay),
    )
    original_requires_grad = {
        name: parameter.requires_grad for name, parameter in runtime.hf_model.named_parameters()
    }
    was_training = runtime.hf_model.training
    for parameter in runtime.hf_model.parameters():
        parameter.requires_grad_(False)
    runtime.hf_model.eval()
    train_history: list[float] = []
    validation_history: list[float] = []
    best_loss = float("inf")
    best_state: tuple[dict[int, Any], dict[int, Any], dict[int, Any]] | None = None
    try:
        for _epoch in range(int(epochs)):
            epoch_losses = []
            for example in train_examples:
                optimizer.zero_grad(set_to_none=True)
                loss = _example_loss(
                    runtime,
                    example,
                    layers=layers,
                    rotations=rotations,
                    weights=weights,
                    biases=biases,
                )
                loss.backward()
                runtime.torch.nn.utils.clip_grad_norm_(parameters, float(max_grad_norm))
                optimizer.step()
                epoch_losses.append(float(loss.detach().float().cpu()))
            train_history.append(sum(epoch_losses) / len(epoch_losses))
            validation_losses = []
            with runtime.torch.no_grad():
                for example in validation_examples:
                    loss = _example_loss(
                        runtime,
                        example,
                        layers=layers,
                        rotations=rotations,
                        weights=weights,
                        biases=biases,
                    )
                    validation_losses.append(float(loss.detach().float().cpu()))
            validation_loss = sum(validation_losses) / len(validation_losses)
            validation_history.append(validation_loss)
            if validation_loss < best_loss:
                best_loss = validation_loss
                best_state = (
                    {
                        layer: _effective_rotation(runtime.torch, rotations[layer])
                        .detach()
                        .cpu()
                        for layer in layers
                    },
                    {layer: weights[layer].detach().cpu().clone() for layer in layers},
                    {layer: biases[layer].detach().cpu().clone() for layer in layers},
                )
    finally:
        for name, parameter in runtime.hf_model.named_parameters():
            parameter.requires_grad_(original_requires_grad[name])
        runtime.hf_model.train(was_training)
    if best_state is None:
        raise RuntimeError("LoReFT training did not produce a finite checkpoint")
    best_rotations, best_weights, best_biases = best_state
    return build_loreft_artifact(
        runtime.torch,
        model_id=model_id,
        model_revision=model_revision,
        layers=layers,
        rotate_by_layer=best_rotations,
        learned_weight_by_layer=best_weights,
        learned_bias_by_layer=best_biases,
        train_example_ids=[example.example_id for example in train_examples],
        validation_example_ids=[example.example_id for example in validation_examples],
        rank=int(rank),
        benchmark=benchmark,
        training={
            "optimizer": "adamw",
            "epochs": int(epochs),
            "learning_rate": float(learning_rate),
            "weight_decay": float(weight_decay),
            "max_grad_norm": float(max_grad_norm),
            "seed": int(seed),
            "selection": "minimum_heldout_response_lm_loss",
            "train_loss_by_epoch": train_history,
            "validation_loss_by_epoch": validation_history,
        },
        validation_loss=best_loss,
        site=site,
        position="last_prompt_token",
        source=source,
    )
