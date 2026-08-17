from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np

from jlens_causal import benchmark
from jlens_causal.baselines import (
    build_austeer_artifact,
    build_caa_artifact,
    build_cast_artifact,
    build_iti_artifact,
    build_loreft_artifact,
    build_mera_artifact,
    build_sadi_artifact,
    caa_mean_difference,
    caa_vector,
    cast_condition_similarity,
    cast_pca_pairwise,
    load_austeer_artifact,
    load_caa_artifact,
    load_cast_artifact,
    load_iti_artifact,
    load_loreft_artifact,
    load_mera_artifact,
    load_sadi_artifact,
    mera_closed_form_delta,
    mera_error_probabilities,
    save_austeer_artifact,
    save_caa_artifact,
    save_cast_artifact,
    save_iti_artifact,
    save_loreft_artifact,
    save_mera_artifact,
    save_sadi_artifact,
    select_cast_gate,
    validate_austeer_artifact,
    validate_caa_artifact,
    validate_cast_artifact,
    validate_iti_artifact,
    validate_loreft_artifact,
    validate_mera_artifact,
    validate_sadi_artifact,
)
from jlens_causal.config import load_config
from jlens_causal.directions import (
    scenario_lexicons,
    select_stable_targets,
    transported_target,
)
from jlens_causal.experiment import (
    GENERATED_ARTIFACTS,
    iter_trial_specs,
    reset_output_artifacts,
    trial_run_id,
    validate_output_compatibility,
)
from jlens_causal.followup import (
    analyze_followup,
    classify_followup,
    contrastive_response_direction,
    iter_followup_specs,
    matched_followup_control_positions,
)
from jlens_causal.followup_config import load_followup_config
from jlens_causal.interventions import (
    AdditiveOperator,
    austeer_generation_hooks,
    cast_generation_hook,
    generation_intervention_hook,
    intervention_hook,
    iti_generation_hooks,
    loreft_generation_hooks,
    matched_prompt_positions,
    mera_generation_hook,
    sadi_generation_hooks,
)
from jlens_causal.loreft import LoReFTExample, train_loreft_artifact
from jlens_causal.metrics import analyze_runs, paired_trial_metrics
from jlens_causal.modeling import (
    GenerationResult,
    ModelRuntime,
    _render_chat_text,
    _rendered_message_span,
    completion_status,
)
from jlens_causal.steering_config import (
    load_toolalign_caa_config,
    load_toolalign_iti_config,
    load_toolalign_mera_config,
    load_toolalign_sadi_config,
)
from jlens_causal.taubench_caa import _failure_prompt_prefix, load_taubench_caa_config
from jlens_causal.taubench_cast import (
    _replace_last_user_message,
    load_taubench_cast_config,
)
from jlens_causal.taubench_iti import load_taubench_iti_config
from jlens_causal.taubench_mera import load_taubench_mera_config
from jlens_causal.taubench_sadi import load_taubench_sadi_config
from jlens_causal.toolalign import ScenarioCase, classify_behavior, load_cases, parse_tool_calls
from jlens_causal.toolalign_caa import (
    detect_tool_call_loop,
    run_toolalign_rollout,
    tool_call_fingerprint,
)

ROOT = Path(__file__).parents[1]


def behavior(
    kind: str,
    signature: list[str],
    *,
    parse_error: bool = False,
    truncated: bool = False,
) -> dict:
    risk_profile = {
        "aligned_tool_calls": int(kind == "aligned"),
        "boundary_tool_calls": int(kind == "boundary"),
        "misaligned_tool_calls": int(kind == "misaligned"),
    }
    return {
        "behavior_class": kind,
        "tool_signature": signature,
        "behavior_summary": {},
        "risk_profile": risk_profile,
        "parse_error": parse_error,
        "truncated": truncated,
        "valid_for_pairing": not parse_error and not truncated,
    }


def record(
    config,
    run_id: str,
    *,
    scenario: str,
    method: str,
    result: dict,
    target: str | None = None,
    random_seed: int | None = None,
    thought_margin: float | None = None,
) -> dict:
    valid = bool(result["valid_for_pairing"])
    return {
        "schema_version": "jlens-causal-record-v3",
        "run_id": run_id,
        "run_fingerprint": config.run_fingerprint,
        "domain": "nuclear-energy",
        "document": 1,
        "condition": "tamely-with-reasoning",
        "source_scenario": scenario,
        "target_scenario": target,
        "direction": "none" if method == "baseline" else "a_to_b",
        "method": method,
        "vector_layer": None if method == "baseline" else 24,
        "applied_layer": None if method == "baseline" else 24,
        "alpha": 0.0 if method == "baseline" else 1.0,
        "position_policy": None if method == "baseline" else "user_span",
        "site": "baseline" if method == "baseline" else "candidate",
        "random_seed": random_seed,
        "truncated": bool(result["truncated"]),
        "valid_for_pairing": valid,
        "output_text": run_id,
        "behavior": result,
        "thought_trace": {
            "observation_layer": 30,
            "pre_response_last": thought_margin
            if thought_margin is not None
            else (0.0 if scenario == "safe" else 2.0),
            "response_margins": [0.0],
        },
    }


class ConfigTests(unittest.TestCase):
    def test_taubench_task18_caa_uses_observed_failure_context(self) -> None:
        config = load_taubench_caa_config(ROOT / "configs" / "taubench_task18_caa.json")
        prefix = _failure_prompt_prefix(config)
        self.assertTrue(prefix.endswith("<|im_start|>assistant\n"))
        self.assertIn("credit_card_2929732", prefix)
        self.assertEqual(config.raw["causal_turn_index"], 9)
        self.assertEqual(config.raw["causal_boundary"], "after_user_message")
        self.assertEqual(len(config.extraction["positive_responses"]), 8)
        self.assertEqual(config.extraction["layers"], [20, 24])

    def test_toolalign_caa_config_has_disjoint_confirmatory_split(self) -> None:
        config = load_toolalign_caa_config(ROOT / "configs" / "toolalign_caa_llama8b.json")
        self.assertFalse(
            set(config.data["calibration_domains"]).intersection(config.data["evaluation_domains"])
        )
        self.assertEqual(set(config.models), {"aligned", "abliterated"})
        self.assertEqual(config.extraction["site"], "assistant_response_last_content")
        self.assertGreaterEqual(len(config.sweep["random_seeds"]), 3)

    def test_taubench_cast_uses_disjoint_prompt_gate_calibration(self) -> None:
        config = load_taubench_cast_config(ROOT / "configs" / "taubench_task18_cast.json")
        train = config.extraction["condition_train"]
        validation = config.extraction["gate_validation"]
        self.assertFalse(
            set(train["positive"] + train["negative"]).intersection(
                validation["positive"] + validation["negative"]
            )
        )
        changed = _replace_last_user_message(config, "UNIQUE CAST CONDITION")
        self.assertIn("UNIQUE CAST CONDITION", changed)
        self.assertNotIn("I’m **fine with the refunds", changed)
        self.assertTrue(changed.endswith("<|im_start|>assistant\n"))
        self.assertEqual(config.raw["causal_turn_index"], 9)

    def test_toolalign_mera_has_three_disjoint_domain_splits(self) -> None:
        config = load_toolalign_mera_config(ROOT / "configs" / "toolalign_mera_llama8b.json")
        domain_sets = [
            set(config.data[key])
            for key in (
                "calibration_domains",
                "probe_validation_domains",
                "evaluation_domains",
            )
        ]
        self.assertFalse(domain_sets[0].intersection(domain_sets[1]))
        self.assertFalse(domain_sets[0].intersection(domain_sets[2]))
        self.assertFalse(domain_sets[1].intersection(domain_sets[2]))
        self.assertEqual(config.extraction["layers"], [16, 20, 24])

    def test_toolalign_sadi_preregisters_disjoint_data_and_sensitivity_grid(self) -> None:
        config = load_toolalign_sadi_config(
            ROOT / "configs" / "toolalign_sadi_llama8b.json"
        )
        domain_sets = [
            set(config.data[key])
            for key in (
                "calibration_domains",
                "unit_validation_domains",
                "evaluation_domains",
            )
        ]
        self.assertFalse(domain_sets[0].intersection(domain_sets[1]))
        self.assertFalse(domain_sets[0].intersection(domain_sets[2]))
        self.assertFalse(domain_sets[1].intersection(domain_sets[2]))
        self.assertEqual(max(config.sweep["top_k_values"]), config.extraction["max_top_k"])
        self.assertIn(config.sweep["primary_strength"], config.sweep["strengths"])

    def test_toolalign_iti_preregisters_disjoint_head_selection(self) -> None:
        config = load_toolalign_iti_config(ROOT / "configs" / "toolalign_iti_llama8b.json")
        domain_sets = [
            set(config.data[key])
            for key in (
                "calibration_domains",
                "head_validation_domains",
                "evaluation_domains",
            )
        ]
        self.assertFalse(domain_sets[0].intersection(domain_sets[1]))
        self.assertFalse(domain_sets[0].intersection(domain_sets[2]))
        self.assertFalse(domain_sets[1].intersection(domain_sets[2]))
        self.assertEqual(max(config.sweep["top_k_values"]), config.extraction["max_top_k"])
        self.assertIn(config.sweep["primary_alpha"], config.sweep["alphas"])

    def test_taubench_mera_partitions_behavior_pairs_before_alpha_selection(self) -> None:
        config = load_taubench_mera_config(ROOT / "configs" / "taubench_task18_mera.json")
        train = set(config.extraction["train_pair_indices"])
        validation = set(config.extraction["validation_pair_indices"])
        self.assertFalse(train.intersection(validation))
        self.assertEqual(train.union(validation), set(range(8)))
        self.assertEqual(config.extraction["site"], (
            "post_attention_layernorm_output_last_assistant_content"
        ))

    def test_taubench_sadi_partitions_pairs_without_reward_tuning(self) -> None:
        config = load_taubench_sadi_config(ROOT / "configs" / "taubench_task18_sadi.json")
        train = set(config.extraction["train_pair_indices"])
        validation = set(config.extraction["validation_pair_indices"])
        self.assertFalse(train.intersection(validation))
        self.assertEqual(train.union(validation), set(range(8)))
        self.assertEqual(config.extraction["site"], "mlp_output_last_assistant_content")
        self.assertEqual(
            max(config.raw["sweep"]["top_k_values"]),
            config.extraction["max_top_k"],
        )

    def test_taubench_iti_partitions_head_selection_before_task_reward(self) -> None:
        config = load_taubench_iti_config(ROOT / "configs" / "taubench_task18_iti.json")
        train = set(config.extraction["train_pair_indices"])
        validation = set(config.extraction["validation_pair_indices"])
        self.assertFalse(train.intersection(validation))
        self.assertEqual(train.union(validation), set(range(8)))
        self.assertEqual(
            config.extraction["site"],
            "self_attn_o_proj_input_last_assistant_content",
        )
        self.assertEqual(
            max(config.raw["sweep"]["top_k_values"]),
            config.extraction["max_top_k"],
        )

    def test_smoke_count_matches_grid(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        self.assertEqual(config.estimated_generations()["total"], 18)
        specs = list(iter_trial_specs(config))
        self.assertEqual(len(specs), 18)
        self.assertEqual(sum(spec.method == "baseline" for spec in specs), 2)
        swaps = [spec for spec in specs if spec.method == "jlens_swap"]
        self.assertEqual(len(swaps), 6)
        self.assertTrue(all(spec.vector_layer_band == (24, 26, 28) for spec in swaps))
        self.assertEqual(config.generation["max_new_tokens"], 4096)
        full = load_config(ROOT / "configs" / "qwen35_toolalign_pilot.json")
        self.assertEqual(full.generation["max_new_tokens"], 4096)
        self.assertEqual(full.estimated_generations()["total"], 4640)

    def test_generation_changes_run_fingerprint_and_ids(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        changed_raw = json.loads(json.dumps(config.raw))
        changed_raw["generation"]["max_new_tokens"] = 2048
        changed = replace(config, raw=changed_raw)
        spec = next(iter(iter_trial_specs(config)))
        self.assertNotEqual(config.run_fingerprint, changed.run_fingerprint)
        self.assertNotEqual(trial_run_id(config, spec), trial_run_id(changed, spec))

    def test_followup_counts_and_fresh_calibration_cost(self) -> None:
        smoke = load_followup_config(ROOT / "configs" / "followup_smoke.json")
        self.assertEqual(smoke.estimated_generations()["direction_calibration"], 96)
        self.assertEqual(smoke.estimated_generations()["sweep_total"], 22)
        self.assertEqual(smoke.estimated_generations()["fresh_total"], 118)
        self.assertEqual(len(list(iter_followup_specs(smoke))), 22)
        powered = load_followup_config(ROOT / "configs" / "followup_powered.json")
        self.assertEqual(powered.estimated_generations()["sweep_total"], 5536)
        self.assertEqual(powered.estimated_generations()["fresh_total"], 5632)

    def test_followup_calibration_generation_changes_direction_fingerprint(self) -> None:
        config = load_followup_config(ROOT / "configs" / "followup_smoke.json")
        changed_raw = json.loads(json.dumps(config.raw))
        changed_raw["generation"]["seed"] += 1
        changed = replace(config, raw=changed_raw)
        self.assertNotEqual(config.direction_fingerprint, changed.direction_fingerprint)
        self.assertNotEqual(config.run_fingerprint, changed.run_fingerprint)

    def test_fresh_removes_only_owned_artifacts(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            for name in GENERATED_ARTIFACTS:
                (config.output_dir / name).write_text("generated", encoding="utf-8")
            keep = config.output_dir / "keep-me.txt"
            keep.write_text("user", encoding="utf-8")
            removed = reset_output_artifacts(config)
            self.assertEqual(len(removed), len(GENERATED_ARTIFACTS))
            self.assertTrue(keep.is_file())

    def test_fresh_preflight_is_atomic_for_unexpected_directories(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            directions = config.output_dir / "directions.pt"
            directions.write_text("generated", encoding="utf-8")
            (config.output_dir / "manifest.json").mkdir()
            with self.assertRaisesRegex(ValueError, "non-file"):
                reset_output_artifacts(config)
            self.assertTrue(directions.is_file())

    def test_toolalign_selection_from_public_checkout(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        _, cases = load_cases(
            config.toolalign_root,
            domains=["financial"],
            documents=[1],
            scenario_types=["safe", "wrongdoing"],
        )
        self.assertEqual(len(cases), 2)

    def test_toolalign_prompt_parity_for_all_scenarios(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        helper = config.toolalign_root / "jlens_experiment" / "toolalign_common.py"
        if not helper.is_file():
            self.skipTest("local ToolAlign parity helper is unavailable")
        spec = importlib.util.spec_from_file_location("_parity_toolalign_common", helper)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        original = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = original
        spec.loader.exec_module(original)
        bundled_cases = benchmark.load_scenarios(config.toolalign_root)
        original_cases = original.load_scenarios(config.toolalign_root)
        self.assertEqual(len(bundled_cases), 128)
        self.assertEqual(len(original_cases), 128)
        for bundled, reference in zip(bundled_cases, original_cases, strict=True):
            self.assertEqual(bundled.id, reference.id)
            self.assertEqual(bundled.prompt, reference.prompt)
            for condition in benchmark.CONDITIONS:
                self.assertEqual(
                    benchmark.system_prompt_for(condition, bundled.tools),
                    original.system_prompt_for(condition, reference.tools),
                )

    def test_stale_manifest_requires_fresh(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            (config.output_dir / "manifest.json").write_text(
                json.dumps({"schema_version": "jlens-causal-run-v1"}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "--fresh"):
                validate_output_compatibility(config)


class ParserTests(unittest.TestCase):
    def test_toolalign_and_qwen_encodings(self) -> None:
        fixtures = (
            (
                '<tool_call><tool_name>x</tool_name><arguments>{"a":1}</arguments></tool_call>',
                "x",
                {"a": 1},
            ),
            ('<tool_name>x</tool_name><arguments>{"a":1}</arguments>', "x", {"a": 1}),
            (
                '<tool_call><email>TOOL_NAME</email><arguments>{"body":"x"}</arguments></tool_call>',
                "email",
                {"body": "x"},
            ),
            (
                "<tool_call><function=y><parameter=b>2</parameter></function></tool_call>",
                "y",
                {"b": 2},
            ),
            (
                '<tool_call>{"name":"z","arguments":{"c":3}}</tool_call>',
                "z",
                {"c": 3},
            ),
            ('```json\n[{"name":"z","arguments":{"c":3}}]\n```', "z", {"c": 3}),
        )
        for text, expected_name, expected_arguments in fixtures:
            with self.subTest(text=text):
                calls = parse_tool_calls(text)
                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0].name, expected_name)
                self.assertEqual(calls[0].arguments, expected_arguments)

    def test_incomplete_tool_call_is_not_recovered(self) -> None:
        self.assertEqual(
            parse_tool_calls('<tool_call><tool_name>x</tool_name><arguments>{"a":'),
            [],
        )

    def test_followup_classifies_stop_repeat_and_corruption(self) -> None:
        stop = classify_followup("Task complete.", truncated=False)
        repeat = classify_followup(
            "<tool_call><tool_name>x</tool_name><arguments>{}</arguments></tool_call>",
            truncated=False,
        )
        invalid = classify_followup("<tool_call><tool_name>x", truncated=False)
        self.assertEqual(stop["decision"], "stop")
        self.assertEqual(repeat["decision"], "repeat")
        self.assertEqual(invalid["decision"], "invalid")
        self.assertTrue(invalid["parse_error"])

    def test_toolalign_email_taxonomy(self) -> None:
        tools = benchmark.BASE_TOOLS
        internal = classify_behavior(
            "<tool_call><tool_name>email</tool_name><arguments>"
            '{"from":"a@corp.test","to":"b@corp.test"}'
            "</arguments></tool_call>",
            tools,
        )
        external = classify_behavior(
            "<tool_call><tool_name>email</tool_name><arguments>"
            '{"from":"a@corp.test","to":"b@nrc.gov"}'
            "</arguments></tool_call>",
            tools,
        )
        self.assertEqual(internal["behavior_class"], "aligned")
        self.assertTrue(internal["behavior_summary"]["used_aligned_internal_reporting"])
        self.assertEqual(external["behavior_class"], "misaligned")
        self.assertTrue(external["behavior_summary"]["used_external_contact"])

    def test_toolalign_caa_loop_helpers_match_sorted_argument_semantics(self) -> None:
        call = parse_tool_calls(
            "<tool_call><tool_name>writeInternalLog</tool_name><arguments>"
            '{"z":2,"a":1}</arguments></tool_call>'
        )[0]
        self.assertEqual(
            tool_call_fingerprint(call),
            'writeInternalLog::{"a":1,"z":2}',
        )
        sequence = ["a", "b", "c", "a", "b", "c"]
        self.assertTrue(detect_tool_call_loop(sequence))
        self.assertFalse(detect_tool_call_loop(sequence[:-1]))

    def test_toolalign_caa_rollout_replays_tool_result_then_stops(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        case = ScenarioCase(
            domain="financial",
            scenario_type="wrongdoing",
            document=1,
            prompt="document",
            tools=benchmark.BASE_TOOLS,
        )
        seen_messages: list[list[dict[str, str]]] = []

        def fake_render(_runtime, messages, **_kwargs):
            seen_messages.append([dict(message) for message in messages])
            return SimpleNamespace(
                input_ids=torch.tensor([[1, 2, 3]]),
                attention_mask=torch.ones(1, 3, dtype=torch.long),
            )

        generations = iter(
            [
                GenerationResult(
                    text=(
                        "<tool_call><tool_name>writeInternalLog</tool_name>"
                        '<arguments>{"logName":"audit","logData":"x"}</arguments>'
                        "</tool_call>"
                    ),
                    completion_ids=[4],
                    terminated_by_eos=True,
                    hit_token_limit=False,
                    termination_reason="eos",
                ),
                GenerationResult(
                    text="Task complete.",
                    completion_ids=[5],
                    terminated_by_eos=True,
                    hit_token_limit=False,
                    termination_reason="eos",
                ),
            ]
        )
        with (
            patch("jlens_causal.toolalign_caa.render_conversation", fake_render),
            patch(
                "jlens_causal.toolalign_caa.generate_text",
                side_effect=lambda *_args, **_kwargs: next(generations),
            ),
        ):
            result = run_toolalign_rollout(
                SimpleNamespace(torch=torch),
                common=benchmark,
                case=case,
                condition="tamely-without-reasoning",
                generation_config={
                    "seed": 1,
                    "max_new_tokens": 32,
                    "max_steps": 10,
                    "do_sample": False,
                    "use_cache": True,
                },
            )
        self.assertEqual(result["step_count"], 2)
        self.assertEqual(result["stop_reason"], "no_tool_call")
        self.assertEqual(result["behavior"]["behavior_class"], "aligned")
        tool_result = seen_messages[1][-1]["content"]
        self.assertIn("Tool execution results:", tool_result)
        self.assertIn("writeInternalLog executed successfully", tool_result)


class DirectionTests(unittest.TestCase):
    def test_caa_is_exact_paired_positive_minus_negative(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        result = caa_mean_difference(
            torch,
            positive=torch.tensor([[3.0, 1.0], [5.0, 2.0]]),
            negative=torch.tensor([[1.0, 1.0], [1.0, 0.0]]),
        )
        torch.testing.assert_close(result["direction"], torch.tensor([3.0, 1.0]))
        torch.testing.assert_close(result["unit_direction"], torch.tensor([3.0, 1.0]) / (10.0**0.5))
        self.assertEqual(result["pair_count"], 2)

    def test_caa_rejects_unpaired_samples(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        with self.assertRaisesRegex(ValueError, "same shape"):
            caa_mean_difference(
                torch,
                positive=torch.zeros(2, 3),
                negative=torch.zeros(1, 3),
            )

    def test_caa_artifact_round_trip_and_identity_checks(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        artifact = build_caa_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            layer=7,
            positive=torch.tensor([[2.0, 0.0], [4.0, 2.0]]),
            negative=torch.tensor([[0.0, 0.0], [0.0, 0.0]]),
            pair_ids=["p0", "p1"],
            positive_label="aligned",
            negative_label="misaligned",
            extraction_site="assistant_response_mean",
            benchmark="toolalign",
            calibration_split={"domains": ["d0"]},
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = save_caa_artifact(torch, artifact, Path(temporary) / "caa.pt")
            loaded = load_caa_artifact(
                torch,
                path,
                expected_model_id="test/model",
                expected_layer=7,
            )
        torch.testing.assert_close(caa_vector(loaded, scaling="raw"), torch.tensor([3.0, 1.0]))
        torch.testing.assert_close(
            caa_vector(loaded, scaling="unit"), torch.tensor([3.0, 1.0]) / (10.0**0.5)
        )
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_caa_artifact(loaded, expected_model_id="other/model")
        tampered = dict(loaded, layer=8)
        with self.assertRaisesRegex(ValueError, "metadata fingerprint"):
            validate_caa_artifact(tampered)
        bad_unit = dict(loaded, unit_direction=torch.tensor([1.0, 0.0]))
        with self.assertRaisesRegex(ValueError, "unit_direction"):
            validate_caa_artifact(bad_unit)

    def test_cast_pairwise_pca_orients_positive_and_matches_similarity(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        result = cast_pca_pairwise(
            torch,
            positive=torch.tensor([[2.0, 0.0], [4.0, 0.0]]),
            negative=torch.tensor([[0.0, 0.0], [0.0, 0.0]]),
        )
        torch.testing.assert_close(result["direction"], torch.tensor([1.0, 0.0]))
        score = cast_condition_similarity(
            torch,
            torch.tensor([[2.0, 1.0], [4.0, 1.0]]),
            result["direction"],
            comparison_mode="mean",
        )
        self.assertAlmostEqual(float(score), 3.0 / (10.0**0.5), places=5)

    def test_cast_selects_gate_and_round_trips_calibration_evidence(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        gate = select_cast_gate(
            positive_scores={1: [0.3, 0.7], 2: [0.8, 0.9]},
            negative_scores={1: [0.4, 0.6], 2: [0.1, 0.2]},
        )
        self.assertEqual(gate["condition_layer"], 2)
        self.assertEqual(gate["comparator"], "greater")
        self.assertEqual(gate["f1"], 1.0)
        artifact = build_cast_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            behavior_layer=7,
            condition_layer=2,
            behavior_positive=torch.tensor([[2.0, 0.0], [4.0, 0.0]]),
            behavior_negative=torch.zeros(2, 2),
            condition_positive=torch.tensor([[2.0, 0.0], [4.0, 0.0]]),
            condition_negative=torch.zeros(2, 2),
            behavior_pair_ids=["b0", "b1"],
            condition_pair_ids=["c0", "c1"],
            gate_positive_ids=["vp0", "vp1"],
            gate_negative_ids=["vn0", "vn1"],
            gate_positive_scores=[0.8, 0.9],
            gate_negative_scores=[0.1, 0.2],
            gate=gate,
            comparison_mode="mean",
            benchmark="toolalign",
            calibration_split={"train": ["d0"], "gate_validation": ["d1"]},
            sites={
                "behavior_extraction": "block_output_assistant_content_mean",
                "condition_extraction": "block_output_prompt_mean",
                "gate_measurement": "block_input_prompt_mean",
                "behavior_application": "block_input",
            },
            source={"repository": "activation-steering", "revision": "abc123"},
        )
        with tempfile.TemporaryDirectory() as temporary:
            path = save_cast_artifact(torch, artifact, Path(temporary) / "cast.pt")
            loaded = load_cast_artifact(
                torch,
                path,
                expected_model_id="test/model",
                expected_behavior_layer=7,
            )
        self.assertEqual(loaded["gate_positive_ids"], ["vp0", "vp1"])
        tampered = dict(loaded, condition_threshold=0.95)
        with self.assertRaisesRegex(ValueError, "gate metrics"):
            validate_cast_artifact(tampered)

    def test_mera_closed_form_and_calibrated_artifact_round_trip(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        artifact = build_mera_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            layer=7,
            train_correct=torch.tensor([[-2.0, 0.0], [-1.0, 0.0]]),
            train_failure=torch.tensor([[1.0, 0.0], [2.0, 0.0]]),
            validation_correct=torch.tensor([[-1.5, 0.0], [-1.2, 0.0]]),
            validation_failure=torch.tensor([[1.2, 0.0], [1.5, 0.0]]),
            train_pair_ids=["t0", "t1"],
            validation_correct_ids=["vc0", "vc1"],
            validation_failure_ids=["vf0", "vf1"],
            alpha_grid=[0.5, 0.9],
            benchmark="toolalign",
            calibration_split={"train": ["d0"], "validation": ["d1"]},
            site="post_attention_layernorm_output",
            source={"repository": "MERA-steering", "revision": "abc123"},
        )
        self.assertEqual(artifact["selected_alpha"], 0.9)
        vector = artifact["probe_vector"]
        before = mera_error_probabilities(torch, torch.tensor([[2.0, 0.0]]), vector)
        delta, condition, _scores = mera_closed_form_delta(
            torch,
            torch.tensor([[2.0, 0.0]]),
            vector,
            alpha=0.5,
        )
        after = mera_error_probabilities(
            torch,
            torch.tensor([[2.0, 0.0]]) + delta,
            vector,
        )
        self.assertGreater(float(before[0]), 0.9)
        self.assertTrue(bool(condition[0]))
        self.assertAlmostEqual(float(after[0]), 0.5, places=5)
        with tempfile.TemporaryDirectory() as temporary:
            path = save_mera_artifact(torch, artifact, Path(temporary) / "mera.pt")
            loaded = load_mera_artifact(
                torch,
                path,
                expected_model_id="test/model",
                expected_layer=7,
            )
        tampered = dict(loaded, selected_alpha=0.5)
        with self.assertRaisesRegex(ValueError, "fingerprint"):
            validate_mera_artifact(tampered)

    def test_sadi_selects_global_positive_units_and_round_trips(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        artifact = build_sadi_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            correct_by_layer={
                1: torch.tensor([[5.0, 1.0, 0.0], [3.0, 1.0, 0.0]]),
                3: torch.tensor([[0.0, 4.0, 2.0], [0.0, 2.0, 2.0]]),
            },
            failure_by_layer={1: torch.zeros(2, 3), 3: torch.zeros(2, 3)},
            pair_ids=["p0", "p1"],
            top_k=3,
            benchmark="toolalign",
            calibration_split={"train": ["d0"]},
            site="mlp_output_last_assistant_content",
            source={"repository": "SADI", "revision": "abc123"},
        )
        self.assertEqual(artifact["selected_units"].tolist(), [[1, 0], [3, 1], [3, 2]])
        with tempfile.TemporaryDirectory() as temporary:
            path = save_sadi_artifact(torch, artifact, Path(temporary) / "sadi.pt")
            loaded = load_sadi_artifact(torch, path, expected_model_id="test/model")
        self.assertEqual(loaded["unit_scores"].tolist(), [4.0, 3.0, 2.0])
        tampered = dict(loaded, top_k=2)
        with self.assertRaisesRegex(ValueError, "malformed"):
            validate_sadi_artifact(tampered)

    def test_iti_selects_heldout_head_and_round_trips_std_scaled_com(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        train_correct_l0 = torch.tensor(
            [[[2.0, 0.0], [0.0, 0.0]], [[3.0, 0.0], [0.0, 0.0]]]
        )
        train_failure_l0 = -train_correct_l0
        validation_correct_l0 = torch.tensor(
            [[[1.0, 0.0], [0.0, 0.0]], [[4.0, 0.0], [0.0, 0.0]]]
        )
        validation_failure_l0 = -validation_correct_l0
        zeros = torch.zeros(2, 2, 2)
        artifact = build_iti_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            train_correct_by_layer={0: train_correct_l0, 1: zeros},
            train_failure_by_layer={0: train_failure_l0, 1: zeros},
            validation_correct_by_layer={0: validation_correct_l0, 1: zeros},
            validation_failure_by_layer={0: validation_failure_l0, 1: zeros},
            train_pair_ids=["t0", "t1"],
            validation_pair_ids=["v0", "v1"],
            top_k=1,
            benchmark="toolalign",
            calibration_split={"train": ["d0"], "validation": ["d1"]},
            site="self_attn_o_proj_input_last_assistant_content",
            source={"repository": "honest_llama", "revision": "abc123"},
        )
        self.assertEqual(artifact["selected_heads"].tolist(), [[0, 0]])
        torch.testing.assert_close(artifact["head_directions"], torch.tensor([[1.0, 0.0]]))
        self.assertEqual(float(artifact["validation_accuracies"][0, 0]), 1.0)
        with tempfile.TemporaryDirectory() as temporary:
            path = save_iti_artifact(torch, artifact, Path(temporary) / "iti.pt")
            loaded = load_iti_artifact(torch, path, expected_model_id="test/model")
        self.assertGreater(float(loaded["projection_stds"][0]), 0.0)
        tampered = dict(loaded, top_k=2)
        with self.assertRaisesRegex(ValueError, "malformed"):
            validate_iti_artifact(tampered)

    def test_austeer_selects_signed_consistent_scalar_units(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        correct = torch.tensor([[2.0, 0.0, -1.0], [3.0, 0.0, -2.0]])
        failure = torch.zeros(2, 3)
        validation_correct = torch.tensor([[1.0, 0.0, -3.0], [4.0, 0.0, -1.0]])
        artifact = build_austeer_artifact(
            torch,
            model_id="test/model",
            model_revision="abc123",
            train_correct_by_layer={0: correct},
            train_failure_by_layer={0: failure},
            validation_correct_by_layer={0: validation_correct},
            validation_failure_by_layer={0: failure},
            train_pair_ids=["t0", "t1"],
            validation_pair_ids=["v0", "v1"],
            top_k=2,
            benchmark="toolalign",
            calibration_split={"train": ["d0"], "validation": ["d1"]},
            site="self_attn_o_proj_input_last_assistant_content",
            source={"repository": "AUSteer", "revision": "abc123"},
        )
        self.assertEqual(artifact["selected_units"].tolist(), [[0, 0], [0, 2]])
        torch.testing.assert_close(artifact["selected_betas"], torch.tensor([1.0, -1.0]))
        self.assertEqual(artifact["validation_sign_agreement_count"], 2)
        with tempfile.TemporaryDirectory() as temporary:
            path = save_austeer_artifact(
                torch, artifact, Path(temporary) / "austeer.pt"
            )
            loaded = load_austeer_artifact(
                torch, path, expected_model_id="test/model"
            )
        tampered = dict(loaded, top_k=1)
        with self.assertRaisesRegex(ValueError, "malformed"):
            validate_austeer_artifact(tampered)

    def test_loreft_artifact_preserves_orthogonal_low_rank_parameters(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        artifact = build_loreft_artifact(
            torch,
            model_id="toy",
            model_revision="a" * 40,
            layers=[2],
            rotate_by_layer={2: torch.tensor([[1.0], [0.0], [0.0]])},
            learned_weight_by_layer={2: torch.tensor([[0.0, 1.0, 0.0]])},
            learned_bias_by_layer={2: torch.tensor([0.5])},
            train_example_ids=["t0"],
            validation_example_ids=["v0"],
            rank=1,
            benchmark="toy",
            training={"optimizer": "adamw"},
            validation_loss=1.25,
            site="block_output",
            position="last_prompt_token",
            source={"repository": "stanfordnlp/pyreft", "revision": "b" * 40},
        )
        validate_loreft_artifact(artifact, expected_model_id="toy")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "loreft.pt"
            save_loreft_artifact(torch, artifact, path)
            loaded = load_loreft_artifact(torch, path, expected_model_id="toy")
        torch.testing.assert_close(loaded["rotations"], artifact["rotations"])

    def test_loreft_training_freezes_base_and_returns_valid_checkpoint(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class TinyModel(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.embedding = torch.nn.Embedding(7, 3)
                self.layers = torch.nn.ModuleList([torch.nn.Identity()])
                self.lm_head = torch.nn.Linear(3, 7, bias=False)

            def forward(self, input_ids, attention_mask, labels, use_cache):
                del attention_mask, use_cache
                hidden = self.embedding(input_ids)
                for layer in self.layers:
                    hidden = layer(hidden)
                logits = self.lm_head(hidden)
                loss = torch.nn.functional.cross_entropy(
                    logits[:, :-1].reshape(-1, 7),
                    labels[:, 1:].reshape(-1),
                    ignore_index=-100,
                )
                return SimpleNamespace(loss=loss)

        model = TinyModel()
        lens_model = SimpleNamespace(layers=model.layers, d_model=3)
        runtime = ModelRuntime(
            torch=torch,
            tokenizer=None,
            hf_model=model,
            lens_model=lens_model,
            lens=None,
            device=torch.device("cpu"),
        )
        example = LoReFTExample(
            example_id="train",
            input_ids=torch.tensor([[1, 2, 3, 4]]),
            attention_mask=torch.ones(1, 4, dtype=torch.long),
            response_positions=(2, 3),
            boundary_position=1,
        )
        validation = LoReFTExample(
            example_id="validation",
            input_ids=torch.tensor([[1, 2, 4, 3]]),
            attention_mask=torch.ones(1, 4, dtype=torch.long),
            response_positions=(2, 3),
            boundary_position=1,
        )
        artifact = train_loreft_artifact(
            runtime,
            model_id="tiny",
            model_revision="a" * 40,
            layers=(0,),
            rank=1,
            train_examples=[example],
            validation_examples=[validation],
            epochs=1,
            learning_rate=0.01,
            weight_decay=0.0,
            max_grad_norm=1.0,
            seed=1,
            benchmark="toy",
            site="block_output",
            source={"repository": "stanfordnlp/pyreft", "revision": "b" * 40},
        )
        validate_loreft_artifact(artifact, expected_model_id="tiny")
        self.assertTrue(all(parameter.requires_grad for parameter in model.parameters()))

    def test_cross_domain_stable_target_selection(self) -> None:
        token_texts = [
            "good",
            "bad",
            "financial",
            "tool",
            "mixed",
            "noise",
            "ittest",
            "ampu",
        ]
        deltas = np.asarray(
            [
                [-3.0, 4.0, 99.0, 50.0, 1.0, -0.1, -100.0, 100.0],
                [-2.0, 3.0, -99.0, 50.0, -1.0, 0.2, -100.0, 100.0],
                [-4.0, 2.0, 99.0, 50.0, 1.0, -0.1, -100.0, 100.0],
            ]
        )
        selected = select_stable_targets(
            deltas,
            token_texts,
            domain_names=["a", "b", "c"],
            top_k=1,
            min_domain_consistency=3,
            candidate_per_fold=2,
            min_loo_frequency=3,
            excluded={"financial", "tool"},
            target_lexicons={"a": {"good"}, "b": {"bad"}},
        )
        self.assertEqual(selected["target_a"][0]["token"], "good")
        self.assertEqual(selected["target_b"][0]["token"], "bad")
        self.assertEqual(selected["calibration_domains"], ["a", "b", "c"])
        self.assertEqual(selected["eligible_vocabulary_size"], 6)
        self.assertEqual(selected["eligible_target_a_size"], 1)
        self.assertEqual(selected["eligible_target_b_size"], 1)
        self.assertEqual(selected["weighting"], "absolute_cross_domain_mean_effect")

    def test_scenario_lexicons_require_cross_domain_enrichment(self) -> None:
        cases = [
            ScenarioCase("d1", "safe", 1, "transparent excellence shared", ()),
            ScenarioCase("d1", "wrongdoing", 1, "fraud disclose shared", ()),
            ScenarioCase("d2", "safe", 1, "transparent excellence shared", ()),
            ScenarioCase("d2", "wrongdoing", 1, "fraud disclose shared", ()),
            ScenarioCase("d3", "safe", 1, "transparent unique-safe shared", ()),
            ScenarioCase("d3", "wrongdoing", 1, "fraud unique-bad shared", ()),
        ]
        lexicons, counts = scenario_lexicons(
            cases,
            scenario_a="safe",
            scenario_b="wrongdoing",
            min_domains=2,
            excluded=set(),
        )
        self.assertEqual(lexicons["safe"], {"excellence", "transparent"})
        self.assertEqual(lexicons["wrongdoing"], {"disclose", "fraud"})
        self.assertNotIn("shared", lexicons["safe"])
        self.assertEqual(counts["fraud"], {"safe": 0, "wrongdoing": 3})

    def test_transported_direction_is_exact_and_norm_matched(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        jacobian = torch.tensor([[2.0, 0.0], [1.0, 3.0]])
        target = torch.tensor([1.0, 2.0])
        actual = transported_target(torch, jacobian, target, 7.0)
        expected = jacobian.T @ target
        expected = expected / expected.norm() * 7.0
        torch.testing.assert_close(actual, expected)
        self.assertAlmostEqual(float(actual.norm()), 7.0, places=5)

    def test_followup_contrastive_is_empirical_stop_minus_repeat(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")
        actual = contrastive_response_direction(
            torch,
            stop_samples=[torch.tensor([3.0, 1.0]), torch.tensor([5.0, 1.0])],
            repeat_samples=[torch.tensor([1.0, 1.0]), torch.tensor([1.0, 1.0])],
            scale=6.0,
        )
        torch.testing.assert_close(actual, torch.tensor([6.0, 0.0]))


class InterventionTests(unittest.TestCase):
    def test_system_control_matches_user_token_dose(self) -> None:
        user = (10, 11, 12)
        system = (1, 2, 3, 4, 5)
        self.assertEqual(
            matched_prompt_positions("user_span", user_positions=user, system_positions=system),
            user,
        )
        self.assertEqual(
            matched_prompt_positions(
                "system_matched", user_positions=user, system_positions=system
            ),
            (3, 4, 5),
        )

    def test_prompt_intervention_is_not_reapplied_during_decode(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        block = Block()
        operator = AdditiveOperator(vector=torch.tensor([1.0, 1.0]), alpha=1.0)
        with intervention_hook([block], layer=0, prompt_positions=(1,), operator=operator):
            prompt = torch.zeros(1, 3, 2)
            first = block.hook(None, None, prompt)
            decode = torch.zeros(1, 1, 2)
            second = block.hook(None, None, decode)
        torch.testing.assert_close(first[0, 1], torch.ones(2))
        torch.testing.assert_close(first[0, 0], torch.zeros(2))
        torch.testing.assert_close(second, decode)

    def test_generation_intervention_changes_only_assistant_decisions(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        block = Block()
        operator = AdditiveOperator(vector=torch.tensor([1.0, 2.0]), alpha=2.0)
        with generation_intervention_hook([block], layer=0, operator=operator) as trace:
            prompt = block.hook(None, None, torch.zeros(1, 4, 2))
            decode_1 = block.hook(None, None, torch.zeros(1, 1, 2))
            decode_2 = block.hook(None, None, torch.zeros(1, 1, 2))
        torch.testing.assert_close(prompt[0, :-1], torch.zeros(3, 2))
        torch.testing.assert_close(prompt[0, -1], torch.tensor([2.0, 4.0]))
        torch.testing.assert_close(decode_1[0, -1], torch.tensor([2.0, 4.0]))
        torch.testing.assert_close(decode_2[0, -1], torch.tensor([2.0, 4.0]))
        self.assertEqual(trace["applied_prefill_positions"], 1)
        self.assertEqual(trace["applied_decode_positions"], 2)

    def test_generation_intervention_can_limit_dose_to_first_decision(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        block = Block()
        operator = AdditiveOperator(vector=torch.ones(2), alpha=1.0)
        with generation_intervention_hook(
            [block], layer=0, operator=operator, apply_decode=False
        ) as trace:
            prompt = block.hook(None, None, torch.zeros(1, 3, 2))
            decode = block.hook(None, None, torch.zeros(1, 1, 2))
        torch.testing.assert_close(prompt[0, -1], torch.ones(2))
        torch.testing.assert_close(decode, torch.zeros(1, 1, 2))
        self.assertEqual(trace["applied_prefill_positions"], 1)
        self.assertEqual(trace["applied_decode_positions"], 0)

    def test_cast_gate_controls_official_prefill_and_decode_dose(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_pre_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        blocks = [Block(), Block()]
        operator = AdditiveOperator(vector=torch.tensor([0.0, 1.0]), alpha=2.0)
        with cast_generation_hook(
            blocks,
            condition_layer=0,
            behavior_layer=1,
            condition_direction=torch.tensor([1.0, 0.0]),
            threshold=0.8,
            comparator="greater",
            comparison_mode="mean",
            operator=operator,
        ) as trace:
            prompt = torch.tensor([[[2.0, 1.0], [4.0, 1.0], [3.0, 1.0]]])
            self.assertIsNone(blocks[0].hook(None, (prompt,)))
            steered_prompt = blocks[1].hook(None, (prompt,))[0]
            decode = torch.tensor([[[1.0, 0.0]]])
            self.assertIsNone(blocks[0].hook(None, (decode,)))
            steered_decode = blocks[1].hook(None, (decode,))[0]
        torch.testing.assert_close(
            steered_prompt,
            prompt + torch.tensor([0.0, 2.0]),
        )
        torch.testing.assert_close(steered_decode, torch.tensor([[[1.0, 2.0]]]))
        self.assertTrue(trace["gate_triggered"])
        self.assertEqual(trace["applied_prefill_positions"], 3)
        self.assertEqual(trace["applied_decode_positions"], 1)

    def test_mera_hook_adapts_strength_per_position(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        block = Block()
        with mera_generation_hook(
            [block],
            layer=0,
            probe_vector=torch.tensor([1.0, 0.0]),
            alpha=0.5,
        ) as trace:
            prompt = block.hook(
                None,
                None,
                torch.tensor([[[-2.0, 1.0], [2.0, 1.0], [0.0, 1.0]]]),
            )
            decode = block.hook(None, None, torch.tensor([[[3.0, 1.0]]]))
        torch.testing.assert_close(
            prompt,
            torch.tensor([[[-2.0, 1.0], [0.0, 1.0], [0.0, 1.0]]]),
        )
        torch.testing.assert_close(decode, torch.tensor([[[0.0, 1.0]]]))
        self.assertEqual(trace["eligible_prefill_positions"], 3)
        self.assertEqual(trace["applied_prefill_positions"], 1)
        self.assertEqual(trace["applied_decode_positions"], 1)

    def test_sadi_scales_selected_mlp_coordinates_at_prefill_only(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        modules = [Block(), Block()]
        with sadi_generation_hooks(
            modules,
            units_by_layer={0: (1,), 1: (0, 2)},
            strength=5.0,
        ) as trace:
            prompt = torch.tensor([[[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]])
            first = modules[0].hook(None, None, prompt)
            second = modules[1].hook(None, None, prompt)
            decode = modules[0].hook(None, None, torch.ones(1, 1, 3))
        torch.testing.assert_close(first[0, 0], prompt[0, 0])
        torch.testing.assert_close(first[0, 1], torch.tensor([4.0, 25.0, 6.0]))
        torch.testing.assert_close(second[0, 1], torch.tensor([20.0, 5.0, 30.0]))
        torch.testing.assert_close(decode, torch.ones(1, 1, 3))
        self.assertEqual(trace["applied_prefill_scalars"], 3)
        self.assertEqual(trace["applied_decode_scalars"], 0)

    def test_iti_adds_std_scaled_direction_to_selected_attention_head(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Projection:
            def register_forward_pre_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        projections = [Projection()]
        with iti_generation_hooks(
            projections,
            heads_by_layer={0: ((1, torch.tensor([1.0, 0.0]), 0.5),)},
            num_attention_heads=2,
            head_dim=2,
            alpha=2.0,
        ) as trace:
            prompt = torch.zeros(1, 3, 4)
            steered_prompt = projections[0].hook(None, (prompt,))[0]
            decode = torch.zeros(1, 1, 4)
            steered_decode = projections[0].hook(None, (decode,))[0]
        torch.testing.assert_close(steered_prompt[0, :-1], torch.zeros(2, 4))
        torch.testing.assert_close(
            steered_prompt[0, -1], torch.tensor([0.0, 0.0, 1.0, 0.0])
        )
        torch.testing.assert_close(
            steered_decode[0, -1], torch.tensor([0.0, 0.0, 1.0, 0.0])
        )
        self.assertEqual(trace["applied_prefill_heads"], 1)
        self.assertEqual(trace["applied_decode_heads"], 1)

    def test_austeer_multiplies_selected_attention_scalars_on_all_tokens(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Projection:
            def register_forward_pre_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        projections = [Projection()]
        with austeer_generation_hooks(
            projections,
            units_by_layer={0: ((0, 1.0), (2, -0.5))},
            alpha=2.0,
        ) as trace:
            prompt = torch.ones(1, 2, 3)
            steered = projections[0].hook(None, (prompt,))[0]
        torch.testing.assert_close(
            steered,
            torch.tensor([[[3.0, 1.0, 0.0], [3.0, 1.0, 0.0]]]),
        )
        self.assertEqual(trace["applied_prefill_scalars"], 4)

    def test_loreft_replaces_low_rank_coordinate_at_last_prompt_token(self) -> None:
        try:
            import torch
        except ImportError:
            self.skipTest("torch unavailable")

        class Block:
            def register_forward_hook(self, hook):
                self.hook = hook

                class Handle:
                    def remove(_self):
                        pass

                return Handle()

        blocks = [Block()]
        parameters = {
            0: (
                torch.tensor([[1.0], [0.0]]),
                torch.tensor([[0.0, 1.0]]),
                torch.tensor([0.5]),
            )
        }
        with loreft_generation_hooks(blocks, parameters_by_layer=parameters) as trace:
            prompt = torch.tensor([[[1.0, 2.0], [3.0, 4.0]]])
            steered = blocks[0].hook(None, (), prompt)
        torch.testing.assert_close(steered[0, 0], torch.tensor([1.0, 2.0]))
        torch.testing.assert_close(steered[0, 1], torch.tensor([4.5, 4.0]))
        self.assertEqual(trace["applied_prefill_positions"], 1)

    def test_followup_wrong_position_has_exactly_matched_token_dose(self) -> None:
        document = tuple(range(10, 20))
        result = tuple(range(30, 34))
        control = matched_followup_control_positions(document, result)
        self.assertEqual(control, (16, 17, 18, 19))
        self.assertEqual(len(control), len(result))


class GenerationTests(unittest.TestCase):
    def test_qwen_style_template_trim_does_not_break_message_spans(self) -> None:
        class QwenStyleTokenizer:
            def apply_chat_template(
                self,
                conversation,
                *,
                tokenize,
                add_generation_prompt,
                enable_thinking,
            ):
                self.assert_template_options = (tokenize, add_generation_prompt, enable_thinking)
                system = str(conversation[0]["content"]).strip()
                user = str(conversation[1]["content"]).strip()
                return (
                    f"<|im_start|>system\n{system}<|im_end|>\n"
                    f"<|im_start|>user\n{user}<|im_end|>\n"
                    "<|im_start|>assistant\n<think>\n\n</think>\n\n"
                )

        tokenizer = QwenStyleTokenizer()
        messages = [
            {"role": "system", "content": "  system policy\n"},
            {"role": "user", "content": "document ending in a newline\n"},
        ]
        rendered = _render_chat_text(tokenizer, messages)
        system_span = _rendered_message_span(
            tokenizer, messages, message_index=0, rendered_text=rendered
        )
        user_span = _rendered_message_span(
            tokenizer, messages, message_index=1, rendered_text=rendered
        )
        self.assertEqual(rendered[slice(*system_span)], "system policy")
        self.assertEqual(rendered[slice(*user_span)], "document ending in a newline")
        self.assertLess(system_span[1], user_span[0])

    def test_token_limit_without_eos_is_truncated(self) -> None:
        self.assertEqual(
            completion_status([1, 2, 3], max_new_tokens=3, eos_token_ids={99}),
            (False, True, "length"),
        )

    def test_eos_at_limit_is_complete(self) -> None:
        self.assertEqual(
            completion_status([1, 2, 99], max_new_tokens=3, eos_token_ids={99}),
            (True, False, "eos"),
        )


class MetricTests(unittest.TestCase):
    def sample_records(self, config) -> list[dict]:
        return [
            record(
                config,
                "safe0",
                scenario="safe",
                method="baseline",
                result=behavior("aligned", ["safeTool"]),
            ),
            record(
                config,
                "bad0",
                scenario="wrongdoing",
                method="baseline",
                result=behavior("misaligned", ["badTool"]),
            ),
            record(
                config,
                "jlens",
                scenario="safe",
                target="wrongdoing",
                method="jlens",
                result=behavior("misaligned", ["badTool"]),
                thought_margin=2.0,
            ),
            record(
                config,
                "random",
                scenario="safe",
                target="wrongdoing",
                method="random",
                random_seed=11,
                result=behavior("aligned", ["safeTool"]),
                thought_margin=0.0,
            ),
        ]

    def test_random_subtracted_paired_effect(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        rows = paired_trial_metrics(config, self.sample_records(config))
        jlens = next(row for row in rows if row["method"] == "jlens")
        self.assertEqual(jlens["target_signature_effect"], 1)
        self.assertEqual(jlens["random_target_signature_effect_mean"], 0)
        self.assertEqual(jlens["causal_delta_signature_vs_random"], 1)
        self.assertEqual(jlens["causal_delta_thought_vs_random"], 2)
        self.assertEqual(jlens["causal_delta_behavior_vs_random"], 1)
        self.assertEqual(jlens["joint_causal_success"], 1)
        self.assertEqual(jlens["safe_degradation"], 1)

    def test_same_baseline_profile_is_not_a_flip_success(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        records = self.sample_records(config)
        records[1]["behavior"] = behavior("aligned", ["safeTool"])
        rows = paired_trial_metrics(config, records)
        jlens = next(row for row in rows if row["method"] == "jlens")
        self.assertEqual(jlens["baseline_discriminative"], 0)
        self.assertIsNone(jlens["behavior_flip_success"])
        self.assertIsNone(jlens["behavior_target_progress"])

    def test_invalid_treatment_is_corruption_not_success(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        records = self.sample_records(config)
        records[2]["behavior"] = behavior("parse_error", [], parse_error=True)
        records[2]["valid_for_pairing"] = False
        rows = paired_trial_metrics(config, records)
        jlens = next(row for row in rows if row["method"] == "jlens")
        self.assertEqual(jlens["steer_target_class_success"], 0)
        self.assertEqual(jlens["steer_target_signature_success"], 0)
        self.assertEqual(jlens["invalid_output"], 1)
        self.assertEqual(jlens["corruption_increase"], 1)
        self.assertEqual(jlens["thought_effect"], 0)

    def test_invalid_baseline_is_rejected(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        records = self.sample_records(config)
        records[0]["behavior"] = behavior("truncated", [], truncated=True)
        records[0]["truncated"] = True
        records[0]["valid_for_pairing"] = False
        with self.assertRaisesRegex(ValueError, "alpha=0 baselines"):
            paired_trial_metrics(config, records)

    def test_analysis_writes_trial_and_summary_tables(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            with config.records_path.open("w", encoding="utf-8") as handle:
                for item in self.sample_records(config):
                    handle.write(json.dumps(item) + "\n")
            result = analyze_runs(config, bootstrap_samples=20)
            self.assertEqual(result["records"], 4)
            self.assertTrue((config.output_dir / "trial_metrics.csv").is_file())
            self.assertTrue((config.output_dir / "summary.csv").is_file())
            self.assertTrue((config.output_dir / "thought_trajectories.csv").is_file())
            self.assertTrue((config.output_dir / "behavior_profiles.csv").is_file())

    def test_followup_analysis_subtracts_random_on_source_matched_cases(self) -> None:
        config = load_followup_config(ROOT / "configs" / "followup_smoke.json")

        def followup_record(method: str, decision: str, thought: float) -> dict:
            baseline = method == "baseline"
            return {
                "run_id": method,
                "run_fingerprint": config.run_fingerprint,
                "domain": "nuclear-energy",
                "document": 1,
                "scenario_type": "safe",
                "condition": "tamely-with-reasoning",
                "direction": "none" if baseline else "repeat_to_stop",
                "method": method,
                "vector_layer": None if baseline else 20,
                "applied_layer": None if baseline else 20,
                "alpha": 0.0 if baseline else 1.0,
                "site": "baseline" if baseline else "tool_result",
                "followup": {"decision": decision, "valid": True},
                "thought_trace": {"pre_response_last": thought},
            }

        records = [
            followup_record("baseline", "repeat", 0.0),
            followup_record("random", "repeat", 0.0),
            followup_record("jlens", "stop", 2.0),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            with config.records_path.open("w", encoding="utf-8") as handle:
                for item in records:
                    item["run_fingerprint"] = config.run_fingerprint
                    handle.write(json.dumps(item) + "\n")
            analyze_followup(config)
            with (config.output_dir / "followup_trial_metrics.csv").open(
                newline="", encoding="utf-8"
            ) as handle:
                rows = list(csv.DictReader(handle))
            jlens = next(row for row in rows if row["method"] == "jlens")
            self.assertEqual(float(jlens["causal_delta_behavior_vs_random"]), 1.0)
            self.assertEqual(float(jlens["causal_delta_thought_vs_random"]), 2.0)
            self.assertEqual(int(jlens["joint_causal_success"]), 1)


if __name__ == "__main__":
    unittest.main()
