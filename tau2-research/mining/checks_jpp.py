"""Same confound checks as checks.py, with the decision-point (layer, word) pairs taken from the J++ lens, and from J-lens + J++
together (J++ layers offset to 32-63). B_family stays J-lens based. CPU only.
Output: mining/checks_jpp.md, mining/checks_jpp.json
"""
import json
from pathlib import Path

import numpy as np

import checks
import mine

HERE = Path(__file__).resolve().parent
TOPK = Path(r"C:\Users\h\Documents\ChatGPT\vlm interpretability\work\tau2-topk-20261119")


def build():
    jl, jp = [], []
    for jf in sorted(TOPK.glob("*.json")):
        m = json.loads(jf.read_text(encoding="utf-8"))
        if m.get("cond") != "f_detect":
            continue
        z = np.load(jf.with_suffix(".npz"))
        idx = {int(t): i for i, t in enumerate(z["dec_turn"])}
        for t in m["turns"]:
            di = idx.get(int(t["turn"]))
            if di is not None and t["label"] in ("bad_write", "good_write"):
                jl.append(z["dec_ids_jlens"][di].astype(np.int32))
                jp.append(z["dec_ids_jpp"][di].astype(np.int32))
    return np.stack(jl), np.stack(jp)


def keys_any(dec):
    layers = np.arange(dec.shape[0], dtype=np.int64)[:, None] * mine.V
    return np.unique((dec.astype(np.int64) + layers).ravel())


def main():
    rng = np.random.default_rng(1)
    turns = json.loads((HERE / "cache_turns.json").read_text(encoding="utf-8"))
    dec_j = np.load(HERE / "cache_dec.npy")
    jl, jp = build()
    assert jl.shape == dec_j.shape and (jl == dec_j).all(), "alignment with cache_dec.npy failed"
    mine.pair_keys = keys_any
    variants = {
        "W_clean_all": lambda t: True,
        "W_clean_no_transfer": lambda t: "transfer_to_human_agents" not in t["calls"],
        "W_clean_wrong_args_or_unexpected_write": lambda t: "transfer_to_human_agents" not in t["calls"] and (
            t["label"] == "good_write" or any(b.split(":")[0] in ("wrong_args", "unexpected_write") for b in t["bad"])),
        "transfer_only": lambda t: "transfer_to_human_agents" in t["calls"],
    }
    lenses = {"jlens": dec_j, "jpp": jp, "jlens+jpp": np.concatenate([dec_j, jp], axis=1)}
    res = {}
    for lname, dec in lenses.items():
        for vname, keep in variants.items():
            rows = checks.rows_clean(turns, keep)
            o = checks.evaluate(rows, dec, rng)
            res[f"{lname}|{vname}"] = o
            print(lname, vname, o["n_bad"], o["n_good"], "A", round(o["A_pairs"]["auc"] or 0, 3), "tool",
                  round(o["tool_only"]["auc"] or 0, 3), "within", o["within_tool_weighted_auc"], flush=True)
    md = ["# J-lens vs J++ vs both: decision-point (layer, word) pairs, out-of-fold AUC (5 folds grouped by task)", "",
          "| lens | rows | bad | good | A_pairs AUC [CI] | tool-only AUC | within-tool AUC |", "|---|---|---|---|---|---|---|"]
    for k, o in res.items():
        lname, vname = k.split("|")
        a = o["A_pairs"]
        md.append(f"| {lname} | {vname} | {o['n_bad']} | {o['n_good']} | {None if a['auc'] is None else round(a['auc'], 3)} {a['ci']} | "
                  f"{None if o['tool_only']['auc'] is None else round(o['tool_only']['auc'], 3)} | {o['within_tool_weighted_auc']} |")
    (HERE / "checks_jpp.json").write_text(json.dumps(res, indent=1, default=str), encoding="utf-8")
    (HERE / "checks_jpp.md").write_text("\n".join(md) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
