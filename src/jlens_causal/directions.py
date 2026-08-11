"""Extract and persist layer-wise steering directions."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from jlens_causal.config import PilotConfig
from jlens_causal.modeling import ModelRuntime, capture_block_outputs, render_messages
from jlens_causal.toolalign import ScenarioCase, load_cases, messages_for_case


def _unit(torch: Any, vector: Any, *, label: str) -> Any:
    vector = vector.detach().float().cpu().reshape(-1)
    norm = torch.linalg.vector_norm(vector)
    if not torch.isfinite(norm) or float(norm) == 0.0:
        raise ValueError(f"{label} is zero or non-finite")
    return vector / norm


def _match_norm(torch: Any, vector: Any, reference: Any, *, label: str) -> Any:
    return _unit(torch, vector, label=label) * torch.linalg.vector_norm(reference.float())


def _alias_token_ids(tokenizer: Any, aliases: list[str], *, concept: str) -> list[int]:
    """Resolve aliases to unique single-token IDs, trying word-initial variants."""
    token_ids: list[int] = []
    rejected: list[str] = []
    for alias in aliases:
        accepted = False
        for candidate in (alias, f" {alias}"):
            encoded = tokenizer.encode(candidate, add_special_tokens=False)
            if len(encoded) == 1:
                token_id = int(encoded[0])
                if token_id not in token_ids:
                    token_ids.append(token_id)
                accepted = True
        if not accepted:
            rejected.append(alias)
    if not token_ids:
        raise ValueError(
            f"none of the {concept} aliases is a single token: {rejected}; "
            "choose aliases represented by one tokenizer token"
        )
    return token_ids


def _j_concept_direction(
    runtime: ModelRuntime,
    *,
    layer: int,
    token_ids: list[int],
    label: str,
) -> Any:
    torch = runtime.torch
    rows = runtime.hf_model.get_output_embeddings().weight[token_ids]
    unembedding = rows.detach().float().cpu().mean(dim=0)
    jacobian = runtime.lens.jacobians[layer].detach().float().cpu()
    return _unit(torch, jacobian.T @ unembedding, label=label)


def _capture_calibration(
    config: PilotConfig,
    runtime: ModelRuntime,
    common: Any,
    cases: list[ScenarioCase],
) -> dict[int, dict[str, Any]]:
    """Collect last-prompt-token residuals for every layer and scenario type."""
    torch = runtime.torch
    by_layer: dict[int, dict[str, list[Any]]] = {
        int(layer): defaultdict(list) for layer in config.sweep["layers"]
    }
    with torch.inference_mode():
        for case in cases:
            for condition in config.data["conditions"]:
                messages = messages_for_case(common, case, condition)
                input_ids, attention_mask = render_messages(runtime, messages)
                with capture_block_outputs(runtime.lens_model.layers, config.sweep["layers"]) as captured:
                    runtime.hf_model(
                        input_ids=input_ids,
                        attention_mask=attention_mask,
                        use_cache=False,
                    )
                for layer in config.sweep["layers"]:
                    tensor = captured[int(layer)]
                    by_layer[int(layer)][case.scenario_type].append(
                        tensor[0, -1, :].detach().float().cpu()
                    )
    result: dict[int, dict[str, Any]] = {}
    for layer, grouped in by_layer.items():
        result[layer] = {}
        for scenario_type in (config.data["scenario_a"], config.data["scenario_b"]):
            values = grouped.get(scenario_type, [])
            if not values:
                raise ValueError(f"no calibration activations for {scenario_type!r} at layer {layer}")
            result[layer][scenario_type] = torch.stack(values).mean(dim=0)
    return result


def extract_directions(
    config: PilotConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> Path:
    """Build the complete direction artifact used by all treatment runs."""
    path = config.direction_artifact
    if path.exists() and not force:
        artifact = load_directions(config, runtime.torch)
        if artifact["fingerprint"] == config.direction_fingerprint:
            return path

    missing_lens_layers = set(map(int, config.sweep["layers"])) - set(
        runtime.lens.source_layers
    )
    if missing_lens_layers:
        raise ValueError(
            f"fitted Jacobian lens is missing layers {sorted(missing_lens_layers)}"
        )

    common, cases = load_cases(
        config.toolalign_root,
        domains=config.data["calibration_domains"],
        documents=config.data["calibration_documents"],
        scenario_types=[config.data["scenario_a"], config.data["scenario_b"]],
    )
    means = _capture_calibration(config, runtime, common, cases)
    torch = runtime.torch
    ids_a = _alias_token_ids(
        runtime.tokenizer,
        config.directions["concept_a_aliases"],
        concept="concept_a",
    )
    ids_b = _alias_token_ids(
        runtime.tokenizer,
        config.directions["concept_b_aliases"],
        concept="concept_b",
    )

    layers: dict[int, dict[str, Any]] = {}
    for layer in map(int, config.sweep["layers"]):
        contrastive = means[layer][config.data["scenario_b"]] - means[layer][
            config.data["scenario_a"]
        ]
        contrastive = contrastive.detach().float().cpu()
        _unit(torch, contrastive, label=f"contrastive[{layer}]")
        v_a = _j_concept_direction(
            runtime, layer=layer, token_ids=ids_a, label=f"j_concept_a[{layer}]"
        )
        v_b = _j_concept_direction(
            runtime, layer=layer, token_ids=ids_b, label=f"j_concept_b[{layer}]"
        )
        jlens = _match_norm(
            torch,
            v_b - v_a,
            contrastive,
            label=f"jlens_delta[{layer}]",
        )
        random_vectors: dict[int, Any] = {}
        for seed in config.directions["random_seeds"]:
            generator = torch.Generator(device="cpu")
            generator.manual_seed(int(seed) + 1_000_003 * layer)
            random_vectors[int(seed)] = _match_norm(
                torch,
                torch.randn(contrastive.shape, generator=generator),
                contrastive,
                label=f"random[{layer},{seed}]",
            )
        layers[layer] = {
            "mean_a": means[layer][config.data["scenario_a"]],
            "mean_b": means[layer][config.data["scenario_b"]],
            "contrastive": contrastive,
            "jlens": jlens,
            "j_concept_a": v_a,
            "j_concept_b": v_b,
            "random": random_vectors,
        }

    artifact = {
        "schema_version": "jlens-direction-artifact-v1",
        "fingerprint": config.direction_fingerprint,
        "model_id": config.model["model_id"],
        "model_revision": config.model["model_revision"],
        "lens_revision": config.model["lens_revision"],
        "scenario_a": config.data["scenario_a"],
        "scenario_b": config.data["scenario_b"],
        "concept_a_token_ids": ids_a,
        "concept_b_token_ids": ids_b,
        "calibration_examples": len(cases) * len(config.data["conditions"]),
        "layers": layers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(artifact, path)
    return path


def load_directions(config: PilotConfig, torch: Any) -> dict[str, Any]:
    """Load a safe tensor-only artifact and verify it belongs to this config."""
    if not config.direction_artifact.is_file():
        raise FileNotFoundError(
            f"missing {config.direction_artifact}; run extract-directions first"
        )
    artifact = torch.load(config.direction_artifact, map_location="cpu", weights_only=True)
    if artifact.get("schema_version") != "jlens-direction-artifact-v1":
        raise ValueError("unsupported direction artifact schema")
    if artifact.get("fingerprint") != config.direction_fingerprint:
        raise ValueError("direction artifact fingerprint does not match the current config")
    missing = set(map(int, config.sweep["layers"])) - set(artifact["layers"])
    if missing:
        raise ValueError(f"direction artifact is missing layers {sorted(missing)}")
    return artifact
