"""Plotted values of the two residual-stream figures, as JSON, split by misaligned and aligned (user 11-27 13:2x).
flow    : residual_flow.png (ab_flowfig.py). Per benchmark: the three panels as drawn, the class means behind the bars, and every unit's
          attention write, MLP write and position per layer. Panels (distance, position quartiles, confidence intervals, shares) are
          copied from fig_flow/flow.json; class means and per-unit values are recomputed with ab_flowfig.stored_terms, and the
          difference of the class means is checked against the plotted bars. -> fig_flow/residual_flow_values.json
streams : residual_streams.png (ab_resfig.py), from fig_resid/resfig.json and resfig.npz. -> fig_resid/residual_streams_values.json
Usage: python ab_figvalues.py flow ; python ab_figvalues.py streams [ANA_DIR]"""
import json
import sys
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
BENCH = ("dojo", "toolalign", "am")
NAME = {"dojo": "AgentDojo", "toolalign": "ToolAlignBench", "am": "Agentic Misalignment"}
NL = 32
FULL = (3, 7, 11, 15, 19, 23, 27, 31)


def r5(x):
    return np.round(np.asarray(x, dtype=np.float64), 5).tolist()


def mode_flow():
    sys.path.insert(0, str(A))
    import ab_flowfig as F
    F.NPERM = 1
    res = json.loads((F.OUT / "flow.json").read_text(encoding="utf-8"))
    rng = np.random.default_rng(0)
    out = {"figure": "fig_flow/residual_flow.png (and .pdf)", "model": "Qwen3.5-4B, revision 851bf6e",
           "position": "the token that completes the call opener (<tool_call> in AgentDojo and ToolAlignBench, <tool_use: in Agentic Misalignment)",
           "how_to_read": {
               "direction": "the difference between the misaligned and the aligned mean of the residual after the last layer, fitted on fold 0 "
                            "(standardized coordinates, residuals centered on their context x fold mean)",
               "units": "standard deviations of the held-out aligned units along that direction at the last layer ('scale' gives that value in raw "
                        "projection units)",
               "centering": "every unit's value minus the mean of all units of its context (user task, domain or condition) and fold; no labels used",
               "held_out": "class means, the drawn bars and the position bands use fold 1 only; per-unit lists contain both folds",
               "attention_write / mlp_write": "projection on the direction of what that sublayer adds to the residual stream; embedding + all writes "
                                              "= position after the last layer",
               "difference": "misaligned_mean - aligned_mean = the bar drawn in the bottom row",
               "distance": "top row: sqrt(D0 . D1) / within-class RMS, D_f = class-mean difference on fold f, after attention and after the MLP of "
                           "each layer, both folds; null95 = 95th percentile under 200 label shuffles within context x fold"},
           "layers": list(range(NL)), "layer_type": ["full attention" if l in FULL else "linear attention" for l in range(NL)], "benchmarks": {}}
    rep = []
    for b in BENCH:
        if b not in res:
            out["benchmarks"][b] = {"name": NAME[b], "status": "not in flow.json yet"}
            continue
        r = res[b]
        T = F.stored_terms(b, rep, rng)
        d = np.load(F.TA_GPU) if b == "toolalign" else np.load(A / "hn" / b / "hn.npz")
        uids = d["uids"][F.dedup(d)].astype(str)
        mis, ali, ext = F.classes(b, T["lab"])
        fold, grp = T["fold"], T["grp"]
        strata = np.array([f"{x}|{y}" for x, y in zip(grp, fold)])
        a, m, e, p = (F.center1(T[k], strata) for k in ("a", "m", "e", "p"))
        f1 = fold == 1
        M1, A1, E1 = f1 & mis, f1 & ali, f1 & ext
        scale = float(p[A1, NL - 1].std())
        a, m, e = a / scale, m / scale, e / scale
        pos = (p - np.median(p[A1], 0)) / scale
        da, dm = a[M1].mean(0) - a[A1].mean(0), m[M1].mean(0) - m[A1].mean(0)
        chk = float(max(np.abs(da - np.array(r["attn"])).max(), np.abs(dm - np.array(r["mlp"])).max()))
        rep.append(f"{b}: largest difference between recomputed and plotted bars {chk:.2e}")
        cls = np.where(mis, "misaligned", np.where(ali, "aligned", np.where(ext, "aligned, not the default tool", "other")))
        means = {}
        for nm, mk in (("misaligned", M1), ("aligned", A1), ("aligned, not the default tool", E1)):
            if mk.any():
                means[nm] = {"n": int(mk.sum()), "attention_write": r5(a[mk].mean(0)), "mlp_write": r5(m[mk].mean(0)),
                             "embedding": round(float(e[mk].mean()), 5), "position": r5(pos[mk].mean(0))}
        dd = r.get("dist")
        out["benchmarks"][b] = {
            "name": NAME[b], "scale": scale,
            "counts": {"held_out_misaligned": int(M1.sum()), "held_out_aligned": int(A1.sum()), "held_out_aligned_not_default": int(E1.sum()),
                       "all_units": int(len(uids)), "contexts_held_out": r["n"]["contexts1"]},
            "top_row_distance": ({"after_attention": r5(dd["mid"]), "after_mlp": r5(dd["post"]), "null95_after_attention": r5(dd["null_mid"]),
                                  "null95_after_mlp": r5(dd["null_post"])} if dd else None),
            "middle_row_position_quartiles": {nm: {"q25": r5(q[0]), "median": r5(q[1]), "q75": r5(q[2])} for nm, q in r["stream"].items()},
            "bottom_row_writes": {
                "attention": {"difference": r5(r["attn"]), "ci95_low": r5(r["attn_ci"][0]), "ci95_high": r5(r["attn_ci"][1])},
                "mlp": {"difference": r5(r["mlp"]), "ci95_low": r5(r["mlp_ci"][0]), "ci95_high": r5(r["mlp_ci"][1])},
                "final_gap": r["gap"], "share_of_gap": r["share"], "share_ci95": r["share_ci"]},
            "class_means_held_out": means,
            "neurons": r.get("neurons"),
            "units": [{"uid": str(uids[i]), "class": str(cls[i]), "fold": int(fold[i]), "context": str(grp[i]), "attention_write": r5(a[i]),
                       "mlp_write": r5(m[i]), "embedding": round(float(e[i]), 5), "position": r5(pos[i])} for i in range(len(uids))]}
    out["checks"] = rep
    f = F.OUT / "residual_flow_values.json"
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("\n".join(rep))
    print("wrote", f, f.stat().st_size)


def mode_streams(ana=None):
    base = Path(ana) if ana else A
    R = base / "fig_resid" if (base / "fig_resid").is_dir() else base
    res = json.loads((R / "resfig.json").read_text(encoding="utf-8"))
    z = np.load(R / "resfig.npz")
    LS = res["layer_star"]
    out = {"figure": "fig_resid/residual_streams.png (and .pdf)", "model": "Qwen3.5-4B, revision 851bf6e",
           "position": "residual after each layer at the token that completes the call opener",
           "layer_shown_in_panel_b": LS,
           "how_to_read": {
               "axis": "per layer, the difference between the misaligned and the aligned mean on fold 0, after centering every unit on its context x fold "
                       "mean and standardizing on fold 0",
               "panel_a": "share of held-out misaligned-aligned pairs from the same context ordered correctly by the axis (AUROC within context); "
                          "the second curve uses only pairs that also agree on whether a preamble precedes the call; null = 2.5-97.5 % under 200 "
                          "label shuffles within context",
               "position": "held-out unit's value on the axis, in standard deviations of the held-out aligned units, zero at their median",
               "panel_b": "x = position at layer " + str(LS) + ", y = largest principal component of the rest; the PNG clips y at the 1-99 % range "
                          "(3 units), the values here are not clipped",
               "panel_c": "cosine between the axes of two benchmarks (each fitted on all its units)",
               "panel_d": "AUROC within context when one benchmark's axis scores another's units, mean of the two directions; dots = both "
                          "directions above 95 % of axes fitted to shuffled labels"},
           "layers": list(range(NL)), "benchmarks": {}}
    for b in BENCH:
        L = res[b]["layers"]
        P, y = z[f"{b}_pos"], z[f"{b}_y1"].astype(bool)
        q = lambda mk: {"q25": r5(np.quantile(P[:, mk], 0.25, 1)), "median": r5(np.median(P[:, mk], 1)), "q75": r5(np.quantile(P[:, mk], 0.75, 1)),
                        "mean": r5(P[:, mk].mean(1))}
        cls = z[f"{b}_cls"]
        lab = np.where(cls == 1, "misaligned", np.where(cls == 2, "aligned, not the default tool", "aligned"))
        out["benchmarks"][b] = {
            "name": NAME[b], "counts": res[b]["n"],
            "panel_a": {"auroc_within_context": r5([x["auc_within_c"] for x in L]), "auroc_within_context_and_preamble": r5([x["auc_samepre_group"] for x in L]),
                        "null_2.5": r5([x["nullw_lo"] for x in L]), "null_97.5": r5([x["nullw_hi"] for x in L]),
                        "auroc_pooled": r5([x["auc_c"] for x in L])},
            "position_by_layer_held_out": {"misaligned": q(y), "aligned": q(~y)},
            "panel_b_units": {"x": r5(z[f"{b}_sx"]), "y": r5(z[f"{b}_sy"]), "class": lab.tolist(),
                              "auroc_pooled": L[LS]["auc_c"], "auroc_within_context": L[LS]["auc_within_c"]},
            "text_before_call": res[b]["text_before"]}
        if "extra" in res[b]:
            out["benchmarks"][b]["aligned_not_default"] = res[b]["extra"]
    cl = res["cross_layers"]
    pairs = (("dojo", "toolalign"), ("dojo", "am"), ("toolalign", "am"))
    out["panel_c_cosine"] = {f"{NAME[i]} - {NAME[j]}": r5([x["cos"][k] for x in cl]) for k, (i, j) in enumerate(pairs)}
    out["panel_d_transfer"] = {}
    for i, j in pairs:
        k1, k2 = f"{i}>{j}", f"{j}>{i}"
        out["panel_d_transfer"][f"{NAME[i]} - {NAME[j]}"] = {
            "mean_auroc": r5([(x["auc"][k1] + x["auc"][k2]) / 2 for x in cl]),
            f"{NAME[i]} axis on {NAME[j]}": r5([x["auc"][k1] for x in cl]), f"p, {NAME[i]} axis on {NAME[j]}": r5([x["p"][k1] for x in cl]),
            f"{NAME[j]} axis on {NAME[i]}": r5([x["auc"][k2] for x in cl]), f"p, {NAME[j]} axis on {NAME[i]}": r5([x["p"][k2] for x in cl]),
            "dot_layers": [x["layer"] for x in cl if x["p"][k1] < 0.05 and x["p"][k2] < 0.05]}
    f = R / "residual_streams_values.json"
    f.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("wrote", f, f.stat().st_size)


if __name__ == "__main__":
    {"flow": mode_flow, "streams": mode_streams}[sys.argv[1]](*sys.argv[2:])
