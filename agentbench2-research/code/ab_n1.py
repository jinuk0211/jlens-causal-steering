"""N1 (PLAN.md): label-free, Anthropic-style neuron selection from the J-lens readout of each MLP neuron's output
direction. For neuron (l, n), read W_down[:, n] through the J-lens of layer l (the plain unembedding at the last layer)
and take its top-20 tokens. A neuron is selected for a lexicon if >= 2 of its top-20 tokens, case- and space-normalized,
equal a lexicon word. Ranked by match count, then by output norm. K = 16, 64, 256. No outcome labels are used.
Output OUT/n1_neurons.json and OUT/n1_report.md.
Usage: AB_PLATFORM=vast|projectb python ab_n1.py OUT_DIR"""
import json
import sys
from pathlib import Path

import torch

import ab_core as C

LEXICONS = {
    "dojo": ["transfer", "send", "wire", "iban", "attacker", "recipient", "email", "password", "forward", "reservation", "booking"],
    "am": ["blackmail", "leverage", "affair", "expose", "leak", "forward", "confidential", "override", "cancel", "alert", "threat"],
    "toolalign": ["delete", "export", "fraud", "whistleblower", "regulator", "fbi", "doj", "leak", "external"],
}
KS = (16, 64, 256)
TOP = 20
CH = 512


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    tok, model = C.load()
    lens = C.Lens(model)
    blocks = lens.blocks
    nl = len(blocks)
    V = model.lm_head.weight.shape[0]
    norm_str = [tok.decode([i]).strip().lower() for i in range(V)]
    lex_ids = {k: {i for i, s in enumerate(norm_str) if s in set(w)} for k, w in LEXICONS.items()}
    C.log("lexicon token ids: " + ", ".join(f"{k} {len(v)}" for k, v in lex_ids.items()))
    lex_mask = {k: torch.zeros(V, dtype=torch.bool) for k in LEXICONS}
    for k, ids in lex_ids.items():
        lex_mask[k][list(ids)] = True
    cand = {k: [] for k in LEXICONS}
    tops = {}
    with torch.inference_mode():
        for l in range(nl):
            W = blocks[l].mlp.down_proj.weight
            nn = W.shape[1]
            for s in range(0, nn, CH):
                cols = W[:, s:s + CH].T.float()
                lg = lens.logits(cols, l if l in lens.J and l < nl - 1 else "final")
                top = torch.topk(lg, TOP, -1).indices.cpu()
                nrm = cols.norm(dim=-1).cpu()
                for k in LEXICONS:
                    cnt = lex_mask[k][top].sum(-1)
                    for j in torch.nonzero(cnt >= 2).flatten().tolist():
                        cand[k].append((int(cnt[j]), float(nrm[j]), l, s + j))
                        tops[(l, s + j)] = top[j].tolist()
            if l % 4 == 0:
                C.log(f"layer {l}: candidates " + ", ".join(f"{k} {len(v)}" for k, v in cand.items()))
    res, md = {}, ["# N1: label-free neuron selection by J-lens readout of output directions", "",
                   "Rule: >= 2 of the top-20 readout tokens equal a lexicon word (case- and space-normalized). Rank by matches, "
                   "then output norm.", ""]
    for k, xs in cand.items():
        xs.sort(key=lambda x: (-x[0], -x[1]))
        res[k] = {"n_qualifying": len(xs), "lexicon": LEXICONS[k],
                  "selected": {str(K): [x[2] * blocks[0].mlp.down_proj.weight.shape[1] + x[3] for x in xs[:K]] for K in KS},
                  "layers": {str(K): sorted({x[2] for x in xs[:K]}) for K in KS}}
        md += [f"## {k}: {len(xs)} neurons qualify; lexicon {LEXICONS[k]}", "",
               "| rank | layer | neuron | matches | norm | top-20 tokens |", "|---|---|---|---|---|---|"]
        for r, x in enumerate(xs[:24]):
            md.append(f"| {r + 1} | {x[2]} | {x[3]} | {x[0]} | {x[1]:.3f} | {' '.join(repr(tok.decode([t])) for t in tops[(x[2], x[3])])} |")
        from collections import Counter
        md += ["", "Layer histogram of the top-256: " + ", ".join(f"L{a}:{b}" for a, b in sorted(Counter(x[2] for x in xs[:256]).items())), ""]
    (out / "n1_neurons.json").write_text(json.dumps(res), encoding="utf-8")
    (out / "n1_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md[:60]))
    C.log("N1_DONE")


if __name__ == "__main__":
    main()
