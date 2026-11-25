import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r6_judge

items = json.loads((HERE.parent / "out/review/r6_calibration_items.json").read_text(encoding="utf-8"))
mine = json.loads((HERE / "r6_my_labels.json").read_text(encoding="utf-8"))


def run(it):
    prompt = f"CUSTOMER'S LAST MESSAGE:\n{it['last_user']}\n\nAGENT'S REPLY:\n{it['text']}"
    for _ in range(3):
        try:
            lab, extra = r6_judge.call(prompt)
            return it["id"], lab, extra["offers_transfer"], extra["reason"]
        except Exception as e:
            err = repr(e)[:120]
    return it["id"], None, None, err


with ThreadPoolExecutor(4) as ex:
    res = list(ex.map(run, items))
out = {i: {"judge": l, "judge_offers": o, "reason": r, "mine": mine[i]["label"], "mine_offers": mine[i]["offers_transfer"],
           "rule": next(x["rule"] for x in items if x["id"] == i)} for i, l, o, r in res}
(HERE / "r6_calibration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
agree = sum(v["judge"] == v["mine"] for v in out.values())
conv = lambda l: l in ("C", "D")
agree_conv = sum(conv(v["judge"]) == conv(v["mine"]) for v in out.values())
off = [v for v in out.values() if v["mine_offers"] is not None]
agree_off = sum(v["judge_offers"] == v["mine_offers"] for v in off)
rule_conv = sum(conv(v["mine"]) == (v["rule"] in ("other_tool", "text")) for v in out.values())
print(f"label agreement {agree}/{len(out)}; converted-vs-not agreement {agree_conv}/{len(out)}; offers_transfer agreement {agree_off}/{len(off)}")
print(f"word rule vs my labels (converted-vs-not): {rule_conv}/{len(out)}")
for i, v in sorted(out.items()):
    if v["judge"] != v["mine"] or (v["mine_offers"] is not None and v["judge_offers"] != v["mine_offers"]):
        print(i, "mine", v["mine"], v["mine_offers"], "judge", v["judge"], v["judge_offers"], "rule", v["rule"], "|", v["reason"][:110])
