"""PropensityBench server (PLAN.md "PB"): OpenAI-compatible /v1/chat/completions on an in-process vLLM Qwen3.5-4B (rev 851bf6e) with
continuous batching, and an optional upper clamp on MLP neurons (down_proj input) at decode positions.
- Rendering: the model's chat template with the request's tools, enable_thinking false (as serve_ab.sh); qwen3_coder-style tool-call
  parsing (pb_common.parse). Sampling: the model's generation-config defaults (what `vllm serve` applies) overridden by the request's
  temperature (the official harness sends 1) and seed (pb_run.py sends one per task and call, the same in every arm).
- Edit (PB_ARM != base): sets from pb/arms.json, key "<arm>@<PB_SETFOLD>": rows [layer, neuron, limit]; x <- min(x, limit) on the rows
  of decode tokens only (PB_EDITPOS=decode: the first num_decode_tokens rows of the batch, which vLLM orders decodes first because the
  Gated DeltaNet layers need it), i.e. every generated token after the first; prompts are read unedited. PB_EDITPOS=all edits every row.
- Every arm, base included, runs eager (no CUDA graphs, no torch.compile) so the Python hooks fire and base and arms share one engine.
- Each response carries "pb": prompt length and md5 of the prompt ids, completion token ids, finish reason; pb/logs/serve_<tag>.jsonl
  keeps one small line per request. GET /pb_stats reports edited decode rows.
Env: PB_PORT, PB_ARM (base | H512 | ...), PB_SETFOLD, PB_TAG, PB_EDITPOS, PB_MEM (0.85), PB_NSEQ (64), PB_MAXLEN (32768),
PB_MAXTOK (2048), PB_DTYPE (bfloat16; float16 on Turing)."""
import json
import os
import queue
import re
import sys
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

os.environ.setdefault("VLLM_ENABLE_V1_MULTIPROCESSING", "0")
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pb_common as P

ARM = os.environ.get("PB_ARM", "base")
SETFOLD = os.environ.get("PB_SETFOLD", "-")
PORT = int(os.environ["PB_PORT"])
TAG = os.environ.get("PB_TAG", f"{ARM}_{SETFOLD}_{PORT}")
EDITPOS = os.environ.get("PB_EDITPOS", "decode")
MAXLEN = int(os.environ.get("PB_MAXLEN", "32768"))
MAXTOK = int(os.environ.get("PB_MAXTOK", "2048"))
(P.PB / "logs").mkdir(parents=True, exist_ok=True)
LOG = P.PB / "logs" / f"serve_{TAG}.jsonl"
LOGLOCK = threading.Lock()
STATS = {"requests": 0, "edit_forwards": 0, "edit_rows": 0, "gen_tokens": 0, "overflow": 0}


def say(m):
    print(time.strftime("%H:%M:%S"), m, flush=True)


def load_edit():
    if ARM == "base":
        return None
    spec = json.loads((P.PB / "arms.json").read_text(encoding="utf-8"))
    rows = spec["sets"][f"{ARM}@{SETFOLD}"]
    by = {}
    for l, j, lim in rows:
        by.setdefault(int(l), []).append((int(j), float(lim)))
    return by


EDIT = load_edit()

from vllm import LLM, SamplingParams

llm = LLM(model=P.MODEL, revision=P.REV, tokenizer_revision=P.REV, dtype=os.environ.get("PB_DTYPE", "bfloat16"), max_model_len=MAXLEN,
          gpu_memory_utilization=float(os.environ.get("PB_MEM", "0.85")), max_num_seqs=int(os.environ.get("PB_NSEQ", "64")),
          enforce_eager=True, enable_prefix_caching=True, seed=0, compilation_config={"mode": 0})
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained(P.MODEL, revision=P.REV)
DEF = llm.get_default_sampling_params()
DEFKW = {k: getattr(DEF, k) for k in ("top_p", "top_k", "min_p", "repetition_penalty", "presence_penalty", "frequency_penalty")}
say(f"engine up: arm {ARM} set fold {SETFOLD} edit {EDITPOS}, sampling defaults {DEFKW}")


def install(model):
    import torch
    from vllm.forward_context import get_forward_context
    mods = {}
    for name, mod in model.named_modules():
        m = re.search(r"layers\.(\d+)\.mlp\.down_proj$", name)
        if m:
            mods[int(m.group(1))] = mod
    first = min(EDIT)

    def ndec(n_rows):
        if EDITPOS == "all":
            return n_rows
        md = get_forward_context().attn_metadata
        if isinstance(md, list):
            md = md[0] if md else None
        if not md:
            return 0
        for v in md.values():
            if type(v).__name__ == "GDNAttentionMetadata":
                return min(int(v.num_decode_tokens), n_rows)
        return 0

    def mk(l, mod):
        w = mod.weight
        idx = torch.tensor([j for j, _ in EDIT[l]], dtype=torch.long, device=w.device)
        lim = torch.tensor([v for _, v in EDIT[l]], dtype=w.dtype, device=w.device)

        def f(module, args):
            x = args[0]
            n = ndec(x.shape[0])
            if n <= 0:
                return None
            sub = x[:n]
            sub[:, idx] = torch.minimum(sub[:, idx], lim)
            if l == first:
                STATS["edit_forwards"] += 1
                STATS["edit_rows"] += n
            return None
        return f
    for l in EDIT:
        mods[l].register_forward_pre_hook(mk(l, mods[l]))
    return {"layers_found": len(mods), "layers_hooked": len(EDIT), "neurons": sum(len(v) for v in EDIT.values())}


if EDIT is not None:
    say(f"hooks: {llm.apply_model(install)}")

Q = queue.Queue()


def engine_loop():
    eng = llm.llm_engine
    pend = {}
    while True:
        items = [] if pend else [Q.get()]
        while True:
            try:
                items.append(Q.get_nowait())
            except queue.Empty:
                break
        for rid, ids, sp, box in items:
            try:
                eng.add_request(rid, {"prompt_token_ids": ids}, sp)
                pend[rid] = box
            except Exception as exc:
                box["err"] = repr(exc)
                box["ev"].set()
        if not pend:
            continue
        try:
            outs = eng.step()
        except Exception as exc:
            for b in pend.values():
                b["err"] = repr(exc)
                b["ev"].set()
            pend.clear()
            continue
        for o in outs:
            if not o.finished:
                continue
            rid = o.request_id if o.request_id in pend else next((r for r in pend if o.request_id.startswith(r)), None)
            if rid is not None:
                b = pend.pop(rid)
                b["out"] = o
                b["ev"].set()


threading.Thread(target=engine_loop, daemon=True).start()


def complete(req):
    t0 = time.time()
    tools = req.get("tools")
    ids = P.render(tok, req["messages"], tools)
    room = MAXLEN - len(ids) - 1
    info = {"n_prompt": len(ids), "md5": P.ids_md5(ids), "task": req.get("pb_task"), "call": req.get("pb_call")}
    if room < 16:
        STATS["overflow"] += 1
        text, comp, finish = "", [], "overflow"
    else:
        sp = SamplingParams(temperature=float(req.get("temperature", 1.0)), seed=req.get("seed"),
                            max_tokens=min(int(req.get("max_tokens") or MAXTOK), MAXTOK, room), **DEFKW)
        box = {"ev": threading.Event()}
        Q.put(("pb-" + uuid.uuid4().hex, ids, sp, box))
        box["ev"].wait()
        if "err" in box:
            raise RuntimeError(box["err"])
        o = box["out"].outputs[0]
        text, comp, finish = o.text, [int(t) for t in o.token_ids], o.finish_reason
    STATS["requests"] += 1
    STATS["gen_tokens"] += len(comp)
    pre, calls = P.parse(text, tools)
    msg = {"role": "assistant", "content": (pre or None) if calls else text, "tool_calls": calls or None}
    info.update(completion_ids=comp, finish=finish, text=text)
    with LOGLOCK, LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"task": info["task"], "call": info["call"], "n_prompt": len(ids), "md5": info["md5"], "n_gen": len(comp),
                             "finish": finish, "sec": round(time.time() - t0, 2), "calls": [c["function"]["name"] for c in calls]}) + "\n")
    return {"id": "chatcmpl-" + uuid.uuid4().hex[:16], "object": "chat.completion", "created": int(time.time()), "model": req.get("model"),
            "choices": [{"index": 0, "message": msg, "finish_reason": "tool_calls" if calls else "stop"}],
            "usage": {"prompt_tokens": len(ids), "completion_tokens": len(comp), "total_tokens": len(ids) + len(comp)}, "pb": info}


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
        if self.path.startswith("/pb_stats"):
            self._send(200, {"arm": ARM, "set_fold": SETFOLD, "edit": EDITPOS, **STATS})
        else:
            self._send(200, {"object": "list", "data": [{"id": P.MODEL, "object": "model"}]})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", "0"))
        req = json.loads(self.rfile.read(n) or b"{}")
        try:
            self._send(200, complete(req))
        except Exception as exc:
            say(f"error {exc!r}"[:300])
            self._send(500, {"error": {"message": repr(exc)[:500]}})


class Srv(ThreadingHTTPServer):
    request_queue_size = 256
    daemon_threads = True


if __name__ == "__main__":
    say(f"listening on 127.0.0.1:{PORT}")
    Srv(("127.0.0.1", PORT), Hd).serve_forever()
