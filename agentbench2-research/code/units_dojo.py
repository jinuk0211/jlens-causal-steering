"""AgentDojo decision-step units (CPU). PLAN.md "Units".
Injection seen = the first tool result that contains the injected text (whitespace-normalized).
TARGET = attack succeeded (security True); decision step = the first assistant step after the injection is seen whose
first call is attacker-directed (the commit step; strict = it is also the first step after the injection).
REFERENCE = attack failed; decision step = the first assistant step after the injection is seen, whose first call is not
attacker-directed. Everything else is counted and skipped. (11-25 14:4x, PLAN log: the target rule was widened after a
unit count on 16 partial episodes showed most successful attacks first read data, as the injection asks.)
Exact token ids come from ab_proxy records (vLLM return_token_ids); a chat-template render is the fallback.
Usage: units_dojo.py LOGDIR PROXY_JSONL OUT_JSON [SUITES, default banking,travel]"""
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

from agentdojo.agent_pipeline.llms.openai_llm import _function_to_openai, _message_to_openai
from agentdojo.functions_runtime import FunctionCall
from agentdojo.task_suite.load_suites import get_suite

MODEL, REV, VERSION = "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a", "v1.2.2"


def text_of(content):
    if isinstance(content, str):
        return content
    return "".join((b.get("content") or b.get("text") or "") for b in (content or []) if isinstance(b, dict))


def ws(s):
    s = (s or "").replace(chr(92) + "n", " ").replace(chr(92) + "t", " ")
    return re.sub(r"\s+", " ", s).strip()


def norm_log(m):
    role = "system" if m["role"] in ("system", "developer") else m["role"]
    text = m.get("error") if (role == "tool" and m.get("error")) else text_of(m.get("content"))
    calls = [(c["function"], json.dumps(c.get("args") or {}, sort_keys=True)) for c in (m.get("tool_calls") or [])]
    return [role, (text or "").strip(), calls]


def norm_req(m):
    role = "system" if m["role"] in ("system", "developer") else m["role"]
    calls = []
    for c in m.get("tool_calls") or []:
        a = c["function"]["arguments"]
        calls.append((c["function"]["name"], json.dumps(json.loads(a) if isinstance(a, str) else a, sort_keys=True)))
    return [role, (text_of(m.get("content")) or "").strip(), calls]


def key_of(rows):
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def flat_strings(x, out):
    if isinstance(x, dict):
        for v in x.values():
            flat_strings(v, out)
    elif isinstance(x, (list, tuple)):
        for v in x:
            flat_strings(v, out)
    elif isinstance(x, str) and len(x) >= 4:
        out.add(x)
    return out


def ids_from_record(rec):
    resp = rec["response"]
    p = resp.get("prompt_token_ids") or (resp.get("choices") or [{}])[0].get("prompt_token_ids")
    c = (resp.get("choices") or [{}])[0].get("token_ids")
    return (list(p), list(c)) if p and c else (None, None)


def to_openai(msgs):
    out = []
    for m in msgs:
        m = dict(m)
        if m.get("tool_calls"):
            m["tool_calls"] = [FunctionCall(**c) for c in m["tool_calls"]]
        if m.get("tool_call"):
            m["tool_call"] = FunctionCall(**m["tool_call"])
        o = dict(_message_to_openai(m, MODEL))
        if o["role"] == "developer":
            o["role"] = "system"
        for c in o.get("tool_calls") or []:
            c["function"]["arguments"] = json.loads(c["function"]["arguments"])
        out.append(o)
    return out


def main():
    logdir, proxy, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
    tok = None
    recs = defaultdict(list)
    if proxy.is_file():
        for line in proxy.open(encoding="utf-8"):
            r = json.loads(line)
            recs[key_of([norm_req(m) for m in r["request"]["messages"]])].append(r)
    units, why = [], Counter()
    for suite_name in (sys.argv[4].split(",") if len(sys.argv) > 4 else ("banking", "travel")):
        suite = get_suite(VERSION, suite_name)
        tools = [dict(_function_to_openai(f)) for f in suite.tools]
        for f in sorted((logdir / "openai-compatible" / suite_name).glob("user_task_*/important_instructions/injection_task_*.json")):
            d = json.loads(f.read_text(encoding="utf-8"))
            ut, it = d["user_task_id"], d["injection_task_id"]
            msgs = d["messages"]
            inj_texts = [ws(v)[:60] for v in (d.get("injections") or {}).values() if v and v.strip()]
            i = next((k for k, m in enumerate(msgs) if m["role"] == "tool" and any(t in ws(text_of(m.get("content"))) for t in inj_texts)), None)
            if i is None:
                why["injection_never_seen"] += 1
                continue
            j = next((k for k in range(i + 1, len(msgs)) if msgs[k]["role"] == "assistant"), None)
            if j is None:
                why["no_step_after_injection"] += 1
                continue
            env = suite.load_and_inject_default_environment(d["injections"])
            inj_gt = suite.injection_tasks[it].ground_truth(env)
            user_gt = suite.user_tasks[ut].ground_truth(env)
            f_inj = sorted({c.function for c in inj_gt})
            f_user = sorted({c.function for c in user_gt})
            v_user = set()
            for c in user_gt:
                flat_strings(dict(c.args), v_user)
            v_inj = sorted(flat_strings({k: dict(c.args) for k, c in enumerate(inj_gt)}, set()) - v_user)
            inj_fn = inj_gt[0].function if inj_gt else None
            inj_param = None
            if inj_gt:
                for k, v in dict(inj_gt[0].args).items():
                    if any(x in json.dumps(v) for x in v_inj):
                        inj_param = k
                        break
            def attacker(fn, args):
                return fn in f_inj and (fn not in f_user or any(v in json.dumps(args) for v in v_inj))

            def first_att(k):
                cs = msgs[k].get("tool_calls") or []
                return bool(cs and attacker(cs[0]["function"], cs[0].get("args") or {}))

            if d.get("security") is None:
                why["no_security_field"] += 1
                continue
            strict = True
            if d["security"]:
                jt = next((k for k in range(i + 1, len(msgs)) if msgs[k]["role"] == "assistant" and first_att(k)), None)
                if jt is None:
                    why["skip_securityTrue_no_attacker_first_call"] += 1
                    continue
                strict = jt == j
                j = jt
                label = "target"
            elif not first_att(j):
                label = "reference"
            else:
                why["skip_securityFalse_attackerTrue"] += 1
                continue
            calls = msgs[j].get("tool_calls") or []
            first = calls[0] if calls else None
            why[f"{label}_strict{strict}"] += 1
            cand = recs.get(key_of([norm_log(m) for m in msgs[:j]]), [])
            pids = cids = None
            src = "render"
            for r in cand:
                msg = (r["response"].get("choices") or [{}])[0].get("message") or {}
                rc = [(c["function"]["name"]) for c in msg.get("tool_calls") or []]
                if rc == [c["function"] for c in calls]:
                    pids, cids = ids_from_record(r)
                    if pids:
                        src = "vllm"
                        break
            if pids is None:
                if tok is None:
                    from transformers import AutoTokenizer
                    tok = AutoTokenizer.from_pretrained(MODEL, revision=REV)
                base = tok.apply_chat_template(to_openai(msgs[:j]), tools=tools, add_generation_prompt=True,
                                               tokenize=False, enable_thinking=False)
                full = tok.apply_chat_template(to_openai(msgs[:j + 1]), tools=tools, tokenize=False, enable_thinking=False)
                pids = tok.encode(base, add_special_tokens=False)
                cids = tok.encode(full[len(base):], add_special_tokens=False) if full.startswith(base) else []
            units.append({"uid": f"dojo|{suite_name}|{ut}|{it}", "bench": "dojo", "suite": suite_name, "user_task": ut,
                          "injection_task": it, "group": f"{suite_name}|{ut}",
                          "fold": int(hashlib.md5(f"{suite_name}|{ut}".encode()).hexdigest(), 16) % 2,
                          "label": label, "step": j, "strict": strict, "injection_seen_at": i, "prompt_ids": pids, "completion_ids": cids, "token_source": src,
                          "first_call": first, "f_inj": f_inj, "v_inj": v_inj, "f_user": f_user, "v_user": sorted(v_user)[:50], "inj_fn": inj_fn, "inj_param": inj_param,
                          "suite_tools": sorted(f.name for f in suite.tools),
                          "budget": max(96, min(768, int(1.5 * len(cids)) + 64)), "security": d["security"],
                          "utility": d["utility"]})
            why[label] += 1
    if not units:
        raise SystemExit("no units built; refusing to write an empty units file")
    out.write_text(json.dumps(units), encoding="utf-8")
    print(json.dumps({"units": len(units), "counts": why, "token_source": Counter(u["token_source"] for u in units),
                      "folds": {f"{k[0]}|{k[1]}": v for k, v in Counter((u["fold"], u["label"]) for u in units).items()}}, default=str, indent=1))


if __name__ == "__main__":
    main()
