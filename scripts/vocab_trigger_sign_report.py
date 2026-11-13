"""Paired +/- steering report for vocab-trigger replays.

The label table of ``vocab_trigger_summary.py`` only sees the final tool call.
This report asks whether the *direction* matters, per turn and per condition:

* tool-name transitions relative to ``off`` (free-text arguments such as the
  transfer summary are ignored, so rewording is not counted as a new action);
* text markers of the two vocabularies the direction was built from: asking the
  user (``?``, "would you", "confirm") versus policy-compliance / apology language;
* a paired sign test: on how many turns does +alpha end better than -alpha
  (bad -> not bad), and vice versa.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ASK = re.compile(r"\?|\bwould you\b|\bcould you\b|\bplease (?:confirm|provide|let me know)\b|\bconfirm\b", re.I)
COMPLY = re.compile(r"\bpolic(?:y|ies)\b|\bunable\b|\bcannot\b|\bcan't\b|\bnot (?:able|allowed|eligible)\b|"
                    r"\bstrict(?:ly)?\b|\bcompl(?:y|iance)\b", re.I)
APOLOGY = re.compile(r"\bapolog|\bsorry\b", re.I)
RANK = {"bad_write": 0, "no_call": 1, "read": 1, "good_write": 2}


def visible(text: str) -> str:
    """Drop the reasoning block and tool-call markup, keep what the user would read."""
    text = re.sub(r"<think>.*?</think>", " ", text, flags=re.S)
    text = re.sub(r"<tool_call>.*?(</tool_call>|$)", " ", text, flags=re.S)
    return text


def names(row: dict) -> tuple[str, ...]:
    return tuple(call["name"] for call in row["tool_calls"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("results", type=Path, nargs="+")
    parser.add_argument("--exclude-tools", nargs="*", default=[],
                        help="drop turns whose off regeneration calls one of these tools")
    args = parser.parse_args()
    rows = [json.loads(line) for path in args.results for line in open(path, encoding="utf-8")]
    by_turn: dict[str, dict[str, dict]] = defaultdict(dict)
    for row in rows:
        by_turn[row["record_id"]][row["condition"]] = row
    if args.exclude_tools:
        by_turn = {rid: conds for rid, conds in by_turn.items()
                   if "off@0.0" in conds and not set(names(conds["off@0.0"])) & set(args.exclude_tools)}
    conditions = sorted({c for conds in by_turn.values() for c in conds}, key=lambda c: (c != "off@0.0", c))

    print(f"turns: {len(by_turn)}")
    header = ["n", "bad", "no_call", "good", "tool_changed", "ask", "comply", "apology", "think_tok"]
    print(f"{'logged':<11}{'condition':<15}" + "".join(f"{h:>13}" for h in header))
    for logged in sorted({conds[c]["logged_label"] for conds in by_turn.values() for c in conds}):
        for condition in conditions:
            counts = Counter()
            for conds in by_turn.values():
                row = conds.get(condition)
                if row is None or row["logged_label"] != logged:
                    continue
                off = conds.get("off@0.0")
                text = visible(row["text"])
                counts["n"] += 1
                counts["bad"] += row["label"] == "bad_write"
                counts["no_call"] += row["label"] in {"no_call", "read"}
                counts["good"] += row["label"] == "good_write"
                counts["tool_changed"] += off is not None and names(row) != names(off)
                counts["ask"] += bool(ASK.search(text))
                counts["comply"] += bool(COMPLY.search(text))
                counts["apology"] += bool(APOLOGY.search(text))
                think = re.search(r"<think>(.*?)</think>", row["text"], flags=re.S)
                counts["think_tok"] += len(think.group(1).split()) if think else 0
            if counts["n"]:
                counts["think_tok"] = round(counts["think_tok"] / counts["n"])
                print(f"{logged:<11}{condition:<15}" + "".join(f"{counts[h]:>13}" for h in header))

    probe_layers = sorted({int(k) for conds in by_turn.values() for row in conds.values()
                           for k in row.get("probe_scores") or {}})
    if probe_layers:
        # The direction is safe-minus-risk, so +alpha should lower the risk-minus-safe readout.
        print("\nreadout shift vs off at the decision point: mean delta(risk - safe) [share of turns < 0]")
        print(f"{'condition':<15}" + "".join(f"{'L' + str(layer):>16}" for layer in probe_layers))
        for condition in conditions:
            if condition == "off@0.0":
                continue
            cells = []
            for layer in probe_layers:
                deltas = [conds[condition]["probe_scores"][str(layer)] - conds["off@0.0"]["probe_scores"][str(layer)]
                          for conds in by_turn.values()
                          if condition in conds and "off@0.0" in conds
                          and str(layer) in (conds[condition].get("probe_scores") or {})
                          and str(layer) in (conds["off@0.0"].get("probe_scores") or {})]
                if deltas:
                    negative = sum(d < 0 for d in deltas) / len(deltas)
                    cells.append(f"{sum(deltas) / len(deltas):+8.2f} [{negative:.2f}]")
                else:
                    cells.append("-")
            print(f"{condition:<15}" + "".join(f"{cell:>16}" for cell in cells))

    print("\npaired sign test (better = higher outcome rank: bad < no_call/read < good)")
    for mode in ("trigger", "random", "always"):
        plus = [c for c in conditions if c.startswith(f"{mode}@") and not c.startswith(f"{mode}@-")]
        for p in plus:
            m = p.replace("@", "@-", 1)
            if m not in conditions:
                continue
            tally = Counter()
            for conds in by_turn.values():
                if p in conds and m in conds:
                    a, b = RANK[conds[p]["label"]], RANK[conds[m]["label"]]
                    tally["+ better" if a > b else "- better" if b > a else "tie"] += 1
            print(f"  {p:<14} vs {m:<14} {dict(tally)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
