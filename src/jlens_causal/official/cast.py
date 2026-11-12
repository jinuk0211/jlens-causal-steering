"""Conditional Activation Steering through IBM/activation-steering.

Upstream code that runs unchanged:
  * ``SteeringDataset`` and ``SteeringVector.train`` (``pca_pairwise``) for
    both the behavior and the condition vector;
  * ``MalleableModel.find_best_condition_point`` for the gate (layer,
    threshold, comparator) by F1 over held-out condition prompts;
  * ``MalleableModel`` / ``LeashLayer`` for generation: the condition is
    measured on the first (prefill) forward of the condition layer, and the
    behavior vector is added at the behavior layers' inputs on every prefill
    and decode position once the condition fires.

What this adapter supplies:
  * rendered Tau2 strings: behavior examples are ``prompt + repaired action``
    vs ``prompt + failed action``; condition examples are the rendered
    failure-risk context vs a matched clean context (each ending in the
    generation header).  ``use_chat_template=False`` and a tokenizer without
    special-token strings are passed to ``SteeringDataset`` so the rendered
    template is neither re-wrapped nor mangled by ``clean_text``;
  * a hidden-state view used only while training vectors: it returns
    ``hidden_states[l + 1]`` = output of block ``l`` (the upstream
    convention) in float32 and keeps only the last logit, because
    ``batched_get_hiddens`` calls ``.numpy()`` (fails on bfloat16) and would
    otherwise materialise full-vocabulary logits for every Tau2 token;
  * a ``respond`` override that feeds the rendered prompt as-is
    (``find_best_condition_point`` would wrap it in a new user turn).
"""

from __future__ import annotations

import copy
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import (
    RenderedConditionPair,
    RenderedPair,
    pair_summary,
    response_token_count,
)
from jlens_causal.official.modelparts import (
    decoder_layers,
    first_tensor,
    hooks,
    model_device,
    text_config,
)

METHOD = "cast"
UPSTREAM_FILES = (
    "activation_steering/steering_dataset.py",
    "activation_steering/steering_vector.py",
    "activation_steering/malleable_model.py",
    "activation_steering/leash_layer.py",
    "activation_steering/utils.py",
    "LICENSE",
)
DEVIATIONS = [
    "Behavior and condition strings are full Tau2 chat renderings passed with "
    "use_chat_template=False (CAST's own chat path renders a single user turn).",
    "Behavior vectors average the last k response tokens (accumulate_last_x_tokens=k, "
    "k = shortest action in tokens, capped) - the suffix-only rule for per-pair responses.",
    "Vector training goes through a hidden-state view (float32, last logit only); the PCA "
    "and sign rule are upstream.",
    "find_best_condition_point reads rendered prompts directly via a respond() override.",
]
_NO_SPECIAL_TOKENS = SimpleNamespace(bos_token=None, eos_token=None, pad_token=None, unk_token=None)


def _package() -> Any:
    package = upstream.import_package(METHOD, "activation_steering")
    from activation_steering.config import GlobalConfig

    GlobalConfig.set_verbose(False)
    return package


class _HiddenStateView:
    """What ``read_representations``/``batched_get_hiddens`` need from a model."""

    def __init__(self, model: Any, layer_ids: list[int]):
        import torch

        self._torch = torch
        self._model = model
        self._layer_ids = sorted(set(layer_ids))
        blocks = decoder_layers(model)
        self.model = SimpleNamespace(layers=blocks)
        self.config = SimpleNamespace(
            model_type=text_config(model).model_type, num_hidden_layers=len(blocks)
        )
        self.device = model_device(model)

    def __call__(self, input_ids: Any, attention_mask: Any = None, output_hidden_states: bool = True,
                 **kwargs: Any) -> Any:  # noqa: ARG002
        blocks = self.model.layers
        captured: dict[int, Any] = {}

        def record(layer: int):
            def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
                captured[layer] = first_tensor(output).detach().float()

            return hook

        handles = [blocks[layer].register_forward_hook(record(layer)) for layer in self._layer_ids]
        with hooks(handles), self._torch.no_grad():
            self._model(input_ids=input_ids, attention_mask=attention_mask, logits_to_keep=1)
        hidden_states: list[Any] = [None] * (len(blocks) + 1)
        for layer, value in captured.items():
            hidden_states[layer + 1] = value
        return SimpleNamespace(hidden_states=tuple(hidden_states))


def _malleable_class() -> Any:
    _package()
    from activation_steering import MalleableModel

    class RenderedPromptMalleableModel(MalleableModel):
        def respond(self, prompt, settings=None, use_chat_template=True, reset_after_response=True):  # noqa: ARG002
            return super().respond(
                prompt, settings, use_chat_template=False, reset_after_response=reset_after_response
            )

    return RenderedPromptMalleableModel


def _reset_leash_class_state() -> None:
    from activation_steering.leash_layer import LeashLayer

    # Exactly what MalleableModel.respond resets after each response.
    LeashLayer.condition_met = defaultdict(lambda: False)
    LeashLayer.forward_calls = defaultdict(int)
    LeashLayer.condition_similarities = defaultdict(lambda: defaultdict(float))


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    condition_pairs: list[RenderedConditionPair],
    *,
    behavior_layers: list[int],
    condition_layer_range: tuple[int, int],
    max_response_tokens: int,
    threshold_range: tuple[float, float],
    threshold_step: float,
    output_path: Path,
    model_id: str,
    model_revision: str,
) -> Path:
    import numpy as np
    import torch

    _package()
    from activation_steering import SteeringDataset, SteeringVector

    train = [pair for pair in pairs if pair.split == "train"]
    condition_train = [pair for pair in condition_pairs if pair.split == "train"]
    condition_search = [pair for pair in condition_pairs if pair.split == "validation"] or condition_train
    if len(train) < 2 or len(condition_train) < 2:
        raise ValueError("CAST needs at least two behavior pairs and two condition pairs")
    model = runtime.hf_model
    tokenizer = copy.deepcopy(runtime.tokenizer)  # train() and MalleableModel mutate pad tokens

    k = min(
        int(max_response_tokens),
        *(response_token_count(runtime.tokenizer, pair.prompt, pair.positive) for pair in train),
        *(response_token_count(runtime.tokenizer, pair.prompt, pair.negative) for pair in train),
    )
    if k < 1:
        raise ValueError("CAST behavior window is empty")
    behavior_dataset = SteeringDataset(
        tokenizer=_NO_SPECIAL_TOKENS,
        examples=[(pair.prompt + pair.positive, pair.prompt + pair.negative) for pair in train],
        disable_suffixes=True,
        use_chat_template=False,
    )
    behavior_vector = SteeringVector.train(
        model=_HiddenStateView(model, behavior_layers),
        tokenizer=tokenizer,
        steering_dataset=behavior_dataset,
        method="pca_pairwise",
        accumulate_last_x_tokens=k,
        hidden_layer_ids=list(behavior_layers),
        batch_size=1,
    )
    condition_layers = list(range(*condition_layer_range))
    condition_dataset = SteeringDataset(
        tokenizer=_NO_SPECIAL_TOKENS,
        examples=[(pair.positive_prompt, pair.negative_prompt) for pair in condition_train],
        disable_suffixes=True,
        use_chat_template=False,
    )
    condition_vector = SteeringVector.train(
        model=_HiddenStateView(model, condition_layers),
        tokenizer=tokenizer,
        steering_dataset=condition_dataset,
        method="pca_pairwise",
        accumulate_last_x_tokens="all",
        hidden_layer_ids=condition_layers,
        batch_size=1,
    )
    malleable = _malleable_class()(model, tokenizer)
    try:
        try:
            best_layers, threshold, direction, f1 = malleable.find_best_condition_point(
                positive_strings=[pair.positive_prompt for pair in condition_search],
                negative_strings=[pair.negative_prompt for pair in condition_search],
                condition_vector=condition_vector,
                layer_range=condition_layer_range,
                max_layers_to_combine=1,
                threshold_range=threshold_range,
                threshold_step=threshold_step,
                condition_threshold_comparison_mode="mean",
            )
        except TypeError as error:  # upstream indexes best_config=None when every F1 is 0
            raise RuntimeError("CAST found no condition point with F1 > 0") from error
    finally:
        malleable.reset_leash_to_default()
        malleable.unwrap()

    def as_tensors(directions: dict[int, Any]) -> dict[str, Any]:
        return {str(layer): torch.tensor(np.asarray(value, dtype=np.float32)) for layer, value in directions.items()}

    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={
            "method": "pca_pairwise",
            "model_type": behavior_vector.model_type,
            "behavior_layers": list(behavior_layers),
            "behavior_accumulate_last_x_tokens": int(k),
            "condition_layer_range": list(condition_layer_range),
            "condition_accumulate": "all",
            "condition_layers": [int(layer) for layer in best_layers],
            "condition_threshold": float(threshold),
            "condition_comparator_threshold_is": str(direction),
            "condition_threshold_comparison_mode": "mean",
            "condition_f1": float(f1),
            "threshold_range": list(threshold_range),
            "threshold_step": float(threshold_step),
            "behavior_explained_variance": {
                str(layer): float(value) for layer, value in behavior_vector.explained_variances.items()
            },
            "data": pair_summary(train),
            "condition_train_pairs": [pair.pair_id for pair in condition_train],
            "condition_search_pairs": [pair.pair_id for pair in condition_search],
        },
        deviations=DEVIATIONS,
        state={
            "behavior_directions": as_tensors(behavior_vector.directions),
            "condition_directions": as_tensors(
                {layer: condition_vector.directions[layer] for layer in best_layers}
            ),
        },
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,  # noqa: ARG001  (CAST steers its configured behavior layers)
    prompt_ids: list[int],  # noqa: ARG001
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    import numpy as np

    _package()
    from activation_steering import SteeringVector
    from activation_steering.leash_layer import LeashLayer

    fit_record = artifact["fit"]
    state = artifact["state"]
    behavior = SteeringVector(
        model_type=fit_record["model_type"],
        directions={int(key): value.numpy().astype(np.float32) for key, value in state["behavior_directions"].items()},
        explained_variances={},
    )
    gated = not bool(options.get("ungated", False))
    malleable = _malleable_class()(model, copy.deepcopy(tokenizer))
    trace: dict[str, Any] = {"strength": float(strength), "gated": gated, "applied_edits": 0}
    behavior_layers = [int(value) for value in fit_record["behavior_layers"]]

    def count_applied(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
        # Mirrors LeashLayer._apply_single_behavior's should_apply / first-call rule.
        applied_now = (not gated) or bool(LeashLayer.condition_met[0])
        first_call = LeashLayer.forward_calls[module.layer_id] == 1
        if applied_now and (not first_call or module.apply_behavior_on_first_call):
            trace["applied_edits"] += int(args[0].shape[1])

    counting = []
    try:
        kwargs: dict[str, Any] = {
            "behavior_vector": behavior,
            "behavior_layer_ids": list(fit_record["behavior_layers"]),
            "behavior_vector_strength": float(strength),
            "apply_behavior_on_first_call": True,
        }
        if gated:
            condition = SteeringVector(
                model_type=fit_record["model_type"],
                directions={
                    int(key): value.numpy().astype(np.float32)
                    for key, value in state["condition_directions"].items()
                },
                explained_variances={},
            )
            kwargs.update(
                condition_vector=condition,
                condition_layer_ids=list(fit_record["condition_layers"]),
                condition_vector_threshold=float(fit_record["condition_threshold"]),
                condition_comparator_threshold_is=str(
                    options.get("condition_comparator_threshold_is", fit_record["condition_comparator_threshold_is"])
                ),
                condition_threshold_comparison_mode=fit_record["condition_threshold_comparison_mode"],
            )
        malleable.steer(**kwargs)
        _reset_leash_class_state()
        wrapped = decoder_layers(model)
        counting = [wrapped[layer_id].register_forward_hook(count_applied) for layer_id in behavior_layers]
        yield trace
        trace["condition_met"] = bool(LeashLayer.condition_met[0]) if gated else None
        trace["condition_similarity"] = (
            {str(key): float(value) for key, value in LeashLayer.condition_similarities[0].items()}
            if gated
            else None
        )
    finally:
        for handle in counting:
            handle.remove()
        malleable.reset_leash_to_default()
        malleable.unwrap()
        _reset_leash_class_state()
