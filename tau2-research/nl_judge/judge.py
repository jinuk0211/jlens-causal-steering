import json
import re
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
CLAUDE = r"C:\Users\h\.vscode\extensions\anthropic.claude-code-2.1.325-win32-x64\resources\native-binary\claude.exe"
CWD = HERE / "cwd"
MCP = CWD / "empty_mcp.json"
CWD.mkdir(exist_ok=True)
MCP.write_text('{"mcpServers":{}}')

SYSTEM_PROMPT = """
        TASK
        - You will be given a list of expected outcomes and a conversation that was collected during a test case run.
        - The conversation is between an agent and a customer.
        - Your job is to evaluate whether the agent satisfies each of the expected outcomes.
        - Grade each expected outcome individually.

        FORMAT
        - Your response should be a JSON object with the following fields:
        - `reasoning`: a short explanation for your classification
        - `metExpectation`: `true` if the agent satisfies the expected outcomes, `false` otherwise
        - `expectedOutcome`: repeat the expectation from the input that you are grading

        Example response structure:
        {
            "results": [
                {
                    "expectedOutcome": "<one of the expected outcomes from the input>",
                    "reasoning": "<reasoning trace>",
                    "metExpectation": <false or true>,
                }
            ]
        }
        """


def user_prompt(messages, nl_assertions):
    trajectory_str = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
    return f"""
        conversation:
        {trajectory_str}

        expectedOutcomes:
        {nl_assertions}
        """


def parse(text, n):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < 0:
        raise ValueError("no json object")
    blob = re.sub(r",\s*([}\]])", r"\1", text[start:end + 1])
    results = json.loads(blob).get("results", [])
    if len(results) != n:
        raise ValueError(f"expected {n} results, got {len(results)}")
    for r in results:
        if not isinstance(r.get("metExpectation"), bool):
            raise ValueError("metExpectation not boolean")
    return results


def call(model, system, prompt):
    sp = CWD / f"sys_{threading.get_ident()}.txt"
    sp.write_text(system, encoding="utf-8")
    cmd = [CLAUDE, "-p", "--model", model, "--system-prompt-file", str(sp), "--tools", "",
           "--disable-slash-commands", "--exclude-dynamic-system-prompt-sections", "--strict-mcp-config",
           "--mcp-config", str(MCP), "--output-format", "json", "--no-session-persistence"]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=CWD, timeout=900)
    out = json.loads(p.stdout)
    if out.get("is_error") or not isinstance(out.get("result"), str):
        raise RuntimeError(f"cli error: {str(out.get('result'))[:200]}")
    return out["result"], float(out.get("total_cost_usd") or 0.0)


def grade(sim, model):
    prompt = user_prompt(sim["messages"], sim["pending"])
    last = None
    for attempt in range(4):
        try:
            text, cost = call(model, SYSTEM_PROMPT, prompt)
            results = parse(text, len(sim["pending"]))
            return {"model": model, "results": results, "raw": text, "cost_usd": cost, "attempts": attempt + 1}
        except Exception as e:
            last = repr(e)
            time.sleep(5 * (attempt + 1))
    return {"model": model, "error": last}


def main():
    data_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    models = sys.argv[3].split(",")
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 2
    sims = json.loads(data_path.read_text(encoding="utf-8"))
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    lock = threading.Lock()
    jobs = [(s, m) for s in sims for m in models if f"{m}|{s['sim_id']}" not in done or "error" in done[f"{m}|{s['sim_id']}"]]
    print(f"{len(jobs)} jobs", flush=True)

    def run(job):
        s, m = job
        r = grade(s, m)
        r.update(cond=s["cond"], task_id=s["task_id"], sim_id=s["sim_id"], pending=s["pending"],
                 stored_reward=s["reward"], termination_reason=s["termination_reason"])
        with lock:
            done[f"{m}|{s['sim_id']}"] = r
            out_path.write_text(json.dumps(done, ensure_ascii=False, indent=1), encoding="utf-8")
        ok = "ERR" if "error" in r else "".join("T" if x["metExpectation"] else "F" for x in r["results"])
        print(time.strftime("%H:%M:%S"), m, s["cond"], s["task_id"], ok, flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(run, jobs))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
