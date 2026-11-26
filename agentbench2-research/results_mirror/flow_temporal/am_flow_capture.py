"""Standalone per-token neuron flow for the agentic-misalignment responses, the same computation as the explorer's
ne_flow_ext (bf16 Qwen3.5-4B rev 851bf6e, Gated DeltaNet torch fallback run in segments, explorer act_scale score:
+ side / max(pos, 0.1 * -neg), - side / |min(neg, -0.1 * pos)|). The model runs over prompt + response in CHUNK-token
pieces with its cache; a down_proj pre-hook per layer keeps the top-K neurons by |score| at every token (sign kept).
Output per case: OUT_DIR/f_am_{condition}_{sample}.npz with flow_idx [T, 32, K] int16, flow_val [T, 32, K] float16.
Order: leaking, murder, blackmail. Resumes (skips existing files); stops when OUT_DIR/STOP exists.
Usage: python am_flow_capture.py CASES_JSON ACT_SCALE_NPZ OUT_DIR [K] [CHUNK]"""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

MODEL, REV = "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def patch_gdn(segment=1024):
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    orig = mq.torch_chunk_gated_delta_rule

    def chunk_seg(query, key, value, g, beta, chunk_size=64, initial_state=None, output_final_state=False,
                  use_qk_l2norm_in_kernel=False, **kw):
        st = None if initial_state is None else initial_state.clone()
        n = query.shape[1]
        if n <= segment:
            return orig(query, key, value, g, beta, chunk_size=chunk_size, initial_state=st, output_final_state=output_final_state,
                        use_qk_l2norm_in_kernel=use_qk_l2norm_in_kernel, **kw)
        outs = []
        for s in range(0, n, segment):
            e = s + segment
            o, st = orig(query[:, s:e], key[:, s:e], value[:, s:e], g[:, s:e], beta[:, s:e], chunk_size=chunk_size,
                         initial_state=st, output_final_state=True, use_qk_l2norm_in_kernel=use_qk_l2norm_in_kernel, **kw)
            outs.append(o)
        return torch.cat(outs, dim=1), (st if output_final_state else None)
    mq.torch_chunk_gated_delta_rule = chunk_seg


def main():
    cases = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    sc = np.load(sys.argv[2])
    out = Path(sys.argv[3])
    out.mkdir(parents=True, exist_ok=True)
    K = int(sys.argv[4]) if len(sys.argv) > 4 else 16
    CH = int(sys.argv[5]) if len(sys.argv) > 5 else 2048
    patch_gdn()
    from transformers import Qwen3_5ForConditionalGeneration
    m = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, revision=REV, dtype=torch.bfloat16, device_map="cuda").eval()
    m.model.visual = None
    lm = m.model.language_model
    torch.cuda.empty_cache()
    ps = torch.tensor(np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3)), dtype=torch.float32, device="cuda")
    ng = torch.tensor(np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3)), dtype=torch.float32, device="cuda")
    st = {}

    def mk(i):
        def f(mod, args):
            x = args[0][0].float()
            s = torch.where(x >= 0, x / ps[i], -(x / ng[i]))
            idx = s.abs().topk(K, dim=-1).indices
            a = st["s0"]
            st["fi"][a:a + x.shape[0], i] = idx.to(torch.int16).cpu()
            st["fv"][a:a + x.shape[0], i] = s.gather(1, idx).half().cpu()
        return f
    for i, lay in enumerate(lm.layers):
        lay.mlp.down_proj.register_forward_pre_hook(mk(i))
    order = {"leaking": 0, "murder": 1, "blackmail": 2}
    todo = sorted(range(len(cases)), key=lambda j: (order[cases[j]["scenario"]], j))
    t0, n_done = time.time(), 0
    for j in todo:
        if (out / "STOP").exists():
            print("STOP", flush=True)
            break
        c = cases[j]
        f = out / f"f_am_{c['condition']}_{c['sample_id']}.npz"
        if f.exists():
            continue
        ids = c["ids"][:c["pos"] + 1]
        T, L = len(ids), len(lm.layers)
        st.update(fi=torch.zeros((T, L, K), dtype=torch.int16), fv=torch.zeros((T, L, K), dtype=torch.float16))
        with torch.inference_mode():
            cache = None
            for s0 in range(0, T, CH):
                st["s0"] = s0
                o = lm(input_ids=torch.tensor([ids[s0:s0 + CH]], device="cuda"), past_key_values=cache, use_cache=True)
                cache = o.past_key_values
            del cache, o
        st["fi"][0], st["fv"][0] = 0, 0
        tmp = f.with_suffix(".tmp.npz")
        np.savez_compressed(tmp, flow_idx=st["fi"].numpy(), flow_val=st["fv"].numpy())
        os.replace(tmp, f)
        torch.cuda.empty_cache()
        n_done += 1
        print(f"{n_done} {c['condition']} s{c['sample_id']} {c['risk']} T={T} {time.time() - t0:.0f}s", flush=True)
    print("CAPTURE_DONE", n_done, flush=True)


if __name__ == "__main__":
    main()
