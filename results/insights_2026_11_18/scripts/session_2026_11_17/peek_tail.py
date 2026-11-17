import json, sys
path = sys.argv[1]
want = int(sys.argv[2])
with open(path, encoding="utf-8") as f:
    for i, line in enumerate(f):
        rec = json.loads(line)
        if rec["turn_index"] != want:
            continue
        ctx = rec["rendered_context"]
        print(repr(ctx[-2500:]))
        print("----- generated:")
        print(repr(rec["generated_text"][:800]))
        print("----- tool_calls:", json.dumps(rec["tool_calls"], ensure_ascii=False)[:600])
        print("----- residual labels:", sorted({(r["label"], r["layer"]) for r in rec["measurement"]["residuals"]}))
        break
