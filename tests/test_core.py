from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from jlens_causal.config import load_config
from jlens_causal.experiment import iter_trial_specs
from jlens_causal.metrics import analyze_runs, paired_trial_metrics
from jlens_causal.toolalign import load_cases, parse_tool_calls


ROOT = Path(__file__).parents[1]


def behavior(kind: str, signature: list[str]) -> dict:
    return {
        "behavior_class": kind,
        "tool_signature": signature,
        "parse_error": False,
    }


def record(
    run_id: str,
    *,
    scenario: str,
    method: str,
    result: dict,
    target: str | None = None,
    random_seed: int | None = None,
) -> dict:
    return {
        "schema_version": "jlens-causal-record-v1",
        "run_id": run_id,
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

    def test_toolalign_selection_and_dynamic_dataclasses(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        _, cases = load_cases(
            config.toolalign_root,
            domains=["financial"],
            documents=[1],
            scenario_types=["safe", "wrongdoing"],
        )
        self.assertEqual(len(cases), 2)


class ParserTests(unittest.TestCase):
    def test_all_supported_tool_call_encodings(self) -> None:
        custom = '<tool_call><tool_name>x</tool_name><arguments>{"a": 1}</arguments></tool_call>'
        native = "<tool_call><function=y><parameter=b>2</parameter></function></tool_call>"
        json_call = '<tool_call>{"name":"z","arguments":{"c":3}}</tool_call>'
        calls = parse_tool_calls("\n".join([custom, native, json_call]))
        self.assertEqual([call.name for call in calls], ["x", "y", "z"])
        self.assertEqual(calls[1].arguments, {"b": 2})


class MetricTests(unittest.TestCase):
    def sample_records(self) -> list[dict]:
        return [
            record("safe0", scenario="safe", method="baseline", result=behavior("aligned", ["safeTool"])),
            record(
                "bad0",
                scenario="wrongdoing",
                method="baseline",
                result=behavior("misaligned", ["badTool"]),
            ),
            record(
                "jlens",
                scenario="safe",
                target="wrongdoing",
                method="jlens",
                result=behavior("misaligned", ["badTool"]),
            ),
            record(
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
        rows = paired_trial_metrics(config, self.sample_records())
        jlens = next(row for row in rows if row["method"] == "jlens")
        self.assertEqual(jlens["target_signature_effect"], 1)
        self.assertEqual(jlens["random_target_signature_effect_mean"], 0)
        self.assertEqual(jlens["causal_delta_signature_vs_random"], 1)
        self.assertEqual(jlens["safe_degradation"], 1)

    def test_analysis_writes_trial_and_summary_tables(self) -> None:
        config = load_config(ROOT / "configs" / "smoke.json")
        with tempfile.TemporaryDirectory() as temporary:
            config = replace(config, output_dir=Path(temporary))
            with config.records_path.open("w", encoding="utf-8") as handle:
                for item in self.sample_records():
                    handle.write(json.dumps(item) + "\n")
            result = analyze_runs(config, bootstrap_samples=20)
            self.assertEqual(result["records"], 4)
            self.assertTrue((config.output_dir / "trial_metrics.csv").is_file())
            self.assertTrue((config.output_dir / "summary.csv").is_file())


if __name__ == "__main__":
    unittest.main()
