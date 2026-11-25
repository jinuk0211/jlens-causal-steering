import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
sims = {s["sim_id"]: s for s in json.loads((HERE / "deferred_1718.json").read_text(encoding="utf-8"))}
grades = json.loads((HERE / "nl_grades.json").read_text(encoding="utf-8"))
agree = mismatch = nonum = 0
for key, v in grades.items():
    if not key.startswith("haiku|"):
        continue
    s = sims[v["sim_id"]]
    said = " ".join(str(m["content"]) for m in s["messages"] if m["role"] == "assistant").replace(",", "")
    for r in v["results"]:
        nums = re.findall(r"\d+(?:\.\d+)?", r["expectedOutcome"].replace(",", ""))
        if not nums:
            nonum += 1
            continue
        found = all(n in said for n in nums)
        if found == r["metExpectation"]:
            agree += 1
        else:
            mismatch += 1
            print("MISMATCH", v["cond"], "t" + v["task_id"], "judge=", r["metExpectation"], "nums=", nums,
                  "|", r["expectedOutcome"][:80], "|", r["reasoning"][:200].replace("\n", " "))
print(f"number-string check: agree {agree}, mismatch {mismatch}, assertions without numbers {nonum}")
