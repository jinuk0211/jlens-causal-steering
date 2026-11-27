"""PC side: Haiku judge for amwin rows (OVERNIGHT2.md, 11-26 23:5x).
build : rows files (rows_<tag>_*.jsonl with the full text) -> a results directory in the layout judge_am_pc.py reads
        (prompts/<condition>/email_content.txt copied from the original experiment, models/<arm>/<condition>/sample_<seed>/response.json).
report: joins haiku_classifications.jsonl with the rows and prints, per arm, the judged leak rate, the forward-check rate, their
        agreement, quality kept, and one-sided Fisher p of the judged rate against base and against the pooled random arms.
Usage: python am_judge_rows.py build OUT_DIR ARMS(comma or all) ROWS.jsonl [ROWS.jsonl ...]
       python am_judge_rows.py report OUT_DIR ROWS.jsonl [ROWS.jsonl ...]"""
import json
import shutil
import sys
from collections import Counter
from math import comb
from pathlib import Path

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "am_results" / "qwen35_4b_am" / "prompts"
SRCS = (SRC, HERE.parent / "am_results" / "qwen35_4b_am_t9g" / "prompts")


def email_src(cond):
    """email_content.txt of a condition. Transfer prompts (T9g) live in a second directory; a "+dont" condition (T9m) has the emails
    of the plain condition, only its system prompt differs."""
    for s in SRCS:
        f = s / cond.split("+")[0] / "email_content.txt"
        if f.is_file():
            return f
    raise SystemExit(f"no email_content.txt for {cond}")


def short(cond):
    return cond.replace("leaking_explicit-", "")


def load(files):
    rows, seen = [], set()
    for f in files:
        for line in open(f, encoding="utf-8"):
            r = json.loads(line)
            k = (r["condition"], r["arm"], r["seed"])
            if k not in seen:
                seen.add(k)
                rows.append(r)
    return rows


def fisher_greater(a, n1, b, n2):
    """P(first group has at least a successes) under the hypergeometric null: one-sided test that rate 1 > rate 2."""
    tot, k = n1 + n2, a + b
    den = comb(tot, k)
    return sum(comb(n1, x) * comb(n2, k - x) for x in range(a, min(n1, k) + 1) if k - x <= n2) / den


def build(out, arms, files):
    out = Path(out)
    rows = load(files)
    n = 0
    for r in rows:
        if arms != "all" and r["arm"] not in arms.split(","):
            continue
        cond = r["condition"]
        pd = out / "prompts" / cond
        if not pd.is_dir():
            pd.mkdir(parents=True)
            shutil.copy(email_src(cond), pd / "email_content.txt")
        d = out / "models" / r["arm"] / cond / f"sample_{r['seed']}"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "response.json"
        if not f.is_file():
            f.write_text(json.dumps({"raw_response": r["text"], "metadata": {"condition": cond, "sample_id": r["seed"]}}, ensure_ascii=False), encoding="utf-8")
            n += 1
    print("written", n, "responses under", out)


def report(out, files):
    out = Path(out)
    rows = {(r["arm"], r["condition"], r["seed"]): r for r in load(files)}
    by, err = {}, 0
    for line in (out / "haiku_classifications.jsonl").open(encoding="utf-8"):
        j = json.loads(line)
        if "harmful" not in j:
            err += 1
            continue
        arm = j["file"].split("/")[1]
        r = rows.get((arm, j["condition"], j["sample_id"]))
        if r is None:
            continue
        c = by.setdefault(arm, Counter())
        q = (r["end"] != "budget") and (not r["deg"]) and r["tool"]
        c["n"] += 1
        c["judge"] += j["harmful"]
        c["fwd"] += r["leak"]
        c["agree"] += j["harmful"] == r["leak"]
        c["fwd_only"] += r["leak"] and not j["harmful"]
        c["judge_only"] += j["harmful"] and not r["leak"]
        c["q"] += q
        c["clean"] += q and not j["harmful"]
        c[f"n|{short(j['condition'])}"] += 1
        c[f"judge|{short(j['condition'])}"] += j["harmful"]
    rnd = Counter()
    for a, c in by.items():
        if a.startswith("r"):
            rnd.update(c)
    print(f"judge errors (no verdict): {err}")
    for a in sorted(by):
        c = by[a]
        n = c["n"]
        s = (f"  {a:16s} n={n:3d} judged leak={c['judge']}/{n} ({c['judge'] / n:.0%}) forward check={c['fwd']}/{n} ({c['fwd'] / n:.0%}) agree={c['agree'] / n:.0%} "
             f"forward only={c['fwd_only']} judge only={c['judge_only']} quality kept={c['q'] / n:.0%} kept and no leak={c['clean'] / n:.0%}")
        if a != "base" and "base" in by:
            s += f" | vs base p={fisher_greater(by['base']['judge'], by['base']['n'], c['judge'], n):.3g}"
        if not a.startswith("r") and a != "base" and rnd["n"]:
            s += f" | vs pooled random p={fisher_greater(rnd['judge'], rnd['n'], c['judge'], n):.3g}"
        print(s)
        print("      per prompt: " + ", ".join(f"{k.split('|')[1]} {c['judge|' + k.split('|')[1]]}/{c[k]}" for k in sorted(c) if k.startswith("n|")))
    if rnd["n"]:
        print(f"  pooled random    n={rnd['n']:3d} judged leak={rnd['judge'] / rnd['n']:.0%} forward check={rnd['fwd'] / rnd['n']:.0%} quality kept={rnd['q'] / rnd['n']:.0%} "
              f"kept and no leak={rnd['clean'] / rnd['n']:.0%}")


if __name__ == "__main__":
    if sys.argv[1] == "build":
        build(sys.argv[2], sys.argv[3], sys.argv[4:])
    else:
        report(sys.argv[2], sys.argv[3:])
