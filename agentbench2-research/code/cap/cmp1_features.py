"""Comparison 1 features (PC, numpy), CIRCUIT.md. For every sample and segment of segs.json, from the capture files on D:
  head_n  [32, 32]   mean over the segment's tokens of each head's write norm
  attn, mlp [32, 2560] mean attention write and MLP write per layer (tier-1 tokens only; their count in n_t1)
  neuron  [32, 9216] mean of every MLP neuron (128-token pieces weighted by overlap with the segment)
  z       [32, 4096] mean of every head's o_proj input (same pieces)
A sample's positions are owned by the sequences before it in sorted order (prefix sharing); the owner of position p is found by
walking down the sorted order from the sample until a sequence whose stored range starts at or below p.
Usage: python cmp1_features.py BENCH CAP_DIR SEGS_JSON OUT_NPZ"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

NL, D, NI, NZ = 32, 2560, 9216, 4096


def e4m3_lut():
    lut = np.zeros(256, np.float32)
    for b in range(256):
        s, e, m = (b >> 7) & 1, (b >> 3) & 15, b & 7
        if e == 15 and m == 7:
            v = np.nan
        elif e == 0:
            v = (m / 8.0) * 2.0 ** -6
        else:
            v = (1 + m / 8.0) * 2.0 ** (e - 7)
        lut[b] = -v if s else v
    return lut


LUT = e4m3_lut()


def deq_sum(q, s, rows):
    """Sum over rows of the block-scaled fp8 vectors: q [T, 32, 2560] uint8, s [T, 32, 20] fp16 -> [32, 2560] float64."""
    out = np.zeros((NL, D), np.float64)
    for c in range(0, len(rows), 128):
        r = rows[c:c + 128]
        x = LUT[q[r]].reshape(len(r), NL, s.shape[-1], -1) * s[r].astype(np.float32)[..., None]
        out += x.reshape(len(r), NL, D).sum(0)
    return out


def main():
    bench, cap, segs_p, out_p = sys.argv[1], Path(sys.argv[2]), sys.argv[3], sys.argv[4]
    samples = json.load(open(segs_p, encoding="utf-8"))[bench]
    import os
    if os.environ.get("CMP_LIMIT"):
        samples = samples[:int(os.environ["CMP_LIMIT"])]
    plan = json.load(open(cap / "plan.json", encoding="utf-8"))
    order = {s: i for i, s in enumerate(plan["order"])}
    start = plan["start"]
    files = {}
    for l in open(cap / "index.jsonl", encoding="utf-8"):
        r = json.loads(l)
        files[r["order"]] = r["files"]
    seg_names = sorted({s[0] for x in samples for s in x["segs"]}, key=lambda n: (n[0] != "r", int(n[1:].split("-")[0]) if n[0] == "r" and n[1].isdigit() else 0, n))
    si = {n: k for k, n in enumerate(seg_names)}
    N, S = len(samples), len(seg_names)
    need = defaultdict(list)
    for a, x in enumerate(samples):
        o = order[x["sid"]]
        chain, hi, k = [], x["len"], o
        while hi > 0 and k >= 0:
            lo = start[k]
            if lo < hi:
                chain.append((k, lo, hi))
                hi = lo
            k -= 1
        for name, s0, s1 in x["segs"]:
            for k, lo, hi in chain:
                u, v = max(lo, s0), min(hi, s1)
                if u < v:
                    need[k].append((a, si[name], u, v))
    missing = [k for k in need if k not in files]
    print(f"{bench}: {N} samples, segments {seg_names}, owner sequences {len(need)}, owners without an index line {len(missing)}", flush=True)
    F = {"head_n": np.zeros((N, S, NL, 32), np.float64), "attn": np.zeros((N, S, NL, D), np.float64), "mlp": np.zeros((N, S, NL, D), np.float64),
         "neuron": np.zeros((N, S, NL, NI), np.float32), "z": np.zeros((N, S, NL, NZ), np.float32)}
    n_tok, n_t1, n_pw = np.zeros((N, S)), np.zeros((N, S)), np.zeros((N, S))
    lost = 0
    for c, (k, iv) in enumerate(sorted(need.items())):
        for name in files.get(k, []):
            p = cap / "pending" / f"{name}.npz"
            if not p.exists():
                lost += 1
                continue
            z = np.load(p)
            pos = z["pos"]
            p0, p1 = int(pos[0]), int(pos[-1]) + 1
            mine = [(a, s, u, v) for a, s, u, v in iv if u < p1 and v > p0]
            if not mine:
                continue
            hn = z["head_n"]
            t1p = z["t1_pos"] if "t1_pos" in z.files else None
            if t1p is not None:
                aq, as_, mq, ms = z["attn_q"], z["attn_s"], z["mlp_q"], z["mlp_s"]
            pc, pn, pz = z["piece"], None, None
            for a, s, u, v in mine:
                r = np.nonzero((pos >= u) & (pos < v))[0]
                if len(r):
                    F["head_n"][a, s] += hn[r].astype(np.float64).sum(0)
                    n_tok[a, s] += len(r)
                if t1p is not None:
                    r1 = np.nonzero((t1p >= u) & (t1p < v))[0]
                    if len(r1):
                        F["attn"][a, s] += deq_sum(aq, as_, r1)
                        F["mlp"][a, s] += deq_sum(mq, ms, r1)
                        n_t1[a, s] += len(r1)
                ov = np.minimum(pc[:, 1], v) - np.maximum(pc[:, 0], u)
                w = np.nonzero(ov > 0)[0]
                if len(w):
                    if pn is None:
                        pn, pz = z["piece_neuron_mean"], z["piece_z_mean"]
                    wt = ov[w].astype(np.float32)
                    F["neuron"][a, s] += np.einsum("p,pld->ld", wt, pn[w].astype(np.float32))
                    F["z"][a, s] += np.einsum("p,pld->ld", wt, pz[w].astype(np.float32))
                    n_pw[a, s] += wt.sum()
        if c % 50 == 0:
            print(f"  owner {c + 1}/{len(need)}", flush=True)
    with np.errstate(invalid="ignore", divide="ignore"):
        F["head_n"] /= n_tok[..., None, None]
        F["attn"] /= n_t1[..., None, None]
        F["mlp"] /= n_t1[..., None, None]
        F["neuron"] /= n_pw[..., None, None].astype(np.float32)
        F["z"] /= n_pw[..., None, None].astype(np.float32)
    meta = [{k: v for k, v in x.items() if k != "segs"} for x in samples]
    np.savez(out_p, seg_names=np.array(seg_names), n_tok=n_tok, n_t1=n_t1, n_pw=n_pw, meta=np.array(json.dumps(meta)),
             head_n=F["head_n"].astype(np.float32), attn=F["attn"].astype(np.float32), mlp=F["mlp"].astype(np.float32),
             neuron=F["neuron"].astype(np.float16), z=F["z"].astype(np.float16))
    print(f"saved {out_p}; files missing {lost}; segment token counts (median) " +
          ", ".join(f"{n} {np.nanmedian(np.where(n_tok[:, k] > 0, n_tok[:, k], np.nan)):.0f}" for n, k in si.items()), flush=True)


if __name__ == "__main__":
    main()
