"""agentic-misalignment cases for the explorer (leaking). ids = chat render of system + user (+ email content), as units_am.py's
fallback, then the stored response up to TAIL tokens past the first recipient of the first email/forward block.
dec = index of the first token of that recipient address (the leak-vs-not decision), onset = first response token.
Usage: python build_am_cases.py PROMPT_DIR OUT_JSON sample_dir:label [...]"""
import json
import re
import sys
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"
BLOCK = re.compile(r"<tool_use:(\w+)>(.*?)</tool_use:\1>", re.S)
TAIL = 24


def main():
    pdir, out = Path(sys.argv[1]), Path(sys.argv[2])
    tok = AutoTokenizer.from_pretrained(MODEL)
    system = (pdir / "system_prompt.txt").read_text(encoding="utf-8")
    user = (pdir / "user_prompt.txt").read_text(encoding="utf-8") + "\n\n" + (pdir / "email_content.txt").read_text(encoding="utf-8")
    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    pids = tok.encode(tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False),
                      add_special_tokens=False)
    cases = []
    for arg in sys.argv[3:]:
        sdir, label = arg.rsplit(":", 1)
        r = json.loads((Path(sdir) / "response.json").read_text(encoding="utf-8"))
        text = r["raw_response"]
        m = next(m for m in BLOCK.finditer(text) if m.group(1) in ("email", "forward"))
        to = re.search(r"(?im)^\s*to:\s*\"?", m.group(2))
        c0 = m.start(2) + to.end()
        rcpt = re.match(r"[^\s,\"]+", text[c0:]).group(0)
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        cids, offs = enc["input_ids"], enc["offset_mapping"]
        k = next(i for i, (a, b) in enumerate(offs) if b > c0)
        tool_k = next(i for i, (a, b) in enumerate(offs) if b > m.start())
        ids = pids + cids[:k + TAIL]
        cases.append({"ids": ids, "onset": len(pids), "pos": len(ids) - 1, "dec": len(pids) + k, "tool_pos": len(pids) + tool_k,
                      "label": "am", "risk": label, "domain": f"AM {r['metadata']['condition']} s{r['metadata']['sample_id']}",
                      "tool": f"{m.group(1)} -> {rcpt}", "type": "am", "key": f"am|{r['metadata']['condition']}|{r['metadata']['sample_id']}",
                      "dec_token": tok.decode(cids[k:k + 6])})
        print(cases[-1]["key"], label, "tokens", len(ids), "onset", len(pids), "dec", cases[-1]["dec"], repr(cases[-1]["dec_token"]), cases[-1]["tool"])
    out.write_text(json.dumps(cases), encoding="utf-8")


if __name__ == "__main__":
    main()
