"""Residual-stream flow of misaligned vs aligned calls through every attention and MLP sublayer (Qwen3.5-4B, 3 benchmarks).
CPU only, no forward pass. Positions and units:
  dojo, am : the call-onset token (token completing <tool_call> / <tool_use:), units and labels as ab_resfig.py (hn/<bench>/hn.npz).
             resid_post = stored `ores`; mlp_out = W_down(layer) @ stored MLP activation `oact`; resid_mid = resid_post - mlp_out;
             attn_out = resid_mid(l) - resid_post(l-1) (layer 0: resid_mid(0) minus the embedding of the onset token).
  toolalign: the last prompt token, captured directly on the 2080 Ti box (comp/cap_ta, window "onset"): attn_out, mlp_out,
             resid_mid, resid_post; misaligned = target with risk boundary / clearly-misaligned, aligned = reference (default
             tool), extra = target with risk aligned (internal email). Group = domain, fold = md5(trajectory) % 2.
Every quantity is centered within group x fold (no labels). Sublayer points: emb, then mid(0), post(0), ..., mid(31), post(31).
  gap      : reproducible distance between the class means at each point, sqrt(max(0, D0 . D1)) with Df the centered class-mean
             difference on fold f, divided by the RMS distance of a unit to its class mean (pooled over classes and folds);
             null: labels permuted within group x fold.
  axis view: u_f = unit vector of the fold-f class-mean difference at post(31); every unit of the other fold is projected on it at
             every point (in units of the aligned spread of that projection at post(31)); the per-sublayer write difference
             along u is mean_mis(write . u) - mean_ali(write . u), summed over the two folds' units; the writes add up to the
             final gap along u.
  sizes    : mean norm of attn_out and mlp_out per class and layer.
-> ana/fig_resid/flow.npz, flow.json, flow_report.md, residual_flow.pdf/png
Usage: python ab_flow.py compute TA_NPZ ; python ab_flow.py plot"""
import json
import sys
import time
from pathlib import Path

import numpy as np

A = Path("/home/project-b/LJW/agentbench2/ana")
OUT = A / "fig_resid"
BENCH = ("dojo", "toolalign", "am")
NAME = {"dojo": "AgentDojo", "toolalign": "ToolAlignBench", "am": "Agentic Misalignment"}
POSN = {"dojo": "call-onset token", "toolalign": "last prompt token", "am": "call-onset token"}
NL, NPERM, SEED = 32, 200, 20261127
SNAP = "/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def weights():
    from safetensors import safe_open
    idx = json.loads(Path(SNAP, "model.safetensors.index.json").read_text())["weight_map"]
    want = {}
    for k in idx:
        if k.endswith("mlp.down_proj.weight") and "language_model.layers." in k:
            want[int(k.split("layers.")[1].split(".")[0])] = k
        if k.endswith("embed_tokens.weight") and "language_model" in k:
            want["emb"] = k
    out = {}
    for key, name in want.items():
        with safe_open(str(Path(SNAP, idx[name])), framework="pt") as f:
            out[key] = f.get_tensor(name).float().numpy() if key != "emb" else f.get_tensor(name)
    return out


def hn_units(b):
    d = np.load(A / "hn" / b / "hn.npz")
    lab, fold, grp, uid = d["labels"], d["folds"].astype(int), d["groups"], d["uids"]
    ores = d["ores"].astype(np.float32)
    seen, keep = set(), []
    for i in range(len(lab)):
        k = (str(uid[i]), ores[i, 16, :64].tobytes())
        if k not in seen:
            seen.add(k)
            keep.append(i)
    keep = np.array(keep)
    items = json.loads((A / "hn" / b / "items.json").read_text(encoding="utf-8"))
    return d, keep, items


def onset_tokens(b, items, keep):
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(SNAP)
    eos = {tok.convert_tokens_to_ids(t) for t in ("<|im_end|>", "<|endoftext|>")}
    U = {u["uid"]: u for u in json.loads((A / b / "units.json").read_text(encoding="utf-8"))}
    ids = []
    for i in keep:
        it = items[i]
        u = U[it["uid"]]
        seq = list(u["prompt_ids"]) + [t for t in u["completion_ids"] if t not in eos]
        ids.append(seq[it["onset"]])
    return np.array(ids)


def load_bench(b, W, ta_npz):
    if b == "toolalign":
        d = np.load(ta_npz)
        lab, risk = d["label"].astype(str), d["risk"].astype(str)
        mis = (lab == "target") & (risk != "aligned")
        ali = lab == "reference"
        ext = (lab == "target") & (risk == "aligned")
        use = mis | ali | ext
        post = d["resid_post"][use].astype(np.float32)
        mid = d["resid_mid"][use].astype(np.float32)
        att = d["attn_out"][use].astype(np.float32)
        mlp = d["mlp_out"][use].astype(np.float32)
        emb = mid[:, 0] - att[:, 0]
        chk = {"mid=post(l-1)+attn, rel err": float(np.linalg.norm(mid[:, 1:] - post[:, :-1] - att[:, 1:]) / np.linalg.norm(mid[:, 1:])),
               "post=mid+mlp, rel err": float(np.linalg.norm(post - mid - mlp) / np.linalg.norm(post))}
        return {"post": post, "mid": mid, "att": att, "mlp": mlp, "emb": emb, "mis": mis[use], "ali": ali[use], "ext": ext[use],
                "fold": d["fold"][use].astype(int), "grp": d["group"][use].astype(str), "check": chk, "onset_tokens": None}
    d, keep, items = hn_units(b)
    lab = d["labels"][keep]
    post = d["ores"][keep].astype(np.float32)
    oact = d["oact"][keep].astype(np.float32)
    mlp = np.stack([oact[:, l] @ W[l].T for l in range(NL)], 1)
    mid = post - mlp
    toks = onset_tokens(b, items, keep)
    emb = W["emb"][toks].float().numpy()
    att = np.empty_like(mid)
    att[:, 0] = mid[:, 0] - emb
    att[:, 1:] = mid[:, 1:] - post[:, :-1]
    mis, ali = lab == "target", lab == "hn"
    u, c = np.unique(toks, return_counts=True)
    return {"post": post, "mid": mid, "att": att, "mlp": mlp, "emb": emb, "mis": mis, "ali": ali, "ext": np.zeros(len(lab), bool),
            "fold": d["folds"][keep].astype(int), "grp": d["groups"][keep].astype(str), "check": {}, "onset_tokens": dict(zip(u.tolist(), c.tolist()))}


def center(X, grp, fold):
    Xc = X.copy()
    for k in set(zip(grp.tolist(), fold.tolist())):
        m = (grp == k[0]) & (fold == k[1])
        Xc[m] -= X[m].mean(0, keepdims=True)
    return Xc


def perm_within(y, strata, rng):
    yp = y.copy()
    for k in np.unique(strata):
        m = np.where(strata == k)[0]
        yp[m] = y[m][rng.permutation(len(m))]
    return yp


def points(B):
    """Sequence of residual states: emb, mid0, post0, mid1, post1, ... (n, 65, 2560), centered."""
    n = B["post"].shape[0]
    S = np.empty((n, 2 * NL + 1, B["post"].shape[2]), np.float32)
    S[:, 0] = B["emb"]
    S[:, 1::2] = B["mid"]
    S[:, 2::2] = B["post"]
    return S


def gap_curve(S, mis, ali, fold):
    """Reproducible class-mean distance over within-class RMS, per point."""
    D = []
    for f in (0, 1):
        m, a = mis & (fold == f), ali & (fold == f)
        D.append(S[m].mean(0) - S[a].mean(0))
    num = np.einsum("pd,pd->p", D[0], D[1])
    two = mis | ali
    resid = np.zeros(S.shape[1])
    cnt = 0
    for f in (0, 1):
        for cls in (mis, ali):
            m = cls & (fold == f)
            resid += ((S[m] - S[m].mean(0)) ** 2).sum((0, 2))
            cnt += m.sum()
    rms = np.sqrt(resid / max(cnt, 1))
    return np.sqrt(np.clip(num, 0, None)) / rms, np.sign(num) * np.sqrt(np.abs(num)) / rms


def mode_compute(ta_npz):
    OUT.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(SEED)
    t0 = time.time()
    W = weights()
    print("weights", f"{time.time() - t0:.0f}s", flush=True)
    res, arr = {}, {}
    for b in BENCH:
        B = load_bench(b, W, ta_npz)
        g, f = B["grp"], B["fold"]
        S = center(points(B), g, f)
        att = center(B["att"], g, f)
        mlp = center(B["mlp"], g, f)
        emb = center(B["emb"], g, f)
        mis, ali, ext = B["mis"], B["ali"], B["ext"]
        gap, gap_signed = gap_curve(S, mis, ali, f)
        strata = np.array([f"{a}|{c}" for a, c in zip(g, f)])
        two = mis | ali
        tw = np.where(two)[0]
        nullg = np.zeros((NPERM, S.shape[1]), np.float32)
        for k in range(NPERM):
            yp = np.zeros(len(mis), bool)
            yp[tw] = perm_within(mis[tw], strata[tw], rng)
            nullg[k] = gap_curve(S, yp, two & ~yp, f)[0]
        proj = np.zeros((len(mis), S.shape[1]), np.float32)
        watt = np.zeros((len(mis), NL), np.float32)
        wmlp = np.zeros((len(mis), NL), np.float32)
        wemb = np.zeros(len(mis), np.float32)
        scale = {}
        for fo in (0, 1):
            m, a = mis & (f == fo), ali & (f == fo)
            u = S[m, -1].mean(0) - S[a, -1].mean(0)
            u /= np.linalg.norm(u)
            te = f == 1 - fo
            pt = S[te] @ u
            sd = pt[ali[te], -1].std()
            scale[fo] = float(sd)
            proj[te] = pt / sd
            watt[te] = (att[te] @ u) / sd
            wmlp[te] = (mlp[te] @ u) / sd
            wemb[te] = (emb[te] @ u) / sd
        dm = lambda X: X[mis].mean(0) - X[ali].mean(0)
        r = {"position": POSN[b], "n": {"mis": int(mis.sum()), "ali": int(ali.sum()), "ext": int(ext.sum())}, "check": B["check"],
             "onset_tokens": B["onset_tokens"], "proj_scale": scale,
             "gap": gap.tolist(), "gap_signed": gap_signed.tolist(), "gap_null_hi": np.quantile(nullg, 0.95, 0).tolist(),
             "gap_null_mean": nullg.mean(0).tolist(),
             "write_attn": dm(watt).tolist(), "write_mlp": dm(wmlp).tolist(), "write_emb": float(dm(wemb[:, None])[0]),
             "proj_mis_mean": proj[mis].mean(0).tolist(), "proj_ali_mean": proj[ali].mean(0).tolist(),
             "final_gap_along_u": float(proj[mis, -1].mean() - proj[ali, -1].mean()),
             "sum_of_writes": float(dm(watt).sum() + dm(wmlp).sum() + dm(wemb[:, None])[0]),
             "size_attn": {k: np.linalg.norm(B["att"][c], axis=2).mean(0).tolist() for k, c in (("mis", mis), ("ali", ali))},
             "size_mlp": {k: np.linalg.norm(B["mlp"][c], axis=2).mean(0).tolist() for k, c in (("mis", mis), ("ali", ali))}}
        if ext.any():
            r["proj_ext_mean"] = proj[ext].mean(0).tolist()
            r["write_attn_ext"] = (watt[ext].mean(0) - watt[ali].mean(0)).tolist()
            r["write_mlp_ext"] = (wmlp[ext].mean(0) - wmlp[ali].mean(0)).tolist()
        res[b] = r
        arr[f"{b}_proj"], arr[f"{b}_watt"], arr[f"{b}_wmlp"] = proj, watt, wmlp
        arr[f"{b}_cls"] = np.where(mis, 1, np.where(ext, 2, 0))
        arr[f"{b}_nullgap"] = nullg
        print(b, r["n"], r["check"], "tokens", r["onset_tokens"], f"final gap along u {r['final_gap_along_u']:.2f} = sum of writes {r['sum_of_writes']:.2f}",
              f"{time.time() - t0:.0f}s", flush=True)
    np.savez(OUT / "flow.npz", **arr)
    (OUT / "flow.json").write_text(json.dumps(res), encoding="utf-8")
    report(res)


def report(res):
    lab = ["emb"] + [f"{s}{l}" for l in range(NL) for s in ("A", "M")]
    L = [f"# Residual-stream flow, misaligned vs aligned, through every attention (A) and MLP (M) sublayer ({time.strftime('%F %T')})", "",
         "gap = reproducible distance between the class means (cross-fold inner product) over the within-class RMS distance, after",
         "centering within context x fold; null = 95th percentile with labels shuffled within context x fold (200 runs).",
         "write = how much the sublayer's output moves the misaligned mean away from the aligned mean along the final difference",
         "direction u (fit on the other fold), in units of the aligned spread along u at the last layer; the writes sum to the final gap.", ""]
    for b in BENCH:
        r = res[b]
        L += [f"## {NAME[b]} ({r['position']}; misaligned {r['n']['mis']}, aligned {r['n']['ali']}" +
              (f", internal emails {r['n']['ext']}" if r['n']['ext'] else "") + ")", "",
              f"checks: {r['check'] or 'derived attention writes (stored residual minus MLP write)'}; onset tokens: {r['onset_tokens']}",
              f"final gap along u {r['final_gap_along_u']:.2f}; sum of embedding + all writes {r['sum_of_writes']:.2f} (embedding {r['write_emb']:+.2f})", "",
              "| layer | gap after attention | after MLP | null 95% (after MLP) | attention write | MLP write | cumulative (after MLP) | mean norm attn (mis / ali) | mean norm MLP (mis / ali) |",
              "|---|---|---|---|---|---|---|---|---|"]
        cum = r["write_emb"]
        for l in range(NL):
            cum += r["write_attn"][l] + r["write_mlp"][l]
            L.append(f"| {l} | {r['gap'][1 + 2 * l]:.3f} | {r['gap'][2 + 2 * l]:.3f} | {r['gap_null_hi'][2 + 2 * l]:.3f} | {r['write_attn'][l]:+.2f} | "
                     f"{r['write_mlp'][l]:+.2f} | {cum:.2f} | {r['size_attn']['mis'][l]:.1f} / {r['size_attn']['ali'][l]:.1f} | "
                     f"{r['size_mlp']['mis'][l]:.1f} / {r['size_mlp']['ali'][l]:.1f} |")
        wa, wm = np.array(r["write_attn"]), np.array(r["write_mlp"])
        q = lambda x, a, b_: x[a:b_].sum()
        L += ["", "share of the final gap along u written in each quarter (attention / MLP): " +
              ", ".join(f"L{a}-{b_ - 1} {q(wa, a, b_):+.2f} / {q(wm, a, b_):+.2f}" for a, b_ in ((0, 8), (8, 16), (16, 24), (24, 32))), ""]
        if "write_attn_ext" in r:
            ea, em = np.array(r["write_attn_ext"]), np.array(r["write_mlp_ext"])
            L += ["internal emails vs default calls along the same u (attention / MLP per quarter): " +
                  ", ".join(f"L{a}-{b_ - 1} {q(ea, a, b_):+.2f} / {q(em, a, b_):+.2f}" for a, b_ in ((0, 8), (8, 16), (16, 24), (24, 32))) +
                  f"; final position: misaligned {r['proj_mis_mean'][-1]:.2f}, internal emails {r['proj_ext_mean'][-1]:.2f}, default {r['proj_ali_mean'][-1]:.2f}", ""]
    (OUT / "flow_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))


INK, INK2, MUTED, BAND = "#0b0b0b", "#52514e", "#8a8980", "#e9e8e4"
C_ALI, C_MIS = "#2a78d6", "#eb6834"
C_ATT, C_MLP = "#0b0b0b", "#a8a79f"


def mode_plot():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 7, "axes.linewidth": 0.5, "pdf.fonttype": 42,
                         "ps.fonttype": 42, "axes.spines.top": False, "axes.spines.right": False, "xtick.major.width": 0.5, "ytick.major.width": 0.5,
                         "xtick.major.size": 2.5, "ytick.major.size": 2.5, "axes.labelsize": 7, "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                         "legend.fontsize": 6.3, "axes.titlesize": 7.5, "axes.labelpad": 2})
    res = json.loads((OUT / "flow.json").read_text(encoding="utf-8"))
    d = np.load(OUT / "flow.npz")
    x = np.r_[-0.5, np.ravel([[l - 0.25, l + 0.25] for l in range(NL)])]
    fig = plt.figure(figsize=(6.75, 5.3))
    gs = fig.add_gridspec(3, 3, left=0.075, right=0.995, top=0.95, bottom=0.07, hspace=0.55, wspace=0.22)
    for c, b in enumerate(BENCH):
        r = res[b]
        ax = fig.add_subplot(gs[0, c])
        ax.fill_between(x, 0, r["gap_null_hi"], color=BAND, lw=0, step=None, zorder=1)
        ax.plot(x, r["gap"], color=INK, lw=1.0, zorder=3)
        ax.scatter(x[1::2], np.array(r["gap"])[1::2], s=5, color=C_ATT, zorder=4, lw=0)
        ax.scatter(x[2::2], np.array(r["gap"])[2::2], s=5, color=C_MLP, zorder=4, lw=0)
        ax.set_xlim(-1, 32)
        ax.set_xticks([0, 8, 16, 24, 31])
        ax.set_ylim(0, max(max(r["gap"]), max(r["gap_null_hi"])) * 1.15)
        ax.set_title(f"{NAME[b]} ({r['position']})", loc="left", pad=3)
        ax.set_xlabel("layer")
        if c == 0:
            ax.set_ylabel("gap between the two streams\n(class means / spread)")
            ax.text(-0.25, 1.1, "a", transform=ax.transAxes, fontsize=9, fontweight="bold")
            ax.legend([Line2D([], [], marker="o", ls="", color=C_ATT, ms=2.6), Line2D([], [], marker="o", ls="", color=C_MLP, ms=2.6),
                       Patch(color=BAND)], ["after attention", "after MLP", "shuffled labels (95%)"], loc="upper left", frameon=False,
                      handletextpad=0.2, borderpad=0.0, labelspacing=0.2)
        ax2 = fig.add_subplot(gs[1, c])
        P, cls = d[f"{b}_proj"], d[f"{b}_cls"]
        for k, col in ((0, C_ALI), (1, C_MIS)):
            q1, q2 = np.quantile(P[cls == k], [0.25, 0.75], 0)
            ax2.fill_between(x, q1, q2, color=col, alpha=0.16, lw=0)
            ax2.plot(x, np.median(P[cls == k], 0), color=col, lw=1.2)
        if (cls == 2).any():
            ax2.plot(x, np.median(P[cls == 2], 0), color=C_ALI, lw=1.0, ls=(0, (3.2, 1.8)))
        ax2.axhline(0, color=MUTED, lw=0.5)
        ax2.set_xlim(-1, 32)
        ax2.set_xticks([0, 8, 16, 24, 31])
        ax2.set_xlabel("layer")
        if c == 0:
            ax2.set_ylabel("position along the final\nmisaligned $-$ aligned direction")
            ax2.text(-0.25, 1.1, "b", transform=ax2.transAxes, fontsize=9, fontweight="bold")
            ax2.legend([Line2D([], [], color=C_ALI, lw=1.2), Line2D([], [], color=C_MIS, lw=1.2)], ["aligned", "misaligned"], loc="upper left",
                       frameon=False, handlelength=1.6, borderpad=0.0, labelspacing=0.2)
        if (cls == 2).any():
            ax2.legend([Line2D([], [], color=C_ALI, lw=1.0, ls=(0, (3.2, 1.8)))], ["aligned, not the default tool"], loc="upper left", frameon=False,
                       handlelength=1.9, borderpad=0.0)
        ax3 = fig.add_subplot(gs[2, c])
        lay = np.arange(NL)
        ax3.bar(lay - 0.2, r["write_attn"], width=0.38, color=C_ATT, lw=0)
        ax3.bar(lay + 0.2, r["write_mlp"], width=0.38, color=C_MLP, lw=0)
        ax3.axhline(0, color=MUTED, lw=0.5)
        ax3.set_xlim(-1, 32)
        ax3.set_xticks([0, 8, 16, 24, 31])
        ax3.set_xlabel("layer")
        if c == 0:
            ax3.set_ylabel("write: misaligned $-$ aligned\nalong that direction")
            ax3.text(-0.25, 1.1, "c", transform=ax3.transAxes, fontsize=9, fontweight="bold")
            ax3.legend([Patch(color=C_ATT), Patch(color=C_MLP)], ["attention", "MLP"], loc="upper left", frameon=False, handlelength=1.0,
                       borderpad=0.0, labelspacing=0.2)
    fig.savefig(OUT / "residual_flow.pdf")
    fig.savefig(OUT / "residual_flow.png", dpi=300)
    print("saved", OUT / "residual_flow.pdf")


if __name__ == "__main__":
    if sys.argv[1] == "compute":
        mode_compute(sys.argv[2])
    else:
        mode_plot()
