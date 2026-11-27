"""X20: OpenAI-compatible chat server for AgentDojo, one model per process (AB_DS_MODEL = 4b | 9b | 27b), every arm of that model in
the same process. The arm comes from the URL: OPENAI_COMPATIBLE_BASE_URL=http://127.0.0.1:PORT/<suite>.<arm>/v1, arm keys from
dojo_suite.arm_specs (<suite>.base, and <suite>.s<A>d1024_tr / s<A>r1024_tr once arms.json exists). GET /arms lists them.
Generation is that of ab_serve_steer.py (X12-X19): the model's chat template with tools, enable_thinking false, greedy, budget
1536, qwen3_coder-style tool-call parsing; a clamp arm prefills the prompt in 1024-token chunks with the clamp at tool-result
positions only, then generates without any edit. Requests run one at a time (lock).
Logs: ana/ds/<mk>/logs/serve_<port>.jsonl (one line per request); prompt ids of every base request (and of every request with
AB_REQLOG_ALL=1) in ana/ds/<mk>/reqlogs/<arm key>_<port>.jsonl, the input of the units' reqparity check.
Usage: AB_DS_MODEL=4b AB_PLATFORM=projectb CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 AB_PORT=18400 python dojo_serve.py"""
import ast
import json
import os
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dojo_suite as DSU

MK = DSU.use_model(os.environ["AB_DS_MODEL"])
import torch

import ab_core as C
import ab_ne as NEM

PORT = int(os.environ["AB_PORT"])
BUDGET = int(os.environ.get("AB_BUDGET", "1536"))
LOGALL = os.environ.get("AB_REQLOG_ALL") == "1"
OUT = DSU.DS / MK
(OUT / "logs").mkdir(parents=True, exist_ok=True)
(OUT / "reqlogs").mkdir(parents=True, exist_ok=True)
LOG = OUT / "logs" / f"serve_{PORT}.jsonl"
TC_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)

tok, model = DSU.load_model()
H = C.Hooked(model)
CL = DSU.TrClamp(H.blocks)
ARMS = DSU.arm_specs(MK)
LOCK = threading.Lock()
C.log(f"dojo_serve {DSU.MODELS[MK]['id']} port {PORT}: arms {sorted(ARMS)}")


def text_of(content):
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(p.get("text", "") for p in content if isinstance(p, dict))


def norm_messages(msgs):
    out = []
    for m in msgs:
        m2 = {"role": "system" if m["role"] == "developer" else m["role"], "content": text_of(m.get("content"))}
        if m.get("tool_calls"):
            tcs = []
            for tc in m["tool_calls"]:
                f = tc.get("function", {})
                args = f.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except ValueError:
                        args = {}
                tcs.append({"id": tc.get("id"), "type": "function", "function": {"name": f.get("name"), "arguments": args}})
            m2["tool_calls"] = tcs
        if m.get("tool_call_id"):
            m2["tool_call_id"] = m["tool_call_id"]
        if m.get("name"):
            m2["name"] = m["name"]
        out.append(m2)
    return out


def convert(val, schema):
    t = (schema or {}).get("type")
    if t is None and "anyOf" in (schema or {}):
        ts = [x.get("type") for x in schema["anyOf"] if isinstance(x, dict)]
        t = next((x for x in ts if x and x != "null"), None)
        if val.strip().lower() in ("null", "none") and "null" in ts:
            return None
    v = val
    if t == "string":
        return v
    if t == "integer":
        try:
            return int(v.strip())
        except ValueError:
            return v
    if t == "number":
        try:
            f = float(v.strip())
            return int(f) if f.is_integer() else f
        except ValueError:
            return v
    if t == "boolean":
        return v.strip().lower() == "true"
    if t in ("array", "object") or t is None:
        try:
            return json.loads(v)
        except ValueError:
            try:
                return ast.literal_eval(v)
            except (ValueError, SyntaxError):
                return v
    return v


def parse(text, tools):
    schemas = {t["function"]["name"]: (t["function"].get("parameters") or {}).get("properties", {}) for t in tools or []}
    calls = []
    for m in TC_RE.finditer(text):
        name = m.group(1).strip()
        props = schemas.get(name, {})
        args = {p.strip(): convert(v, props.get(p.strip())) for p, v in PARAM_RE.findall(m.group(2))}
        calls.append({"id": "call_" + uuid.uuid4().hex[:16], "type": "function", "function": {"name": name, "arguments": json.dumps(args)}})
    pre = text.split("<tool_call>")[0].strip() if calls else text.strip()
    return pre, calls


def complete(req, key):
    msgs = norm_messages(req["messages"])
    tools = req.get("tools")
    ids = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, enable_thinking=False, tokenize=True)
    if hasattr(ids, "input_ids"):
        ids = ids["input_ids"]
    ids = list(ids)
    spec = ARMS[key]
    t0 = time.time()
    with LOCK:
        if spec is None or LOGALL:
            with (OUT / "reqlogs" / f"{key}_{PORT}.jsonl").open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"arm": key, "n_prompt": len(ids), "ids": ids}) + "\n")
        pc = None
        if spec is not None:
            CL.set_spec(spec)
            _, pc = DSU.prefill_masked(model, ids[:-1], CL, NEM.tool_result_mask(tok, ids)[:len(ids) - 1], C)
        res = C.regen(model, tok, H, ids, [{}], BUDGET, lambda t, r: False, trigger=None, gate_fn=None, prefix_cache=pc)[0]
        del pc
        torch.cuda.empty_cache()
    text = res["text"]
    pre, calls = parse(text, tools)
    msg = {"role": "assistant", "content": (pre or None) if calls else text, "tool_calls": calls or None}
    out = {"id": "chatcmpl-" + uuid.uuid4().hex[:16], "object": "chat.completion", "created": int(time.time()), "model": req.get("model"),
           "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if calls else "stop"}],
           "usage": {"prompt_tokens": len(ids), "completion_tokens": res["n"], "total_tokens": len(ids) + res["n"]},
           "prompt_token_ids": ids}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"arm": key, "n_prompt": len(ids), "n": res["n"], "end": res["end"], "sec": round(time.time() - t0, 1),
                             "text": text[:2000], "calls": [c["function"]["name"] for c in calls]}, ensure_ascii=False) + "\n")
    return out


def arm_of(path):
    parts = path.split("?")[0].strip("/").split("/")
    return parts[0] if len(parts) >= 2 and parts[1] == "v1" else None


class Hd(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj, ctype="application/json"):
        data = obj.encode() if isinstance(obj, str) else json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path.rstrip("/") == "/arms":
            return self._send(200, "".join(k + "\n" for k in sorted(ARMS)), "text/plain")
        key = arm_of(self.path)
        if key not in ARMS:
            return self._send(404, {"error": {"message": f"unknown arm {key!r}; GET /arms"}})
        self._send(200, {"object": "list", "data": [{"id": DSU.MODELS[MK]["id"], "object": "model"}]})

    def do_POST(self):
        key = arm_of(self.path)
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n) or b"{}")
        if key not in ARMS:
            return self._send(404, {"error": {"message": f"unknown arm {key!r}; GET /arms"}})
        try:
            self._send(200, complete(req, key))
        except Exception as exc:
            C.log(f"error {exc!r}"[:300])
            self._send(500, {"error": {"message": repr(exc)[:500]}})


if __name__ == "__main__":
    C.log(f"listening on 127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Hd).serve_forever()
