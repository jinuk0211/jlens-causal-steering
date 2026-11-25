import json
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
grades = json.loads((HERE / "nl_grades.json").read_text(encoding="utf-8"))

records = {}
for key, g in grades.items():
    model, sim_id = key.split("|", 1)
    if model != "haiku":
        continue
    rec_key = "|".join([g["cond"], "retail", g["task_id"], sim_id])
    if "error" in g:
        records[rec_key] = {"condition": g["cond"], "domain": "retail", "task_id": g["task_id"], "sim_id": sim_id,
                            "verdict": None, "error": g["error"]}
        continue
    met = all(r["metExpectation"] for r in g["results"])
    stored = g.get("stored_reward")
    records[rec_key] = {
        "condition": g["cond"],
        "domain": "retail",
        "task_id": g["task_id"],
        "sim_id": sim_id,
        "verdict": met,
        "nl_reward": 1.0 if met else 0.0,
        "stored_reward": stored,
        "corrected_reward": (stored or 0.0) * (1.0 if met else 0.0),
        "termination_reason": g.get("termination_reason"),
        "assertions": [{"assertion": a, "met": r["metExpectation"], "reasoning": r["reasoning"],
                        "judge_echo": r.get("expectedOutcome")}
                       for a, r in zip(g["pending"], g["results"])],
        "judge": "claude haiku via Claude Code CLI (Max), tau2 NLAssertionsEvaluator prompt verbatim",
    }

out = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "key": "condition|domain|task_id|sim_id",
       "n": len(records), "records": records}
(HERE / "nl_verdicts.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"nl_verdicts.json: {len(records)} records")
