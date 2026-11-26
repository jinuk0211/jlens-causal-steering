"""Decode-speed profile on the 2080 Ti for the AM steering loop (separate process; the explorer server stays up).
For dtype in argv: load Qwen3.5-4B, prefill one AM prompt for B rows in 512-token chunks, then time decode steps.
Also checks fp16 vs bf16 agreement: max |logit diff| and top-1 match on the last prompt position, and inf/nan.
Usage: python gen_profile.py CASES_JSON CASE_DOMAIN B STEPS dtype [dtype ...]"""
import json
import sys
import time

import torch

sys.path.insert(0, "/workspace/tj")
import ab_core as C

C.patch_gdn()
from transformers import Qwen3_5ForConditionalGeneration

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def main():
    cases = {c["domain"]: c for c in json.load(open(sys.argv[1]))}
    ids = cases[sys.argv[2]]["ids"]
    B, steps = int(sys.argv[3]), int(sys.argv[4])
    ref = None
    for dt in sys.argv[5:]:
        m = Qwen3_5ForConditionalGeneration.from_pretrained(MODEL, dtype=getattr(torch, dt), device_map="cuda").eval()
        m.model.visual = None
        torch.cuda.empty_cache()
        x = torch.tensor([ids] * B, device="cuda")
        with torch.inference_mode():
            torch.cuda.synchronize()
            t = time.time()
            out = None
            for s0 in range(0, x.shape[1], 512):
                out = m(input_ids=x[:, s0:s0 + 512], past_key_values=out.past_key_values if out is not None else None, use_cache=True, logits_to_keep=1)
            torch.cuda.synchronize()
            pre = time.time() - t
            lg = out.logits[0, -1].float()
            bad = int((~torch.isfinite(lg)).sum())
            if ref is None:
                ref = lg.cpu()
                agree = "-"
            else:
                agree = f"max|dlogit| {float((lg.cpu() - ref).abs().max()):.3f}, top1 same {int(lg.argmax()) == int(ref.argmax())}, top10 overlap {len(set(lg.topk(10).indices.tolist()) & set(ref.topk(10).indices.tolist()))}"
            gs = [torch.Generator(device="cuda").manual_seed(r) for r in range(B)]
            nxt = out.logits[:, -1].argmax(-1)
            torch.cuda.synchronize()
            t = time.time()
            tf = 0.0
            for _ in range(steps):
                t1 = time.time()
                out = m(input_ids=nxt[:, None], past_key_values=out.past_key_values, use_cache=True, logits_to_keep=1)
                torch.cuda.synchronize()
                tf += time.time() - t1
                lg = out.logits[:, -1].float()
                g = torch.stack([-torch.log(-torch.log(torch.rand(lg.shape[1], device="cuda", generator=gs[r]).clamp_min(1e-20))) for r in range(B)])
                nxt = (lg + g).argmax(-1)
            torch.cuda.synchronize()
            tot = time.time() - t
        print(f"{dt}: B={B} prefill {pre:.1f}s, decode {1000 * tot / steps:.1f} ms/step (forward {1000 * tf / steps:.1f}), "
              f"inf/nan in logits {bad}, vs first dtype: {agree}, peak mem {torch.cuda.max_memory_allocated() / 2**30:.1f} GB", flush=True)
        del m, out
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()


if __name__ == "__main__":
    main()
