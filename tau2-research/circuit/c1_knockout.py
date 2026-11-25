"""C-LOOP C1 causal source test: attention knockout at the decision position. GPU 0 only.
For each unit (C0a row: c, g by the symmetric rule), the prefix is cached and the decision token is re-run with eager attention in which
the decision query of all 8 full-attention layers gets -inf on a set of key positions (Geva et al. style knockout; linear-attention
layers are untouched, so this is a lower bound on the information the set carries). Groups are defined by role and by fixed word
lists, identically for bad and good units; each word/role group has a random control of the same size drawn from the same roles.
m' = logit(c) - logit(g); flip = m' < 0. Output <C0_OUT>/knockout.json. Usage: env C0_UNITS, C0_OUT as for c0_graph.py."""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np
import torch

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
sys.path.insert(0, str(R / "probe/circuit"))
import build_topk as bt
from c0_graph import ROLE, role_codes

OUT = Path(os.environ.get("C0_OUT", str(R / "probe/circuit/out/c0")))
UNITS = Path(os.environ.get("C0_UNITS", str(R / "probe/m1/out/units.json")))
CHUNK = 4096
NRAND = 3
MENTION = {"human", "humans", "agent", "agents", "supervisor", "transfer", "transferred", "transferring", "person", "someone",
           "representative", "escalate", "manager", "real"}
CLAUSE = {"transfer", "human", "escalate", "transferred"}


def log(msg):
    print(f"{time.strftime('%H:%M:%S')} {msg}", flush=True)


def main():
    uuid = str(torch.cuda.get_device_properties(0).uuid)
    if os.environ.get("CUDA_DEVICE_ORDER") != "PCI_BUS_ID" or "c27bc2d7" not in uuid:
        log(f"wrong GPU {uuid}; exiting")
        return 2
    os.chdir(R / "tau2-bench")
    torch.set_grad_enabled(False)
    import transformers.models.qwen3_5.modeling_qwen3_5 as mq
    KO = {"pos": None}

    def eager_ko(module, query, key, value, attention_mask, scaling, dropout=0.0, **kwargs):
        key_states = mq.repeat_kv(key, module.num_key_value_groups)
        value_states = mq.repeat_kv(value, module.num_key_value_groups)
        w = torch.matmul(query, key_states.transpose(2, 3)) * scaling
        if attention_mask is not None:
            w = w + attention_mask
        if KO["pos"] is not None:
            w[:, :, -1, KO["pos"]] = float("-inf")
        w = torch.nn.functional.softmax(w, dim=-1, dtype=torch.float32).to(query.dtype)
        out = torch.matmul(w, value_states).transpose(1, 2).contiguous()
        return out, w

    mq.eager_attention_forward = eager_ko
    tok, model = bt.load_model(os.environ["JC_MODEL"], "cuda")
    cfg = model.config
    blocks = model.model.layers
    full = [i for i, b in enumerate(blocks) if hasattr(b, "self_attn")]

    def set_attn(impl):
        cfg._attn_implementation = impl
        for i in full:
            blocks[i].self_attn.config._attn_implementation = impl

    units = {u["k"]: u for u in json.loads(UNITS.read_text(encoding="utf-8"))}
    rows = [r for r in json.loads((OUT / "units.json").read_text(encoding="utf-8")) if r["k"] in units]
    want = {(r["cond"], r["sim"], r["turn"]): r["k"] for r in rows}
    seqs = {}
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({r["cond"] for r in rows if r["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key in want:
                    k = want[key]
                    seqs[k] = (list(rec["input_ids"]), list(rec["generated_ids"]))
    words = {}

    def word(t):
        if t not in words:
            words[t] = tok.decode([t]).strip().lower()
        return words[t]

    rng = np.random.default_rng(0)
    res = []
    t0 = time.time()
    for n, r in enumerate(rows):
        if r["k"] not in seqs:
            continue
        inp, gen = seqs[r["k"]]
        d = units[r["k"]]["d"]
        seq = inp + gen[:d]
        T = len(seq)
        codes = role_codes(inp, d, tok)[:T]
        last = T - 1
        z = np.load(OUT / f"n_{r['k']}.npz")
        tot = z["tsrc_pos"].astype(np.float32).sum(0)
        user = np.isin(codes, [ROLE["user_last"], ROLE["user_earlier"]])
        sysm = codes == ROLE["system"]
        genm = codes == ROLE["gen"]
        idx = np.arange(T)
        mention_user = idx[user & np.array([word(t) in MENTION for t in seq])]
        mention_gen = idx[genm & np.array([word(t) in MENTION for t in seq])]
        mention_gen = mention_gen[mention_gen < last]
        anchor = idx[sysm & np.array([word(t) in CLAUSE for t in seq])]
        clause = np.unique(np.concatenate([np.arange(max(0, a - 12), a + 13) for a in anchor])) if len(anchor) else np.array([], int)
        clause = clause[sysm[clause]] if len(clause) else clause
        order = np.argsort(-tot[:last])
        groups = {
            "user_last": idx[codes == ROLE["user_last"]],
            "user_mention": mention_user,
            "gen_mention": mention_gen,
            "user+gen_mention": np.concatenate([mention_user, mention_gen]),
            "system_all": idx[sysm],
            "system_transfer_clause": clause,
            "gen_before": idx[genm][idx[genm] < last],
            "assistant_earlier": idx[codes == ROLE["assistant_earlier"]],
            "tool_all": idx[np.isin(codes, [ROLE["tool_last"], ROLE["tool_earlier"]])],
            "top10_total": order[:10],
            "top50_total": order[:50],
        }
        pools = {"user_mention": user, "gen_mention": genm & (idx < last), "user+gen_mention": (user | genm) & (idx < last),
                 "system_transfer_clause": sysm, "top10_total": idx < last, "top50_total": idx < last}
        set_attn("sdpa")
        cache0 = None
        for s in range(0, T - 1, CHUNK):
            ids = torch.tensor([seq[s:min(s + CHUNK, T - 1)]], device="cuda")
            cache0 = model.model(input_ids=ids, past_key_values=cache0, use_cache=True).past_key_values
        set_attn("eager")
        import copy

        def run(pos):
            cache = copy.deepcopy(cache0)
            KO["pos"] = None if pos is None or len(pos) == 0 else torch.as_tensor(np.asarray(pos, dtype=np.int64), device="cuda")
            out = model.model(input_ids=torch.tensor([[seq[-1]]], device="cuda"), past_key_values=cache, use_cache=True)
            KO["pos"] = None
            lg = model.lm_head(out.last_hidden_state[0, -1]).float()
            top = int(lg.argmax())
            return float(lg[r["c"]] - lg[r["g"]]), top

        m_base, top_base = run(None)
        row = {k: r[k] for k in ("k", "label", "kind", "ptype", "call", "domain", "task", "c_tok", "g_tok", "m")} | {
            "m_base": m_base, "top_base": tok.decode([top_base]), "groups": {}}
        for gname, pos in groups.items():
            pos = np.asarray(pos, dtype=np.int64)
            if len(pos) == 0:
                continue
            m_ko, top = run(pos)
            entry = {"n": int(len(pos)), "m_ko": m_ko, "dm": m_ko - m_base, "flip": m_ko < 0, "top": tok.decode([top])}
            if gname in pools:
                cand = idx[pools[gname] & ~np.isin(idx, pos)]
                rd = []
                for _ in range(NRAND):
                    if len(cand) >= len(pos):
                        rd.append(run(rng.choice(cand, size=len(pos), replace=False))[0] - m_base)
                entry["dm_rand"] = rd
            row["groups"][gname] = entry
        set_attn("sdpa")
        del cache0
        res.append(row)
        g = row["groups"]
        log(f"{n + 1}/{len(rows)} k={r['k']} {r['label']} m {m_base:.2f}: " + ", ".join(
            f"{kname} {v['dm']:+.1f}{'F' if v['flip'] else ''}" for kname, v in g.items()) + f" ({time.time() - t0:.0f}s)")
        (OUT / "knockout.json").write_text(json.dumps(res, indent=0, default=float), encoding="utf-8")
    log(f"KO_DONE {len(res)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
