from __future__ import annotations

import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np

from jlens_causal import benchmark
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
    intervention_hook,
    matched_prompt_positions,
)
from jlens_causal.metrics import analyze_runs, paired_trial_metrics
from jlens_causal.modeling import _render_chat_text, _rendered_message_span, completion_status
from jlens_causal.toolalign import ScenarioCase, classify_behavior, load_cases, parse_tool_calls

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


class DirectionTests(unittest.TestCase):
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
