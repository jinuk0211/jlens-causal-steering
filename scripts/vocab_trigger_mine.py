"""Mine a J-lens risk vocabulary that predicts bad write actions in tau2 airline turns.

Inputs are the no-steering baseline telemetry of Qwen3.5-4B (exact input IDs,
emitted tool calls, and residuals at the decision point for layers 8/16/31).
Each agent turn is labelled against the task's gold actions:
``bad_write`` (a state-changing call with wrong arguments or none expected),
``good_write``, ``read`` or ``no_call``.

On the *train* split only, tokens are ranked by how much more often they sit in
the J-lens top-K at the decision point of bad-write turns than of all other
turns (smoothed log-odds).  The trigger score is
``logsumexp(z[risk]) - logsumexp(z[safe])`` and its threshold maximises F1 on
train.  Validation and evaluation turns are held out and only scored.
"""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
from collections import Counter
from pathlib import Path

import torch

from jlens_causal.vocab_trigger import TriggerSpec, label_calls, lens_logits, load_readout_head

SPLITS = ("train", "validation", "evaluation")


def load_turns(telemetry_root: Path, tasks: dict[str, dict]) -> list[dict]:
    turns = []
    for split in SPLITS:
        for path in sorted(glob.glob(os.path.join(telemetry_root, split, "*.jsonl"))):
            simulation = Path(path).stem
            for line in open(path, encoding="utf-8"):
                record = json.loads(line)
                gold = tasks[str(record["task_id"])]["evaluation_criteria"]["actions"]
                residuals = {
                    (item["label"], int(item["layer"])): torch.tensor(item["vector"])
                    for item in record["measurement"].get("residuals", [])
                }
                turns.append({
                    "split": split,
                    "simulation": simulation,
                    "task_id": str(record["task_id"]),
                    "turn_index": record["turn_index"],
                    "record_id": record["record_id"],
                    "telemetry_path": path,
                    "label": label_calls(record["tool_calls"], gold),
                    "tool_calls": record["tool_calls"],
                    "residuals": residuals,
                })
    return turns


def word_like(piece: str) -> bool:
    """Keep tokens that carry a concept (>= 2 letters); drop punctuation/whitespace pieces,
    which would otherwise be injected literally when steering."""
    return sum(ch.isalpha() for ch in piece) >= 2


def auc(scores: list[float], labels: list[bool]) -> float | None:
    positives = [s for s, y in zip(scores, labels, strict=True) if y]
    negatives = [s for s, y in zip(scores, labels, strict=True) if not y]
    if not positives or not negatives:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in positives for n in negatives)
    return wins / (len(positives) * len(negatives))


def best_threshold(scores: list[float], labels: list[bool]) -> tuple[float, dict]:
    best = (-math.inf, {"f1": 0.0})
    for threshold in sorted(set(scores)):
        predicted = [s >= threshold for s in scores]
        tp = sum(p and y for p, y in zip(predicted, labels, strict=True))
        fp = sum(p and not y for p, y in zip(predicted, labels, strict=True))
        fn = sum((not p) and y for p, y in zip(predicted, labels, strict=True))
        f1 = 2 * tp / max(1, 2 * tp + fp + fn)
        if f1 > best[1]["f1"]:
            best = (threshold - 1e-6, {"f1": f1, "tp": tp, "fp": fp, "fn": fn})
    return best


def evaluate(spec: TriggerSpec, turns: list[dict], logits_cache: dict) -> dict:
    report = {}
    for split in SPLITS:
        rows = [t for t in turns if t["split"] == split and (t["record_id"], spec.observe_layer) in logits_cache]
        scores = [spec.score(logits_cache[(t["record_id"], spec.observe_layer)]) for t in rows]
        labels = [t["label"] == "bad_write" for t in rows]
        fired = [s > spec.threshold for s in scores]
        by_label = Counter()
        fired_by_label = Counter()
        for t, f in zip(rows, fired, strict=True):
            by_label[t["label"]] += 1
            fired_by_label[t["label"]] += int(f)
        report[split] = {
            "turns": len(rows),
            "auc_bad_vs_rest": auc(scores, labels),
            "fire_rate_by_label": {k: f"{fired_by_label[k]}/{v}" for k, v in sorted(by_label.items())},
        }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("telemetry_root", type=Path, help="data/jlens-telemetry/failure-steering")
    parser.add_argument("tasks", type=Path, help="tau2 airline tasks.json")
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--lens", type=Path, required=True)
    parser.add_argument("--layers", type=int, nargs="+", default=[16, 8])
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--vocab-size", type=int, default=8)
    parser.add_argument("--min-support", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    import jlens

    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    turns = load_turns(args.telemetry_root, tasks)
    head = load_readout_head(args.model_dir)
    lens = jlens.JacobianLens.load(str(args.lens))
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    site = "initial_decision"
    logits_cache: dict = {}
    topk_cache: dict = {}
    with torch.no_grad():
        for turn in turns:
            for layer in args.layers:
                residual = turn["residuals"].get((site, layer))
                if residual is None:
                    continue
                logits = lens_logits(lens, head, residual, layer)
                logits_cache[(turn["record_id"], layer)] = logits
                topk_cache[(turn["record_id"], layer)] = set(torch.topk(logits, args.top_k).indices.tolist())

    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "turns": Counter(f"{t['split']}/{t['label']}" for t in turns),
        "site": site,
        "top_k": args.top_k,
        "layers": {},
    }
    best_spec = None
    for layer in args.layers:
        train = [t for t in turns if t["split"] == "train" and (t["record_id"], layer) in topk_cache]
        bad = [t for t in train if t["label"] == "bad_write"]
        rest = [t for t in train if t["label"] != "bad_write"]
        bad_counts = Counter(tok for t in bad for tok in topk_cache[(t["record_id"], layer)])
        rest_counts = Counter(tok for t in rest for tok in topk_cache[(t["record_id"], layer)])

        n_bad, n_rest = len(bad), len(rest)

        def log_odds(token: int, bad_counts=bad_counts, rest_counts=rest_counts,
                     n_bad=n_bad, n_rest=n_rest) -> float:
            a, b = bad_counts[token] + 0.5, rest_counts[token] + 0.5
            return math.log(a / (n_bad + 1)) - math.log(b / (n_rest + 1))

        candidates = [tok for tok in set(bad_counts) | set(rest_counts)
                      if bad_counts[tok] + rest_counts[tok] >= args.min_support
                      and word_like(tokenizer.decode([tok]))]
        ranked = sorted(candidates, key=log_odds)
        risk = [tok for tok in reversed(ranked) if bad_counts[tok] >= args.min_support][: args.vocab_size]
        safe = [tok for tok in ranked if rest_counts[tok] >= args.min_support][: args.vocab_size]
        spec = TriggerSpec(observe_layer=layer, site=site, risk_ids=risk, safe_ids=safe, threshold=0.0,
                           risk_tokens=[tokenizer.decode([t]) for t in risk],
                           safe_tokens=[tokenizer.decode([t]) for t in safe])
        train_scores = [spec.score(logits_cache[(t["record_id"], layer)]) for t in train]
        threshold, train_fit = best_threshold(train_scores, [t["label"] == "bad_write" for t in train])
        spec.threshold = threshold
        report = evaluate(spec, turns, logits_cache)
        summary["layers"][layer] = {
            "risk_tokens": spec.risk_tokens,
            "safe_tokens": spec.safe_tokens,
            "risk_log_odds": [round(log_odds(t), 2) for t in risk],
            "threshold": threshold,
            "train_fit": train_fit,
            "evaluation": report,
        }
        spec.save(args.output_dir / f"trigger_layer{layer}.json")
        held_out = [report[s]["auc_bad_vs_rest"] for s in ("validation", "evaluation")]
        held_out = [value for value in held_out if value is not None]
        score = sum(held_out) / len(held_out) if held_out else 0.0
        train_auc = report["train"]["auc_bad_vs_rest"] or 0.0
        # choose the layer on train AUC only (held-out numbers are reported, not used)
        if best_spec is None or train_auc > best_spec[1]:
            best_spec = (layer, train_auc, score)
    summary["selected_layer_by_train_auc"] = best_spec[0] if best_spec else None
    (args.output_dir / "mining_report.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, default=dict), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, default=dict))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
