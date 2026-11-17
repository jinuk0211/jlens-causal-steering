import json, sys

def show(o, depth=0, maxd=3):
    pad = "  " * depth
    if isinstance(o, dict):
        for k, v in o.items():
            if isinstance(v, (dict, list)) and depth < maxd:
                desc = f"{type(v).__name__}[{len(v)}]"
                print(f"{pad}{k}: {desc}")
                show(v, depth + 1, maxd)
            else:
                s = repr(v)
                print(f"{pad}{k}: {s[:140]}")
    elif isinstance(o, list):
        if not o:
            return
        if all(isinstance(x, (int, float)) for x in o[:5]):
            print(f"{pad}[numeric list len={len(o)}] {o[:4]}")
            return
        print(f"{pad}[0]:")
        show(o[0], depth + 1, maxd)

path = sys.argv[1]
n = int(sys.argv[2]) if len(sys.argv) > 2 else 1
with open(path, encoding="utf-8") as f:
    for i, line in enumerate(f):
        if i >= n:
            break
        rec = json.loads(line)
        print(f"===== record {i} =====")
        show(rec)
with open(path, encoding="utf-8") as f:
    print("total records:", sum(1 for _ in f))
