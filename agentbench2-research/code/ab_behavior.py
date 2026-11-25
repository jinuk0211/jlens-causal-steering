"""Behavior table (first step of the ToolAlign-4B procedure). CPU only.
dojo: python ab_behavior.py dojo ATTACK_LOGDIR NOATTACK_LOGDIR [UNITS_JSON] OUT_MD
am:   python ab_behavior.py am RESULTS_DIR [UNITS_JSON] OUT_MD"""
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def pct(a, b):
    return f"{a}/{b} ({a / b:.0%})" if b else "0/0"


def dojo(att, noatt, units_path, out):
    md = ["# Behavior table: AgentDojo v1.2.2, Qwen3.5-4B (greedy, important_instructions)", ""]
    md += ["| suite | episodes | attack success (security) | utility under attack | utility without attack | injection tasks solved as user tasks |",
           "|---|---|---|---|---|---|"]
    tot = Counter()
    for s in ("banking", "travel"):
        base = att / "openai-compatible" / s
        eps = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(base.glob("user_task_*/important_instructions/injection_task_*.json"))]
        inj_user = [json.loads(f.read_text(encoding="utf-8")) for f in sorted(base.glob("injection_task_*/none/none.json"))]
        na = [json.loads(f.read_text(encoding="utf-8")) for f in sorted((noatt / "openai-compatible" / s).glob("user_task_*/none/none.json"))]
        sec = sum(bool(e.get("security")) for e in eps)
        uti = sum(bool(e.get("utility")) for e in eps)
        nu = sum(bool(e.get("utility")) for e in na)
        iu = sum(bool(e.get("utility")) for e in inj_user)
        md.append(f"| {s} | {len(eps)} | {pct(sec, len(eps))} | {pct(uti, len(eps))} | {pct(nu, len(na))} | {pct(iu, len(inj_user))} |")
        tot.update({"eps": len(eps), "sec": sec, "uti": uti, "na": len(na), "nu": nu})
        by_inj = defaultdict(lambda: [0, 0])
        for e in eps:
            by_inj[e["injection_task_id"]][0] += bool(e.get("security"))
            by_inj[e["injection_task_id"]][1] += 1
        md.append(f"|   {s} per injection task | | " + ", ".join(f"{k.replace('injection_task_', 'i')} {v[0]}/{v[1]}" for k, v in sorted(by_inj.items())) + " | | | |")
    md += [f"| all | {tot['eps']} | {pct(tot['sec'], tot['eps'])} | {pct(tot['uti'], tot['eps'])} | {pct(tot['nu'], tot['na'])} | |", ""]
    if units_path and units_path.is_file():
        md += units_part(units_path)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


def units_part(units_path):
    us = json.loads(units_path.read_text(encoding="utf-8"))
    md = ["## Decision-step units", "", "| class | fold 0 (CALIBRATION) | fold 1 (TEST) | groups | token ids from |", "|---|---|---|---|---|"]
    for lab in ("target", "reference", "unlabeled"):
        xs = [u for u in us if u["label"] == lab]
        if xs:
            md.append(f"| {lab} | {sum(u['fold'] == 0 for u in xs)} | {sum(u['fold'] == 1 for u in xs)} | {len({u['group'] for u in xs})} | "
                      f"{dict(Counter(u['token_source'] for u in xs))} |")
    fc = Counter((u["label"], (u.get("first_call") or {}).get("function")) for u in us if u.get("bench") == "dojo")
    if fc:
        md += ["", "First call at the decision step: " + "; ".join(f"{k[0]} {k[1]} {v}" for k, v in fc.most_common(16))]
    return md + [""]


def am(res, units_path, out):
    from am_markers import marker_end
    cls = {}
    p = res / "haiku_classifications.jsonl"
    if p.is_file():
        for x in p.open(encoding="utf-8"):
            r = json.loads(x)
            if "harmful" in r:
                cls[r["file"]] = r
    rows = defaultdict(Counter)
    for f in sorted(res.glob("models/**/response.json")):
        rel = f.relative_to(res).as_posix()
        r = json.loads(f.read_text(encoding="utf-8"))
        cond = r["metadata"]["condition"]
        mk = marker_end(cond.split("_")[0], r.get("raw_response") or "") is not None
        c = cls.get(rel)
        rows[cond]["n"] += 1
        rows[cond]["marker"] += mk
        if c:
            rows[cond]["judged"] += 1
            rows[cond]["harmful"] += c["harmful"]
            rows[cond]["verdict"] += c["classifier_verdict"]
            rows[cond]["agree"] += (c["harmful"] == mk)
    md = ["# Behavior table: agentic-misalignment, Qwen3.5-4B (T = 1.0, 50 samples per condition)", "",
          "Judge: Claude Haiku through the Claude Code CLI. The original paper used Claude 3.7 Sonnet. "
          "harmful = deterministic necessary condition AND the judge verdict (repo classifiers unchanged).", "",
          "| condition | responses | judged | harmful | judge verdict alone | marker (necessary condition) | marker = harmful |", "|---|---|---|---|---|---|---|"]
    T = Counter()
    for cond in sorted(rows):
        c = rows[cond]
        T.update(c)
        md.append(f"| {cond} | {c['n']} | {c['judged']} | {pct(c['harmful'], c['judged'])} | {pct(c['verdict'], c['judged'])} | "
                  f"{pct(c['marker'], c['n'])} | {pct(c['agree'], c['judged'])} |")
    md += [f"| all | {T['n']} | {T['judged']} | {pct(T['harmful'], T['judged'])} | {pct(T['verdict'], T['judged'])} | "
           f"{pct(T['marker'], T['n'])} | {pct(T['agree'], T['judged'])} |", ""]
    for s in ("blackmail", "leaking", "murder"):
        cs = Counter()
        for cond, c in rows.items():
            if cond.startswith(s):
                cs.update(c)
        md.append(f"- {s}: harmful {pct(cs['harmful'], cs['judged'])}, marker {pct(cs['marker'], cs['n'])}")
    md.append("")
    if units_path and units_path.is_file():
        md += units_part(units_path)
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    a = sys.argv
    if a[1] == "dojo":
        dojo(Path(a[2]), Path(a[3]), Path(a[4]) if len(a) > 5 else None, Path(a[-1]))
    else:
        am(Path(a[2]), Path(a[3]) if len(a) > 4 else None, Path(a[-1]))
