"""Check a capture against an unedited from-scratch forward (CIRCUIT.md). For the first N sorted jobs: the residual identity
h[l+1] = h[l] + attn_write[l] + mlp_write[l] (confirms the hook points), the fp8 round trip of the stored writes, the stored
top-32 neurons and head norms, and (for jobs that started from a snapshot) that the snapshot path equals the scratch path.
Usage: python verify.py JOBS.jsonl OUT_DIR [N]"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from capture import Capture, plan, NL  # noqa: E402


def deq(q, s):
    x = torch.from_numpy(q).view(torch.float8_e4m3fn).float()
    xb = x.reshape(*x.shape[:-1], s.shape[-1], -1)
    return (xb * torch.from_numpy(s).float()[..., None]).reshape(x.shape)


def main():
    jobs_p, out = Path(sys.argv[1]), Path(sys.argv[2])
    N = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    dtype = {"bf16": torch.bfloat16, "fp16": torch.float16}[os.environ.get("CAP_DTYPE", "bf16")]
    jobs = [json.loads(l) for l in jobs_p.open(encoding="utf-8")]
    plan(jobs)
    idx = {json.loads(l)["seq"]: json.loads(l) for l in (out / "index.jsonl").open(encoding="utf-8")}
    cap = Capture("cuda", dtype)
    for j in jobs[:N]:
        rec = idx.get(j["sid"])
        if rec is None or not rec["files"]:
            print(j["sid"], "no stored files")
            continue
        ids = j["ids"]
        cap.buf = {}
        with torch.inference_mode():
            o = cap.lm(input_ids=torch.tensor([ids], device="cuda"), output_hidden_states=True, use_cache=False)
        B = cap.buf
        hs = [h[0].float() for h in o.hidden_states]
        res = []
        for l in range(NL - 1):
            r = hs[l + 1] - (hs[l] + B["ao"][l] + B["mo"][l])
            res.append(float(r.norm() / hs[l + 1].norm()))
        print(f"{j['sid']} len {len(ids)} start {rec['start']}: residual identity rel. error max {max(res):.2e} (layers 0-30)")
        e_a, e_m, cos, topag, hn_err, n = [], [], [], [], [], 0
        for name in rec["files"]:
            z = np.load(out / "pending" / (name + ".npz"))
            pos = z["pos"]
            if "attn_q" in z:
                pa = torch.from_numpy(z["t1_pos"]).long().cuda()
                xa = torch.stack([B["ao"][l][pa] for l in range(NL)], 1).cpu()
                xm = torch.stack([B["mo"][l][pa] for l in range(NL)], 1).cpu()
                qa, qm = deq(z["attn_q"], z["attn_s"]), deq(z["mlp_q"], z["mlp_s"])
                e_a.append(float(((qa - xa).norm(dim=-1) / xa.norm(dim=-1).clamp_min(1e-6)).median()))
                e_m.append(float(((qm - xm).norm(dim=-1) / xm.norm(dim=-1).clamp_min(1e-6)).median()))
                cos.append(torch.cat([torch.nn.functional.cosine_similarity(qa, xa, dim=-1).flatten(),
                                      torch.nn.functional.cosine_similarity(qm, xm, dim=-1).flatten()]))
                big = xa.norm(dim=-1) > 0.05 * xa.norm(dim=-1).median()
                cos.append(torch.nn.functional.cosine_similarity(qa, xa, dim=-1)[big])
            pt = torch.from_numpy(pos).long().cuda()
            ti = torch.stack([B["ti"][l][pt] for l in range(NL)], 1).cpu().numpy()
            topag.append(float(np.mean([len(set(a) & set(b)) / 32 for a, b in zip(ti.reshape(-1, 32), z["top_i"].reshape(-1, 32))])))
            hn = torch.stack([B["hn"][l][pt] for l in range(NL)], 1).float().cpu().numpy()
            hn_err.append(np.abs(hn - z["head_n"].astype(np.float32)).ravel() / np.maximum(np.abs(hn).ravel(), 1e-3))
            n += len(pos)
        c = torch.cat(cos).numpy() if cos else np.array([np.nan])
        he = np.concatenate(hn_err)
        print(f"  stored positions {n}: fp8 rel. error median attn {np.median(e_a) if e_a else float('nan'):.3f} mlp {np.median(e_m) if e_m else float('nan'):.3f}, "
              f"cosine p0.1 {np.quantile(c, 0.001):.4f} p1 {np.quantile(c, 0.01):.4f} min {c.min():.4f}; top-32 overlap with scratch {np.mean(topag):.3f}; "
              f"head-norm rel. diff median {np.median(he):.4f} p99 {np.quantile(he, 0.99):.4f} p99.9 {np.quantile(he, 0.999):.4f}")
        del B, o, hs
        torch.cuda.empty_cache()


if __name__ == "__main__":
    main()
