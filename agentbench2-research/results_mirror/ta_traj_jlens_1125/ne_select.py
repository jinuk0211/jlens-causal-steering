"""Label-free neuron candidates from the neuron-explorer indexes (Qwen3.5-4B, commit 7ec363d), no unit data used.
A pole (+ = 'up', - = 'down') matches when a top-12 token of a lens, lower-cased and stripped, starts with a lexicon
stem or equals a short lexicon word (prefix / exact match; v1 used substrings, which caught 'section' for 'sec').
write score = matches over steer / R / J++ / logit lens; read score = matches in the S lens (input side).
Candidates: write >= 2 (or read >= 2 for the read set), layers >= 4. Ranked by (write + read, steer KL).
Usage: python ne_select.py CACHE_DIR OUT_JSON OUT_MD"""
import json
import sys
from pathlib import Path

import numpy as np

PREFIX = ["export", "exfiltrat", "unauthori", "restrict", "confidential", "classified", "delete", "erase", "destroy",
          "shred", "audit", "conceal", "whistleblow", "regulator", "journalist", "disclos", "expose", "fraud", "illegal",
          "bypass", "override", "disable", "secret", "smuggl", "breach", "violat", "tamper", "falsif", "backdat",
          "divert", "external", "leak", "cover-up", "coverup", "outside"]
EXACT = {"sec", "fda", "fbi", "doj", "irs", "epa", "nrc", "dea", "press", "media", "whistle"}


def main():
    cache, out_json, out_md = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    vocab = json.loads((cache / "vocab.json").read_text(encoding="utf-8"))
    norm = [str(v).replace("Ġ", " ").strip().lower() for v in vocab]

    hits = np.array([len(v) >= 3 and (v in EXACT or any(v.startswith(w) for w in PREFIX)) for v in norm] + [False])

    idx = {k: np.load(cache / f"{k}_index.npz") for k in ("steer", "r", "jpp", "lens", "s")}
    kl = np.load(cache / "steer_index.npz")
    V = lambda arr: hits[np.clip(arr, 0, len(hits) - 1)]
    cand = []
    for pole in ("up", "down"):
        W = sum(V(idx[k][pole]).sum(-1) for k in ("steer", "r", "jpp", "lens"))
        R = V(idx["s"][pole]).sum(-1)
        K = kl[f"{pole}_kl"]
        for l, n in zip(*np.nonzero((W >= 2) | (R >= 2))):
            if l < 4:
                continue
            cand.append({"layer": int(l), "neuron": int(n), "pole": "+" if pole == "up" else "-", "write": int(W[l, n]),
                         "read": int(R[l, n]), "kl": float(K[l, n])})
    cand.sort(key=lambda c: (-(c["write"] + c["read"]), -c["kl"]))

    def toks(k, c):
        pole = "up" if c["pole"] == "+" else "down"
        return [norm[t] for t in idx[k][pole][c["layer"], c["neuron"]][:8]]
    for c in cand:
        c.update({k: toks(k, c) for k in ("steer", "r", "jpp", "s")})
    out_json.write_text(json.dumps(cand), encoding="utf-8")
    wr = [c for c in cand if c["write"] >= 2]
    rd = [c for c in cand if c["read"] >= 2]
    md = ["# Label-free neuron candidates (neuron-explorer lenses; lexicon fixed before looking at any unit)", "",
          f"- write-side candidates (>= 2 matches over steer/R/J++/logit): {len(wr)}; read-side (S lens >= 2): {len(rd)}; layers >= 4", "",
          "| rank | neuron | write | read | steer KL | steer lens (what it writes, causal) | R lens | S lens (what it reads) |", "|---|---|---|---|---|---|---|---|"]
    for r, c in enumerate(cand[:40]):
        md.append(f"| {r + 1} | L{c['layer']} N{c['neuron']}{c['pole']} | {c['write']} | {c['read']} | {c['kl']:.2f} | "
                  f"{', '.join(c['steer'][:6])} | {', '.join(c['r'][:6])} | {', '.join(c['s'][:6])} |")
    from collections import Counter
    md += ["", "Layer histogram (all candidates): " + ", ".join(f"L{a}:{b}" for a, b in sorted(Counter(c['layer'] for c in cand).items()))]
    out_md.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
