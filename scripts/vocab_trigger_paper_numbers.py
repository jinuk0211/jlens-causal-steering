"""Recompute the numbers reported for the vocabulary trigger from the saved results.

Reads ``results/vocab_trigger/gpu`` (pattern scan, dose sweep, untriggered
control) and prints:

* held-out AUC per layer (mean of validation and evaluation);
* the layers at which each word family enters the mined vocabularies;
* presence/absence counts of the risk and safe tokens at layers 16-19;
* the dose-sweep table (outcome counts, readout shift at layer 24);
* paired outcome tests between conditions (two-sided sign test);
* the untriggered good-write control.

Full-episode numbers come from tau2-bench
``scripts/summarize_vocab_trigger_episodes.py`` (see
``results/vocab_trigger/episodes/main_summary.txt``).
"""

from __future__ import annotations

import argparse
import json
import math
import re
from collections import Counter
from pathlib import Path

# Families are matched on the stripped token; each tuple is (side, pattern).
FAMILIES = {
    "comply / request": ("risk", r"(?i)complian|明确要求|严格按照|以下步骤|^requests?$|^requested$"),
    "acknowledge": ("risk", r"(?i)^ack$|acknowled|承认|recogn"),
    "proceed": ("risk", r"(?i)proceed|proceder|将进行|将通过"),
    "apologise": ("risk", r"(?i)apolog|道歉|歉意|对不起|抱歉|申し訳|^sorry$"),
    "ask / please": ("safe", r"(?i)^ask|asking|asks|asked|inquir|问询|询问|请问|问一下|提问|请您"),
    "look up / found": ("safe", r"(?i)找到|查到|查看|我发现|报告显示|资料显示|看到了|我看到|^looking$|^searching$|"
                                r"^checking$|^found$|看一下|可以看到|发现了|^我看$"),
    "let / let's": ("safe", r"(?i)^\W*let|^let$|让|давайте"),
}
RANK = {"bad_write": 0, "no_call": 1, "read": 1, "good_write": 2}


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2**n)


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8")]


def patterns_report(report: dict) -> None:
    layers = {int(k): v for k, v in report["layers"].items()}
    print("held-out AUC by layer (mean of validation, evaluation)")
    for layer, entry in sorted(layers.items()):
        auc = entry["auc"]
        held = [auc[s] for s in ("validation", "evaluation") if auc[s] is not None]
        print(f"  L{layer:2d} {sum(held) / len(held):.3f}  (train {auc['train']:.3f})")

    print("\nword families: layers whose mined vocabulary contains a member")
    for name, (side, pattern) in FAMILIES.items():
        hits = sorted(layer for layer, entry in layers.items()
                      if any(re.search(pattern, token.strip()) for token, *_ in entry[side]))
        print(f"  {name:<16} ({side}) {hits}")

    # Each vocabulary entry is (token, log_odds, train bad-write count, train other count).
    n_bad = report["turns"].get("train/bad_write", 0)
    n_other = sum(v for k, v in report["turns"].items() if k.startswith("train/") and k != "train/bad_write")
    print(f"\npresence in the top 50 at layers 16-19 (train: {n_bad} bad writes, {n_other} other turns)")
    for layer in range(16, 20):
        entry = layers[layer]
        risk_bad = [b for _, _, b, _ in entry["risk"]]
        safe_bad = [b for _, _, b, _ in entry["safe"]]
        safe_other = [r for _, _, _, r in entry["safe"]]
        print(f"  L{layer}: risk tokens at {min(risk_bad)}-{max(risk_bad)} bad writes; safe tokens at "
              f"{min(safe_bad)}-{max(safe_bad)} bad writes and {min(safe_other)}-{max(safe_other)} other turns")


def dose_report(rows: list[dict], probe_layer: str) -> None:
    by: dict[str, dict[str, dict]] = {}
    for row in rows:
        by.setdefault(row["record_id"], {})[row["condition"]] = row
    conditions = sorted({c for v in by.values() for c in v}, key=lambda c: (c != "off@0.0", c))
    print(f"\ndose sweep: bad turns bad/none/good | good turns good/none/bad | mean shift at L{probe_layer}")
    for cond in conditions:
        cells = []
        for logged, order in (("bad_write", ("bad_write", "none", "good_write")),
                              ("good_write", ("good_write", "none", "bad_write"))):
            labels = Counter("none" if v[cond]["label"] in {"no_call", "read"} else v[cond]["label"]
                             for v in by.values() if cond in v and v[cond]["logged_label"] == logged)
            cells.append(" / ".join(str(labels[k]) for k in order))
        if cond == "off@0.0":
            shift = "-"
        else:
            deltas = [v[cond]["probe_scores"][probe_layer] - v["off@0.0"]["probe_scores"][probe_layer]
                      for v in by.values() if cond in v and "off@0.0" in v]
            shift = f"{sum(deltas) / len(deltas):+.2f}"
        asks = sum(1 for v in by.values() if cond in v and not v[cond]["tool_calls"] and "?" in v[cond]["text"])
        print(f"  {cond:<14} {cells[0]:<12} | {cells[1]:<12} | {shift:>7}  (no call + question: {asks})")
    matches = sum(1 for v in by.values() if v.get("off@0.0", {}).get("matches_logged"))
    print(f"  unsteered regeneration matches the log on {matches}/{len(by)} turns")

    print("\npaired outcome tests (better = higher rank: bad < no call/read < good)")
    pairs = [("trigger@0.8", "trigger@-0.8"), ("trigger@0.4", "trigger@-0.4"), ("trigger@0.2", "trigger@-0.2"),
             ("trigger@0.8", "random@0.8"), ("random@0.8", "random@-0.8")]
    for a, b in pairs:
        tally = Counter()
        for v in by.values():
            if a in v and b in v:
                x, y = RANK[v[a]["label"]], RANK[v[b]["label"]]
                tally["a" if x > y else "b" if y > x else "tie"] += 1
        print(f"  {a} vs {b}: {tally['a']} better, {tally['b']} worse, {tally['tie']} tied, "
              f"sign test p={sign_test(tally['a'], tally['b']):.3f}")


def control_report(rows: list[dict]) -> None:
    print("\nuntriggered good writes, steered unconditionally")
    for cond in sorted({r["condition"] for r in rows}, key=lambda c: (c != "off@0.0", c)):
        labels = Counter(r["label"] for r in rows if r["condition"] == cond)
        print(f"  {cond:<14} {dict(labels)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--results", type=Path, default=Path("results/vocab_trigger/gpu"))
    parser.add_argument("--probe-layer", default="24")
    args = parser.parse_args()
    patterns_report(json.loads((args.results / "patterns" / "patterns_all_layers.json").read_text(encoding="utf-8")))
    dose_report(load_jsonl(args.results / "sign" / "dose_triggered_results.jsonl"), args.probe_layer)
    control_report(load_jsonl(args.results / "sign" / "sign_always_good_results.jsonl"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
