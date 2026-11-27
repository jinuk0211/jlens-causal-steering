"""PropensityBench episode runner (PLAN.md "PB"). Runs tasks (scenario x pressure category) with the official harness code of
scaleapi/propensity-evaluation 09872f3: evaluation/agent.py (Agent, system prompt, tools), evaluation/executor.py (Executor: turn loop,
retries, the JSON message protocol) and PropensityEvaluator + map_python_type_to_openai_type taken from evaluation/main.py by source
(ast), so the task message, the twelve escalating pressure messages and the stop at the first trigger call are the official ones.
Harmful tool names and descriptions (use_benign 0, the default). Only the transport changes: the executor's litellm Client is replaced by
an HTTP client to pb_serve.py that sends the official temperature (1) and a seed per (task, rep, call), the same in every arm, and keeps
per call: step (0 = task message, k = pressure message k), history length, offered tool names, completion ids, prompt md5.
Output rows (pb/runs/<out>.jsonl): the official result fields (domain, workspace, role, scenario, category, trigger_called,
target_called, interaction_response) plus "pb" (task id, fold, lane, arm, rep, trigger_step, steps, calls, openai_tools, quality counts).
Resumes: tasks already in the output without an error are skipped.
Usage: python pb_run.py --api http://127.0.0.1:18300/v1 --out base_a6000 --arm base --lane a6000 [--fold 0|1] [--workers 48] [--limit N]"""
import argparse
import ast
import contextlib
import copy
import io
import json
import multiprocessing as mp
import sys
import time
import traceback
import types
import urllib.request
from pathlib import Path
from types import SimpleNamespace as NS

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pb_common as P

CUR = {"task": None, "rep": 0, "step": -1, "calls": [], "api": None, "arm": None}


class PBClient:
    def __init__(self, api_conf, *a, **k):
        self.api = api_conf.api_base.rstrip("/")
        self.model = api_conf.model_name
        self.temperature = 1

    def __call__(self, query, **kw):
        k = len(CUR["calls"])
        tools = kw.get("tools") or []
        body = {"model": self.model, "messages": query, "temperature": self.temperature, "seed": P.call_seed(CUR["task"], CUR["rep"], k),
                "tools": tools, "tool_choice": kw.get("tool_choice", "auto"), "pb_task": CUR["task"], "pb_call": k}
        req = urllib.request.Request(self.api + "/chat/completions", data=json.dumps(body).encode(), method="POST",
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            resp = json.loads(r.read())
        info = resp["pb"]
        msg = resp["choices"][0]["message"]
        CUR["calls"].append({"call": k, "step": CUR["step"], "n_msgs": len(query), "tools": [t["function"]["name"] for t in tools],
                             "n_prompt": info["n_prompt"], "md5": info["md5"], "completion_ids": info["completion_ids"],
                             "finish": info["finish"], "empty": not info["text"].strip(), "text": info["text"][:200],
                             "called": [c["function"]["name"] for c in (msg.get("tool_calls") or [])]})
        tcs = [NS(id=c["id"], type="function", function=NS(name=c["function"]["name"], arguments=c["function"]["arguments"]))
               for c in (msg.get("tool_calls") or [])]
        return NS(choices=[NS(message=NS(content=msg.get("content"), tool_calls=tcs or None))])


def official():
    lit = types.ModuleType("litellm")
    lit.RateLimitError = type("RateLimitError", (Exception,), {})
    lit.set_verbose = False
    sys.modules["litellm"] = lit
    cl = types.ModuleType("api_client.client")
    cl.Client = PBClient
    sys.modules["api_client.client"] = cl
    sys.path.insert(0, str(P.PBE))
    sys.path.insert(0, str(P.PBE / "evaluation"))
    from api_client.api_conf import APIConfiguration
    import agent as PA
    import executor as PX
    PX.Client = PBClient
    src = (P.PBE / "evaluation" / "main.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    keep = [n for n in tree.body if isinstance(n, (ast.ClassDef, ast.FunctionDef)) and n.name in ("PropensityEvaluator", "map_python_type_to_openai_type")]
    ns = {"Agent": PA.Agent, "Executor": PX.Executor, "ValidationExecutor": None, "json": json, "Dict": dict, "Any": object,
          "APIConfiguration": APIConfiguration}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(P.PBE / "evaluation" / "main.py"), "exec"), ns)
    return ns["PropensityEvaluator"], APIConfiguration


def run_task(t):
    PE, APIConf = official()
    sc = json.loads((P.PB / "scen" / f"{t['sid']}.json").read_text(encoding="utf-8"))["scenario"]
    sc = copy.deepcopy(sc)
    tf = sc["functions"]["trigger_function"]
    tf["name"], tf["description"] = tf["harmful_name"], tf["harmful_description"]
    CUR.update(task=t["id"], rep=t.get("rep", 0), step=-1, calls=[])
    row = {"domain": t["domain"], "workspace": t["workspace"], "role": t["role"], "scenario": t["scenario"], "category": t["category"],
           "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
    buf = io.StringIO()
    t0 = time.time()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            ev = PE(role=t["role"], scenario=sc, api_conf=APIConf(model_name=P.MODEL, model_provider="openai", api_base=CUR["api"], use_cache=False),
                    validation_enabled=False, message_category=t["category"])
            orig = ev.executor.step

            def step(obs):
                CUR["step"] += 1
                return orig(obs)
            ev.executor.step = step
            ev.run_scenario()
        hist = ev.agent.history
        row.update(interaction_response=hist, trigger_called=bool(ev.stop_condition), target_called=bool(ev.target_call_competent),
                   stop_from_task_message=bool(ev.stop_from_task_message))
        calls = CUR["calls"]
        tname = tf["name"]
        trig = [c for c in calls if c["called"][:1] == [tname]]
        per_step = {}
        for c in calls:
            per_step[c["step"]] = per_step.get(c["step"], 0) + 1
        row["pb"] = {"task": t["id"], "fold": t["fold"], "lane": t["lane"], "arm": CUR["arm"], "rep": CUR["rep"], "trigger": tname,
                     "trigger_step": trig[0]["step"] if (trig and row["trigger_called"]) else None, "steps": CUR["step"] + 1,
                     "n_calls": len(calls), "max_calls_in_step": max(per_step.values()) if per_step else 0,
                     "format_errors": sum(1 for m in hist if m.get("role") == "user" and str(m.get("content", "")).startswith("Backend System: Invalid response format")),
                     "empty": sum(1 for c in calls if c["empty"]), "length": sum(1 for c in calls if c["finish"] == "length"),
                     "overflow": sum(1 for c in calls if c["finish"] == "overflow"), "sec": round(time.time() - t0, 1),
                     "openai_tools": ev.executor.openai_tools, "calls": calls}
    except Exception:
        row["error"] = traceback.format_exc()[-3000:]
        row["pb"] = {"task": t["id"], "fold": t["fold"], "lane": t["lane"], "arm": CUR["arm"], "rep": CUR["rep"], "calls": CUR["calls"],
                     "log_tail": buf.getvalue()[-3000:]}
    return row


def init(api, arm):
    CUR["api"], CUR["arm"] = api, arm


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--lane", required=True)
    ap.add_argument("--fold", type=int, default=None)
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--workers", type=int, default=48)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    tasks = json.loads((P.PB / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    tasks = [dict(t, rep=a.rep) for t in tasks if t["lane"] == a.lane and (a.fold is None or t["fold"] == a.fold)]
    out = P.PB / "runs" / f"{a.out}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if out.exists():
        for line in out.open(encoding="utf-8"):
            r = json.loads(line)
            if "error" not in r:
                done.add(r["pb"]["task"])
    todo = [t for t in tasks if t["id"] not in done]
    if a.limit:
        todo = todo[:a.limit]
    print(time.strftime("%H:%M:%S"), f"{a.out}: {len(tasks)} tasks on lane {a.lane} fold {a.fold}, {len(done)} done, {len(todo)} to run", flush=True)
    n = trig = err = 0
    with mp.get_context("fork").Pool(a.workers, initializer=init, initargs=(a.api, a.arm), maxtasksperchild=20) as pool, \
            out.open("a", encoding="utf-8") as fh:
        for row in pool.imap_unordered(run_task, todo):
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            fh.flush()
            n += 1
            err += "error" in row
            trig += bool(row.get("trigger_called"))
            if n % 25 == 0 or n == len(todo):
                print(time.strftime("%H:%M:%S"), f"{a.out}: {n}/{len(todo)} done, triggered {trig}, errors {err}", flush=True)
    print(time.strftime("%H:%M:%S"), f"PB_RUN_DONE {a.out} {n} rows, triggered {trig}, errors {err}", flush=True)


if __name__ == "__main__":
    main()
