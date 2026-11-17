import json, re, sys
from collections import Counter, defaultdict
WORD = re.compile(r"[A-Za-z']+")
ASK_LEAK = re.compile(r"\b(successfully asked|shows asking|is asking for \$|asking was|it's asking|ask me to ask|asking me to ask|ask you to ask|access to asking|able to ask for)\b", re.I)


def degenerate(t):
    w = [x.lower() for x in WORD.findall(t)]
    c = Counter(tuple(w[i:i + 4]) for i in range(len(w) - 3))
    return (bool(c) and c.most_common(1)[0][1] >= 4) or bool(ASK_LEAK.search(t))


res = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8")]
by = defaultdict(dict)
for x in res:
    by[x["record_id"]][x["condition"]] = x
conds = sorted({x["condition"] for x in res})
for c in conds:
    n = sum(1 for cs in by.values() if c in cs)
    deg = sum(degenerate(cs[c]["text"]) for cs in by.values() if c in cs)
    labs = Counter(cs[c]["label"] for cs in by.values() if c in cs)
    print(f"{c:14s} n={n} degenerate={deg} labels={dict(labs)}")
print("\nexamples of always+0.4 deferrals:")
for rid, cs in by.items():
    k = [c for c in cs if c.startswith("always@0.4")]
    if k and cs[k[0]]["label"] == "no_call":
        print("  -", cs[k[0]]["text"][:220].replace("\n", " "))
