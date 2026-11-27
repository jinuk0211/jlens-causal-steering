"""PropensityBench shared pieces (PLAN.md "PB"): paths, chat rendering and qwen3_coder tool-call parsing, used by the vLLM server
(pb_serve.py), the episode runner (pb_run.py) and the capture (ab_pb.py capture), so the capture rebuilds exactly the token ids the
server generated from."""
import ast
import hashlib
import json
import os
import re
import uuid
from pathlib import Path

ROOT = Path("/home/project-b/LJW/agentbench2")
A = ROOT / "ana"
PB = Path(os.environ.get("PB_DIR", str(A / "pb")))
PBE = ROOT / "propensity-evaluation"
COMMIT = "09872f3bbb900a18b2ddc1b5a95d74a0f4db9e17"
MODEL = "Qwen/Qwen3.5-4B"
REV = "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
NL, NN = 32, 9216
CATS = ("evaluation-awareness", "financials", "power-seeking", "resource-deprivation", "self-preservation", "time")
TC_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)


def md5(s):
    return hashlib.md5(s.encode("utf-8")).hexdigest()


def ids_md5(ids):
    return md5(",".join(str(int(i)) for i in ids))


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


def render(tok, msgs, tools):
    ids = tok.apply_chat_template(norm_messages(msgs), tools=tools or None, add_generation_prompt=True, enable_thinking=False,
                                  tokenize=True)
    if hasattr(ids, "input_ids"):
        ids = ids["input_ids"]
    if isinstance(ids, dict):
        ids = ids["input_ids"]
    return [int(i) for i in ids]


def convert(val, schema):
    t = (schema or {}).get("type")
    if t == "string":
        return val
    if t == "integer":
        try:
            return int(val.strip())
        except ValueError:
            return val
    if t == "number":
        try:
            f = float(val.strip())
            return int(f) if f.is_integer() else f
        except ValueError:
            return val
    if t == "boolean":
        return val.strip().lower() == "true"
    if t in ("array", "object") or t is None or t == "unknown" or t == "null":
        try:
            return json.loads(val)
        except ValueError:
            try:
                return ast.literal_eval(val)
            except (ValueError, SyntaxError):
                return val
    return val


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


def call_seed(task, rep, k):
    return int(md5(f"{task}|{rep}|{k}")[:8], 16) & 0x7FFFFFFF
