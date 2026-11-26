"""Neuron collections per agentic-misalignment prompt type (3 scenarios x 3 urgency x 2 goal = 18 prompts), from the
explorer dumps (ne_cases.py /api/ne_dump). Units: neuron-explorer act_scale, the same rule as server.score_text
(+ side / typical max, - side / typical min); a value >= 1 means stronger than the neuron's typical web-text extreme.
Key = (layer, neuron, pole). Per prompt and window, value = the strongest firing of that pole in the window.
For a factor level (e.g. urgency = replacement): margin = min over the level's prompts - max over the other prompts.
A neuron is in the level's collection when it fires (>= 1) in every prompt of the level and margin > 0, i.e. it separates
the level from all other prompts of that factor perfectly. Ranked by margin.
Windows: prompt = whole prompt (system + user + emails); gen = the generation-prompt tokens (the reply starts here).
Connections: the explorer's precomputed direct links (connections.npz, weights only) whose two ends are both in the
level's collection (top 40).
Usage: python am18_types.py DUMP_DIR CASES_JSON EXPLORER_CACHE OUT_MD [OUT_JSON]"""
import json
import sys
from pathlib import Path

import numpy as np
from transformers import AutoTokenizer

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
FACTORS = {"scenario": ["blackmail", "leaking", "murder"], "urgency": ["replacement", "restriction", "none"],
           "goal": ["explicit-america", "none-none"]}
TOP, TOPCON = 12, 40


def main():
    dd, cp, cache, out_md = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), Path(sys.argv[4])
    out_js = Path(sys.argv[5]) if len(sys.argv) > 5 else None
    cases = {c["domain"]: c for c in json.loads(cp.read_text(encoding="utf-8"))}
    tok = AutoTokenizer.from_pretrained(MODEL)
    sc = np.load(cache / "act_scale.npz")
    ps = np.maximum(sc["pos"], np.maximum(0.1 * -sc["neg"], 1e-3)).astype(np.float32)
    ng = np.minimum(sc["neg"], np.minimum(-0.1 * sc["pos"], -1e-3)).astype(np.float32)
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    vs = lambda t: str(vocab[t]).replace("Ġ", " ").replace("Ċ", "\\n").replace("\n", "\\n").replace("|", "/").strip() or repr(vocab[t])
    ix = {k: dict(np.load(cache / f"{k}_index.npz")) for k in ("steer", "s")}
    _c = np.load(cache / "connections.npz")
    con = {k: _c[k] for k in _c.files}
    names = sorted(cases)
    meta = {c: dict(zip(("scenario", "goal", "urgency"), c.split("_"))) for c in names}
    for c in names:
        meta[c]["goal"] = "explicit-america" if meta[c]["goal"] == "explicit-america" else "none-none"
    Z = {c: {k: v for k, v in np.load(dd / f"p_{c}.npz").items() if k != "flow_idx" and k != "flow_val"} for c in names}
    W0 = list(Z[names[0]]["windows"])
    L, N = Z[names[0]]["mx"].shape[1:]
    NK = L * N * 2

    def vals(c, wins):
        z = Z[c]
        wi = [W0.index(w) for w in wins]
        up = (z["mx"][wi] / ps).max(0)
        dn = (z["mn"][wi] / ng).max(0)
        amx = z["amx"][wi][np.argmax(z["mx"][wi] / ps, 0), np.arange(L)[:, None], np.arange(N)[None, :]]
        amn = z["amn"][wi][np.argmax(z["mn"][wi] / ng, 0), np.arange(L)[:, None], np.arange(N)[None, :]]
        return np.stack([up, dn], -1).reshape(-1), np.stack([amx, amn], -1).reshape(-1)

    def label(key):
        l, rest = divmod(int(key), 2 * N)
        n, neg = divmod(rest, 2)
        pole = "down" if neg else "up"
        return l, n, neg, " ".join(vs(t) for t in ix["steer"][pole][l, n, :6]), " ".join(vs(t) for t in ix["s"][pole][l, n, :5])

    def ctx(c, pos):
        ids = cases[c]["ids"]
        a, b = max(0, pos - 8), min(len(ids), pos + 3)
        s = tok.decode(ids[a:pos]) + "[[" + tok.decode(ids[pos:pos + 1]) + "]]" + tok.decode(ids[pos + 1:b])
        return s.replace("\n", " ").replace("|", "/")[:110]

    md = ["# Neuron collections per agentic-misalignment prompt type (Qwen3.5-4B, neuron-explorer units)", "",
          f"18 prompts = scenario {FACTORS['scenario']} x urgency {FACTORS['urgency']} x goal {FACTORS['goal']}. Prompt only "
          "(no response). Value = strongest firing in the window in act_scale units (>= 1 = above the neuron's web-text extreme).", "",
          "A collection = neurons that fire >= 1 in every prompt of the level and higher there than in every other prompt of "
          "that factor (margin = min inside - max outside > 0). writes = steer lens (what pushing it does), reads = S lens.", ""]
    js = {}
    for wname, wins in (("prompt", [w for w in W0 if w != "gen"]), ("gen (reply start)", ["gen"])):
        V, A = {}, {}
        for c in names:
            V[c], A[c] = vals(c, wins)
        M = np.stack([V[c] for c in names])
        md += [f"## Window: {wname}", ""]
        for f, levels in FACTORS.items():
            md += [f"### {f}", ""]
            for lv in levels:
                inn = np.array([meta[c][f] == lv for c in names])
                lo_in = M[inn].min(0)
                hi_out = M[~inn].max(0)
                margin = lo_in - hi_out
                ok = (lo_in >= 1) & (margin > 0)
                ok[:4 * N] = False
                keys = np.nonzero(ok)[0]
                keys = keys[np.argsort(-margin[keys])]
                ex = next(c for c in names if meta[c][f] == lv)
                md += [f"**{f} = {lv}**: {len(keys)} neurons (layers >= 2). Example prompt for the context column: `{ex}`.", "",
                       "| neuron | min in level | max elsewhere | writes (steer lens) | reads (S lens) | where it peaks (example prompt) |",
                       "|---|---|---|---|---|---|"]
                rows = []
                for k in keys[:TOP]:
                    l, n, neg, wr, rd = label(k)
                    md.append(f"| L{l}/N{n}{'-' if neg else '+'} | {lo_in[k]:.2f} | {hi_out[k]:.2f} | {wr} | {rd} | {ctx(ex, int(A[ex][k]))} |")
                    rows.append({"layer": l, "n": n, "sign": "-" if neg else "+", "min_in": float(lo_in[k]), "max_out": float(hi_out[k]),
                                 "writes": wr, "reads": rd})
                coll = set((int(k) // (2 * N), (int(k) % (2 * N)) // 2) for k in keys[:TOPCON])
                links = []
                for (l, n) in coll:
                    for i in range(int(con["k"])):
                        z = float(con["down_z"][l, n, i])
                        if z < -1e4:
                            break
                        t = (int(con["down_layer"][l, n, i]), int(con["down_n"][l, n, i]))
                        if t in coll:
                            links.append((z, l, n, t[0], t[1], int(con["down_sign"][l, n, i])))
                links.sort(reverse=True)
                md += ["", f"Direct links inside the top-{TOPCON} collection: {len(links)}" +
                       (": " + "; ".join(f"L{a}/N{b} → L{c}/N{d} ({'+' if s > 0 else '−'}, z {z:.1f})" for z, a, b, c, d, s in links[:8]) if links else ""), ""]
                js[f"{wname}|{f}|{lv}"] = {"n": int(len(keys)), "top": rows, "links": [list(x) for x in links[:20]]}
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    if out_js:
        out_js.write_text(json.dumps(js, ensure_ascii=False), encoding="utf-8")
    print("\n".join(md[:60]))


if __name__ == "__main__":
    main()
