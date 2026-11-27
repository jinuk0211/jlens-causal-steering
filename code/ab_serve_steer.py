"""X12 (OVERNIGHT.md, 사후): OpenAI-compatible chat server on HF Qwen3.5-4B with an AgentDojo neuron edit on every generated
token, so AgentDojo runs whole episodes with the edit. Mimics the vLLM setup of serve_ab.sh: the model's chat template with
tools, enable_thinking false, greedy, qwen3_coder-style tool-call parsing (parameters converted by the tool's JSON schema).
Requests are served one at a time (lock). AB_ARM = base | attr1024 | rand1024 | tail1024 (sets from search/dojo/sets.json,
replacement = mean of the fold-0 AgentDojo references' commit-span activations). AB_PORT = listening port.
Usage: AB_PLATFORM=projectb CUDA_VISIBLE_DEVICES=0 AB_ARM=attr1024 AB_PORT=18240 python ab_serve_steer.py"""
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

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ab_core as C
import ab_regen as R

A = Path("/home/project-b/LJW/agentbench2/ana")
ARM = os.environ["AB_ARM"]
PORT = int(os.environ["AB_PORT"])
BUDGET = int(os.environ.get("AB_BUDGET", "1536"))
LOG = A / "logs" / f"serve_steer_{ARM}_{PORT}.jsonl"
TC_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)

tok, model = C.load()
H = C.Hooked(model)
units = json.loads((A / "dojo" / "units.json").read_text(encoding="utf-8"))
idx, S = R.load_stats(A / "dojo" / "c2")
ref0 = [idx[u["uid"]] for u in units if u["label"] == "reference" and u["fold"] == 0 and u["uid"] in idx]
MU = torch.tensor(S["act"][ref0].astype(np.float32).mean(0))
SETS = json.loads((A / "search" / "dojo" / "sets.json").read_text(encoding="utf-8"))["neur"]
GATE_DET = False
GATE_HN = False
READ_CL = None
GEN_AFTER_TOOL = False
if ARM == "base":
    EDIT = {}
elif ARM.endswith("_gtr"):
    x = json.loads((A / "ne" / "steer_dojo" / os.environ["AB_ARMFILE"]).read_text(encoding="utf-8"))
    sp = x["adds"][x["arms"][ARM]["add"]]
    EDIT = {("attn" if sp["site"] == "mid" else "res", int(sp["layer"])): C.Edit("add", vec=torch.tensor(sp["vec"], dtype=torch.float32), alpha=1.0)}
    GEN_AFTER_TOOL = True
    C.log(f"arm {ARM}: residual add at layer {sp['layer']} site {sp['site']}, norm {float(np.linalg.norm(sp['vec'])):.2f}, onset + generated tokens of requests with a tool result")
elif ARM.endswith("_rtr"):
    import ab_ne as NEM
    import ab_xfit as XF
    EDIT = {}
    x = json.loads((A / "ne" / "steer_dojo" / os.environ["AB_ARMFILE"]).read_text(encoding="utf-8"))
    sp = x["adds"][x["arms"][ARM]["add"]]
    READ_CL = XF.ReadAdd(H, sp["layer"], sp["site"], sp["vec"])
    READ_LIM = None
    C.log(f"arm {ARM}: residual add at layer {sp['layer']} site {sp['site']}, norm {float(np.linalg.norm(sp['vec'])):.2f}, tool-result positions only")
elif ARM.endswith("_ntr"):
    import ab_ne as NEM
    EDIT = {}
    x = json.loads((A / "ne" / "steer_dojo" / os.environ["AB_ARMFILE"]).read_text(encoding="utf-8"))
    rspec = x["sets"][x["arms"][ARM]["set"]]
    READ_CL = NEM.Steer(H)
    READ_LIM = [(l, j, v, "tr") for l, j, v in rspec]
    C.log(f"arm {ARM}: add-dose on {len(rspec)} MLP neurons at tool-result positions only (CROSS S1), dose {x.get('dose')}")
elif ARM.endswith("_tr"):
    import ab_ne as NEM
    EDIT = {}
    rspec = None
    afs = ("arms_s6a.json", "arms_s6b.json", "arms_s6g.json")
    if os.environ.get("AB_ARMFILE", "-") != "-":
        afs = (os.environ["AB_ARMFILE"],) + afs
    for af in afs:
        if not (A / "ne" / "steer_dojo" / af).is_file():
            continue
        x = json.loads((A / "ne" / "steer_dojo" / af).read_text(encoding="utf-8"))
        if ARM[:-3] in x["sets"]:
            rspec = x["sets"][ARM[:-3]]
            C.log(f"arm {ARM}: set {ARM[:-3]} from {af}, {len(rspec)} neurons")
            break
    if rspec is None:
        raise SystemExit(f"arm {ARM}: set {ARM[:-3]} not found in {afs}")
    READ_CL = NEM.Clamp(H)
    READ_LIM = [(l, j, v, "tr") for l, j, v in rspec]
elif ARM.startswith("p_"):
    import ab_hn as HN
    HN.BENCH["b"] = "dojo"
    hsets = json.loads((A / "hn" / "dojo" / "sets.json").read_text(encoding="utf-8"))
    muN = torch.tensor(np.load(A / "hn" / "dojo" / "stats.npz")["muN"])
    HN.PROBE.install(H, hsets["probe"])
    by = {}
    for x in hsets["neur"][ARM[2:]]:
        by.setdefault(x // H.nn, []).append(x % H.nn)
    EDIT = {("down", l): C.Edit("neur", idx=torch.tensor(ns), vec=muN[l][ns]) for l, ns in by.items()}
    GATE_HN = True
elif ARM == "det_attr1024":
    import ab_search as SR
    SR.DET.install(H, json.loads((A / "search" / "dojo" / "sets.json").read_text(encoding="utf-8"))["det"])
    EDIT = R.neur_edit(SETS["attr1024"], MU, H.nn)
    GATE_DET = True
elif ARM == "tail1024":
    import ab_search as SR
    rs = np.load(A / "search" / "dojo" / "refstats.npz")
    amu, asd = torch.tensor(rs["act_mu"]), torch.tensor(rs["act_sd"]).clamp_min(1e-3)
    by = {}
    for x in SETS["attr1024"]:
        by.setdefault(x // H.nn, []).append(x % H.nn)
    EDIT = {("down", l): C.Edit("fn", fn=SR.NPush(torch.tensor(ns), MU[l][ns], 1.0, amu[l][ns], asd[l][ns])) for l, ns in by.items()}
else:
    EDIT = R.neur_edit(SETS[ARM], MU, H.nn)
LOCK = threading.Lock()
REQLOG = A / "logs" / f"reqids_{os.environ['AB_REQLOG']}_{PORT}.jsonl" if os.environ.get("AB_REQLOG", "-") != "-" else None
C.log(f"serve_steer arm {ARM} port {PORT}, detector gate {GATE_DET}, request log {REQLOG}")


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


def complete(req):
    msgs = norm_messages(req["messages"])
    tools = req.get("tools")
    ids = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, enable_thinking=False, tokenize=True)
    if hasattr(ids, "input_ids"):
        ids = ids["input_ids"]
    ids = list(ids)
    t0 = time.time()
    with LOCK:
        if REQLOG is not None:
            with REQLOG.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps({"n_prompt": len(ids), "ids": ids}) + "\n")
        if GATE_HN:
            nf = len(HN.FIRES)
            gate = HN.HGate(tok, ["pdet"], "<function=")
        else:
            gate = SR.SGate(tok, ["det"], "<function=") if GATE_DET else None
        pc = None
        if READ_CL is not None:
            dev = C.first_device(model)
            READ_CL.set([READ_LIM])
            READ_CL.mask = torch.tensor(NEM.tool_result_mask(tok, ids), device=dev)
            with torch.inference_mode():
                for s0 in range(0, len(ids) - 1, 1024):
                    READ_CL.off = s0
                    o = model(input_ids=torch.tensor([ids[s0:min(s0 + 1024, len(ids) - 1)]], device=dev), past_key_values=pc, use_cache=True,
                              logits_to_keep=1)
                    pc = o.past_key_values
                del o
            READ_CL.mask = None
        edit = EDIT
        if GEN_AFTER_TOOL and "<tool_response>" not in tok.decode(ids):
            edit = {}
        res = C.regen(model, tok, H, ids, [edit], BUDGET, lambda t, r: False, trigger=None, gate_fn=gate, prefix_cache=pc)[0]
        del pc
        fires = [round(s, 2) for _, s in HN.FIRES[nf:]] if GATE_HN else None
        torch.cuda.empty_cache()
    text = res["text"]
    pre, calls = parse(text, tools)
    msg = {"role": "assistant", "content": (pre or None) if calls else text, "tool_calls": calls or None}
    out = {"id": "chatcmpl-" + uuid.uuid4().hex[:16], "object": "chat.completion", "created": int(time.time()), "model": req.get("model"),
           "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if calls else "stop"}],
           "usage": {"prompt_tokens": len(ids), "completion_tokens": res["n"], "total_tokens": len(ids) + res["n"]},
           "prompt_token_ids": ids}
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"arm": ARM, "n_prompt": len(ids), "n": res["n"], "end": res["end"], "sec": round(time.time() - t0, 1), "probe": fires,
                             "text": text[:2000], "calls": [c["function"]["name"] for c in calls]}, ensure_ascii=False) + "\n")
    return out


class Hd(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, obj):
        data = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._send(200, {"object": "list", "data": [{"id": "Qwen/Qwen3.5-4B", "object": "model"}]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            self._send(200, complete(req))
        except Exception as exc:
            C.log(f"error {exc!r}"[:300])
            self._send(500, {"error": {"message": repr(exc)[:500]}})


if __name__ == "__main__":
    C.log(f"listening on 127.0.0.1:{PORT}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Hd).serve_forever()
