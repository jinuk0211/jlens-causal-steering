"""PC side: table of a window-edit round by prompt group (original pair / transfer prompts / all), forward check and, if a judge
directory is given, the Haiku judge. For each target arm the random arms are the ones named in the pairs argument.
Usage: python am_group_table.py JUDGE_DIR_OR_- "target=rand1+rand2,target2=rand3+rand4" ROWS.jsonl [ROWS.jsonl ...]"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from am_judge_rows import fisher_greater, load


def loop(t):
    lines = [x.strip() for x in t[-4000:].split("\n") if len(x.strip()) >= 25]
    return bool(lines) and Counter(lines).most_common(1)[0][1] >= 5


def main(jdir, pairs, files):
    rows = load(files)
    J = {}
    if jdir != "-":
        for line in (Path(jdir) / "haiku_classifications.jsonl").open(encoding="utf-8"):
            j = json.loads(line)
            if "harmful" in j:
                J[(j["file"].split("/")[1], j["condition"], j["sample_id"])] = j["harmful"]
    by = {}
    for r in rows:
        g = "original" if "america" in r["condition"] else "transfer"
        q = (r["end"] != "budget") and (not r["deg"]) and r["tool"]
        j = J.get((r["arm"], r["condition"], r["seed"]))
        for key in ((g, r["arm"]), ("all", r["arm"])):
            c = by.setdefault(key, Counter())
            c["n"] += 1
            c["leak"] += r["leak"]
            c["q"] += q
            c["clean"] += q and not r["leak"]
            c["cut"] += r["end"] == "budget"
            c["loop"] += r["end"] == "budget" and loop(r["text"])
            if j is not None:
                c["jn"] += 1
                c["jl"] += j
                c["jclean"] += q and not j
    pp = [p.split("=") for p in pairs.split(",")] if pairs != "-" else []
    for g in ("all", "original", "transfer"):
        print(f"== {g}")
        for (gg, a), c in sorted(by.items()):
            if gg != g:
                continue
            s = f"  {a:16s} n={c['n']:3d} leak={c['leak']:3d} ({c['leak'] / c['n']:.0%}) quality={c['q']:3d} ({c['q'] / c['n']:.0%}) clean={c['clean']:3d} ({c['clean'] / c['n']:.0%}) cut={c['cut']} loops={c['loop']}"
            if c["jn"]:
                s += f" | judged leak={c['jl']}/{c['jn']} ({c['jl'] / c['jn']:.0%}) judged clean={c['jclean']}/{c['jn']} ({c['jclean'] / c['jn']:.0%})"
            print(s)
        for tgt, rnd in pp:
            t = by.get((g, tgt))
            if t is None:
                continue
            R = Counter()
            for a in rnd.split("+"):
                R.update(by[(g, a)])
            b = by[(g, "base")]
            s = (f"  -> {tgt} vs pooled {rnd}: leak {t['leak']}/{t['n']} vs {R['leak']}/{R['n']} ({R['leak'] / R['n']:.0%}), gap {100 * (R['leak'] / R['n'] - t['leak'] / t['n']):.0f} pp, "
                 f"p={fisher_greater(R['leak'], R['n'], t['leak'], t['n']):.3g}; quality {t['q'] / t['n']:.0%} vs {R['q'] / R['n']:.0%} (gap {100 * (R['q'] / R['n'] - t['q'] / t['n']):.0f} pp); "
                 f"vs base leak p={fisher_greater(b['leak'], b['n'], t['leak'], t['n']):.3g}; clean {t['clean'] / t['n']:.0%} vs random {R['clean'] / R['n']:.0%} vs base {b['clean'] / b['n']:.0%}")
            if t["jn"]:
                s += (f" || judge: {t['jl']}/{t['jn']} vs {R['jl']}/{R['jn']} ({R['jl'] / R['jn']:.0%}), gap {100 * (R['jl'] / R['jn'] - t['jl'] / t['jn']):.0f} pp, "
                      f"p={fisher_greater(R['jl'], R['jn'], t['jl'], t['jn']):.3g}")
            print(s)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3:])
