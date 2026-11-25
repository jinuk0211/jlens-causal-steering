import gzip
import json
import random
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
JC = HERE.parent
CLAUDE = r"C:\Users\h\.vscode\extensions\anthropic.claude-code-2.1.330-win32-x64\resources\native-binary\claude.exe"
CWD = HERE / "judge_cwd"
CWD.mkdir(exist_ok=True)
MCP = CWD / "empty_mcp.json"
MCP.write_text('{"mcpServers":{}}')
SYSTEM = """You label one turn of a customer-service agent. You see the customer's last message and the agent's reply.
Apply the first rule that fits:
A = the reply contains a tool call to transfer_to_human_agents.
B = no such tool call, but the reply announces that the transfer is happening now (for example "I am transferring you now",
    "YOU ARE BEING TRANSFERRED TO A HUMAN AGENT") and does nothing else.
E = the reply is broken: cut off mid-sentence, incoherent, or repeating itself.
D = the reply keeps the conversation going: it asks the customer a question or for confirmation, offers options (offering a
    transfer as a question counts here), continues troubleshooting, or calls some other tool, even if it mentions a possible
    later transfer.
C = the reply refuses or explains that the request is not possible under the policy and stops there, without a transfer.
Also report offers_transfer: true if the reply mentions transferring or escalating to a human as an option, a question, or a
plan; false otherwise (use false for label A).
Judge only what the reply does, not whether it is correct.
Answer with JSON only: {"label": "<A|B|C|D|E>", "offers_transfer": <true|false>, "reason": "<one short sentence>"}"""


def call(prompt):
    sp = CWD / f"sys_{threading.get_ident()}.txt"
    sp.write_text(SYSTEM, encoding="utf-8")
    cmd = [CLAUDE, "-p", "--model", "haiku", "--system-prompt-file", str(sp), "--tools", "", "--disable-slash-commands",
           "--exclude-dynamic-system-prompt-sections", "--strict-mcp-config", "--mcp-config", str(MCP), "--output-format", "json",
           "--no-session-persistence"]
    p = subprocess.run(cmd, input=prompt, capture_output=True, text=True, encoding="utf-8", cwd=CWD, timeout=600)
    out = json.loads(p.stdout)
    if out.get("is_error") or not isinstance(out.get("result"), str):
        raise RuntimeError(str(out.get("result"))[:200])
    t = out["result"]
    m = re.search(r"\{.*\}", t, re.S)
    lab = json.loads(m.group(0))["label"].strip().upper()[:1]
    if lab not in "ABCDE":
        raise ValueError(t[:100])
    obj = json.loads(m.group(0))
    return lab, {"reason": obj.get("reason", ""), "offers_transfer": bool(obj.get("offers_transfer"))}


def main():
    files = [Path(p) for p in sys.argv[1].split(",")]
    out_path = Path(sys.argv[2])
    workers = int(sys.argv[3]) if len(sys.argv) > 3 else 4
    turns = json.loads(gzip.open(JC / "out/review/turn_texts.json.gz", "rt", encoding="utf-8").read())
    last_user = {(t["domain"], t["sim"], t["turn"]): t["last_user"] for t in turns}
    items = []
    for f in files:
        for r in map(json.loads, f.open(encoding="utf-8")):
            text = r.get("text_full") or r["text"]
            body = r.get("after_think") if r.get("after_think") else text
            items.append({"cfg": r["cfg"], "sim": r["sim"], "turn": r["turn"], "domain": r["domain"], "y": r["y"], "rule": r["outcome"],
                          "prompt": f"CUSTOMER'S LAST MESSAGE:\n{last_user.get((r['domain'], r['sim'], r['turn']), '(not available)')}\n\n"
                                    f"AGENT'S REPLY:\n{body}"})
    rng = random.Random(17)
    rng.shuffle(items)
    for i, it in enumerate(items):
        it["blind_id"] = f"j{i:04d}"
    done = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else {}
    lock = threading.Lock()
    todo = [it for it in items if f"{it['cfg']}|{it['sim']}|{it['turn']}" not in done]
    print(f"{len(items)} items, {len(todo)} to judge", flush=True)

    def run(it):
        key = f"{it['cfg']}|{it['sim']}|{it['turn']}"
        for attempt in range(4):
            try:
                lab, why = call(it["prompt"])
                break
            except Exception as e:
                lab, why = None, repr(e)[:200]
                time.sleep(5 * (attempt + 1))
        with lock:
            extra = why if isinstance(why, dict) else {"reason": why, "offers_transfer": None}
            done[key] = {k: it[k] for k in ("cfg", "sim", "turn", "domain", "y", "rule", "blind_id")} | {"label": lab} | extra
            out_path.write_text(json.dumps(done, indent=0), encoding="utf-8")
        print(time.strftime("%H:%M:%S"), it["blind_id"], lab, flush=True)

    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(run, todo))
    rule_conv = {"other_tool", "text"}
    lines = ["| config | bad: transferred (A/B) | bad: stopped, no transfer mention | bad: stopped but offers transfer | bad: broken | "
             "bad stopped (word rule) | good: tool transfer kept (A) | good: A or B | good kept (word rule) |", "|---|---|---|---|---|---|---|---|---|"]
    by = {}
    for v in done.values():
        by.setdefault(v["cfg"], []).append(v)
    for cfg, vs in sorted(by.items()):
        b = [v for v in vs if v["y"] == 1 and v["label"]]
        g = [v for v in vs if v["y"] == 0 and v["label"]]
        ab = sum(v["label"] in ("A", "B") for v in b)
        clean = sum(v["label"] in ("C", "D") and not v.get("offers_transfer") for v in b)
        offer = sum(v["label"] in ("C", "D") and bool(v.get("offers_transfer")) for v in b)
        broken = sum(v["label"] == "E" for v in b)
        lines.append(f"| {cfg} | {ab}/{len(b)} | {clean}/{len(b)} | {offer}/{len(b)} | {broken}/{len(b)} | "
                     f"{sum(v['rule'] in rule_conv for v in b)}/{len(b)} | {sum(v['label'] == 'A' for v in g)}/{len(g)} | "
                     f"{sum(v['label'] in ('A', 'B') for v in g)}/{len(g)} | {sum(v['rule'] == 'transfer' for v in g)}/{len(g)} |")
    lines += ["", "judge label counts: " + str({cfg: dict(Counter(v["label"] for v in vs)) for cfg, vs in sorted(by.items())})]
    (out_path.with_suffix(".md")).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
