"""Prefix replay of Stage-Anchor on tau2 airline turns (GPU host).

For each selected agent turn the exact logged ``input_ids`` are re-fed to
Qwen3.5-4B and only that turn is regenerated (greedy), once per condition:

* ``off``      score every gated position, never edit (detection + calibration)
* ``anchor``   edit contested positions toward the mid-stage winner
* ``reverse``  same positions and dose, toward the commit-stage winner
* ``random``   same positions and dose, random direction

The prompt minus its last token is prefilled once and every condition continues
from a copy of that cache.  Rows record the tool calls, their label against the
task's gold actions, and a summary of the contested positions (decoded winners,
scores, doses).

Calibrate first::

    python scripts/stage_anchor_replay.py sel.jsonl tasks.json --model-dir M --lens LENS \
        --modes off --output off.jsonl
    # threshold = 95th percentile of contested scores on good_write turns

then run the conditions with ``--threshold`` set.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import time
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from vocab_trigger_replay import load_bf16_storage_fp32_compute, load_record, parse_tool_calls  # noqa: E402

from jlens_causal.stage_anchor import (  # noqa: E402
    MODES,
    StageAnchorSpec,
    content_vocab_from_tokenizer,
    stage_anchor_steering,
    summarise_events,
)
from jlens_causal.vocab_trigger import ReadoutHead, label_calls  # noqa: E402


def load_model(args: argparse.Namespace):  # noqa: ANN201
    if args.stream_weights:
        from transformers import AutoTokenizer

        from jlens_causal.hf_stream import stream_qwen35_text_model

        tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
        model = stream_qwen35_text_model(
            "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a", args.model_dir,
            device="cuda", dtype=torch.float32 if args.precision == "cuda-fp32" else torch.bfloat16,
        )
        return model, tokenizer
    if args.precision in {"fp32", "cuda-bf16", "cuda-fp32"}:
        from jlens_causal.modeling import load_hf_runtime

        runtime = load_hf_runtime({
            "model_id": "Qwen/Qwen3.5-4B", "local_path": str(args.model_dir), "text_only": True,
            "dtype": "bfloat16" if args.precision == "cuda-bf16" else "float32",
            "device": "cpu" if args.precision == "fp32" else "cuda",
        })
        return runtime.hf_model, runtime.tokenizer
    return load_bf16_storage_fp32_compute(args.model_dir)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("selection", type=Path, help="JSONL of turns (telemetry_path, record_id, label[, kind])")
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--lens", type=Path, required=True)
    parser.add_argument("--mid", type=int, default=19)
    parser.add_argument("--commit", type=int, default=23)
    parser.add_argument("--threshold", type=float, default=2.0)
    parser.add_argument("--contest-k", type=int, default=10)
    parser.add_argument("--same-cos", type=float, default=0.4)
    parser.add_argument("--alphas", type=float, nargs="+", default=[0.05, 0.1, 0.2, 0.3],
                        help="dose ladder; the smallest dose that flips the commit readout is used")
    parser.add_argument("--max-edits", type=int, default=8)
    parser.add_argument("--gate", choices=["args", "args+name", "all"], default="args+name")
    parser.add_argument("--modes", nargs="+", choices=MODES, default=list(MODES))
    parser.add_argument("--max-new-tokens", type=int, default=400)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--precision", choices=["bf16-storage", "fp32", "cuda-bf16", "cuda-fp32"],
                        default="cuda-bf16")
    parser.add_argument("--stream-weights", action="store_true")
    parser.add_argument("--prefill-chunk", type=int, default=2048)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import jlens

    torch.set_num_threads(args.threads)
    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    spec = StageAnchorSpec(mid_layer=args.mid, commit_layer=args.commit, threshold=args.threshold,
                           contest_k=args.contest_k, same_cos=args.same_cos, alphas=tuple(args.alphas),
                           gate=args.gate, max_edits_per_turn=args.max_edits)
    model, tokenizer = load_model(args)
    device = next(model.parameters()).device
    lens = jlens.JacobianLens.load(str(args.lens))
    lens.jacobians = {layer: lens.jacobians[layer] for layer in (spec.mid_layer, spec.commit_layer)}
    text_model = model.model
    head = ReadoutHead(
        norm_weight=text_model.norm.weight.detach().float(),
        eps=float(model.config.rms_norm_eps),
        unembed=model.get_output_embeddings().weight.detach(),
    )
    started = time.time()
    vocab = content_vocab_from_tokenizer(tokenizer, head.unembed.shape[0])
    print(f"content vocab: {int(vocab.mask.sum())}/{len(vocab.pieces)} tokens ({time.time() - started:.0f}s)", flush=True)

    done = set()
    if args.output.is_file():
        done = {(r["record_id"], r["condition"]) for r in map(json.loads, open(args.output, encoding="utf-8"))}
    selection = [json.loads(line) for line in open(args.selection, encoding="utf-8")]
    if args.limit:
        selection = selection[: args.limit]
    eos = [tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.eos_token_id]
    for turn in selection:
        record = load_record(turn["telemetry_path"], turn["record_id"])
        gold = tasks[str(record["task_id"])]["evaluation_criteria"]["actions"]
        pending = [m for m in args.modes if (record["record_id"], m) not in done]
        if not pending:
            continue
        prompt = torch.tensor([record["input_ids"]], device=device)
        started = time.time()
        cache = None
        with torch.no_grad():
            body = prompt[:, :-1]
            for start in range(0, body.shape[1], args.prefill_chunk):
                cache = model(input_ids=body[:, start : start + args.prefill_chunk],
                              past_key_values=cache, use_cache=True, logits_to_keep=1).past_key_values
        prefill_seconds = time.time() - started
        for mode in pending:
            started = time.time()
            with torch.no_grad(), stage_anchor_steering(model, lens, head, spec, vocab, tokenizer, mode=mode) as trace:
                output = model.generate(input_ids=prompt, past_key_values=copy.deepcopy(cache),
                                        max_new_tokens=args.max_new_tokens, do_sample=False, eos_token_id=eos)
            generated = output[0, prompt.shape[1]:].tolist()
            text = tokenizer.decode(generated, skip_special_tokens=False)
            calls = parse_tool_calls(text)
            summary = summarise_events(trace["events"], vocab.pieces, top=8)
            row = {
                "record_id": record["record_id"], "task_id": record["task_id"],
                "turn_index": record["turn_index"], "logged_label": turn.get("label"),
                "kind": turn.get("kind"), "condition": mode, "spec": spec.to_dict(),
                "label": label_calls(calls, gold), "tool_calls": calls, "text": text,
                "matches_logged": generated[: len(record["generated_ids"])] == record["generated_ids"][: len(generated)],
                **{f"sa_{k}": v for k, v in summary.items()},
                "events": trace["events"],
                "prompt_tokens": int(prompt.shape[1]),
                "prefill_seconds": round(prefill_seconds, 1),
                "decode_seconds": round(time.time() - started, 1),
            }
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            top = summary["top"][0] if summary["top"] else None
            print(f"{record['task_id']:>3} t{record['turn_index']:<3} {mode:<8} gated={summary['gated']:<4} "
                  f"contested={summary['contested']:<3} fired={summary['fired']:<2} edits={summary['edits']} "
                  f"-> {row['label']:<10} {[c['name'] for c in calls]}"
                  + (f"  top: {top['b_str']!r}>{top['a_str']!r} s={top['score']}" if top else "")
                  + f" ({row['decode_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
