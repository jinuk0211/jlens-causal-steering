"""Fit the official CAA vector (nrimsky/CAA code) on the vocab-trigger train failures.

Data: every train-split turn of the airline telemetry whose tool call is a bad
write (``label_calls``).  The prompt is the exact logged ``rendered_context``.
The A/B choice contrasts the logged failed action (negative) with a repaired
action (positive):

* the task's gold call, when the gold actions contain the same (non-free-text)
  tool: the failure is wrong arguments, and the gold arguments repair it;
* otherwise (an unexpected transfer or a write the task never makes) a fixed
  verify-first reply, the behaviour the vocabulary trigger's safe side reads.

The vector itself comes from ``generate_save_vectors_for_behavior`` unchanged
(:func:`jlens_causal.official.caa.fit_items`).  The sidecar also records the
multiplier that matches the J-lens edit size: ``alpha * median ||h_L|| / ||v_L||``
over the train decision points, so both methods move the residual by the same
fraction of its norm.
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
from pathlib import Path
from types import SimpleNamespace

import torch

from jlens_causal.official import caa
from jlens_causal.vocab_trigger import FREE_TEXT_TOOLS, is_write, label_calls

VERIFY_FIRST = (
    "Before I make any change, let me check this request against the policy and "
    "confirm the details with you."
)
REV = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def visible_text(generated: str) -> str:
    text = re.sub(r"<tool_call>.*?(</tool_call>|$)", " ", generated, flags=re.S)
    text = re.sub(r"<\|im_end\|>|<think>|</think>", " ", text)
    return text.strip()


def repaired(bad_calls: list[dict], gold: list[dict]) -> tuple[dict, str]:
    for call in bad_calls:
        if call["name"] in FREE_TEXT_TOOLS:
            continue
        same = [g for g in gold if g["name"] == call["name"]]
        if same:
            # The gold action that shares the most argument values with the failure.
            best = max(same, key=lambda g: sum((g.get("arguments") or {}).get(k) == v
                                               for k, v in call["arguments"].items()))
            return ({"content": None,
                     "tool_calls": [{"name": best["name"], "arguments": best.get("arguments") or {}}]},
                    "gold_arguments")
    return {"content": VERIFY_FIRST, "tool_calls": []}, "verify_first"


def load_examples(telemetry_root: Path, tasks: dict, split: str) -> list[dict]:
    examples = []
    for path in sorted((telemetry_root / split).glob("*.jsonl")):
        for line in open(path, encoding="utf-8"):
            record = json.loads(line)
            gold = tasks[str(record["task_id"])]["evaluation_criteria"]["actions"]
            calls = [{"name": c["name"], "arguments": c["arguments"]} for c in record["tool_calls"]]
            if label_calls(calls, gold) != "bad_write":
                continue
            positive, source = repaired([c for c in calls if is_write(c["name"])], gold)
            negative = {"content": visible_text(record["generated_text"]) or None, "tool_calls": calls}
            examples.append({
                "record_id": record["record_id"], "task_id": str(record["task_id"]),
                "prompt": record["rendered_context"], "input_ids": record["input_ids"],
                "positive": positive, "negative": negative, "positive_source": source,
            })
    return examples


def load_model(model_dir: Path, *, stream: bool, dtype: torch.dtype, device: str):
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    if stream:
        from jlens_causal.hf_stream import stream_qwen35_text_model

        model = stream_qwen35_text_model("Qwen/Qwen3.5-4B", REV, model_dir, device=device, dtype=dtype)
    else:
        config = Qwen3_5Config.from_pretrained(model_dir).text_config
        model = Qwen3_5ForCausalLM.from_pretrained(
            model_dir, config=config, dtype=dtype,
            key_mapping={r"^model\.language_model\.": "model."},
        ).to(device).eval()
    return model, tokenizer


def decision_norms(model, examples: list[dict], layers: list[int]) -> dict[int, list[float]]:
    """||h_L|| at each train decision point (last prompt token)."""
    blocks = model.model.layers
    norms: dict[int, list[float]] = {layer: [] for layer in layers}
    captured: dict[int, float] = {}

    def hook(layer: int):
        def record(module, args, output):  # noqa: ANN001, ARG001
            hidden = output[0] if isinstance(output, tuple) else output
            captured[layer] = float(hidden[0, -1].float().norm())
        return record

    handles = [blocks[layer].register_forward_hook(hook(layer)) for layer in layers]
    try:
        with torch.no_grad():
            for example in examples:
                ids = torch.tensor([example["input_ids"]], device=model.device)
                model(input_ids=ids, use_cache=False, logits_to_keep=1)
                for layer in layers:
                    norms[layer].append(captured[layer])
    finally:
        for handle in handles:
            handle.remove()
    return norms


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("telemetry_root", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--stream-weights", action="store_true")
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--layers", type=int, nargs="+", default=[13, 20])
    parser.add_argument("--match-alpha", type=float, default=0.8,
                        help="J-lens dose (fraction of ||h||) the matched CAA multiplier reproduces")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    examples = load_examples(args.telemetry_root, tasks, "train")
    sources = {s: sum(e["positive_source"] == s for e in examples) for s in ("gold_arguments", "verify_first")}
    print(f"train bad-write examples: {len(examples)} {sources}", flush=True)
    model, tokenizer = load_model(args.model_dir, stream=args.stream_weights,
                                  dtype=getattr(torch, args.dtype), device="cuda")
    runtime = SimpleNamespace(torch=torch, tokenizer=tokenizer, hf_model=model)
    items = caa.build_ab_items_from_rendered(examples)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    caa.fit_items(
        runtime, items, layers=args.layers, behavior="vocab_trigger_bad_write",
        output_path=args.output, model_id="Qwen/Qwen3.5-4B", model_revision=REV,
        data={"split": "train", "record_ids": [e["record_id"] for e in examples],
              "task_ids": sorted({e["task_id"] for e in examples}, key=int),
              "count": len(examples), "positive_sources": sources},
        extra_deviations=(
            "A/B prompts are the exact logged rendered_context of each train bad-write turn, "
            "with the choice question inserted as a user turn before the generation header.",
            "Positive actions: the task's gold call when it shares the failed tool (wrong "
            "arguments), otherwise a fixed verify-first reply; negatives are the logged actions.",
        ),
    )
    artifact = torch.load(args.output, map_location="cpu", weights_only=False)
    norms = decision_norms(model, examples, args.layers)
    matched = {}
    for layer in args.layers:
        vector_norm = float(artifact["state"]["vectors"][str(layer)].norm())
        median = statistics.median(norms[layer])
        matched[str(layer)] = {
            "vector_norm": vector_norm,
            "median_decision_norm": median,
            "matched_multiplier": args.match_alpha * median / vector_norm,
        }
    sidecar = {"match_alpha": args.match_alpha, "layers": matched, "examples": len(examples),
               "positive_sources": sources}
    args.output.with_suffix(".dose.json").write_text(json.dumps(sidecar, indent=2), encoding="utf-8")
    print(json.dumps(sidecar, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
