from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jlens_causal import benchmark
from jlens_causal.config import load_config
from jlens_causal.experiment import (
    GENERATED_ARTIFACTS,
    iter_trial_specs,
    reset_output_artifacts,
    trial_run_id,
    validate_output_compatibility,
)
from jlens_causal.metrics import analyze_runs, paired_trial_metrics
from jlens_causal.modeling import completion_status
from jlens_causal.toolalign import load_cases, parse_tool_calls

ROOT = Path(__file__).parents[1]


def behavior(
    kind: str,
    signature: list[str],
    *,
    parse_error: bool = False,
    truncated: bool = False,
) -> dict:
    return {
        "behavior_class": kind,
        "tool_signature": signature,
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
) -> dict:
    valid = bool(result["valid_for_pairing"])
    return {
        "schema_version": "jlens-causal-record-v2",
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
        "position_policy": None if method == "baseline" else "all",
        "site": "baseline" if method == "baseline" else "candidate",
        "random_seed": random_seed,
        "truncated": bool(result["truncated"]),
        "valid_for_pairing": valid,
        "output_text": run_id,
        "behavior": result,
    }


class ConfigTests(unittest.TestCase):
    def test_smoke_count_matches_grid(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        self.assertEqual(config.estimated_generations()["total"], 18)
        specs = list(iter_trial_specs(config))
        self.assertEqual(len(specs), 18)
        self.assertEqual(sum(spec.method == "baseline" for spec in specs), 2)
        self.assertEqual(config.generation["max_new_tokens"], 4096)
        full = load_config(ROOT / "configs" / "qwen35_toolalign_pilot.json")
        self.assertEqual(full.generation["max_new_tokens"], 4096)

    def test_generation_changes_run_fingerprint_and_ids(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        changed_raw = json.loads(json.dumps(config.raw))
        changed_raw["generation"]["max_new_tokens"] = 2048
        changed = replace(config, raw=changed_raw)
        spec = next(iter(iter_trial_specs(config)))
        self.assertNotEqual(config.run_fingerprint, changed.run_fingerprint)
        self.assertNotEqual(trial_run_id(config, spec), trial_run_id(changed, spec))

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


class GenerationTests(unittest.TestCase):
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
            ),
            record(
                config,
                "random",
                scenario="safe",
                target="wrongdoing",
                method="random",
                random_seed=11,
                result=behavior("aligned", ["safeTool"]),
            ),
        ]

    def test_random_subtracted_paired_effect(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        rows = paired_trial_metrics(config, self.sample_records(config))
        jlens = next(row for row in rows if row["method"] == "jlens")
        self.assertEqual(jlens["target_signature_effect"], 1)
        self.assertEqual(jlens["random_target_signature_effect_mean"], 0)
        self.assertEqual(jlens["causal_delta_signature_vs_random"], 1)
        self.assertEqual(jlens["safe_degradation"], 1)

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


if __name__ == "__main__":
    unittest.main()
