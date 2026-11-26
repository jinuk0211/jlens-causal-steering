"""X12 parity check: send the first N logged AgentDojo requests (ops/proxy_log/dojo.jsonl, vLLM greedy) to the HF base
server and compare the tool calls. Usage: python steer_parity.py PORT N"""
import json
import sys
import urllib.request

port, n = int(sys.argv[1]), int(sys.argv[2])
same = tot = 0
with open("/home/project-b/LJW/agentbench2/ops/proxy_log/dojo.jsonl") as f:
    for k, line in enumerate(f):
        if k >= n:
            break
        d = json.loads(line)
        req = {kk: v for kk, v in d["request"].items() if kk != "return_token_ids"}
        r = urllib.request.Request(f"http://127.0.0.1:{port}/v1/chat/completions", data=json.dumps(req).encode(),
                                   headers={"Content-Type": "application/json"})
        full = json.loads(urllib.request.urlopen(r, timeout=600).read())
        got = full["choices"][0]["message"]
        ref = d["response"]["choices"][0]["message"]
        pid_same = full.get("prompt_token_ids") == d["response"].get("prompt_token_ids")
        print(k, "prompt ids equal" if pid_same else f"PROMPT IDS DIFFER (hf {len(full.get('prompt_token_ids') or [])}, vllm {len(d['response'].get('prompt_token_ids') or [])})")
        g = [(c["function"]["name"], json.loads(c["function"]["arguments"])) for c in (got.get("tool_calls") or [])]
        e = [(c["function"]["name"], json.loads(c["function"]["arguments"])) for c in (ref.get("tool_calls") or [])]
        tot += 1
        same += int(g == e)
        print(k, "SAME" if g == e else "DIFF", "hf:", g[:2], "| vllm:", e[:2], "| text hf:", (got.get("content") or "")[:80].replace("\n", " "))
print(f"PARITY {same}/{tot}")
