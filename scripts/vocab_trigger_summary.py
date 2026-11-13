"""Summarise replay outcomes per condition: how the regenerated action changed.

For every (logged label, condition) the regenerated turn is counted as
bad_write / good_write / read / no_call, and as changed or unchanged relative
to the ``off`` regeneration of the same turn.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path


def _signature(row: dict) -> str:
    return json.dumps([(c["name"], c["arguments"]) for c in row["tool_calls"]], sort_keys=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, nargs="+")
    args = parser.parse_args()
    rows = [json.loads(line) for path in args.results for line in open(path, encoding="utf-8")]
    baseline = {row["record_id"]: row for row in rows if row["condition"] == "off@0.0"}
    table: dict[tuple[str, str], Counter] = defaultdict(Counter)
    for row in rows:
        key = (row["logged_label"], row["condition"])
        table[key][row["label"]] += 1
        off = baseline.get(row["record_id"])
        if off is not None and row["condition"] != "off@0.0":
            table[key]["action_changed"] += int(_signature(row) != _signature(off))
            table[key]["fixed_bad"] += int(off["label"] == "bad_write" and row["label"] != "bad_write")
            table[key]["broke_good"] += int(off["label"] == "good_write" and row["label"] != "good_write")
            table[key]["made_bad"] += int(off["label"] != "bad_write" and row["label"] == "bad_write")
        table[key]["n"] += 1
    order = ["n", "bad_write", "good_write", "read", "no_call", "action_changed", "fixed_bad", "broke_good", "made_bad"]
    print(f"{'logged':<11}{'condition':<16}" + "".join(f"{name:>15}" for name in order))
    for (label, condition), counts in sorted(table.items()):
        print(f"{label:<11}{condition:<16}" + "".join(f"{counts[name]:>15}" for name in order))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
