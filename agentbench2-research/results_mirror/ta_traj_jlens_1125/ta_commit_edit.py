"""ToolAlign-4B: Goodfire-style mean replacement starting at the J-lens commit sentence (user 11-25 19:4x).
For each of the 53 CAUSAL-1 targets, regenerate greedily from a start point with the edit on at every generated
position, and read the tool that is called:
  start = onset (whole response) | commit (start of the sentence that holds the sustained L24 J-lens commit token)
        | name (the tool-name position only, = CAUSAL-1).
Edits: neurons (MLP down_proj inputs) top-256 / top-1024 by |mu_t - mu_r| / sigma_r on the other domain fold, set to
the leave-one-domain-out reference mean; random neurons in the same layers; attention L16-20 -> reference mean; a random
contiguous 5-layer attention band. Means are over each unit's response span (onset .. name position).
Modes: stats (span means of all 212 units) | run | report.
Usage: python ta_commit_edit.py MODE ta_seqs.json TRAJ_DIR OUT_DIR"""
import hashlib
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "pydeps"))
import ab_core as C

NAME_RE = re.compile(r"<tool_name>\s*([^<\s]+)\s*</tool_name>")
SCAF = "<tool_call>\n<tool_name>"
KEY = 24
BATCH = int(os.environ.get("TJ_BATCH", "4"))
BAND = list(range(16, 21))
RAND_BAND = list(range(4, 9))


def fold(domain):
    return int(hashlib.md5(domain.encode()).hexdigest(), 16) % 2


def load_model():
    q = os.popen("nvidia-smi --query-compute-apps=pid --format=csv,noheader").read().split()
    if [p for p in q if p.strip() and int(p) != os.getpid()]:
        raise SystemExit(f"GPU guard: other compute processes {q}")
    C.patch_gdn()
    from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
    tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
    model = Qwen3_5ForConditionalGeneration.from_pretrained(C.MODEL, revision=C.REV, dtype=torch.float32, device_map={"": 0})
    model.model.visual = None
    model.eval()
    for p in model.parameters():
        p.requires_grad_(False)
    torch.cuda.empty_cache()
    return tok, model


def commit_start(tok, u, traj):
    """Start of the sentence that holds the sustained L24 commit token (response region), or the scaffold start."""
    z = np.load(traj / f"u_{u['idx']}.npz")
    cl = z["cand_lp"].astype(np.float32)
    s0 = u["span"][0]
    ci, wi = u["cand_ids"].index(u["c"]), u["cand_ids"].index(u["w"])
    marg = cl[:, KEY, ci] - cl[:, KEY, wi]
    on = u["onset"] - s0
    n = cl.shape[0]
    ids = u["span_ids"][:n]
    scaf = tok.encode(SCAF, add_special_tokens=False)
    scaf_start = n - len(scaf) if ids[n - len(scaf):n] == scaf else n - 1
    commit = next((t for t in range(on, n) if marg[t] > 0 and (marg[t:] > 0).mean() >= 0.8), None)
    if commit is None:
        return None, None
    if commit >= scaf_start:
        return s0 + scaf_start, "scaffold"
    t = commit
    while t > on + 1:
        piece = tok.decode([ids[t - 1]])
        if "\n" in piece or re.search(r"[.!?]\s*$", piece):
            break
        t -= 1
    return s0 + max(t, on + 1), ("onset" if commit <= on + 1 else "response")


def mode_stats(seqs, out):
    tok, model = load_model()
    H = C.Hooked(model)
    A, M, uids = [], [], []
    t0 = time.time()
    for n, u in enumerate(seqs):
        ids = u["ids"][:u["pos"] + 1]
        on = u["onset"]
        _, cache = C.prefill(model, ids[:on])
        H.store = {}
        H.cap = {"mode": "mean", "kinds": {"act", "attn"}}
        with torch.inference_mode():
            model(input_ids=torch.tensor([ids[on:]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
        H.cap = None
        A.append(torch.stack([H.store[("act", i)] for i in range(H.nl)]).half().numpy())
        M.append(torch.stack([H.store[("attn", i)] for i in range(H.nl)]).half().numpy())
        uids.append(n)
        H.store = {}
        del cache
        if n % 20 == 0:
            C.log(f"stats {n + 1}/{len(seqs)} {time.time() - t0:.0f}s")
    np.savez(out / "stats.npz", act=np.stack(A), attn=np.stack(M))
    C.log("STATS_DONE")


def mode_run(seqs, traj, out):
    tok, model = load_model()
    H = C.Hooked(model)
    meta = json.loads((traj / "meta.json").read_text(encoding="utf-8"))
    S = np.load(out / "stats.npz")
    act, attn = S["act"].astype(np.float32), S["attn"].astype(np.float32)
    nn = act.shape[2]
    tg = [i for i, u in enumerate(seqs) if u["label"] == "target"]
    rf = [i for i, u in enumerate(seqs) if u["label"] == "reference"]
    sets = {}
    rng = np.random.default_rng(7)
    for f in (0, 1):
        t_ = [i for i in tg if fold(seqs[i]["domain"]) == f and seqs[i]["risk"] != "aligned"]
        r_ = [i for i in rf if fold(seqs[i]["domain"]) == f]
        z = (np.abs(act[t_].mean(0) - act[r_].mean(0)) / (act[r_].std(0) + 1e-3)).ravel()
        order = np.argsort(-z)
        for K in (256, 1024):
            top = order[:K]
            sets[(f, K, "top")] = top
            sets[(f, K, "rand")] = (top // nn) * nn + rng.integers(0, nn, K)

    def mu_excl(dom, arr):
        ii = [i for i in rf if seqs[i]["domain"] != dom]
        return torch.tensor(arr[ii].mean(0))

    def neur(flat, mu):
        by = defaultdict(list)
        for x in flat.tolist():
            by[x // nn].append(x % nn)
        return {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=mu[l][ns]) for l, ns in by.items()}

    rows_path = out / "rows.jsonl"
    done = set()
    if rows_path.is_file():
        for line in rows_path.open(encoding="utf-8"):
            r = json.loads(line)
            done.add((r["idx"], r["start"], r["config"]))
    fh = rows_path.open("a", encoding="utf-8")
    t0 = time.time()
    stop = lambda text, r: bool(NAME_RE.search(text))
    for n, i in enumerate(tg):
        u = seqs[i]
        ids = u["ids"][:u["pos"] + 1]
        cs, ckind = commit_start(tok, meta[i], traj)
        starts = {"onset": u["onset"] + 1, "name": u["pos"] + 1}
        if cs is not None:
            starts["commit"] = cs
        dom = u["domain"]
        ma, mt = mu_excl(dom, act), mu_excl(dom, attn)
        fo = 1 - fold(dom)
        cfgs = [("base", {}), ("neur_top_256", neur(sets[(fo, 256, "top")], ma)), ("neur_rand_256", neur(sets[(fo, 256, "rand")], ma)),
                ("neur_top_1024", neur(sets[(fo, 1024, "top")], ma)), ("neur_rand_1024", neur(sets[(fo, 1024, "rand")], ma)),
                ("attn_16_20", {("attn", l): C.Edit("set", vec=mt[l]) for l in BAND}),
                ("attn_rand_4_8", {("attn", l): C.Edit("set", vec=mt[l]) for l in RAND_BAND})]
        for sname, st in starts.items():
            todo = [c for c in cfgs if (i, sname, c[0]) not in done]
            if not todo:
                continue
            prompt = ids[:st]
            budget = max(16, min(1200, int(1.5 * (u["pos"] - st)) + 64))
            _, cache0 = C.prefill(model, prompt[:-1])
            for b in range(0, len(todo), BATCH):
                chunk = todo[b:b + BATCH]
                res = C.regen(model, tok, H, prompt, [e for _, e in chunk], budget, stop, prefix_cache=cache0, trigger="</tool_name>")
                for (cname, _), r in zip(chunk, res):
                    m = NAME_RE.search(r["text"])
                    fh.write(json.dumps({"idx": i, "domain": dom, "risk": u["risk"], "kind": (u.get("n4") or {}).get("kind"),
                                         "orig_tool": u["tool"], "start": sname, "commit_kind": ckind, "start_pos": st,
                                         "tokens_regenerated_to_name": u["pos"] - st, "config": cname,
                                         "gen_tool": m.group(1) if m else None, "n": r["n"], "end": r["end"],
                                         "text_head": r["text"][:300]}, ensure_ascii=False) + "\n")
                fh.flush()
            del cache0
            torch.cuda.empty_cache()
        C.log(f"unit {n + 1}/{len(tg)} {u['tool']} starts {list(starts)} {time.time() - t0:.0f}s")
    C.log("RUN_DONE")


def mode_report(out):
    rows = [json.loads(l) for l in (out / "rows.jsonl").open(encoding="utf-8")]
    base = {(r["idx"], r["start"]): r for r in rows if r["config"] == "base"}
    ok = {k for k, r in base.items() if r["gen_tool"] == r["orig_tool"]}
    md = ["# Goodfire-style mean replacement from the J-lens commit sentence (ToolAlign-4B targets, greedy regeneration)", "",
          "Base reproduces the original tool: " + ", ".join(f"{s} {sum(1 for k in ok if k[1] == s)}/{sum(1 for k in base if k[1] == s)}"
                                                       for s in ("onset", "commit", "name")), "",
          "flip = the regenerated call is writeInternalLog; other = another tool; broken = no tool name within budget.", ""]
    for grp, pred in (("misaligned + boundary", lambda r: r["risk"] != "aligned"), ("aligned (legit internal emails etc.)", lambda r: r["risk"] == "aligned")):
        md += [f"## {grp}", "", "| start | config | n | flip | other | same | broken |", "|---|---|---|---|---|---|---|"]
        by = defaultdict(list)
        for r in rows:
            if (r["idx"], r["start"]) in ok and pred(r):
                by[(r["start"], r["config"])].append(r)
        for (s, c) in sorted(by, key=lambda k: (["onset", "commit", "name"].index(k[0]), k[1] != "base", k[1])):
            v = by[(s, c)]
            f = lambda p: f"{sum(map(p, v))}/{len(v)}"
            md.append(f"| {s} | {c} | {len(v)} | {f(lambda r: r['gen_tool'] == 'writeInternalLog')} | "
                      f"{f(lambda r: r['gen_tool'] not in (None, 'writeInternalLog', r['orig_tool']))} | {f(lambda r: r['gen_tool'] == r['orig_tool'])} | "
                      f"{f(lambda r: r['gen_tool'] is None)} |")
        md.append("")
    (out / "report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def main():
    mode, seqs, traj, out = sys.argv[1], json.loads(Path(sys.argv[2]).read_text(encoding="utf-8")), Path(sys.argv[3]), Path(sys.argv[4])
    out.mkdir(parents=True, exist_ok=True)
    if mode == "stats":
        return mode_stats(seqs, out)
    if mode == "run":
        return mode_run(seqs, traj, out)
    return mode_report(out)


if __name__ == "__main__":
    main()
