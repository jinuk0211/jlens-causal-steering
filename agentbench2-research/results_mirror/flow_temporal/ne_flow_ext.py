"""Optional add-on for ne_cases.py: POST /api/ne_flow {"case": N, "out": "name.npz", "k": 16, "chunk": 1024}.
Per-token flow for long cases: the model runs in CHUNK-token pieces with its cache (no [L, T, N] array), a temporary
down_proj pre-hook per layer keeps the top-K neurons by |score| at every token (sign kept; score as server.score_text).
Saved under NE_DUMP_DIR as flow_idx [T, L, K] int16, flow_val [T, L, K] float16. Holds rt.lock for the whole run.
Use from ne_cases.py, after its routes are set:  import ne_flow_ext; ne_flow_ext.register(S, SEQS)"""
import asyncio
import os

import numpy as np
from fastapi import Request


def register(S, SEQS):
    async def flow(req: Request):
        b = await req.json()
        u = SEQS[int(b["case"])]
        ids = list(u["ids"][:u["pos"] + 1])
        out = os.path.join(os.environ.get("NE_DUMP_DIR", "/workspace/tj/ne_x/dump"), os.path.basename(b["out"]))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        k, chunk = int(b.get("k", 16)), int(b.get("chunk", 1024))

        def work():
            import torch
            S.rt.ensure_loaded()
            with S.rt.lock, torch.inference_mode():
                sc = np.load(S.ACT_SCALE)
                ps = torch.tensor(np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3)), dtype=torch.float32, device="cuda")
                ng = torch.tensor(np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3)), dtype=torch.float32, device="cuda")
                layers = S.rt.lm.layers
                T, L = len(ids), len(layers)
                fi = torch.zeros((T, L, k), dtype=torch.int16)
                fv = torch.zeros((T, L, k), dtype=torch.float16)
                cur = {"s0": 0}

                def mk(i):
                    def f(mod, args):
                        x = args[0][0].float()
                        s = torch.where(x >= 0, x / ps[i], -(x / ng[i]))
                        idx = s.abs().topk(k, dim=-1).indices
                        s0 = cur["s0"]
                        fi[s0:s0 + x.shape[0], i] = idx.to(torch.int16).cpu()
                        fv[s0:s0 + x.shape[0], i] = s.gather(1, idx).half().cpu()
                    return f
                hs = [lay.mlp.down_proj.register_forward_pre_hook(mk(i)) for i, lay in enumerate(layers)]
                try:
                    cache = None
                    for s0 in range(0, T, chunk):
                        cur["s0"] = s0
                        o = S.rt.lm(input_ids=torch.tensor([ids[s0:s0 + chunk]], device=S.rt.dev), past_key_values=cache, use_cache=True)
                        cache = o.past_key_values
                    del cache, o
                finally:
                    for h in hs:
                        h.remove()
                fi[0], fv[0] = 0, 0
                torch.cuda.empty_cache()
            np.savez_compressed(out, flow_idx=fi.numpy(), flow_val=fv.numpy())
            return {"out": out, "T": T}
        return await asyncio.to_thread(work)

    routes = S.app.router.routes
    S.app.add_api_route("/api/ne_flow", flow, methods=["POST"])
    routes.insert(0, routes.pop())
