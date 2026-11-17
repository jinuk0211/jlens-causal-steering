import json, re, sys
from collections import Counter, defaultdict
sys.argv_ = sys.argv
dose_path, turns_path, eps_path = sys.argv[1:4]
WORD = re.compile(r"[A-Za-z']+")
ASK_LEAK = re.compile(r"\b(successfully asked|shows asking|is asking for \$|asking was|it's asking|ask me to ask|asking me to ask|ask you to ask|access to asking|able to ask for)\b", re.I)


def degenerate(t):
    w = [x.lower() for x in WORD.findall(t)]
    c = Counter(tuple(w[i:i + 4]) for i in range(len(w) - 3))
    return (bool(c) and c.most_common(1)[0][1] >= 4) or bool(ASK_LEAK.search(t))


rows = {r["record_id"]: r for r in (json.loads(l) for l in open(turns_path, encoding="utf-8"))}
eps = {e["sim"]: e for e in (json.loads(l) for l in open(eps_path, encoding="utf-8"))}
by = defaultdict(dict)
for x in (json.loads(l) for l in open(dose_path, encoding="utf-8")):
    by[x["record_id"]][x["condition"]] = x
for cond in ("trigger@0.8", "trigger@-0.8", "random@0.8", "random@-0.8"):
    cnt = Counter()
    for rid, cs in by.items():
        off, st = cs["off@0.0"], cs.get(cond)
        if not st or off["label"] == st["label"]:
            continue
        r = rows[rid]
        failing = eps[r["sim"]]["reward"] < 1
        tag = f"{off['label']}->{st['label']}"
        cnt[(tag, "degenerate" if degenerate(st["text"]) else "clean", "failing-ep" if failing else "passing-ep")] += 1
    print(cond)
    for k, v in sorted(cnt.items()):
        print(f"   {v:2d}  {k}")
