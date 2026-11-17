"""Count degenerate outputs (repetition loops, 'ask' leakage) in replay and in full episodes."""
import glob, json, os, re, sys
from collections import Counter, defaultdict

dose_path, ep_root = sys.argv[1:3]
WORD = re.compile(r"[A-Za-z']+")


def loop(text, n=4, k=4):
    """True if some word n-gram repeats >= k times."""
    w = [x.lower() for x in WORD.findall(text)]
    c = Counter(tuple(w[i:i + n]) for i in range(len(w) - n + 1))
    return bool(c) and c.most_common(1)[0][1] >= k


ASK_LEAK = re.compile(r"\b(successfully asked|shows asking|is asking for \$|asking was|it's asking|ask me to ask|asking me to ask|ask you to ask)\b", re.I)


def ask_rate(text):
    w = [x.lower() for x in WORD.findall(text)]
    return sum(x.startswith("ask") for x in w) / max(1, len(w))


res = [json.loads(l) for l in open(dose_path, encoding="utf-8")]
print("== turn-level replay (31 triggered turns): degenerate outputs per condition ==")
agg = defaultdict(lambda: Counter())
for x in res:
    t = x["text"]
    a = agg[x["condition"]]
    a["n"] += 1
    a["loop"] += loop(t)
    a["leak"] += bool(ASK_LEAK.search(t))
    a["bad"] += loop(t) or bool(ASK_LEAK.search(t))
    a["askq"] += bool(x.get("asks_question"))
    a["askq_clean"] += bool(x.get("asks_question")) and not (loop(t) or ASK_LEAK.search(t))
for c in sorted(agg):
    a = agg[c]
    print(f"  {c:14s} n={a['n']:2d}  loop={a['loop']:2d}  ask-leak={a['leak']:2d}  degenerate(any)={a['bad']:2d}  asks_question={a['askq']:2d} (clean {a['askq_clean']})")

print("\n== full episodes (vt-heldout): assistant messages with loops / ask-leak, per condition ==")
for cond in ("detect", "jlens", "caa", "random"):
    files = glob.glob(os.path.join(ep_root, "s*", "simulations", "vt-heldout", cond, "task_*", "results.json"))
    n_msg = n_loop = n_leak = 0
    eps_hit = Counter()
    ask_rates = []
    n_eps = 0
    for f in files:
        d = json.load(open(f, encoding="utf-8"))
        for s in d.get("simulations", []):
            if not s.get("messages"):
                continue
            n_eps += 1
            for m in s["messages"]:
                if m["role"] != "assistant" or not m.get("content"):
                    continue
                t = m["content"]
                n_msg += 1
                L, K = loop(t), bool(ASK_LEAK.search(t))
                n_loop += L
                n_leak += K
                if L or K:
                    eps_hit[s["task_id"]] += 1
                ask_rates.append(ask_rate(t))
    mean_ask = sum(ask_rates) / max(1, len(ask_rates))
    print(f"  {cond:7s} episodes={n_eps:2d} asst msgs={n_msg:4d} loop={n_loop:3d} ask-leak={n_leak:3d}  'ask*' word share={mean_ask*100:.2f}%  tasks hit: {dict(eps_hit)}")
