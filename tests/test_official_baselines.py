"""Official-baseline adapters: manifest, rendering, artifacts, and (on a host with
the fetched upstreams and network access) an end-to-end fit/steer run on a tiny
random Qwen3.5 model for every method."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from jlens_causal.failure_steering import (
    compile_failure_steering_matrix,
    load_failure_steering_manifest,
)
from jlens_causal.official import upstream
from jlens_causal.official.artifact import METHODS
from jlens_causal.official.data import (
    RenderedConditionPair,
    RenderSettings,
    action_text,
    render_pair,
)

ROOT = Path(__file__).resolve().parents[1]
OFFICIAL_CONFIG = ROOT / "configs" / "taubench_airline_official_baselines_qwen35_4b.json"
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "cancel_reservation",
            "description": "Cancel a reservation.",
            "parameters": {
                "type": "object",
                "properties": {"reservation_id": {"type": "string"}},
                "required": ["reservation_id"],
            },
        },
    }
]


def _pair(index: int, split: str) -> dict:
    good, bad = f"RES{index}A", f"RES{index}Z"
    return {
        "schema_version": "agent-failure-repair-pair-v1",
        "pair_id": f"pair-{index}",
        "task_id": str(index),
        "split": split,
        "failure_category": "tool_call_error",
        "context_messages": [
            {"role": "system", "content": "You are an airline agent. Follow the policy."},
            {"role": "user", "content": f"Please cancel reservation {good}; my name is Kim {index}."},
        ],
        "positive_repaired_message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "x", "name": "cancel_reservation", "arguments": {"reservation_id": good}}],
        },
        "negative_failed_message": {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "y", "name": "cancel_reservation", "arguments": {"reservation_id": bad}}],
        },
    }


class _ToyTemplate:
    """Minimal chat template with Qwen-style markers."""

    def apply_chat_template(self, messages, tokenize=False, add_generation_prompt=False, tools=None, **kwargs):
        text = "".join(
            f"<|im_start|>{m['role']}\n{m.get('content') or ''}"
            + "".join(
                f"<tool_call>{c['function']['name']} {json.dumps(c['function']['arguments'])}</tool_call>"
                for c in m.get("tool_calls") or []
            )
            + "<|im_end|>\n"
            for m in messages
        )
        return text + ("<|im_start|>assistant\n" if add_generation_prompt else "")


def test_official_manifest_compiles_with_official_dispatch():
    manifest = load_failure_steering_manifest(OFFICIAL_CONFIG)
    assert set(manifest.enabled_methods) == set(METHODS)
    matrix = compile_failure_steering_matrix(manifest)
    by_method: dict[str, list[dict]] = {}
    for condition in matrix["conditions"]:
        by_method.setdefault(condition["method"], []).append(condition)
    for method in METHODS:
        interventions = [c["agent_llm_args"]["jlens_intervention"] for c in by_method[method]]
        assert all(item["implementation"] == "official" for item in interventions)
    # MERA's strength is an abstention threshold: no sign-flipped control.
    assert not [c for c in by_method["mera"] if c["control_type"] == "negative_direction"]
    assert [c for c in by_method["sadi"] if c["control_type"] == "zero_dose"]
    # The CAA wrong-layer control must add a fitted vector (vector_layer) at layer 4.
    fitted = set(json.loads(OFFICIAL_CONFIG.read_text())["official_fit"]["caa"]["layers"])
    for condition in by_method["caa"]:
        intervention = condition["agent_llm_args"]["jlens_intervention"]
        assert intervention["official_options"]["vector_layer"] in fitted
    wrong = [c for c in by_method["caa"] if c["control_type"] == "wrong_layer"]
    assert wrong and wrong[0]["agent_llm_args"]["jlens_intervention"]["layer"] == 4


def test_render_pair_isolates_the_two_actions():
    settings = RenderSettings(tools=[], chat_template_kwargs={})
    rendered = render_pair(_ToyTemplate(), _pair(1, "train"), settings)
    assert rendered.prompt.endswith("<|im_start|>assistant\n")
    assert rendered.positive.startswith("<tool_call>") and rendered.positive != rendered.negative
    assert "<|im_end|>" not in rendered.positive
    assert action_text(rendered.positive_message) == 'cancel_reservation({"reservation_id": "RES1A"})'


def test_upstream_registry_pins_full_commits():
    for method in METHODS:
        source = upstream.UPSTREAMS[method]
        assert len(source.commit) == 40 and source.repository.count("/") == 1


def test_artifact_round_trip_detects_tampering(tmp_path):
    torch = pytest.importorskip("torch")
    from jlens_causal.official.artifact import build_artifact, load_artifact, save_artifact

    artifact = build_artifact(
        method="caa", model_id="m", model_revision="r" * 40, upstream={"repository": "x/y"},
        fit={"layers": [1]}, deviations=["d"], state={"vectors": {"1": torch.ones(3)}},
    )
    path = save_artifact(torch, artifact, tmp_path / "caa.pt")
    loaded = load_artifact(torch, path, expected_model_id="m", expected_method="caa")
    assert torch.equal(loaded["state"]["vectors"]["1"], torch.ones(3))
    assert json.loads(path.with_suffix(".pt.json").read_text())["method"] == "caa"
    loaded["fit"]["layers"] = [2]
    torch.save(loaded, tmp_path / "tampered.pt")
    with pytest.raises(ValueError):
        load_artifact(torch, tmp_path / "tampered.pt")


# --------------------------------------------------------------------------- end to end


def _upstreams_ready() -> bool:
    try:
        for method in METHODS:
            upstream.checkout(method)
    except (FileNotFoundError, RuntimeError):
        return False
    return True


@pytest.fixture(scope="module")
def tiny_runtime():
    if not _upstreams_ready():
        pytest.skip("run scripts/fetch_official_upstreams.sh first")
    torch = pytest.importorskip("torch")
    transformers = pytest.importorskip("transformers")
    from jlens_causal.modeling import ModelRuntime

    try:
        tokenizer = transformers.AutoTokenizer.from_pretrained(
            "Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
        )
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"Qwen3.5 tokenizer unavailable: {error}")
    config = transformers.Qwen3_5TextConfig(
        vocab_size=max(len(tokenizer), tokenizer.vocab_size),
        hidden_size=64,
        intermediate_size=512,
        num_hidden_layers=4,
        layer_types=["linear_attention", "linear_attention", "linear_attention", "full_attention"],
        num_attention_heads=32,
        num_key_value_heads=4,
        head_dim=8,
        linear_num_key_heads=2,
        linear_num_value_heads=4,
        linear_key_head_dim=16,
        linear_value_head_dim=16,
        linear_conv_kernel_dim=4,
    )
    torch.manual_seed(0)
    model = transformers.Qwen3_5ForCausalLM(config).eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return ModelRuntime(torch=torch, tokenizer=tokenizer, hf_model=model, lens_model=None, lens=None,
                        device=device)


@pytest.fixture(scope="module")
def tiny_pairs(tiny_runtime):
    settings = RenderSettings(tools=TOOLS, chat_template_kwargs={"enable_thinking": False})
    pairs = [render_pair(tiny_runtime.tokenizer, _pair(i, "train"), settings) for i in range(6)]
    pairs += [render_pair(tiny_runtime.tokenizer, _pair(i, "validation"), settings) for i in range(6, 8)]
    return settings, pairs


def _generate(runtime, method, path, *, strength, layer=1, options=None):
    from jlens_causal.official.runtime import official_steering

    prompt = runtime.tokenizer.apply_chat_template(
        [{"role": "user", "content": "Cancel reservation RES9A."}],
        tools=TOOLS, add_generation_prompt=True, tokenize=False, enable_thinking=False,
    )
    ids = runtime.tokenizer(prompt, add_special_tokens=False)["input_ids"]
    with official_steering(
        model=runtime.hf_model, tokenizer=runtime.tokenizer, method=method, artifact_path=path,
        model_id="tiny", strength=strength, layer=layer, prompt_ids=ids, options=options or {},
    ) as trace:
        runtime.hf_model.generate(
            input_ids=runtime.torch.tensor([ids], device=runtime.device),
            max_new_tokens=3, do_sample=False,
        )
    return trace


@pytest.mark.parametrize("method", ["caa", "mera", "sadi", "austeer", "iti"])
def test_end_to_end_fit_and_steer(method, tiny_runtime, tiny_pairs, tmp_path):
    from jlens_causal.official import austeer, caa, iti, mera, sadi

    settings, pairs = tiny_pairs
    common = {"output_path": tmp_path / f"{method}.pt", "model_id": "tiny", "model_revision": "0" * 40}
    if method == "caa":
        path = caa.fit(tiny_runtime, pairs, settings=settings, layers=[1, 2], behavior="tool_call_error", **common)
        trace = _generate(tiny_runtime, method, path, strength=1.0, layer=1)
        # wrong-layer control: the layer-1 vector injected at an unfitted layer.
        wrong = _generate(tiny_runtime, method, path, strength=1.0, layer=3, options={"vector_layer": 1})
        assert wrong["hook_layer"] == 3 and wrong["vector_layer"] == 1 and wrong["applied_edits"] > 0
    elif method == "mera":
        path = mera.fit(tiny_runtime, pairs, seed=0, **common)
        trace = _generate(tiny_runtime, method, path, strength=0.01)
        assert trace["seen_positions"] > 0
        return
    elif method == "sadi":
        path = sadi.fit(tiny_runtime, pairs, max_tokens=None, **common)
        trace = _generate(tiny_runtime, method, path, strength=5.0, options={"top_k": 3})
    elif method == "austeer":
        path = austeer.fit(tiny_runtime, pairs, **common)
        trace = _generate(tiny_runtime, method, path, strength=10.0, options={"top_k": 4})
        ffn = _generate(tiny_runtime, method, path, strength=10.0,
                        options={"top_k": 4, "applied_module": "ffn"})
        assert ffn["applied_module"] == "ffn" and ffn["applied_edits"] > 0
    else:
        path = iti.fit(tiny_runtime, pairs, num_heads_to_intervene=2, seed=0, val_ratio=0.2, **common)
        if not tiny_runtime.torch.cuda.is_available():
            pytest.skip("ITI_Intervener moves its direction to CUDA")
        trace = _generate(tiny_runtime, method, path, strength=5.0)
    assert trace["applied_edits"] > 0
    assert trace["implementation"] == "official"


def test_end_to_end_cast(tiny_runtime, tiny_pairs, tmp_path):
    from jlens_causal.official import cast

    _settings, pairs = tiny_pairs
    conditions = [
        RenderedConditionPair(
            pair_id=f"c{i}", split=split, failure_category="tool_call_error",
            positive_prompt=pairs[i].prompt.replace("Kim", "Kim (tool error: reservation not found)"),
            negative_prompt=pairs[i].prompt,
        )
        for i, split in enumerate(["train", "train", "train", "validation", "validation", "validation"])
    ]
    path = cast.fit(
        tiny_runtime, pairs, conditions,
        behavior_layers=[1, 2], condition_layer_range=(1, 3), max_response_tokens=8,
        threshold_range=(0.0, 0.1), threshold_step=0.001,
        output_path=tmp_path / "cast.pt", model_id="tiny", model_revision="0" * 40,
    )
    trace = _generate(tiny_runtime, "cast", path, strength=1.0, options={"ungated": True})
    assert trace["applied_edits"] > 0
    gated = _generate(tiny_runtime, "cast", path, strength=1.0)
    assert gated["condition_met"] in {True, False}
