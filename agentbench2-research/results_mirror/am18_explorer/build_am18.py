"""The 18 agentic-misalignment prompts (3 scenarios x 3 urgency x 2 goal) as explorer cases, rendered like units_am.py
(system; user prompt + blank line + email content; enable_thinking=False; generation prompt added).
windows (token index ranges, end exclusive): sys = system prompt text, instr = user instruction text, email = email
content, gen = the generation-prompt tokens from "<|im_start|>assistant" to the end (the position that starts the reply).
Usage: python build_am18.py PROMPTS_DIR OUT_JSON"""
import json
import sys
from pathlib import Path

from transformers import AutoTokenizer

MODEL = "/workspace/.hf_home/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a"


def main():
    pdir, out = Path(sys.argv[1]), Path(sys.argv[2])
    tok = AutoTokenizer.from_pretrained(MODEL)
    cases = []
    for c in sorted(p.name for p in pdir.iterdir() if p.is_dir()):
        d = pdir / c
        system = (d / "system_prompt.txt").read_text(encoding="utf-8")
        instr = (d / "user_prompt.txt").read_text(encoding="utf-8")
        email = (d / "email_content.txt").read_text(encoding="utf-8")
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": instr + "\n\n" + email}]
        text = tok.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
        enc = tok(text, add_special_tokens=False, return_offsets_mapping=True)
        ids, offs = enc["input_ids"], enc["offset_mapping"]

        def span(c0, c1):
            a = next(i for i, (x, y) in enumerate(offs) if y > c0)
            b = next((i for i, (x, y) in enumerate(offs) if x >= c1), len(ids))
            return [a, b]
        system, instr, email = system.strip(), instr.strip(), email.strip()
        s0 = text.index(system)
        u0 = text.index(instr, s0 + len(system))
        e0 = text.index(email, u0 + len(instr))
        g0 = text.rindex("<|im_start|>assistant")
        scen, goal, urg = c.split("_")
        w = {"sys": span(s0, s0 + len(system)), "instr": span(u0, u0 + len(instr)), "email": span(e0, e0 + len(email)),
             "gen": span(g0, len(text))}
        cases.append({"ids": ids, "onset": len(ids) - 1, "pos": len(ids) - 1, "scaf": len(ids), "label": "am18", "group": "am_prompt",
                      "risk": f"{scen} / goal {goal} / urgency {urg}", "domain": c, "tool": "-", "type": "am_prompt",
                      "key": f"am18|{c}", "scenario": scen, "goal": goal, "urgency": urg, "windows": w})
        print(c, len(ids), w)
    out.write_text(json.dumps(cases), encoding="utf-8")


if __name__ == "__main__":
    main()
