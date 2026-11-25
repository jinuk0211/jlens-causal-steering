"""J-Cascade stage 1a (vast box): MLP neuron values at decision points of the unsteered tau2 episodes.
For every agent turn: act = silu(gate) * up at the last prompt token (decision point), layers L12-31 (fp16).
Write turns also store gate and up; transfer turns also store act/gate/up at the position that predicts the tool-name token.
Input /workspace/jc/data/episodes/*.json.gz (prompts delta-coded: prev[:lcp] + tail). Output /workspace/jc/out/neurons/<name>.npz
"""
import copy
import gzip
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

J = Path(os.environ.get("JC_DIR", "/workspace/jc"))
EP = J / "data/episodes"
OUT = J / "out/neurons"
LAYERS = list(range(12, 32))
CHUNK = 2048
READS = ("get_", "find_", "list_", "search_", "calculate", "think")


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main():
    from huggingface_hub import snapshot_download
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM

    want = os.environ.get("JC_GPU_UUID")
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if want and want not in uuid:
        log(f"wrong GPU {uuid}, expected {want}; exiting")
        return 2
    mp = os.environ.get("JC_MODEL") or snapshot_download("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")
    tok = AutoTokenizer.from_pretrained(mp)
    dtype = getattr(torch, os.environ.get("JC_DTYPE", "bfloat16"))
    config = Qwen3_5Config.from_pretrained(mp).text_config
    model = Qwen3_5ForCausalLM.from_pretrained(mp, config=config, dtype=dtype,
                                               key_mapping={r"^model\.language_model\.": "model."}).to("cuda").eval()
    blocks = model.model.layers
    state = {"on": False}
    cap = {}

    def hook_mlp(i):
        def pre(module, args):
            if state["on"]:
                x = args[0][0, -1]
                g = module.gate_proj(x)
                u = module.up_proj(x)
                cap[i] = (g.float(), u.float(), (torch.nn.functional.silu(g.float()) * u.float()))
        return pre

    for i in LAYERS:
        blocks[i].mlp.register_forward_pre_hook(hook_mlp(i))
    log(f"model loaded dtype {dtype}, {len(blocks)} blocks, mlp {blocks[12].mlp.gate_proj.out_features} neurons")

    def pieces(n):
        out, s = [], 0
        while n - s >= CHUNK:
            out.append((s, s + CHUNK))
            s += CHUNK
        size = CHUNK // 2
        while s < n:
            while size > n - s:
                size //= 2
            out.append((s, s + size))
            s += size
        return out

    def feed(tokens, cache, capture=False):
        # power-of-two pieces: a handful of distinct shapes, so the fla/triton kernels compile once instead of per turn
        with torch.no_grad():
            ps = pieces(len(tokens))
            for k, (s, e) in enumerate(ps):
                state["on"] = capture and k == len(ps) - 1
                ids = torch.tensor([tokens[s:e]], device="cuda")
                cache = model.model(input_ids=ids, past_key_values=cache, use_cache=True).past_key_values
        state["on"] = False
        return cache

    def grab(kind):
        idx = {"a": 2, "g": 0, "u": 1}[kind]
        return torch.stack([cap[i][idx] for i in LAYERS]).half().cpu().numpy()

    OUT.mkdir(parents=True, exist_ok=True)
    files = sorted(EP.glob("*.json.gz"))
    shard = os.environ.get("JC_SHARD")
    if shard:
        si, sn = (int(x) for x in shard.split("/"))
        files = [f for k, f in enumerate(files) if k % sn == si]
    t_all = time.time()
    for n, f in enumerate(files):
        out = OUT / (f.name[:-8] + ".npz")
        if out.exists():
            continue
        t0 = time.time()
        ep = json.loads(gzip.open(f, "rt").read())
        turns = ep["turns"]
        prompts, prev = [], []
        for t in turns:
            ids = prev[:t["lcp"]] + t["tail"]
            prompts.append(ids)
            prev = ids
        dec_a, wr_g, wr_u, wr_turn, tn_a, tn_g, tn_u, tn_turn = [], [], [], [], [], [], [], []
        cache, pos = None, 0
        for k, (t, ids) in enumerate(zip(turns, prompts)):
            nxt = prompts[k + 1] if k + 1 < len(prompts) else []
            lcp = 0
            while lcp < min(len(ids), len(nxt)) and ids[lcp] == nxt[lcp]:
                lcp += 1
            if pos > len(ids) or (pos and prompts[k - 1][:pos] != ids[:pos]):
                cache, pos = None, 0
            split = max(pos, min(lcp, len(ids) - 1))
            cache = feed(ids[pos:split], cache)
            snap = copy.deepcopy(cache) if (k + 1 < len(prompts) and lcp >= split and cache is not None) else None
            cache = feed(ids[split:], cache, capture=True)
            dec_a.append(grab("a"))
            writes = [c for c in t["calls"] if not c.startswith(READS)]
            if writes:
                wr_g.append(grab("g"))
                wr_u.append(grab("u"))
                wr_turn.append(t["turn"])
            if "transfer_to_human_agents" in t["calls"]:
                gen = t["gen"]
                name = tok.encode("transfer_to_human_agents", add_special_tokens=False)
                j0 = next((s for s in range(len(gen)) if gen[s:s + len(name)] == name), None)
                if j0 is not None and j0 > 0:
                    cache = feed(gen[:j0], cache, capture=True)
                    tn_a.append(grab("a"))
                    tn_g.append(grab("g"))
                    tn_u.append(grab("u"))
                    tn_turn.append(t["turn"])
            cache, pos = (snap, split) if snap is not None else (None, 0)
        z = lambda xs: np.stack(xs) if xs else np.zeros((0, len(LAYERS), 9216), np.float16)
        tmp = out.with_suffix(".tmp.npz")
        np.savez(tmp, dec_a=z(dec_a), dec_turn=np.array([t["turn"] for t in turns], np.int16),
                 wr_g=z(wr_g), wr_u=z(wr_u), wr_turn=np.array(wr_turn, np.int16),
                 tn_a=z(tn_a), tn_g=z(tn_g), tn_u=z(tn_u), tn_turn=np.array(tn_turn, np.int16),
                 layers=np.array(LAYERS, np.int16), meta=np.array(json.dumps({k: ep[k] for k in ("domain", "file", "sim_id", "task_id")})))
        tmp.rename(out)
        del cache
        torch.cuda.empty_cache()
        log(f"{n + 1}/{len(files)} {f.name[:40]} turns {len(turns)} writes {len(wr_turn)} transfers {len(tn_turn)} {time.time() - t0:.0f}s")
    log(f"STAGE1A_DONE {time.time() - t_all:.0f}s")


if __name__ == "__main__":
    sys.exit(main())
