"""Broad J-lens mining over every failure type, every layer, every logged position (CPU, PC; 278 f_detect episodes).

Feature = (position group, layer, token) present in the J-lens readout of some position in the window.
  groups: C = user / tool context tokens (top-30), A = agent header + generated tokens (top-30), D = decision points (top-100);
  layer 0-31, plus layer 32 = "this token at any layer" (cross-layer).
  Surface baseline: the actual tokens at the same positions (group, token), no lens.
Windows:
  E1  whole episode, failed (43) vs passed (235). Diagnostic only: it includes the failing actions themselves.
  E2  before the first bad write (unneeded transfer / wrong args / unexpected write; 30 failed episodes): turns t*-3 .. t*,
      everything up to the decision point of t* (the bad action itself excluded); controls = good write turns of the same
      tools in passed episodes, same window.
  E3  last 3 agent turns, failed episodes with no bad write (missing write / NL; 13) vs passed episodes (235).
Selection inside the training folds only (task-grouped 5-fold, mine.fold_of): candidate features with df >= 3 over all events
(label-free); per fold, the top-K features by smoothed log ratio in each direction (K = 20 / 100 / 500); score = # failure
features present - # success features present. Out-of-fold AUC with a task-cluster bootstrap CI; for E2 also the within-tool AUC.
Output: mining/broad_mine.md, broad_mine.json
"""
import gzip
import json
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import mine

HERE = Path(__file__).resolve().parent
TOPK = HERE.parent.parent / "tau2-topk-20261119"
TMP = HERE / "broad_tmp"
V = 248320
NL = 33
READS = ("get_", "find_", "list_", "search_", "calculate", "think")
KS = (20, 100, 500)


def enc_lens(group, topk):
    n = topk.shape[0]
    if n == 0:
        return np.zeros(0, np.int64)
    L = np.arange(topk.shape[1], dtype=np.int64)[None, :, None]
    t = topk.astype(np.int64)
    per_layer = ((group * NL + L) * V + t).ravel()
    any_layer = ((group * NL + 32) * V + t).ravel()
    return np.unique(np.concatenate([per_layer, any_layer]))


def enc_surface(group, toks):
    return np.unique(group * V + toks.astype(np.int64))


def window_codes(z, turns_keep, upto_turn=None, include_gen_of_last=True):
    at, aseg = z["agent_turn"], z["agent_seg"]
    ct = z["ctx_turn"]
    keep_c = np.isin(ct, turns_keep)
    keep_a = np.isin(at, turns_keep) & (aseg != 3)
    if upto_turn is not None:
        keep_a &= ~((at == upto_turn) & (aseg == 4))
    dec_keep = np.isin(z["dec_turn"], turns_keep)
    lens = np.unique(np.concatenate([enc_lens(0, z["ctx_topk_jlens"][keep_c]), enc_lens(1, z["agent_topk_jlens"][keep_a]),
                                     enc_lens(2, z["dec_ids_jlens"][dec_keep])]))
    surf = np.unique(np.concatenate([enc_surface(0, z["ctx_tok"][keep_c]), enc_surface(1, z["agent_tok"][keep_a])]))
    return lens, surf


def auc(s, y):
    return mine.auc(np.asarray(s, float), np.asarray(y))


def cluster_ci(s, y, g, rng, B=1000):
    groups = sorted(set(g))
    idx = {k: np.nonzero(np.array(g) == k)[0] for k in groups}
    vals = []
    for _ in range(B):
        pick = rng.choice(len(groups), len(groups))
        ii = np.concatenate([idx[groups[p]] for p in pick])
        a = auc(np.asarray(s)[ii], np.asarray(y)[ii])
        if a is not None:
            vals.append(a)
    return [round(float(np.percentile(vals, 2.5)), 3), round(float(np.percentile(vals, 97.5)), 3)] if vals else None


def run_analysis(name, events, md, res, voc, rng):
    y = np.array([e["y"] for e in events])
    groups = np.array([e["group"] for e in events])
    folds = np.array([mine.fold_of(g) for g in groups])
    out = {}
    for kind in ("lens", "surf"):
        acc_c, acc_k = np.zeros(0, np.int64), np.zeros(0, np.int64)
        paths = [e[kind] for e in events]
        for b in range(0, len(paths), 30):
            u, c = np.unique(np.concatenate([np.load(p) for p in paths[b:b + 30]]), return_counts=True)
            allc = np.concatenate([acc_c, u])
            allk = np.concatenate([acc_k, c])
            order = np.argsort(allc, kind="stable")
            allc, allk = allc[order], allk[order]
            acc_c, start = np.unique(allc, return_index=True)
            acc_k = np.add.reduceat(allk, start)
            del allc, allk, order, u, c
        cand = acc_c[acc_k >= 3]
        del acc_c, acc_k
        idx = []
        for p in paths:
            s = np.load(p)
            idx.append(np.searchsorted(cand, s[np.isin(s, cand, assume_unique=True)]).astype(np.int32))
        oof = {k: np.zeros(len(y)) for k in KS}
        picked = Counter()
        for f in range(mine.NFOLD):
            tr, te = np.nonzero(folds != f)[0], np.nonzero(folds == f)[0]
            if len(te) == 0 or len(set(y[tr].tolist())) < 2:
                continue
            npos, nneg = int(y[tr].sum()), int((1 - y[tr]).sum())
            dpos = np.bincount(np.concatenate([idx[i] for i in tr if y[i] == 1]), minlength=len(cand))
            dneg = np.bincount(np.concatenate([idx[i] for i in tr if y[i] == 0]), minlength=len(cand))
            lr = np.log((dpos + 0.5) / (npos + 1)) - np.log((dneg + 0.5) / (nneg + 1))
            okp = dpos >= 3
            okn = dneg >= 3
            for k in KS:
                pos_sel = np.where(okp)[0][np.argsort(-lr[okp])[:k]]
                neg_sel = np.where(okn)[0][np.argsort(lr[okn])[:k]]
                pmask = np.zeros(len(cand), bool)
                pmask[pos_sel] = True
                nmask = np.zeros(len(cand), bool)
                nmask[neg_sel] = True
                for i in te:
                    oof[k][i] = pmask[idx[i]].sum() - nmask[idx[i]].sum()
                if k == 100 and kind == "lens":
                    picked.update(cand[pos_sel].tolist())
        for k in KS:
            out[f"{kind}_K{k}"] = {"auc": auc(oof[k], y), "ci": cluster_ci(oof[k], y, groups, rng)}
            if "tool" in events[0]:
                tools = np.array([e["tool"] for e in events])
                within = []
                for t in sorted(set(tools.tolist())):
                    m = tools == t
                    if len(set(y[m].tolist())) == 2:
                        a = auc(oof[k][m], y[m])
                        within.append((a, int(m.sum())))
                out[f"{kind}_K{k}"]["within_tool"] = round(sum(a * n for a, n in within) / max(sum(n for _, n in within), 1), 3) if within else None
            out[f"{kind}_K{k}_scores"] = oof[k].tolist()
        if kind == "lens":
            out["stable_failure_features"] = []
            for code, cnt in picked.most_common(40):
                g, rest = divmod(code, NL * V)
                layer, tok = divmod(rest, V)
                out["stable_failure_features"].append({"group": "CAD"[g], "layer": "any" if layer == 32 else int(layer),
                                                       "word": voc[tok], "folds": cnt})
    res[name] = {k: v for k, v in out.items() if not k.endswith("_scores")}
    res[name]["n_pos"], res[name]["n_neg"] = int(y.sum()), int((1 - y).sum())
    md += [f"## {name}: positives {int(y.sum())}, negatives {int((1 - y).sum())}", "",
           "| features | K | AUC | 95% task-cluster CI | within-tool AUC |", "|---|---|---|---|---|"]
    for kind, lab in (("lens", "J-lens (group, layer, word)"), ("surf", "surface tokens only (no lens)")):
        for k in KS:
            o = out[f"{kind}_K{k}"]
            md.append(f"| {lab} | {k} | {o['auc'] if o['auc'] is None else round(o['auc'], 3)} | {o['ci']} | {o.get('within_tool', '-')} |")
    md += ["", "J-lens failure features picked in the most folds (K = 100): "
           + "; ".join(f"{f['group']}/L{f['layer']}/{f['word']!r}×{f['folds']}" for f in out["stable_failure_features"][:25]), ""]


def main():
    t0 = time.time()
    rng = np.random.default_rng(3)
    voc = json.loads(gzip.open(HERE / "vocab.json.gz", "rt", encoding="utf-8").read())
    nl = json.loads((HERE.parent / "nl_judge/nl_verdicts.json").read_text(encoding="utf-8"))["records"]
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir()
    E1, E2, E3 = [], [], []
    files = sorted(TOPK.glob("*.json"))
    for n, jf in enumerate(files):
        m = json.loads(jf.read_text(encoding="utf-8"))
        if m.get("cond") != "f_detect":
            continue
        dom, task, sid = m["domain"], str(m["task"]), m["sim_id"]
        r = float(m["reward"] or 0)
        key = f"f_detect|{dom}|{task}|{sid}"
        nl_flip = False
        if dom == "retail" and key in nl:
            r2 = float(nl[key]["corrected_reward"])
            nl_flip = r >= 1 and r2 < 1
            r = r2
        ok = r >= 1
        group = f"{dom}|{task}"
        z = np.load(jf.with_suffix(".npz"))
        turns = sorted(int(t["turn"]) for t in m["turns"])
        tag = jf.stem
        lens, surf = window_codes(z, turns)
        p1, p2 = TMP / f"{tag}_E1_l.npy", TMP / f"{tag}_E1_s.npy"
        np.save(p1, lens)
        np.save(p2, surf)
        E1.append({"y": int(not ok), "group": group, "lens": p1, "surf": p2})
        bad_turns = [int(t["turn"]) for t in m["turns"] if t["bad"]]
        if not ok and bad_turns:
            ts = bad_turns[0]
            tt = next(t for t in m["turns"] if int(t["turn"]) == ts)
            tool = next((b.split(":")[1] for b in tt["bad"]), "?")
            keep = [t for t in turns if ts - 3 <= t <= ts]
            lens, surf = window_codes(z, keep, upto_turn=ts)
            p1, p2 = TMP / f"{tag}_E2_l.npy", TMP / f"{tag}_E2_s.npy"
            np.save(p1, lens)
            np.save(p2, surf)
            E2.append({"y": 1, "group": group, "tool": tool, "lens": p1, "surf": p2, "kind": tt["bad"][0].split(":")[0]})
        if ok:
            good = [t for t in m["turns"] if t["label"] == "good_write"]
            for j, tt in enumerate(good[:2]):
                ts = int(tt["turn"])
                tool = next((c["name"] for c in tt["calls"] if not c["name"].startswith(READS)), "?")
                keep = [t for t in turns if ts - 3 <= t <= ts]
                lens, surf = window_codes(z, keep, upto_turn=ts)
                p1, p2 = TMP / f"{tag}_E2c{j}_l.npy", TMP / f"{tag}_E2c{j}_s.npy"
                np.save(p1, lens)
                np.save(p2, surf)
                E2.append({"y": 0, "group": group, "tool": tool, "lens": p1, "surf": p2})
        if ok or not bad_turns:
            keep = turns[-3:]
            lens, surf = window_codes(z, keep)
            p1, p2 = TMP / f"{tag}_E3_l.npy", TMP / f"{tag}_E3_s.npy"
            np.save(p1, lens)
            np.save(p2, surf)
            E3.append({"y": int(not ok), "group": group, "lens": p1, "surf": p2, "nl_flip": nl_flip})
        if n % 30 == 0:
            print(f"{n}/{len(files)} {time.time() - t0:.0f}s", flush=True)
    pos_tools = {e["tool"] for e in E2 if e["y"] == 1}
    E2 = [e for e in E2 if e["y"] == 1 or e["tool"] in pos_tools]
    print("events E1", len(E1), "E2", len(E2), Counter(e["y"] for e in E2), "E3", len(E3), Counter(e["y"] for e in E3), flush=True)
    md = ["# Broad J-lens mining: every failure type, all layers, all logged positions (278 f_detect episodes)", "",
          f"E2 positive kinds: {dict(Counter(e['kind'] for e in E2 if e['y'] == 1))}; tools: {dict(Counter(e['tool'] for e in E2 if e['y'] == 1))}", ""]
    res = {}
    for name, ev in (("E1 whole episode (diagnostic, includes the failing actions)", E1),
                     ("E2 three turns before the first bad write, up to its decision point (vs good writes of the same tools)", E2),
                     ("E3 last three turns, failures without a bad write (missing write / NL) vs passed", E3)):
        run_analysis(name, ev, md, res, voc, rng)
        print(f"done {name[:3]} {time.time() - t0:.0f}s", flush=True)
    (HERE / "broad_mine.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    (HERE / "broad_mine.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    shutil.rmtree(TMP)
    print("\n".join(md))
    print(f"BROAD_DONE {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
