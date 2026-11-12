"""MERA (mechanistic error reduction with abstention) through annahedstroem/MERA-steering.

Upstream code that runs unchanged:
  * ``probes.probes_train.train_probes`` fits the per-layer error probes
    (Lasso grid + no-intercept LinearRegression, five 70/30 splits, logit
    transform of the error target);
  * ``probes.probes_utils.postprocess_df_probes`` and ``get_best_coefficients``
    pick each layer's lowest-RMSE coefficient vector;
  * ``steering.by_mera.MERA`` (``optimal_probe`` mode, class-default derivation
    flags) applies the closed-form update through its own
    ``post_attention_layernorm`` forward hooks (``with mera: generate``).

What this adapter supplies:
  * the probe dataset.  MERA's target is ``1 - p(true class)`` restricted to
    the class tokens at the answer position.  For a Tau2 repair pair the two
    "classes" are the repaired and the failed action, which first differ at
    one token; the feature is the ``post_attention_layernorm`` output at the
    last shared position and the target is
    ``1 - p(repaired token) / (p(repaired token) + p(failed token))`` from the
    model's own next-token distribution there.  One example per pair.
  * the estimator dict and metric functions that the upstream defines inside
    ``__main__`` (copied, with ``root_mean_squared_error`` because
    ``mean_squared_error(squared=False)`` was removed from scikit-learn);
  * a model view (``.model.layers``/``.device``) and a float32 cast around
    ``steer`` (the upstream ran fp32 checkpoints; ``matmul`` of bf16
    activations with the fp32 probe raises).
  * alpha: the upstream selects it by task accuracy on held-out prompts; here
    each candidate alpha is a Tau2 validation condition and the strength sweep
    selects it by task success, keeping "no steering" if nothing beats it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import RenderedPair, encode, pair_summary
from jlens_causal.official.modelparts import decoder_layers, first_tensor, hooks, model_device

METHOD = "mera"
UPSTREAM_FILES = (
    "src/probes/probes_train.py",
    "src/probes/probes_utils.py",
    "src/steering/base.py",
    "src/steering/by_probe.py",
    "src/steering/by_mera.py",
)
LASSO_ALPHAS = [0.5, 0.25, 0.1, 0.05, 0.01, 0.005]  # probes_train.py __main__
DEVIATIONS = [
    "Probe data: one example per Tau2 repair pair at the first token where the repaired and "
    "failed actions diverge; target = 1 - restricted softmax of the repaired token "
    "(the upstream's 'sm' error over class tokens).",
    "RMSE uses sklearn root_mean_squared_error (the upstream's squared=False keyword no "
    "longer exists); classification probes are skipped because optimal_probe uses only the "
    "regression coefficients.",
    "Activations are cast to float32 around MERA.steer and back to the model dtype.",
    "Alpha is chosen by Tau2 validation task success instead of MERA.calibrate_alpha "
    "(which assumes single-token classification datasets).",
]


def _wandb_stub() -> Any:
    """Only used when wandb is not installed; log_with_wandb=False never calls it."""

    def unavailable(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise RuntimeError("wandb logging is disabled for the Tau2 MERA adapter")

    return upstream.stub_module("wandb", run=None, init=unavailable, log=unavailable, Table=unavailable)


def _datasets_stub() -> Any:
    """Only used when `datasets` cannot be imported; MERA's task loaders are never called."""

    def unavailable(*args: Any, **kwargs: Any) -> Any:  # noqa: ARG001
        raise RuntimeError("MERA's benchmark dataset loaders are not used by the Tau2 adapter")

    return upstream.stub_module(
        "datasets", load_dataset=unavailable, load_from_disk=unavailable,
        concatenate_datasets=unavailable,
    )


def _modules() -> tuple[Any, Any, Any]:
    stubs = {"wandb": _wandb_stub(), "datasets": _datasets_stub()}
    probes_train = upstream.import_upstream(METHOD, "probes.probes_train", stubs=stubs)
    probes_utils = upstream.import_upstream(METHOD, "probes.probes_utils", stubs=stubs)
    by_mera = upstream.import_upstream(METHOD, "steering.by_mera", stubs=stubs)
    return probes_train, probes_utils, by_mera


def _divergence_example(model: Any, tokenizer: Any, pair: RenderedPair) -> tuple[dict[int, Any], float]:
    """Features (all layers) at the last shared token and the restricted error target."""
    import torch

    positive = encode(tokenizer, pair.prompt + pair.positive)
    negative = encode(tokenizer, pair.prompt + pair.negative)
    k = 0
    while k < min(len(positive), len(negative)) and positive[k] == negative[k]:
        k += 1
    if k == 0 or k >= min(len(positive), len(negative)):
        raise ValueError(f"pair {pair.pair_id} has no token-level divergence inside both actions")
    blocks = decoder_layers(model)
    features: dict[int, Any] = {}

    def capture(layer: int):
        def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
            features[layer] = first_tensor(output)[0, -1].detach().float().cpu().numpy()

        return hook

    handles = [
        block.post_attention_layernorm.register_forward_hook(capture(layer))
        for layer, block in enumerate(blocks)
    ]
    with hooks(handles), torch.no_grad():
        logits = model(
            input_ids=torch.tensor([positive[:k]], device=model_device(model)), logits_to_keep=1
        ).logits[0, -1].float()
    restricted = torch.softmax(logits[[positive[k], negative[k]]], dim=-1)
    return features, float(1.0 - restricted[0])


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    seed: int,
    output_path: Path,
    model_id: str,
    model_revision: str,
) -> Path:
    import numpy as np
    import torch
    from sklearn.linear_model import Lasso, LinearRegression
    from sklearn.metrics import mean_squared_error, root_mean_squared_error

    probes_train, probes_utils, _ = _modules()
    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 4:
        raise ValueError("MERA needs at least four training repair pairs (70/30 probe splits)")
    model = runtime.hf_model
    n_layers = len(decoder_layers(model))
    rows: dict[int, list[Any]] = {layer: [] for layer in range(n_layers)}
    errors = []
    for pair in train:
        features, error = _divergence_example(model, runtime.tokenizer, pair)
        for layer in range(n_layers):
            rows[layer].append(features[layer])
        errors.append(error)

    # probes_train.py __main__: initialise_regression_models(seed, alphas)
    models = {
        "regression": {
            **{
                f"L-{alpha}": Lasso(alpha=alpha, fit_intercept=False, max_iter=2000, random_state=seed)
                for alpha in LASSO_ALPHAS
            },
            "L-0": LinearRegression(fit_intercept=False, n_jobs=5),
        }
    }
    metrics = {
        "regression": {
            "RMSE": root_mean_squared_error,
            "MSE": mean_squared_error,
        }
    }
    features = {"activations": {layer: np.stack(rows[layer]) for layer in range(n_layers)}}
    df_probes, _ = probes_train.train_probes(
        features,
        models,
        {"regression": np.array(errors, dtype=np.float64)},
        metrics,
        dataset_name="tau2_airline",
        llm_name=model_id,
        path="",
        path_probes="",
        nr_layers=n_layers,
        error_type="sm",
        seed=seed,
        nr_models=5,
        save=False,
        transform_error=True,
        token_pos="exact",
    )
    for column in ("AUCROC", "Dummy-AUCROC", "Accuracy", "Dummy-Accuracy"):
        if column not in df_probes:
            df_probes[column] = np.nan
    df_probes = probes_utils.postprocess_df_probes(df_probes, "sm", "exact", "activations")
    best = probes_utils.get_best_coefficients(df_probes, task="regression", metric="RMSE", mode="best")
    probe_layers = sorted(int(layer) for layer in df_probes["Layer"].unique())
    if len(best) != len(probe_layers):
        raise RuntimeError("MERA returned a different number of probes than layers")
    probe_weights = {
        str(layer): torch.tensor(np.asarray(coefficients, dtype=np.float32))
        for layer, coefficients in zip(probe_layers, best, strict=True)
    }
    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={
            "mode": "optimal_probe",
            "probe_site": "post_attention_layernorm output",
            "token_pos": "exact (last shared token before the repaired/failed divergence)",
            "seed": int(seed),
            "lasso_alphas": LASSO_ALPHAS,
            "error_targets": {"mean": float(np.mean(errors)), "min": float(np.min(errors)),
                              "max": float(np.max(errors))},
            "data": pair_summary(train),
        },
        deviations=DEVIATIONS,
        state={"probe_weights": probe_weights},
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,  # noqa: ARG001  (MERA steers every probed layer)
    prompt_ids: list[int],  # noqa: ARG001
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    _, _, by_mera = _modules()
    alpha = float(strength)
    if not 0.0 < alpha < 1.0:
        raise ValueError("MERA strength is the abstention threshold alpha and must be in (0, 1)")
    trace = {"alpha": alpha, "applied_edits": 0, "seen_positions": 0}

    class _MERA(by_mera.MERA):
        def steer(self, activations: Any, layer_idx: int) -> Any:
            return super().steer(activations.float(), layer_idx).to(activations.dtype)

        def optimise_steering_closed_form(self, activations: Any, vector: Any) -> Any:
            result = super().optimise_steering_closed_form(activations, vector)
            condition = result[2]
            trace["applied_edits"] += int(condition.sum())  # positions moved to the boundary
            trace["seen_positions"] += int(condition.numel())
            return result

    view = SimpleNamespace(
        model=SimpleNamespace(layers=decoder_layers(model)), device=model_device(model)
    )
    layers = options.get("layers")
    probe_weights = {
        int(key): value.numpy()
        for key, value in artifact["state"]["probe_weights"].items()
        if layers is None or int(key) in set(layers)
    }
    mera = _MERA(
        view,
        tokenizer,
        {},
        {},
        {
            "probe_weights": probe_weights,
            "mode": "optimal_probe",
            "alpha_value": alpha,
            "best_alpha_last": alpha,
            "best_alpha_exact": alpha,
            "apply_token_pos_to_steer": str(options.get("apply_token_pos_to_steer", "all")),
            "derive_with_all": True,
            "derive_with_sigmoid": bool(options.get("derive_with_sigmoid", False)),
            "derive_with_logit": bool(options.get("derive_with_logit", True)),
            "log_with_wandb": False,
            "debug": False,
        },
    )
    trace["layers"] = sorted(probe_weights)
    with mera:
        yield trace
