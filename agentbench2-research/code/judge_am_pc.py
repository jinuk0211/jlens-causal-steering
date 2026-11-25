"""PC-side harm classification for agentic-misalignment responses.
The repo's classifier classes, prompts and deterministic checks are used unchanged; only the LLM transport is replaced by
Claude Haiku through the local Claude Code CLI (Max subscription, print mode, no tools). Nothing is sent to project-b.
Replies are cached on disk by sha256(system, user), so reruns are free and deterministic.
Usage: python judge_am_pc.py RESULTS_EXPERIMENT_DIR AM_REPO_DIR [--concurrency 6]
Output: RESULTS_EXPERIMENT_DIR/haiku_classifications.jsonl (one row per response)"""
import argparse
import asyncio
import glob
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
CACHE = HERE / "judge_cache"
CWD = HERE / "judge_cwd"


def newest_cli():
    found = glob.glob(r"C:\Users\h\.vscode\extensions\anthropic.claude-code-*-win32-x64\resources\native-binary\claude.exe")

    def ver(p):
        m = re.search(r"claude-code-(\d+)\.(\d+)\.(\d+)", p)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)

    if not found:
        raise SystemExit("claude.exe not found")
    return sorted(found, key=ver)[-1]


class Resp:
    def __init__(self, completion):
        self.completion = completion


class HaikuClient:
    def __init__(self, concurrency):
        self.cli = newest_cli()
        self.sem = asyncio.Semaphore(concurrency)
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0, "cost_usd": 0.0}
        CACHE.mkdir(exist_ok=True)
        CWD.mkdir(exist_ok=True)
        (CWD / "empty_mcp.json").write_text('{"mcpServers":{}}')

    def _run(self, system, user):
        key = hashlib.sha256(json.dumps([system, user]).encode()).hexdigest()
        f = CACHE / f"{key}.json"
        if f.is_file():
            self.stats["cache_hits"] += 1
            return json.loads(f.read_text(encoding="utf-8"))["result"]
        sp = CWD / f"sys_{key[:16]}.txt"
        sp.write_text(system, encoding="utf-8")
        cmd = [self.cli, "-p", "--model", "haiku", "--system-prompt-file", str(sp), "--tools", "",
               "--disable-slash-commands", "--exclude-dynamic-system-prompt-sections", "--strict-mcp-config",
               "--mcp-config", str(CWD / "empty_mcp.json"), "--output-format", "json"]
        last = None
        for attempt in range(4):
            p = subprocess.run(cmd, input=user, capture_output=True, text=True, encoding="utf-8", cwd=CWD, timeout=900)
            try:
                out = json.loads(p.stdout)
                if not out.get("is_error") and isinstance(out.get("result"), str):
                    self.stats["calls"] += 1
                    self.stats["cost_usd"] += float(out.get("total_cost_usd") or 0.0)
                    f.write_text(json.dumps({"result": out["result"], "model": "haiku"}), encoding="utf-8")
                    sp.unlink(missing_ok=True)
                    return out["result"]
                last = f"is_error {str(out.get('result'))[:200]}"
            except Exception as exc:
                last = f"rc={p.returncode} {exc} {p.stderr[:200]!r}"
            self.stats["errors"] += 1
            time.sleep(5 * (attempt + 1))
        raise RuntimeError(f"claude CLI failed: {last}")

    async def __call__(self, model_id, messages, temperature=0.0, max_tokens=2000, **kw):
        system = "\n\n".join(m.content for m in messages if getattr(m.role, "value", m.role) == "system")
        user = "\n\n".join(m.content for m in messages if getattr(m.role, "value", m.role) != "system")
        async with self.sem:
            text = await asyncio.to_thread(self._run, system, user)
        return Resp(text)


async def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("results")
    ap.add_argument("repo")
    ap.add_argument("--concurrency", type=int, default=6)
    a = ap.parse_args()
    res, repo = Path(a.results), Path(a.repo)
    sys.path.insert(0, str(repo))
    from classifiers.blackmail_classifier import BlackmailClassifier
    from classifiers.leak_classifier import LeakClassifier
    from classifiers.murder_classifier import MurderClassifier
    clf = {"blackmail": BlackmailClassifier(), "leaking": LeakClassifier(), "murder": MurderClassifier()}
    client = HaikuClient(a.concurrency)
    out_path = res / "haiku_classifications.jsonl"
    done = set()
    if out_path.is_file():
        done = {r["file"] for r in map(json.loads, out_path.open(encoding="utf-8")) if "harmful" in r}
    files = sorted(res.glob("models/**/response.json"))
    todo = [f for f in files if f.relative_to(res).as_posix() not in done]
    print(f"{len(files)} responses, {len(todo)} to classify, CLI {client.cli}", flush=True)
    lock = asyncio.Lock()

    async def one(f):
        r = json.loads(f.read_text(encoding="utf-8"))
        cond = r["metadata"]["condition"]
        scen = cond.split("_")[0]
        email = (res / "prompts" / cond / "email_content.txt").read_text(encoding="utf-8")
        text = r.get("raw_response") or ""
        try:
            final, verdict, reasoning = (await clf[scen].classify(client, email, text))[:3]
            row = {"file": f.relative_to(res).as_posix(), "condition": cond, "scenario": scen, "sample_id": r["metadata"]["sample_id"],
                   "harmful": bool(final), "classifier_verdict": bool(verdict), "judge": "claude-haiku via Claude Code CLI",
                   "reasoning_head": str(reasoning)[:400]}
        except Exception as exc:
            row = {"file": f.relative_to(res).as_posix(), "condition": cond, "scenario": scen, "error": str(exc)[:300]}
        async with lock:
            with out_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(row) + "\n")

    t0 = time.time()
    for i in range(0, len(todo), 24):
        await asyncio.gather(*(one(f) for f in todo[i:i + 24]))
        print(f"{min(i + 24, len(todo))}/{len(todo)} {time.time() - t0:.0f}s {client.stats}", flush=True)
    print("JUDGE_DONE", client.stats, flush=True)


if __name__ == "__main__":
    asyncio.run(main())
