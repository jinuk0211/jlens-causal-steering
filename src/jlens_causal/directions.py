"""Extract cross-domain thought targets and layer-wise steering directions."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

from jlens_causal.config import PilotConfig
from jlens_causal.modeling import ModelRuntime, capture_block_outputs, render_messages
from jlens_causal.toolalign import ScenarioCase, load_cases, messages_for_case

DIRECTION_SCHEMA_VERSION = "jlens-direction-artifact-v3"

_STOPWORDS = {
    "about",
    "after",
    "again",
    "against",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "assistant",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "just",
    "me",
    "may",
    "more",
    "most",
    "might",
    "must",
    "my",
    "myself",
    "need",
    "needs",
    "no",
    "nor",
    "not",
    "now",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "arguments",
    "call",
    "content",
    "from",
    "function",
    "name",
    "parameter",
    "scratchpad",
    "system",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "tool",
    "tools",
    "user",
    "value",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "will",
    "with",
    "would",
    "xml",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
}


def _unit_scaled(torch: Any, vector: Any, scale: float, *, label: str) -> Any:
    vector = vector.detach().float().cpu().reshape(-1)
    norm = torch.linalg.vector_norm(vector)
    if not torch.isfinite(norm) or float(norm) == 0.0:
        raise ValueError(f"{label} is zero or non-finite")
    return vector / norm * float(scale)


def _normalized_token(value: str) -> str:
    return value.strip().lower().lstrip("▁Ġ").strip()


def _camel_words(value: str) -> set[str]:
    pieces = re.sub(r"([a-z])([A-Z])", r"\1 \2", value).replace("-", " ").split()
    return {_normalized_token(piece) for piece in pieces if piece}


def _eligible_token(text: str, excluded: set[str]) -> bool:
    token = _normalized_token(text)
    return bool(re.fullmatch(r"[a-zA-Z][a-zA-Z-]{2,}", token)) and token not in excluded


def scenario_lexicons(
    cases: list[ScenarioCase],
    *,
    scenario_a: str,
    scenario_b: str,
    min_domains: int,
    excluded: set[str],
) -> tuple[dict[str, set[str]], dict[str, dict[str, int]]]:
    """Derive scenario-enriched whole-word vocabularies from calibration only."""
    by_scenario: dict[str, dict[str, set[str]]] = {
        scenario_a: defaultdict(set),
        scenario_b: defaultdict(set),
    }
    for case in cases:
        if case.scenario_type not in by_scenario:
            continue
        words = {
            _normalized_token(word)
            for word in re.findall(r"[A-Za-z][A-Za-z-]{2,}", case.prompt)
        }
        for word in words:
            if word and word not in excluded:
                by_scenario[case.scenario_type][word].add(case.domain)

    counts: dict[str, dict[str, int]] = {}
    for word in set(by_scenario[scenario_a]) | set(by_scenario[scenario_b]):
        counts[word] = {
            scenario_a: len(by_scenario[scenario_a].get(word, set())),
            scenario_b: len(by_scenario[scenario_b].get(word, set())),
        }
    lexicons: dict[str, set[str]] = {scenario_a: set(), scenario_b: set()}
    for scenario, other in ((scenario_a, scenario_b), (scenario_b, scenario_a)):
        lexicons[scenario] = {
            word
            for word, row in counts.items()
            if row[scenario] >= int(min_domains) and row[scenario] > row[other]
        }
    return lexicons, counts


def select_stable_targets(
    domain_deltas: np.ndarray,
    token_texts: list[str],
    *,
    domain_names: list[str],
    top_k: int,
    min_domain_consistency: int,
    candidate_per_fold: int,
    min_loo_frequency: int,
    excluded: set[str],
    target_lexicons: dict[str, set[str]] | None = None,
    lexical_domain_counts: dict[str, dict[str, int]] | None = None,
    scenario_a: str = "a",
    scenario_b: str = "b",
) -> dict[str, Any]:
    """Select effect-ranked, lexically anchored targets without evaluation leakage."""
    values = np.asarray(domain_deltas, dtype=np.float64)
    if values.ndim != 2 or values.shape[1] != len(token_texts):
        raise ValueError("domain_deltas must be [domains, vocabulary]")
    if values.shape[0] != len(domain_names):
        raise ValueError("domain_names do not match domain_deltas")
    if min_domain_consistency > values.shape[0]:
        raise ValueError("min_domain_consistency exceeds the calibration domain count")
    if min_loo_frequency > values.shape[0]:
        raise ValueError("min_loo_frequency exceeds the calibration domain count")
    base_eligible = np.asarray([_eligible_token(text, excluded) for text in token_texts])
    normalized_tokens = [_normalized_token(text) for text in token_texts]
    if target_lexicons is None:
        target_lexicons = {
            scenario_a: set(normalized_tokens),
            scenario_b: set(normalized_tokens),
        }
    missing_lexicons = {scenario_a, scenario_b} - set(target_lexicons)
    if missing_lexicons:
        raise ValueError(f"target lexicons are missing scenarios {sorted(missing_lexicons)}")
    eligible_by_target = {
        scenario: base_eligible
        & np.asarray([token in target_lexicons[scenario] for token in normalized_tokens])
        for scenario in (scenario_a, scenario_b)
    }
    mean_delta = values.mean(axis=0)
    std_delta = values.std(axis=0, ddof=1) if values.shape[0] > 1 else np.ones(values.shape[1])
    standardized = mean_delta / np.maximum(std_delta, 1e-6)
    positive_consistency = (values > 0).sum(axis=0)
    negative_consistency = (values < 0).sum(axis=0)

    loo_frequency = {
        scenario_a: np.zeros(values.shape[1], dtype=np.int64),
        scenario_b: np.zeros(values.shape[1], dtype=np.int64),
    }
    for scenario, sign in ((scenario_a, -1.0), (scenario_b, 1.0)):
        eligible_ids = np.flatnonzero(eligible_by_target[scenario])
        fold_width = min(int(candidate_per_fold), len(eligible_ids))
        for held_out in range(values.shape[0]):
            fold = sign * np.delete(values, held_out, axis=0).mean(axis=0)
            top = eligible_ids[np.argsort(fold[eligible_ids])[-fold_width:]]
            loo_frequency[scenario][top] += 1

    def choose(scenario: str) -> list[dict[str, Any]]:
        if scenario == scenario_b:
            mask = eligible_by_target[scenario] & (
                positive_consistency >= min_domain_consistency
            )
            signed_effect = mean_delta
            consistency = positive_consistency
            kind = "b"
        else:
            mask = eligible_by_target[scenario] & (
                negative_consistency >= min_domain_consistency
            )
            signed_effect = -mean_delta
            consistency = negative_consistency
            kind = "a"
        frequency = loo_frequency[scenario]
        mask &= frequency >= int(min_loo_frequency)
        mask &= signed_effect > 0
        score = signed_effect * (frequency / values.shape[0])
        order = np.argsort(score)[::-1]
        selected_ids: list[int] = []
        selected_tokens: set[str] = set()
        for index in order:
            if not mask[index]:
                continue
            token = _normalized_token(token_texts[index])
            if token in selected_tokens:
                continue
            selected_ids.append(int(index))
            selected_tokens.add(token)
            if len(selected_ids) == top_k:
                break
        if len(selected_ids) != top_k:
            raise ValueError(
                f"only {len(selected_ids)} stable concept tokens for target {kind}; "
                "relax the preregistered selection threshold explicitly"
            )
        raw_weights = np.asarray([abs(mean_delta[index]) for index in selected_ids])
        if not np.isfinite(raw_weights).all() or float(raw_weights.sum()) == 0.0:
            raw_weights = np.ones(len(selected_ids), dtype=np.float64)
        weights = raw_weights / raw_weights.sum()
        rows: list[dict[str, Any]] = []
        for index, weight in zip(selected_ids, weights, strict=True):
            token = normalized_tokens[index]
            row = {
                "token_id": index,
                "token": token,
                "mean_delta_b_minus_a": float(mean_delta[index]),
                "standardized_effect": float(standardized[index]),
                "domain_consistency": int(consistency[index]),
                "loo_top_frequency": int(frequency[index]),
                "weight": float(weight),
            }
            if lexical_domain_counts is not None:
                lexical_counts = lexical_domain_counts.get(token, {})
                row["lexical_domains_target"] = int(lexical_counts.get(scenario, 0))
                other = scenario_a if scenario == scenario_b else scenario_b
                row["lexical_domains_other"] = int(lexical_counts.get(other, 0))
            rows.append(row)
        return rows

    return {
        "calibration_domains": domain_names,
        "vocabulary_size": len(token_texts),
        "eligible_vocabulary_size": int(base_eligible.sum()),
        "eligible_target_a_size": int(eligible_by_target[scenario_a].sum()),
        "eligible_target_b_size": int(eligible_by_target[scenario_b].sum()),
        "top_k": int(top_k),
        "min_domain_consistency": int(min_domain_consistency),
        "candidate_per_fold": int(candidate_per_fold),
        "min_loo_frequency": int(min_loo_frequency),
        "ranking": "cross_domain_mean_effect_x_loo_frequency",
        "weighting": "absolute_cross_domain_mean_effect",
        "target_a": choose(scenario_a),
        "target_b": choose(scenario_b),
    }


def transported_target(torch: Any, jacobian: Any, target: Any, scale: float) -> Any:
    """Return the exact normalized ``J.T @ u_target`` steering direction."""
    return _unit_scaled(
        torch,
        jacobian.detach().float().cpu().T @ target.detach().float().cpu(),
        scale,
        label="transported_target",
    )


def _capture_calibration(
    config: PilotConfig,
    runtime: ModelRuntime,
    common: Any,
    cases: list[ScenarioCase],
) -> tuple[dict[int, dict[tuple[str, int, str], dict[str, Any]]], dict[int, float]]:
    """Collect paired last-user residuals and layer residual-norm scales."""
    layers = sorted(
        set(map(int, config.sweep["coordinate_swap_layers"]))
        | {int(config.directions["target_selection"]["readout_layer"])}
    )
    samples: dict[int, dict[tuple[str, int, str], dict[str, Any]]] = {
        layer: defaultdict(dict) for layer in layers
    }
    norms: dict[int, list[float]] = {layer: [] for layer in layers}
    torch = runtime.torch
    with torch.inference_mode():
        for case in cases:
            for condition in config.data["conditions"]:
                prompt = render_messages(runtime, messages_for_case(common, case, condition))
                with capture_block_outputs(runtime.lens_model.layers, layers) as captured:
                    runtime.hf_model(
                        input_ids=prompt.input_ids,
                        attention_mask=prompt.attention_mask,
                        use_cache=False,
                    )
                key = (case.domain, int(case.document), condition)
                for layer in layers:
                    tensor = captured[layer][0, list(prompt.user_positions), :]
                    samples[layer][key][case.scenario_type] = {
                        "last_user": tensor[-1].detach().float().cpu(),
                        "pre_response": captured[layer][0, -1, :].detach().float().cpu(),
                    }
                    norms[layer].append(
                        float(torch.linalg.vector_norm(tensor.detach().float(), dim=-1).mean())
                    )
    for layer, grouped in samples.items():
        for key, pair in grouped.items():
            if set(pair) != {config.data["scenario_a"], config.data["scenario_b"]}:
                raise ValueError(f"incomplete calibration pair at layer {layer}: {key}")
    return samples, {layer: float(np.mean(values)) for layer, values in norms.items()}


def _domain_readout_deltas(
    config: PilotConfig,
    runtime: ModelRuntime,
    samples: dict[int, dict[tuple[str, int, str], dict[str, Any]]],
) -> tuple[list[str], np.ndarray]:
    layer = int(config.directions["target_selection"]["readout_layer"])
    a = config.data["scenario_a"]
    b = config.data["scenario_b"]
    by_domain: dict[str, list[Any]] = defaultdict(list)
    jacobian = runtime.lens.jacobians[layer].detach()
    with runtime.torch.inference_mode():
        for (domain, _document, _condition), pair in samples[layer].items():
            delta_logits = []
            for scenario in (a, b):
                residual = pair[scenario]["pre_response"].to(runtime.device)
                transported = jacobian.to(runtime.device, dtype=residual.dtype) @ residual
                logits = runtime.lens_model.unembed(transported[None, None, :])[0, 0]
                delta_logits.append(logits.detach().float().cpu())
            by_domain[domain].append(delta_logits[1] - delta_logits[0])
    domains = sorted(by_domain)
    rows: list[np.ndarray] = []
    for domain in domains:
        rows.append(runtime.torch.stack(by_domain[domain]).mean(dim=0).numpy())
    return domains, np.stack(rows)


def _excluded_terms(cases: list[ScenarioCase], tokenizer: Any) -> set[str]:
    excluded = set(_STOPWORDS)
    prompt_domains: dict[str, set[str]] = defaultdict(set)
    for case in cases:
        excluded.update(_camel_words(case.domain))
        for word in re.findall(r"[A-Za-z][A-Za-z-]{2,}", case.prompt):
            prompt_domains[_normalized_token(word)].add(case.domain)
        prompt_ids = tokenizer.encode(case.prompt, add_special_tokens=False)
        for token in tokenizer.convert_ids_to_tokens(prompt_ids):
            normalized = _normalized_token(str(token))
            if normalized:
                prompt_domains[normalized].add(case.domain)
        for tool in case.tools:
            excluded.update(_camel_words(str(tool.name)))
            excluded.update(_camel_words(str(tool.category)))
            tool_ids = tokenizer.encode(str(tool.name), add_special_tokens=False)
            excluded.update(
                _normalized_token(str(token)) for token in tokenizer.convert_ids_to_tokens(tool_ids)
            )
    excluded.update(word for word, domains in prompt_domains.items() if len(domains) == 1)
    return excluded


def _weighted_target(embedding: Any, rows: list[dict[str, Any]]) -> Any:
    ids = [int(row["token_id"]) for row in rows]
    weights = embedding.new_tensor([float(row["weight"]) for row in rows]).float().cpu()
    selected = embedding[ids].detach().float().cpu()
    return (selected * weights[:, None]).sum(dim=0)


def extract_directions(
    config: PilotConfig,
    runtime: ModelRuntime,
    *,
    force: bool = False,
) -> Path:
    """Build thought targets and all norm-matched causal-control directions."""
    path = config.direction_artifact
    if path.exists() and config.target_selection_path.exists() and not force:
        artifact = load_directions(config, runtime.torch)
        if artifact["fingerprint"] == config.direction_fingerprint:
            return path

    required_layers = set(map(int, config.sweep["coordinate_swap_layers"])) | {
        int(config.directions["target_selection"]["readout_layer"])
    }
    missing = required_layers - set(runtime.lens.source_layers)
    if missing:
        raise ValueError(f"fitted Jacobian lens is missing layers {sorted(missing)}")

    common, cases = load_cases(
        config.toolalign_root,
        domains=config.data["calibration_domains"],
        documents=config.data["calibration_documents"],
        scenario_types=[config.data["scenario_a"], config.data["scenario_b"]],
    )
    samples, residual_scales = _capture_calibration(config, runtime, common, cases)
    domains, domain_scores = _domain_readout_deltas(config, runtime, samples)
    vocab_size = int(runtime.hf_model.get_output_embeddings().weight.shape[0])
    token_texts = [
        str(value) for value in runtime.tokenizer.convert_ids_to_tokens(range(vocab_size))
    ]
    selection_config = config.directions["target_selection"]
    excluded = _excluded_terms(cases, runtime.tokenizer)
    a = config.data["scenario_a"]
    b = config.data["scenario_b"]
    lexicons, lexical_domain_counts = scenario_lexicons(
        cases,
        scenario_a=a,
        scenario_b=b,
        min_domains=int(selection_config["min_lexical_domains"]),
        excluded=excluded,
    )
    selection = select_stable_targets(
        domain_scores,
        token_texts,
        domain_names=domains,
        top_k=int(selection_config["top_k"]),
        min_domain_consistency=int(selection_config["min_domain_consistency"]),
        candidate_per_fold=int(selection_config["candidate_per_fold"]),
        min_loo_frequency=int(selection_config["min_loo_frequency"]),
        excluded=excluded,
        target_lexicons=lexicons,
        lexical_domain_counts=lexical_domain_counts,
        scenario_a=a,
        scenario_b=b,
    )
    selection.update(
        {
            "schema_version": "jlens-target-selection-v2",
            "scenario_a": a,
            "scenario_b": b,
            "readout_layer": int(selection_config["readout_layer"]),
            "calibration_pairs": len(samples[int(selection_config["readout_layer"])]),
            "min_lexical_domains": int(selection_config["min_lexical_domains"]),
            "target_a_lexicon_size": len(lexicons[a]),
            "target_b_lexicon_size": len(lexicons[b]),
        }
    )

    torch = runtime.torch
    embedding = runtime.hf_model.get_output_embeddings().weight
    u_a = _weighted_target(embedding, selection["target_a"])
    u_b = _weighted_target(embedding, selection["target_b"])
    layers: dict[int, dict[str, Any]] = {}
    for layer in map(int, config.sweep["coordinate_swap_layers"]):
        pair_deltas = [
            pair[b]["last_user"] - pair[a]["last_user"] for pair in samples[layer].values()
        ]
        contrastive_raw = torch.stack(pair_deltas).mean(dim=0)
        scale = residual_scales[layer]
        jacobian = runtime.lens.jacobians[layer]
        jlens_a = transported_target(torch, jacobian, u_a, scale)
        jlens_b = transported_target(torch, jacobian, u_b, scale)
        contrastive_b = _unit_scaled(torch, contrastive_raw, scale, label=f"contrastive[{layer}]")
        random_vectors: dict[str, dict[int, Any]] = {"a_to_b": {}, "b_to_a": {}}
        for direction_index, direction in enumerate(("a_to_b", "b_to_a")):
            for seed in config.directions["random_seeds"]:
                generator = torch.Generator(device="cpu")
                generator.manual_seed(int(seed) + 1_000_003 * layer + 97_409 * direction_index)
                random_vectors[direction][int(seed)] = _unit_scaled(
                    torch,
                    torch.randn(contrastive_raw.shape, generator=generator),
                    scale,
                    label=f"random[{layer},{direction},{seed}]",
                )
        layers[layer] = {
            "mean_a": torch.stack([pair[a]["last_user"] for pair in samples[layer].values()]).mean(
                dim=0
            ),
            "mean_b": torch.stack([pair[b]["last_user"] for pair in samples[layer].values()]).mean(
                dim=0
            ),
            "residual_scale": float(scale),
            "jlens": {"a_to_b": jlens_b, "b_to_a": jlens_a},
            "contrastive": {"a_to_b": contrastive_b, "b_to_a": -contrastive_b},
            "concept_a": jlens_a,
            "concept_b": jlens_b,
            "random": random_vectors,
        }

    observation_layer = int(config.sweep["thought_observation_layer"])
    probe = runtime.lens.jacobians[observation_layer].detach().float().cpu().T @ (u_b - u_a)
    artifact = {
        "schema_version": DIRECTION_SCHEMA_VERSION,
        "fingerprint": config.direction_fingerprint,
        "model_id": config.model["model_id"],
        "model_revision": config.model["model_revision"],
        "lens_revision": config.model["lens_revision"],
        "scenario_a": a,
        "scenario_b": b,
        "calibration_examples": len(cases) * len(config.data["conditions"]),
        "target_a": u_a,
        "target_b": u_b,
        "thought_probe": {
            "layer": observation_layer,
            "vector_b_minus_a": probe,
        },
        "layers": layers,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    config.target_selection_path.write_text(
        json.dumps(selection, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    torch.save(artifact, path)
    return path


def load_directions(config: PilotConfig, torch: Any) -> dict[str, Any]:
    """Load a tensor-only direction artifact and verify its scientific inputs."""
    if not config.direction_artifact.is_file():
        raise FileNotFoundError(
            f"missing {config.direction_artifact}; run extract-directions first"
        )
    if not config.target_selection_path.is_file():
        raise FileNotFoundError(
            f"missing {config.target_selection_path}; rerun extract-directions with --force"
        )
    artifact = torch.load(config.direction_artifact, map_location="cpu", weights_only=True)
    if artifact.get("schema_version") != DIRECTION_SCHEMA_VERSION:
        raise ValueError("unsupported direction artifact schema")
    if artifact.get("fingerprint") != config.direction_fingerprint:
        raise ValueError("direction artifact fingerprint does not match the current config")
    missing = set(map(int, config.sweep["coordinate_swap_layers"])) - set(artifact["layers"])
    if missing:
        raise ValueError(f"direction artifact is missing layers {sorted(missing)}")
    return artifact
