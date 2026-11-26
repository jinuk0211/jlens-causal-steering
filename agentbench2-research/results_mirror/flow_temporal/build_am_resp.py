"""All agentic-misalignment responses (12 conditions x 50) as explorer cases: prompt rendered like units_am.py, then the full
stored response (cap MAXT tokens in total). Events (token indices): onset (first response token), tool (first <tool_use:...>
block), rcpt (first recipient token of the first email/forward block), marker (end of the scenario's harmful marker, if any).
harmful = repo classifier verdict from haiku_classifications.jsonl (None if unjudged); fold = sample_id % 2.
Usage: python build_am_resp.py RESULTS_DIR AM_MARKERS_DIR OUT_JSON"""
import json
import re
import sys
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
MAXT = 12000
BLOCK = re.compile(r"<tool_use:(\w+)>(.*?)</tool_use:\1>", re.S)


def main():
    res, mdir, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    sys.path.insert(0, str(mdir))
    from am_markers import marker_end
    tok = AutoTokenizer.from_pretrained(MODEL)
    cls = {}
    for line in (res / "haiku_classifications.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if "harmful" in r:
            cls[r["file"]] = bool(r["harmful"])
    cases, pcache = [], {}
    for f in sorted(res.glob("models/*/*/sample_*/response.json")):
        rel = str(f.relative_to(res)).replace("\\", "/")
        r = json.loads(f.read_text(encoding="utf-8"))
        cond, sid = r["metadata"]["condition"], int(r["metadata"]["sample_id"])
        scen = cond.split("_")[0]
        if cond not in pcache:
            d = res / "prompts" / cond
            system = (d / "system_prompt.txt").read_text(encoding="utf-8")
            user = (d / "user_prompt.txt").read_text(encoding="utf-8") + "\n\n" + (d / "email_content.txt").read_text(encoding="utf-8")
            msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            pcache[cond] = tok.encode(tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False),
                                      add_special_tokens=False)
        pids = pcache[cond]
        text = r.get("raw_response") or ""
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        cids, offs = enc["input_ids"], enc["offset_mapping"]
        tok_at = lambda c: next((len(pids) + i for i, (a, b) in enumerate(offs) if b > c), None)
        m0 = next(iter(BLOCK.finditer(text)), None)
        me = next((m for m in BLOCK.finditer(text) if m.group(1) in ("email", "forward")), None)
        rc = None
        if me:
            to = re.search(r"(?im)^\s*to:\s*\"?", me.group(2))
            if to:
                rc = tok_at(me.start(2) + to.end())
        mk = marker_end(scen, text)
        ids = (pids + cids)[:MAXT]
        cases.append({"ids": ids, "onset": len(pids), "pos": len(ids) - 1, "scaf": len(ids), "label": "am", "group": "am_resp_all",
                      "risk": {True: "harmful", False: "harmless", None: "unjudged"}[cls.get(rel)], "domain": f"{cond} s{sid}",
                      "tool": (me.group(1) + " -> " + re.match(r"[^\s,\"]*", text[me.start(2) + to.end():]).group(0)) if me and to else (m0.group(1) if m0 else "-"),
                      "type": "am_resp", "key": f"am|{cond}|{sid}", "condition": cond, "scenario": scen, "sample_id": sid, "fold": sid % 2,
                      "harmful": cls.get(rel), "marker": mk is not None, "truncated": len(pids) + len(cids) > MAXT,
                      "ev": {"tool": tok_at(m0.start()) if m0 else None, "rcpt": rc, "marker": tok_at(mk - 1) if mk else None},
                      "dec": rc})
    out.write_text(json.dumps(cases), encoding="utf-8")
    import collections
    print(len(cases), collections.Counter((c["scenario"], c["risk"]) for c in cases), "truncated", sum(c["truncated"] for c in cases),
          "max T", max(len(c["ids"]) for c in cases))


if __name__ == "__main__":
    main()
