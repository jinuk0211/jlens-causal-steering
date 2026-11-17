"""Build a Stage-Anchor replay selection from the airline turn table.

Input is the ``turns.jsonl`` written by the 2026-11-17 re-analysis
(``build_turns.py``: one row per agent turn with ``split``, ``sim``, ``record_id``,
``label`` and per-call ``write_types``).  Each selected turn is written with its
telemetry path and a ``kind``:

* ``harmful``  bad write that is not ``transfer_to_human_agents``
* ``transfer`` bad write that is a transfer (mostly correct refusals; control)
* ``good``     good write (false-alarm and side-effect control)

Example::

    python scripts/stage_anchor_select.py turns.jsonl data/jlens-telemetry/failure-steering \
        --kinds harmful good --output results/stage_anchor/selection.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def kind_of(row: dict) -> str | None:
    if row["label"] == "good_write":
        return "good"
    if row["label"] != "bad_write":
        return None
    first_bad = next(w for w in row["write_types"] if w["type"] != "match")
    return "transfer" if first_bad["name"] == "transfer_to_human_agents" else "harmful"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("turns", type=Path)
    parser.add_argument("telemetry_root",
                        help="directory with train/validation/evaluation/*.jsonl as seen by the replay host "
                             "(written verbatim, e.g. /workspace/vt/vocab-trigger-data/jlens-telemetry/failure-steering)")
    parser.add_argument("--kinds", nargs="+", choices=["harmful", "transfer", "good"], default=["harmful", "good"])
    parser.add_argument("--splits", nargs="+", default=["train", "validation", "evaluation"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    rows = [json.loads(line) for line in open(args.turns, encoding="utf-8")]
    picked = []
    for row in rows:
        kind = kind_of(row)
        if kind in args.kinds and row["split"] in args.splits:
            path = "/".join([args.telemetry_root.rstrip("/\\"), row["split"], f"{row['sim']}.jsonl"])
            picked.append({"telemetry_path": path, "record_id": row["record_id"], "task_id": row["task_id"],
                           "split": row["split"], "label": row["label"], "kind": kind})
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for item in picked:
            handle.write(json.dumps(item) + "\n")
    counts = {k: sum(p["kind"] == k for p in picked) for k in args.kinds}
    print(f"wrote {len(picked)} turns to {args.output}: {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
