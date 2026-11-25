"""Baseline-failure investigation, server side, CPU only (no GPU): compact per-episode records of every F-run condition.

For each f_* condition (all strengths, airline + retail) and each episode:
  reward, termination, reward breakdown; per agent turn: generated-ids sha256, text head, text length, completion tokens,
  tool calls, write label vs gold (build_topk.label_turn), and the logged intervention summary (active, applied edits,
  applied prefill / decode positions, gate fields).
Also dumps a summary of the steering fit data (artifacts/fit_examples.json) and the artifact metadata (*.pt.json).
Run from tau2-bench/ with CUDA_VISIBLE_DEVICES="". Output: /home/project-b/LJW/tau2-steer/probe/baseline_why/episodes.json, fit.json
"""
import json
import sys
from collections import Counter
from pathlib import Path

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

OUT = R / "probe/baseline_why"
SIM = Path("data/simulations/pilot")
TEL = Path("data/jlens-telemetry/pilot")
KEEP_INTERV = ("requested", "active", "reason", "method", "kind", "layer", "strength", "prefill_calls", "decode_calls",
               "applied_prefill_positions", "applied_decode_positions", "implementation")


def interv_summary(iv):
    if not iv:
        return None
    out = {k: iv.get(k) for k in KEEP_INTERV if k in iv}
    off = iv.get("official") or {}
    for k in ("applied_edits", "multiplier", "vector_norm", "hook_layer", "from_position", "condition_met", "condition_score",
              "condition_threshold", "gate", "fallback", "steered", "n_heads", "alpha", "edits"):
        if k in off:
            v = off[k]
            out["off_" + k] = v if not isinstance(v, (list, dict)) else (len(v) if isinstance(v, list) else str(v)[:200])
    trig = iv.get("vocab_trigger") or {}
    if trig:
        out["trigger_score"] = trig.get("score")
        out["triggered"] = trig.get("triggered")
    j5 = iv.get("j5") or iv.get("controller") or {}
    if isinstance(j5, dict) and j5:
        out["j5"] = {k: j5.get(k) for k in list(j5)[:12] if not isinstance(j5.get(k), (list, dict))}
    return out


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    conds = {}
    for dom in ("airline", "retail"):
        conds[dom] = sorted(p.name for p in (SIM / dom).iterdir() if p.is_dir() and p.name.startswith("f_"))
    print("conditions", conds, flush=True)
    eps = []
    for dom, cs in conds.items():
        for domain, cond, task, sim, tel in bt.episodes(SIM, TEL, [dom], cs):
            gold = bt.gold_actions(domain, task)
            turns = []
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                calls = [{"name": c["name"], "arguments": c.get("arguments")} for c in rec.get("tool_calls") or []]
                label, bad = bt.label_turn(calls, gold)
                text = rec.get("generated_text") or ""
                dec = rec.get("decoding") or {}
                turns.append({"turn": int(rec["turn_index"]), "sha": rec.get("generated_ids_sha256"), "text": text[:500],
                              "tlen": len(text), "gen_tokens": rec.get("completion_tokens"), "max_new": dec.get("max_new_tokens"),
                              "calls": [[c["name"], json.dumps(c["arguments"], sort_keys=True)[:200]] for c in calls],
                              "label": label, "bad": bad, "interv": interv_summary(rec.get("intervention"))})
            turns.sort(key=lambda t: t["turn"])
            ri = sim.get("reward_info") or {}
            eps.append({"domain": domain, "cond": cond, "task": task, "sim": sim["id"], "reward": ri.get("reward"),
                        "breakdown": ri.get("reward_breakdown"), "term": sim.get("termination_reason"),
                        "gold_writes": [a["name"] for a in gold if not a["name"].startswith(bt.READ_PREFIXES)],
                        "failure_types": bt.failure_types(ri, [{"bad": t["bad"], "calls": [{"name": c[0], "arguments": json.loads(c[1]) if c[1].endswith("}") else {}} for c in t["calls"]]} for t in turns], gold) if (ri.get("reward") or 0) < 1 else [],
                        "turns": turns})
            if len(eps) % 100 == 0:
                print("episodes", len(eps), flush=True)
    (OUT / "episodes.json").write_text(json.dumps(eps), encoding="utf-8")
    fit = {}
    fe = json.loads((R / "artifacts/fit_examples.json").read_text(encoding="utf-8"))
    ex = fe.get("examples") or []
    fit["n_examples"] = len(ex)
    fit["positive_source"] = dict(Counter(e.get("positive_source") for e in ex))
    fit["source"] = dict(Counter(e.get("source") for e in ex))
    fit["by_task"] = dict(Counter(str(e.get("task_id")) for e in ex))
    fit["negative_calls"] = dict(Counter(",".join(c.get("name", "?") for c in (e.get("negative") or {}).get("tool_calls") or []) or "(text)" for e in ex))
    fit["positive_texts"] = dict(Counter(((e.get("positive") or {}).get("content") or "")[:120] for e in ex).most_common(8))
    fit["examples_head"] = [{"task": e.get("task_id"), "pos_src": e.get("positive_source"),
                             "neg": ((e.get("negative") or {}).get("content") or "")[:200],
                             "neg_calls": [c.get("name") for c in (e.get("negative") or {}).get("tool_calls") or []],
                             "pos": ((e.get("positive") or {}).get("content") or "")[:200],
                             "pos_calls": [c.get("name") for c in (e.get("positive") or {}).get("tool_calls") or []]} for e in ex[:60]]
    for k in ("pairs", "sources", "by_dir"):
        v = fe.get(k)
        fit[k] = v if not isinstance(v, list) else len(v)
    meta = {}
    for p in sorted((R / "artifacts").glob("*.pt.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        meta[p.name] = {k: m[k] for k in list(m)[:40] if not isinstance(m[k], (list, dict)) or len(json.dumps(m[k])) < 400}
    fit["artifact_meta"] = meta
    for name in ("f_selection.json", "fit_status.json", "fit_status_cast_mera.json"):
        p = R / "artifacts" / name
        if p.exists():
            fit[name] = json.loads(p.read_text(encoding="utf-8"))
    (OUT / "fit.json").write_text(json.dumps(fit, indent=1, default=str), encoding="utf-8")
    print("BW_EXTRACT_DONE episodes", len(eps), flush=True)


if __name__ == "__main__":
    main()
