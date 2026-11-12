"""Select held-out turns for the replay: triggered bad writes (can steering fix them?)
and triggered good writes (does steering break them?)."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import torch

from jlens_causal.vocab_trigger import TriggerSpec, lens_logits, load_readout_head


def _mine_module():
    path = Path(__file__).with_name("vocab_trigger_mine.py")
    spec = importlib.util.spec_from_file_location("vocab_trigger_mine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("telemetry_root", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("trigger", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--lens", type=Path, required=True)
    parser.add_argument("--splits", nargs="+", default=["validation", "evaluation"])
    parser.add_argument("--labels", nargs="+", default=["bad_write", "good_write"])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import jlens

    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    spec = TriggerSpec.load(args.trigger)
    turns = _mine_module().load_turns(args.telemetry_root, tasks)
    head = load_readout_head(args.model_dir)
    lens = jlens.JacobianLens.load(str(args.lens))
    rows = []
    with torch.no_grad():
        for turn in turns:
            residual = turn["residuals"].get((spec.site, spec.observe_layer))
            if turn["split"] not in args.splits or turn["label"] not in args.labels or residual is None:
                continue
            score = spec.score(lens_logits(lens, head, residual, spec.observe_layer))
            if score > spec.threshold:
                rows.append({key: turn[key] for key in ("split", "simulation", "task_id", "turn_index",
                                                        "record_id", "telemetry_path", "label")}
                            | {"offline_score": score})
    rows.sort(key=lambda row: (row["label"] != "bad_write", row["split"], row["record_id"]))
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(json.dumps({"selected": len(rows), "bad_write": sum(r["label"] == "bad_write" for r in rows),
                      "good_write": sum(r["label"] == "good_write" for r in rows)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
