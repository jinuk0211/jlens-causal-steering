"""AgentDojo with Qwen3.5-4B run in-process with HF transformers on the vast box (2x GTX 1080 Ti, fp32 split across both GPUs;
Pascal has no bf16 and no vLLM). Greedy, enable_thinking=False, chat template with native tools (Qwen XML tool calls).
The pipeline is named "openai-compatible" so the attack text and log layout match the project-b pilot.
Every LLM call is appended to TRACE (same record shape as ab_proxy: request.messages, response.prompt_token_ids,
choices[0].token_ids / message.tool_calls), so units_dojo.py gets exact token ids.
The prefix KV/linear-attention state of the conversation so far is checkpointed and reused when the next call extends it.
Usage: python dojo_hf.py --suites banking travel [--attack important_instructions | --no-attack] --logdir runs/qwen35_4b"""
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

import torch

MODEL, REV = "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
CALL_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)


def gpu_guard():
    out = subprocess.run(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"], capture_output=True, text=True).stdout
    others = [p for p in out.split() if p.strip() and int(p) != os.getpid()]
    if others and os.environ.get("AB_ALLOW_SHARED") != "1":
        raise SystemExit(f"GPU guard: other compute processes present {others}; refusing")


def convert(value, schema):
    t = (schema or {}).get("type")
    v = value.strip("\n")
    if t in ("integer", "number"):
        try:
            f = float(v)
            return int(f) if t == "integer" and f.is_integer() else f
        except ValueError:
            return v
    if t == "boolean":
        return v.strip().lower() in ("true", "1", "yes")
    if t in ("array", "object") or (t is None and v[:1] in "[{"):
        try:
            return json.loads(v)
        except ValueError:
            return v
    return v


class HFQwenLLM:
    def __init__(self, trace_path):
        from transformers import AutoTokenizer, Qwen3_5ForConditionalGeneration
        self.tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
        self.model = Qwen3_5ForConditionalGeneration.from_pretrained(
            MODEL, revision=REV, dtype=torch.float32, device_map="auto", max_memory={0: "10GiB", 1: "10GiB"}).eval()
        self.model.model.visual = None
        torch.cuda.empty_cache()
        self.eos = {self.tok.eos_token_id, self.tok.convert_tokens_to_ids("<|im_end|>")}
        self.trace = Path(trace_path)
        self.ckpt = None
        self.name = "openai-compatible"
        self.max_new = int(os.environ.get("AB_MAX_NEW", "1024"))

    def _openai(self, messages, runtime):
        from agentdojo.agent_pipeline.llms.openai_llm import _function_to_openai, _message_to_openai
        msgs = []
        for m in messages:
            o = dict(_message_to_openai(m, MODEL))
            if o["role"] == "developer":
                o["role"] = "system"
            if isinstance(o.get("content"), list):
                o["content"] = [dict(p) for p in o["content"]]
            if o.get("tool_calls"):
                o["tool_calls"] = [{"id": c["id"], "type": "function",
                                    "function": {"name": c["function"]["name"],
                                                 "arguments": json.loads(c["function"]["arguments"])}} for c in o["tool_calls"]]
            msgs.append(o)
        tools = [dict(_function_to_openai(f)) for f in runtime.functions.values()]
        for t in tools:
            t["function"] = dict(t["function"])
        return msgs, tools

    def _prefill(self, ids, cache):
        out = None
        for s in range(0, len(ids), 1024):
            x = torch.tensor([ids[s:s + 1024]], device="cuda:0")
            out = self.model(input_ids=x, past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
        return out, cache

    @torch.inference_mode()
    def complete(self, msgs, tools):
        tok = self.tok
        hist = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=False, tokenize=False, enable_thinking=False)
        full = tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        h_ids = tok.encode(hist, add_special_tokens=False)
        ids = tok.encode(full, add_special_tokens=False)
        split_ok = full.startswith(hist) and ids[:len(h_ids)] == h_ids
        cache, start = None, 0
        if split_ok and self.ckpt is not None and h_ids[:len(self.ckpt[0])] == self.ckpt[0]:
            cache, start = copy.deepcopy(self.ckpt[1]), len(self.ckpt[0])
        t0 = time.time()
        if split_ok:
            out, cache = self._prefill(h_ids[start:], cache) if len(h_ids) > start else (None, cache)
            self.ckpt = (list(h_ids), copy.deepcopy(cache))
            out, cache = self._prefill(ids[len(h_ids):], cache)
        else:
            self.ckpt = None
            out, cache = self._prefill(ids, None)
        t_pre = time.time() - t0
        gen = []
        for _ in range(self.max_new):
            nxt = int(out.logits[0, -1].float().argmax())
            gen.append(nxt)
            if nxt in self.eos:
                break
            out = self.model(input_ids=torch.tensor([[nxt]], device="cuda:0"), past_key_values=cache, use_cache=True, logits_to_keep=1)
            cache = out.past_key_values
        del cache
        comp = [t for t in gen if t not in self.eos]
        return ids, gen, tok.decode(comp, skip_special_tokens=False), t_pre, time.time() - t0 - t_pre, start

    def query(self, query, runtime, env=None, messages=(), extra_args=None):
        from agentdojo.functions_runtime import FunctionCall
        from agentdojo.types import ChatAssistantMessage, text_content_block_from_string
        msgs, tools = self._openai(messages, runtime)
        ids, gen, text, t_pre, t_dec, reused = self.complete(msgs, tools)
        schemas = {t["function"]["name"]: (t["function"].get("parameters") or {}).get("properties", {}) for t in tools}
        calls = []
        for k, m in enumerate(CALL_RE.finditer(text)):
            name = m.group(1).strip()
            args = {p.group(1).strip(): convert(p.group(2), schemas.get(name, {}).get(p.group(1).strip()))
                    for p in PARAM_RE.finditer(m.group(2))}
            calls.append(FunctionCall(function=name, args=args, id=f"call_{len(messages)}_{k}"))
        content = CALL_RE.sub("", text).strip()
        out_msg = ChatAssistantMessage(role="assistant", content=[text_content_block_from_string(content)] if content else None,
                                       tool_calls=calls or None)
        rec = {"t": time.time(), "prefill_s": round(t_pre, 2), "decode_s": round(t_dec, 2), "reused_prefix": reused,
               "request": {"messages": msgs},
               "response": {"prompt_token_ids": ids,
                            "choices": [{"token_ids": gen, "text": text,
                                         "message": {"content": content,
                                                     "tool_calls": [{"function": {"name": c.function, "arguments": json.dumps(dict(c.args))}}
                                                                    for c in calls]}}]}}
        with self.trace.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec) + "\n")
        return query, runtime, env, [*messages, out_msg], extra_args or {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--suites", nargs="+", default=["banking", "travel"])
    ap.add_argument("--attack", default="important_instructions")
    ap.add_argument("--no-attack", action="store_true")
    ap.add_argument("--logdir", default="runs/qwen35_4b")
    ap.add_argument("--user-tasks", nargs="*", default=None)
    a = ap.parse_args()
    gpu_guard()
    from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline, PipelineConfig
    from agentdojo.attacks.attack_registry import load_attack
    from agentdojo.base_tasks import BaseInjectionTask  # noqa: F401
    from agentdojo.benchmark import benchmark_suite_with_injections, benchmark_suite_without_injections
    from agentdojo.logging import OutputLogger
    from agentdojo.task_suite.load_suites import get_suite

    from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement

    class Elem(BasePipelineElement):
        def __init__(self, inner):
            self.inner = inner
            self.name = inner.name

        def query(self, query, runtime, env=None, messages=(), extra_args={}):
            return self.inner.query(query, runtime, env, messages, extra_args)

    logdir = Path(a.logdir)
    logdir.mkdir(parents=True, exist_ok=True)
    llm = Elem(HFQwenLLM(logdir / ("trace_noattack.jsonl" if a.no_attack else "trace.jsonl")))
    pipeline = AgentPipeline.from_config(PipelineConfig(llm=llm, model_id=None, defense=None, system_message_name=None,
                                                        system_message=None, tool_delimiter="tool"))
    pipeline.name = "openai-compatible"
    for s in a.suites:
        suite = get_suite("v1.2.2", s)
        t0 = time.time()
        with OutputLogger(str(logdir)):
            if a.no_attack:
                res = benchmark_suite_without_injections(pipeline, suite, user_tasks=a.user_tasks, logdir=logdir,
                                                         force_rerun=False, benchmark_version="v1.2.2")
                print(s, "utility", sum(res["utility_results"].values()) / max(1, len(res["utility_results"])), flush=True)
            else:
                att = load_attack(a.attack, suite, pipeline)
                res = benchmark_suite_with_injections(pipeline, suite, att, user_tasks=a.user_tasks, logdir=logdir,
                                                      force_rerun=False, benchmark_version="v1.2.2")
                sec = res["security_results"].values()
                print(s, "attack success", sum(sec) / max(1, len(sec)), "utility", sum(res["utility_results"].values()) / max(1, len(res["utility_results"])), flush=True)
        print(f"SUITE_DONE {s} {time.time() - t0:.0f}s", flush=True)
    print("DOJO_HF_DONE", flush=True)


if __name__ == "__main__":
    sys.exit(main())
