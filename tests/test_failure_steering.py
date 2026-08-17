import hashlib
import json

import pytest

from jlens_causal.failure_steering import (
    CORE_METHODS,
    FAILURE_MATRIX_SCHEMA,
    compile_failure_steering_matrix,
    load_failure_steering_manifest,
)


def _manifest():
    methods = {}
    for method in CORE_METHODS:
        intervention = {
            "kind": "steer",
            "method": method,
            "layer": 20,
            "vector_path": f"/remote/artifacts/{method}.pt",
            "apply_prefill_decision": True,
            "apply_decode": True,
        }
        methods[method] = {
            "intervention": intervention,
            "strengths": [0.5],
            "wrong_layer": 4,
        }
    return {
        "schema_version": "agent-failure-steering-v1",
        "benchmark": "taubench-airline",
        "model": {"model_id": "org/model", "model_revision": "a" * 40},
        "execution": {
            "mode": "remote",
            "endpoint_env": "JLENS_REMOTE_ENDPOINT",
            "token_env": "JLENS_REMOTE_TOKEN",
        },
        "splits": {
            "train_task_ids": ["0", "1"],
            "validation_task_ids": ["2"],
            "evaluation_task_ids": ["3", "4"],
        },
        "generation": {"seed": 300, "max_new_tokens": 512, "do_sample": False},
        "failure_modes": {
            "retry_without_state_change": {
                "boundary": "after_tool_error",
                "methods": methods,
            },
            "completion_not_released": {
                "boundary": "after_successful_tool_result",
                "methods": {"caa": methods["caa"]},
            },
        },
    }


def _write(tmp_path, value):
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def test_manifest_compiles_all_core_methods_and_runtime_boundaries(tmp_path):
    manifest = load_failure_steering_manifest(_write(tmp_path, _manifest()))
    matrix = compile_failure_steering_matrix(manifest)

    assert matrix["schema_version"] == FAILURE_MATRIX_SCHEMA
    assert matrix["compiler_version"] == "failure-steering-compiler-v2"
    assert len(matrix["matrix_fingerprint"]) == 64
    targeted = [item for item in matrix["conditions"] if item["control_type"] == "targeted"]
    assert set(item["method"] for item in targeted) == set(CORE_METHODS)
    assert all(item["agent_llm_args"]["jlens_require_remote"] for item in targeted)
    assert all(
        "turn_indices" not in item["agent_llm_args"]["jlens_intervention"]
        for item in matrix["conditions"]
        if item["method"] != "none"
    )
    retry = next(
        item
        for item in targeted
        if item["failure_category"] == "retry_without_state_change" and item["method"] == "caa"
    )
    assert retry["agent_llm_args"]["jlens_intervention"]["boundaries"] == ["after_tool_error"]
    controls = {item["control_type"] for item in matrix["conditions"] if item["method"] == "caa"}
    assert {"no_steer", "negative_direction", "wrong_category", "wrong_layer"} - {
        "no_steer"
    } <= controls


def test_manifest_rejects_split_leakage_and_fixed_turns(tmp_path):
    value = _manifest()
    value["splits"]["evaluation_task_ids"] = ["1"]
    with pytest.raises(ValueError, match="must be disjoint"):
        load_failure_steering_manifest(_write(tmp_path, value))

    value = _manifest()
    value["failure_modes"]["retry_without_state_change"]["methods"]["caa"]["intervention"][
        "turn_indices"
    ] = [9]
    with pytest.raises(ValueError, match="may not hard-code"):
        load_failure_steering_manifest(_write(tmp_path, value))


def test_tool_schema_fingerprint_is_independent_of_line_endings(tmp_path):
    schema = [
        {
            "type": "function",
            "function": {
                "name": "lookup",
                "parameters": {"type": "object", "properties": {"id": {"type": "string"}}},
            },
        }
    ]
    canonical = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    expected = hashlib.sha256(canonical.encode()).hexdigest()
    schema_path = tmp_path / "tools.json"
    manifest = _manifest()
    manifest["tool_schema"] = {
        "domain": "airline",
        "path": schema_path.name,
        "sha256": expected,
    }
    manifest_path = _write(tmp_path, manifest)

    pretty = json.dumps(schema, ensure_ascii=False, indent=2)
    schema_path.write_bytes((pretty.replace("\n", "\r\n") + "\r\n").encode())
    load_failure_steering_manifest(manifest_path)

    schema_path.write_text(pretty + "\n", encoding="utf-8", newline="\n")
    load_failure_steering_manifest(manifest_path)

    schema[0]["function"]["name"] = "changed"
    schema_path.write_text(json.dumps(schema), encoding="utf-8")
    with pytest.raises(ValueError, match="sha256 does not match"):
        load_failure_steering_manifest(manifest_path)
