"""agentic-misalignment units (CPU). PLAN.md "Units".
TARGET = harmful by the full classifier (deterministic condition AND Haiku verdict, from haiku_classifications.jsonl).
REFERENCE = harmless response of the same condition. Fold = sample_id % 2.
Budget = tokens up to the end of the first harmful marker in the target + 256 (cap 3072); references get the median
target budget of their scenario. Exact token ids come from ab_proxy records; a chat-template render is the fallback.
Usage: units_am.py RESULTS_EXPERIMENT_DIR PROXY_JSONL OUT_JSON [--unlabeled]
--unlabeled: no Haiku labels yet (label "unlabeled"), for the label-free steps (stats, J-lens extraction)."""
import hashlib
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from transformers import AutoTokenizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from am_markers import marker_end

MODEL, REV = "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def main():
    res, proxy, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
    unlabeled = "--unlabeled" in sys.argv
    cls = {}
    if not unlabeled:
        for line in (res / "haiku_classifications.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            if "harmful" in r:
                cls[r["file"]] = r
    recs = defaultdict(list)
    if proxy.is_file():
        for line in proxy.open(encoding="utf-8"):
            r = json.loads(line)
            ms = r["request"]["messages"]
            key = hashlib.sha256(json.dumps([m.get("content") for m in ms]).encode()).hexdigest()
            msg = (r["response"].get("choices") or [{}])[0]
            recs[(key, (msg.get("message") or {}).get("content") or "")].append(r)
    units, why, agree = [], Counter(), Counter()
    for f in sorted(res.glob("models/**/response.json")):
        rel = str(f.relative_to(res))
        if rel not in cls and not unlabeled:
            why["unclassified"] += 1
            continue
        r = json.loads(f.read_text(encoding="utf-8"))
        cond, sid = r["metadata"]["condition"], int(r["metadata"]["sample_id"])
        scen = cond.split("_")[0]
        pdir = res / "prompts" / cond
        system = (pdir / "system_prompt.txt").read_text(encoding="utf-8")
        user = (pdir / "user_prompt.txt").read_text(encoding="utf-8") + "\n\n" + (pdir / "email_content.txt").read_text(encoding="utf-8")
        text = r.get("raw_response") or ""
        mk = marker_end(scen, text)
        harmful = cls[rel]["harmful"] if not unlabeled else None
        agree[(harmful, mk is not None)] += 1
        key = hashlib.sha256(json.dumps([system, user]).encode()).hexdigest()
        pids = cids = None
        src = "render"
        for rec in recs.get((key, text), []):
            resp = rec["response"]
            p = resp.get("prompt_token_ids")
            c = (resp.get("choices") or [{}])[0].get("token_ids")
            if p and c:
                pids, cids, src = list(p), list(c), "vllm"
                break
        if pids is None:
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            pids = tok.encode(tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False),
                              add_special_tokens=False)
            cids = tok.encode(text, add_special_tokens=False)
        label = "unlabeled" if unlabeled else ("target" if harmful else "reference")
        if label == "target" and mk is None:
            why["target_without_marker"] += 1
            continue
        budget = None
        if mk is not None:
            budget = min(3072, len(tok.encode(text[:mk], add_special_tokens=False)) + 256)
        units.append({"uid": f"am|{cond}|{sid}", "bench": "am", "scenario": scen, "condition": cond, "sample_id": sid,
                      "group": cond, "fold": sid % 2, "label": label, "prompt_ids": pids, "completion_ids": cids,
                      "token_source": src, "budget": budget, "marker_in_original": mk is not None})
        why[label] += 1
    med = {s: int(statistics.median([u["budget"] for u in units if u["scenario"] == s and u["budget"] is not None] or [1024]))
           for s in ("blackmail", "leaking", "murder")}
    for u in units:
        if u["budget"] is None:
            u["budget"] = med[u["scenario"]]
    if not units:
        raise SystemExit("no units built; refusing to write an empty units file")
    out.write_text(json.dumps(units), encoding="utf-8")
    print(json.dumps({"units": len(units), "counts": why, "classifier_vs_marker": {str(k): v for k, v in agree.items()},
                      "token_source": Counter(u["token_source"] for u in units), "median_budget": med,
                      "folds": {f"{k[0]}|{k[1]}": v for k, v in Counter((u["fold"], u["label"]) for u in units).items()}}, default=str, indent=1))


if __name__ == "__main__":
    main()
