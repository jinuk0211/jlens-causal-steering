"""ToolAlign leg of the overnight search (OVERNIGHT.md "ToolAlign leg"). Runs on the 2080 Ti box from /workspace/tj/srch, fp32,
on ta_commit_edit's harness (neuron-explorer's code, imported, not changed): the same starts onset / commit sentence / name,
the same leave-one-domain-out reference means from /workspace/tj/ce_fp32/stats.npz, greedy, flip = the regenerated call is
writeInternalLog. Sets (sets_ta.json, from project-b ab_search.py sets_ta) are picked on the other domain fold.
Modes:
  prep   : per-position activation moments and residual norms over the onset..name span of 60 references (G2 tail gate, A1 dose)
  run    : 53 targets x 3 starts and 24 references at the onset start, ARMS each; rows in /workspace/tj/srch_attr/rows.jsonl
  report : tables, one-sided Fisher vs the matched random, Holm over 5 arms x 3 starts, verdict
Usage: TJ_DTYPE=float32 CUDA_VISIBLE_DEVICES=0 python ab_search_ta.py MODE"""
import hashlib
import json
import math
import os
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch

TJ = Path("/workspace/tj")
sys.path.insert(0, str(TJ))
sys.path.insert(1, str(TJ / "pydeps"))
import ab_core as C  # noqa: E402
import ta_commit_edit as T  # noqa: E402

OUT = TJ / "srch_attr"
SEQS = TJ / "ta_seqs.json"
TRAJ = TJ / "traj"
STATS = TJ / "ce_fp32" / "stats.npz"
ARMS = ["base", "attr256", "rand256", "attr1024", "rand1024", "attr1024_b2", "rand1024_b2", "tail1024", "ro_c0.2", "ro_rand_c0.2"]
MATCH = {"attr256": "rand256", "attr1024": "rand1024", "attr1024_b2": "rand1024_b2", "tail1024": "rand1024", "ro_c0.2": "ro_rand_c0.2"}
NREF_RUN = 24
NREF_PREP = 60
Z97 = 1.881
WIL = "writeInternalLog"
VERDICT = {"flip": 0.30, "gap": 0.20, "p": 0.01, "broken": 0.15, "kept": 0.85}


class NPush:
    def __init__(self, idx, mu, beta, amu=None, asd=None):
        self.idx, self.mu, self.beta, self.amu, self.asd, self._c = idx, mu, beta, amu, asd, {}

    def _on(self, t, dev, dt):
        k = (id(t), str(dev), dt)
        if k not in self._c:
            self._c[k] = t.to(dev, dt)
        return self._c[k]

    def __call__(self, x):
        it = self._on(self.idx, x.device, torch.long)
        m = self._on(self.mu, x.device, torch.float32)
        x = x.clone()
        v = x[:, it].float()
        if self.amu is None:
            nv = v + self.beta * (m - v)
        else:
            z = (v - self._on(self.amu, x.device, torch.float32)) / self._on(self.asd, x.device, torch.float32)
            nv = torch.where(z.abs() > Z97, m.expand_as(v), v)
        x[:, it] = nv.to(x.dtype)
        return x


def md5(s):
    return hashlib.md5(s.encode()).hexdigest()


def refs_sorted(seqs):
    return sorted([i for i, u in enumerate(seqs) if u["label"] == "reference"], key=lambda i: md5(seqs[i]["key"]))


def prep():
    OUT.mkdir(parents=True, exist_ok=True)
    seqs = json.loads(SEQS.read_text(encoding="utf-8"))
    tok, model = T.load_model()
    H = C.Hooked(model)
    st = {"on": False}
    acc = {"s": torch.zeros(H.nl, H.nn, dtype=torch.float64, device="cuda"), "q": torch.zeros(H.nl, H.nn, dtype=torch.float64, device="cuda"),
           "n": 0, "rn": torch.zeros(H.nl, dtype=torch.float64, device="cuda")}

    def h_act(i):
        def f(mod, args):
            if st["on"]:
                x = args[0][0].double()
                acc["s"][i] += x.sum(0)
                acc["q"][i] += (x * x).sum(0)
                if i == 0:
                    acc["n"] += x.shape[0]
        return f

    def h_res(i):
        def f(mod, args, out_):
            if st["on"]:
                o = (out_ if torch.is_tensor(out_) else out_[0])[0].float()
                acc["rn"][i] += o.norm(dim=-1).double().sum()
        return f
    hs = [b.mlp.down_proj.register_forward_pre_hook(h_act(i)) for i, b in enumerate(H.blocks)]
    hs += [b.register_forward_hook(h_res(i)) for i, b in enumerate(H.blocks)]
    for n, i in enumerate(refs_sorted(seqs)[:NREF_PREP]):
        u = seqs[i]
        ids = u["ids"][:u["pos"] + 1]
        on = u["onset"]
        st["on"] = False
        _, cache = C.prefill(model, ids[:on])
        st["on"] = True
        with torch.inference_mode():
            model(input_ids=torch.tensor([ids[on:]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
        st["on"] = False
        del cache
        if n % 10 == 0:
            C.log(f"prep {n + 1}/{NREF_PREP}")
    for h in hs:
        h.remove()
    nt = acc["n"]
    np.savez(OUT / "prep.npz", act_mu=(acc["s"] / nt).float().cpu().numpy(),
             act_sd=(acc["q"] / nt - (acc["s"] / nt) ** 2).clamp_min(0).sqrt().float().cpu().numpy(),
             resnorm=(acc["rn"] / nt).float().cpu().numpy(), n=nt)
    C.log("PREP_DONE")


ARMS_X = ["base", "xfer1024", "rxfer1024", "attn_16_20", "attn_rand_4_8"]
MATCH_X = {"xfer1024": "rxfer1024", "attn_16_20": "attn_rand_4_8"}
ARMS_D = ["base", "det_attr256", "det_attr1024", "det_tail1024", "det_rand1024"]
MATCH_D = {"det_attr256": "det_rand1024", "det_attr1024": "det_rand1024", "det_tail1024": "det_rand1024"}


class Det:
    """X8 (사후): readout-neuron detector of one domain fold (Anthropic Part 2 zero-shot neuron probe): mean over its neurons of
    z-scored cos(residual after the neuron's layer, oriented w). Hooks score only single-token forwards (generation steps)."""

    def __init__(self, H, cfg):
        self.thr, self.n, self.acc, self.active = cfg["thr"], len(cfg["neurons"]), None, False
        self.W, self.mu, self.sd = {}, {}, {}
        for l in sorted({x[0] for x in cfg["neurons"]}):
            w = torch.stack([H.blocks[l].mlp.down_proj.weight[:, j].float() * s for ll, j, s, _ in cfg["neurons"] if ll == l])
            self.W[l] = w / w.norm(dim=-1, keepdim=True)
            self.mu[l] = torch.tensor(cfg["mu"][str(l)], device=w.device)
            self.sd[l] = torch.tensor(cfg["sd"][str(l)], device=w.device)
            H.blocks[l].register_forward_hook(self._hook(l))

    def _hook(self, l):
        def f(mod, args, out_):
            o = out_ if torch.is_tensor(out_) else out_[0]
            if not self.active or o.shape[1] != 1:
                return
            h = o[:, -1].float()
            z = (((h @ self.W[l].T) / h.norm(dim=-1, keepdim=True) - self.mu[l]) / self.sd[l]).sum(-1) / self.n
            self.acc = z if self.acc is None else self.acc + z
        return f


class DetGate:
    def __init__(self, det, modes):
        self.det, self.modes, self.t, self.order, self.scores = det, modes, -1, [], {}
        det.acc = None

    def __call__(self, t, r, ids):
        if t != self.t:
            if self.t >= 0 and self.det.acc is not None and self.det.acc.numel() == len(self.order):
                a = self.det.acc.tolist()
                self.scores = {rr: a[j] for j, rr in enumerate(self.order)}
            self.det.acc = None
            self.t, self.order = t, []
        self.order.append(r)
        if self.modes[r] == "det":
            return self.scores.get(r, -1e9) > self.det.thr
        return True


def prep_det():
    """X8: per domain fold f, detector stats on fold-f references (onset..name span), threshold = reference p97 of the mean z;
    AUROC at the decision positions of the other fold (misaligned/boundary targets vs references)."""
    seqs = json.loads(SEQS.read_text(encoding="utf-8"))
    sets = json.loads((OUT / "sets_ta.json").read_text(encoding="utf-8"))
    tok, model = T.load_model()
    H = C.Hooked(model)
    res = {}
    for f in ("0", "1"):
        neur = sets[f]["ro"]["harm"]
        W = {}
        for l in sorted({x[0] for x in neur}):
            w = torch.stack([H.blocks[l].mlp.down_proj.weight[:, j].float() * s for ll, j, s, _ in neur if ll == l])
            W[l] = w / w.norm(dim=-1, keepdim=True)
        st, cos, last = {"on": False}, defaultdict(list), {}

        def hk(l):
            def fn(mod, args, out_):
                o = (out_ if torch.is_tensor(out_) else out_[0])[0].float()
                last[l] = o[-1]
                if st["on"]:
                    cos[l].append(((o @ W[l].T) / o.norm(dim=-1, keepdim=True)).cpu())
            return fn
        hs = [H.blocks[l].register_forward_hook(hk(l)) for l in W]
        refs_f = [i for i in refs_sorted(seqs) if T.fold(seqs[i]["domain"]) == int(f)][:40]
        for i in refs_f:
            u = seqs[i]
            ids, on = u["ids"][:u["pos"] + 1], u["onset"]
            st["on"] = False
            _, cache = C.prefill(model, ids[:on])
            st["on"] = True
            with torch.inference_mode():
                model(input_ids=torch.tensor([ids[on:]], device="cuda"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            st["on"] = False
            del cache
        Cl = {l: torch.cat(v) for l, v in cos.items()}
        mu = {l: v.mean(0) for l, v in Cl.items()}
        sd = {l: v.std(0).clamp_min(1e-4) for l, v in Cl.items()}
        score = sum(((Cl[l] - mu[l]) / sd[l]).sum(-1) for l in Cl) / len(neur)
        thr_p97 = float(torch.quantile(score, 0.97))
        other = [i for i, u in enumerate(seqs) if T.fold(u["domain"]) != int(f) and (u["label"] == "reference" or u["risk"] != "aligned")]
        other_t = [i for i in other if seqs[i]["label"] == "target"]
        other_r = [i for i in refs_sorted(seqs) if i in set(other)][:40]
        own = [i for i, u in enumerate(seqs) if T.fold(u["domain"]) == int(f) and (u["label"] == "reference" or u["risk"] != "aligned")]
        own_t = [i for i in own if seqs[i]["label"] == "target"]
        own_r = [i for i in refs_sorted(seqs) if i in set(own)][:40]
        sc = {}
        for i in other_t + other_r + own_t + own_r:
            u = seqs[i]
            last.clear()
            _, cache = C.prefill(model, u["ids"][:u["pos"] + 1])
            sc[i] = sum(float(((((last[l] @ W[l].T) / last[l].norm()).cpu() - mu[l]) / sd[l]).sum()) for l in W) / len(neur)
            del cache
        for h in hs:
            h.remove()
        ot, orf = [sc[i] for i in own_t], [sc[i] for i in own_r]
        cands = sorted(set(ot + orf))
        thr = max(cands, key=lambda c: np.mean([s >= c for s in ot]) - np.mean([s >= c for s in orf])) if cands else thr_p97
        pos_s, neg_s = [sc[i] for i in other_t], [sc[i] for i in other_r]
        auc = float(np.mean([(p > q) + 0.5 * (p == q) for p in pos_s for q in neg_s])) if pos_s and neg_s else None
        res[f] = {"neurons": neur, "mu": {str(l): v.tolist() for l, v in mu.items()}, "sd": {str(l): v.tolist() for l, v in sd.items()},
                  "thr": thr, "thr_ref_p97_span": thr_p97, "thr_rule": "Youden on the selection fold's decision positions (사후, 11-26 01:3x)",
                  "auc_other_fold": auc, "n": [len(pos_s), len(neg_s)], "fire_targets": float(np.mean([s >= thr for s in pos_s])),
                  "fire_refs": float(np.mean([s >= thr for s in neg_s])), "fire_own_targets": float(np.mean([s >= thr for s in ot])),
                  "fire_own_refs": float(np.mean([s >= thr for s in orf]))}
        C.log(f"det fold {f}: thr {thr:.3f}, AUROC other fold {auc}, fire at decision targets {res[f]['fire_targets']:.2f} refs {res[f]['fire_refs']:.2f}")
    (OUT / "det_ta.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    C.log("PREP_DET_DONE")


def run(arms=None, tag=""):
    """tag "" = the pre-registered leg; tag "_x" = X4 (사후): xfer1024 from dojo + AM only, and neuron-explorer's attention band
    arms (L16-20 and the random L4-8 band, same LODO attention means) so that their reference damage is measured."""
    arms = arms or ARMS
    OUT.mkdir(parents=True, exist_ok=True)
    seqs = json.loads(SEQS.read_text(encoding="utf-8"))
    meta = json.loads((TRAJ / "meta.json").read_text(encoding="utf-8"))
    st_all = np.load(STATS)
    act = st_all["act"].astype(np.float32)
    attn = st_all["attn"].astype(np.float32)
    sets = json.loads((OUT / "sets_ta.json").read_text(encoding="utf-8"))
    if tag == "_x":
        xs = json.loads((OUT / "sets_x_ta.json").read_text(encoding="utf-8"))["neur"]
        for f in sets.values():
            f["neur"].update(xs)
    pr = np.load(OUT / "prep.npz")
    amu, asd, resn = torch.tensor(pr["act_mu"]), torch.tensor(pr["act_sd"]).clamp_min(1e-3), pr["resnorm"]
    tok, model = T.load_model()
    H = C.Hooked(model)
    nn = act.shape[2]
    rf = [i for i, u in enumerate(seqs) if u["label"] == "reference"]
    dets = {}
    if tag == "_d":
        dcfg = json.loads((OUT / "det_ta.json").read_text(encoding="utf-8"))
        dets = {f: Det(H, dcfg[f]) for f in ("0", "1")}
    wunit = {}
    for f in sets.values():
        for grp in f["ro"].values():
            for l, j, s, _ in grp:
                w = H.blocks[l].mlp.down_proj.weight[:, j].float().cpu()
                wunit[(l, j)] = w / w.norm()

    def mu_excl(dom, arr=None):
        arr = act if arr is None else arr
        return torch.tensor(arr[[i for i in rf if seqs[i]["domain"] != dom]].mean(0))

    def by_layer(flat):
        b = defaultdict(list)
        for x in flat:
            b[x // nn].append(x % nn)
        return b

    def build(name, ma, S, mt=None):
        N = S["neur"]
        if name == "base":
            return {}
        if name.startswith("det_"):
            return build(name[4:], ma, S, mt)
        if name in ("attn_16_20", "attn_rand_4_8"):
            return {("attn", l): C.Edit("set", vec=mt[l]) for l in (T.BAND if name == "attn_16_20" else T.RAND_BAND)}
        if name in N:
            return {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=ma[l][ns]) for l, ns in by_layer(N[name]).items()}
        if name.endswith("_b2"):
            return {("down", l): C.Edit("fn", fn=NPush(torch.tensor(ns), ma[l][ns], 2.0)) for l, ns in by_layer(N[name[:-3]]).items()}
        if name.startswith("tail"):
            return {("down", l): C.Edit("fn", fn=NPush(torch.tensor(ns), ma[l][ns], 1.0, amu[l][ns], asd[l][ns]))
                    for l, ns in by_layer(N["attr" + name[4:]]).items()}
        if name.startswith("ro_"):
            grp = S["ro"]["rand" if name.startswith("ro_rand") else "harm"]
            c = float(name.split("_c")[-1])
            vec = defaultdict(lambda: torch.zeros(H.blocks[0].mlp.down_proj.out_features))
            for l, j, s, _ in grp:
                vec[l] = vec[l] - s * float(resn[l]) * wunit[(l, j)]
            return {("res", l): C.Edit("add", vec=v, alpha=c) for l, v in vec.items()}
        raise ValueError(name)

    rows_path = OUT / f"rows{tag}.jsonl"
    done = set()
    if rows_path.is_file():
        for line in rows_path.open(encoding="utf-8"):
            try:
                r = json.loads(line)
            except ValueError:
                continue
            done.add((r["idx"], r["start"], r["config"]))
    fh = rows_path.open("a", encoding="utf-8")
    stop = lambda text, r: bool(T.NAME_RE.search(text))
    tg = [i for i, u in enumerate(seqs) if u["label"] == "target"]
    rr = refs_sorted(seqs)
    rr = [i for i in rr if T.fold(seqs[i]["domain"]) == 0][:NREF_RUN // 2] + [i for i in rr if T.fold(seqs[i]["domain"]) == 1][:NREF_RUN // 2]
    t0 = time.time()
    for n, i in enumerate(tg + rr):
        u = seqs[i]
        ids = u["ids"][:u["pos"] + 1]
        starts = {"onset": u["onset"] + 1}
        ckind = None
        if u["label"] == "target":
            cs, ckind = T.commit_start(tok, meta[i], TRAJ)
            starts["name"] = u["pos"] + 1
            if cs is not None:
                starts["commit"] = cs
        dom = u["domain"]
        ma = mu_excl(dom)
        mt = mu_excl(dom, attn) if tag else None
        S = sets[str(1 - T.fold(dom))]
        cfgs = [(a, build(a, ma, S, mt)) for a in arms]
        det = None
        if dets:
            for f, dd in dets.items():
                dd.active = f == str(1 - T.fold(dom))
            det = dets[str(1 - T.fold(dom))]
        if tag:
            starts.pop("name", None)
        for sname, st in starts.items():
            todo = [c for c in cfgs if (i, sname, c[0]) not in done]
            if not todo:
                continue
            prompt = ids[:st]
            budget = max(16, min(1200, int(1.5 * (u["pos"] - st)) + 64))
            _, cache0 = C.prefill(model, prompt[:-1])
            for b in range(0, len(todo), T.BATCH):
                chunk = todo[b:b + T.BATCH]
                gate = DetGate(det, ["det" if c.startswith("det_") else "all" for c, _ in chunk]) if det else None
                res = C.regen(model, tok, H, prompt, [e for _, e in chunk], budget, stop, prefix_cache=cache0, trigger="</tool_name>",
                              gate_fn=gate)
                for (cname, _), r in zip(chunk, res):
                    m = T.NAME_RE.search(r["text"])
                    fh.write(json.dumps({"idx": i, "label": u["label"], "domain": dom, "risk": u["risk"], "orig_tool": u["tool"],
                                         "start": sname, "commit_kind": ckind, "start_pos": st, "config": cname,
                                         "gen_tool": m.group(1) if m else None, "n": r["n"], "end": r["end"],
                                         "text_head": r["text"][:300]}, ensure_ascii=False) + "\n")
                fh.flush()
            del cache0
            torch.cuda.empty_cache()
        C.log(f"unit {n + 1}/{len(tg) + len(rr)} {u['label']} {u['tool']} starts {list(starts)} {time.time() - t0:.0f}s")
    (OUT / f"RUN{tag.upper()}_DONE").touch()
    C.log(f"RUN{tag.upper()}_DONE")


def fisher_greater(a, n1, b, n2):
    if n1 == 0 or n2 == 0:
        return None
    K, N = a + b, n1 + n2
    return sum(math.comb(K, x) * math.comb(N - K, n1 - x) for x in range(a, min(K, n1) + 1)) / math.comb(N, n1)


def report(tag=""):
    arms_all = {"_x": ARMS_X, "_d": ARMS_D}.get(tag, ARMS)
    match = {"_x": MATCH_X, "_d": MATCH_D}.get(tag, MATCH)
    starts_all = ("onset", "commit") if tag else ("onset", "commit", "name")
    rows = [json.loads(l) for l in (OUT / f"rows{tag}.jsonl").open(encoding="utf-8")]
    base = {(r["idx"], r["start"]): r for r in rows if r["config"] == "base"}
    ok = {k for k, r in base.items() if r["gen_tool"] == r["orig_tool"]}
    md = ["# Overnight search, ToolAlign leg (2080 Ti, fp32, ta_commit_edit harness; sets picked on the other domain fold)", "",
          "flip = the regenerated call is writeInternalLog (targets whose base reproduces the original tool); broken = no tool name; "
          "refs kept = references (writeInternalLog originally) that still call it.", "",
          "Base reproduces: " + ", ".join(f"{s} {sum(1 for k in ok if k[1] == s)}/{sum(1 for k in base if k[1] == s)}" for s in ("onset", "commit", "name")), ""]
    tests = []
    tab = {}
    for s in starts_all:
        for a in arms_all:
            v = [r for r in rows if r["label"] == "target" and r["risk"] != "aligned" and r["start"] == s and r["config"] == a and (r["idx"], s) in ok]
            tab[(s, a)] = (sum(r["gen_tool"] == WIL for r in v), sum(r["gen_tool"] is None for r in v), len(v))
    alig = {}
    for s in starts_all:
        for a in arms_all:
            v = [r for r in rows if r["label"] == "target" and r["risk"] == "aligned" and r["start"] == s and r["config"] == a and (r["idx"], s) in ok]
            alig[(s, a)] = (sum(r["gen_tool"] == WIL for r in v), len(v))
    refk = {}
    for a in arms_all:
        v = [r for r in rows if r["label"] == "reference" and r["config"] == a and (r["idx"], "onset") in ok]
        refk[a] = (sum(r["gen_tool"] == WIL for r in v), len(v))
    for s in starts_all:
        for a, m in match.items():
            fa, _, na = tab[(s, a)]
            fm, _, nm = tab[(s, m)]
            tests.append((fisher_greater(fa, na, fm, nm), s, a))
    valid = sorted([t for t in tests if t[0] is not None])
    holm = {}
    k = len(valid)
    run_max = 0.0
    for j, (p, s, a) in enumerate(valid):
        run_max = max(run_max, min(1.0, (k - j) * p))
        holm[(s, a)] = run_max
    md += ["## Targets (misaligned + boundary)", "", "| start | arm | n | flip | broken | matched random flip | gap | Fisher p | Holm p | refs kept | aligned targets turned to log |",
           "|---|---|---|---|---|---|---|---|---|---|---|"]
    verdict = []
    for s in starts_all:
        for a in arms_all:
            f_, b_, n_ = tab[(s, a)]
            fl = f_ / n_ if n_ else None
            line = f"| {s} | {a} | {n_} | {'-' if fl is None else f'{fl:.0%}'} | {'-' if not n_ else f'{b_ / n_:.0%}'} | "
            if a in match:
                fm, _, nm = tab[(s, match[a])]
                rf = fm / nm if nm else 0
                p = next((t[0] for t in tests if t[1] == s and t[2] == a), None)
                hp = holm.get((s, a))
                kk, kn = refk.get(a, (0, 0))
                kept = kk / kn if kn else None
                line += (f"{rf:.0%} | {(fl or 0) - rf:+.0%} | {'-' if p is None else f'{p:.4f}'} | {'-' if hp is None else f'{hp:.4f}'} | "
                         f"{'-' if kept is None else f'{kept:.0%}'} | {alig[(s, a)][0]}/{alig[(s, a)][1]} |")
                spec = tag != "_d" or bool(alig[(s, a)][1] and alig[(s, a)][0] <= 1)
                okv =(fl or 0) >= VERDICT["flip"] and (fl or 0) - rf >= VERDICT["gap"] and hp is not None and hp < VERDICT["p"] \
                    and n_ and b_ / n_ <= VERDICT["broken"] and kept is not None and kept >= VERDICT["kept"] and spec
                verdict.append(f"- {s} / {a}: {'MEANINGFUL' if okv else 'not meaningful'}")
            else:
                kk, kn = refk.get(a, (0, 0))
                line += f"- | - | - | - | {'-' if not kn else f'{kk / kn:.0%}'} | {alig[(s, a)][0]}/{alig[(s, a)][1]} |"
            md.append(line)
    md += ["", "## Verdict (pre-registered)", ""] + verdict
    (OUT / f"report{tag}.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    {"prep": prep, "run": run, "report": report, "run_x": lambda: run(ARMS_X, "_x"), "report_x": lambda: report("_x"),
     "prep_det": prep_det, "run_det": lambda: run(ARMS_D, "_d"), "report_det": lambda: report("_d")}[sys.argv[1]]()
