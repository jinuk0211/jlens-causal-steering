import importlib.util
import json
from pathlib import Path

import pytest


def _load_script():
    path = Path(__file__).parents[1] / "scripts" / "summarize_toolalign_core7.py"
    spec = importlib.util.spec_from_file_location("summarize_toolalign_core7", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_core7_summary_requires_both_roles_and_flattens_paired_rows(tmp_path):
    script = _load_script()
    configs = tmp_path / "configs"
    configs.mkdir()
    for method in script.METHODS:
        output = tmp_path / method
        (configs / f"toolalign_{method}_llama8b.json").write_text(
            json.dumps(
                {
                    "output_dir": str(output),
                    "data": {
                        "evaluation_domains": ["domain"],
                        "evaluation_documents": [1],
                        "evaluation_scenario_types": ["wrongdoing"],
                    },
                }
            ),
            encoding="utf-8",
        )
        for role in script.ROLES:
            analysis = output / "analysis" / f"{role}.json"
            analysis.parent.mkdir(parents=True, exist_ok=True)
            analysis.write_text(
                json.dumps(
                    {
                        "config_fingerprint": f"{method}-fingerprint",
                        "paired_transitions": {
                            "schema_version": "toolalign-paired-transitions-v1",
                            "model_role": role,
                            "role_target": (
                                "aligned_to_misaligned"
                                if role == "aligned"
                                else "misaligned_to_aligned"
                            ),
                            "baseline_cases": 1,
                            "paired_trials": 1,
                            "summary": [
                                {
                                    "method": method,
                                    "scenario_type": "wrongdoing",
                                    "parameters": {"alpha": 1.0},
                                    "role_target_flip_rate": 0.5,
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

    result = script.collect_core7(configs)

    assert result["complete"]
    assert len(result["sources"]) == 14
    assert len(result["rows"]) == 14
    assert {row["model_role"] for row in result["rows"]} == {"aligned", "abliterated"}

    (tmp_path / "caa" / "analysis" / "aligned.json").unlink()
    with pytest.raises(FileNotFoundError, match="missing 1"):
        script.collect_core7(configs)
