"""C-LOOP C1 upstream units (PLAN.md "C-LOOP"). The tool-name token copies a choice the agent already wrote in its reply text
("... I need to transfer you to a human agent.\n\n<tool_call>"). For every transfer T-name unit (bad and good, same rule), the upstream
decision point is the first verb token ' transfer' / ' Transfer' / ' escalate' of this turn's reply text, before <tool_call>, whose
previous 8 tokens contain a commitment phrase (PATS: "need to", "must", "Let me", "will", ...), so quoted policy text ("the agent cannot
help and a transfer is needed") and noun uses are skipped. Version 2 (11-24 15:0x): v1 also took ' human' and used the novariant
contrast, whose alternative was the translation '转移'; c0_graph.py now gives these U-text units the "concept" contrast (best top-64
ASCII word outside the transfer concept). Units with no such token keep their tool-call decision only.
Output probe/circuit/out/units_up.json (k = 100000 + M1 k), read by c0_graph.py with C0_UNITS / C0_OUT."""
import json
import sys
from pathlib import Path

R = Path("/home/project-b/LJW/tau2-steer")
sys.path.insert(0, str(R / "probe/topk"))
import build_topk as bt

WORDS = {8059: " transfer", 22476: " Transfer", 85541: " escalate"}
PATS = ("need to", "must", " will", "Let me", "let me", "I'll", "going to", "have to")


def main():
    import os
    os.chdir(R / "tau2-bench")
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(os.environ["JC_MODEL"])
    tc = tok.convert_tokens_to_ids("<tool_call>")
    units = json.loads((R / "probe/m1/out/units.json").read_text(encoding="utf-8"))
    pick = [u for u in units if u["call"] == "transfer_to_human_agents" and u["ptype"] == "T-name"]
    want = {(u["cond"], u["sim"], u["turn"]): u for u in pick}
    out = []
    skipped = []
    for domain in ("airline", "retail", "telecom"):
        conds = sorted({u["cond"] for u in pick if u["domain"] == domain})
        if not conds:
            continue
        for domain_, cond, task, sim, tel in bt.episodes(Path("data/simulations/pilot"), Path("data/jlens-telemetry/pilot"), [domain], conds):
            for line in tel.open(encoding="utf-8"):
                rec = json.loads(line)
                key = (cond, sim["id"], int(rec["turn_index"]))
                if key not in want:
                    continue
                u = want[key]
                gen = rec["generated_ids"]
                stop = gen.index(tc) if tc in gen[:u["d"]] else u["d"]
                pos = next((i for i in range(stop) if gen[i] in WORDS
                            and any(p in tok.decode(gen[max(0, i - 8):i]) for p in PATS)), None)
                if pos is None or pos == 0:
                    skipped.append(u["k"])
                    continue
                out.append({k: u[k] for k in ("domain", "cond", "task", "sim", "turn", "call", "passed", "reward", "label", "kind")} | {
                    "ptype": "U-text", "d": pos, "c": gen[pos], "c_tok": tok.decode([gen[pos]]), "g": None, "g_tok": None, "m": None,
                    "k": 100000 + u["k"], "k_m1": u["k"], "inp_len": len(rec["input_ids"]),
                    "before": tok.decode(gen[max(0, pos - 24):pos]), "text_len_before_call": stop})
    (R / "probe/circuit/out").mkdir(parents=True, exist_ok=True)
    (R / "probe/circuit/out/units_up.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    print(f"{len(out)} upstream units ({sum(u['label'] == 'bad' for u in out)} bad), skipped (no text before the call): {len(skipped)}")
    for u in out:
        print(u["k_m1"], u["label"], u["domain"], u["task"][:20], repr(u["c_tok"]), "|", repr(u["before"][-80:]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
