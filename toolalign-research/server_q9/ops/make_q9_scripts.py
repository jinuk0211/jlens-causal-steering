"""Create Qwen3.5-9B (J++ lens) copies of the ToolAlign scripts, GPU 0. Originals untouched. Run on the server."""
from pathlib import Path

T = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench")
A = T / "ops/analysis"
Q = T / "ops/analysis_q9"
Q.mkdir(exist_ok=True)
REV = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"


def sub(s, old, new, count=1):
    assert s.count(old) == count, (old[:80], s.count(old))
    return s.replace(old, new)


p = T / "jlens_experiment/model_profiles.py"
s = p.read_text(encoding="utf-8")
if '"qwen3.5-9b": ModelProfile(' not in s:
    add = f'''    "qwen3.5-9b": ModelProfile(
        name="qwen3.5-9b",
        model_id="Qwen/Qwen3.5-9B",
        model_revision="{REV}",
        lens_repo=LENS_REPO,
        lens_revision="d2527c3cdbaa60dd4b65cbca1604921f044e989a",
        lens_file="qwen3.5-9b/jpp/Salesforce-wikitext/Qwen3.5-9B_jpp_lens.pt",
        diagnostic_only=False,
        warning="J++ lens (Ayonrinde & Lindsey) fitted on Qwen/Qwen3.5-9B itself",
        min_vram_gib=24.0,
    ),
'''
    s = sub(s, '    "qwen3.5-9b-base": ModelProfile(', add + '    "qwen3.5-9b-base": ModelProfile(')
    p.write_text(s, encoding="utf-8")
p = T / "inference/models.yaml"
s = p.read_text(encoding="utf-8")
if "\nqwen3.5-9b:\n" not in s:
    s = sub(s, "qwen3.5-9b-base:\n", f'''qwen3.5-9b:
  path: Qwen/Qwen3.5-9B
  served_model_name: Qwen/Qwen3.5-9B
  revision: {REV}
  dtype: profile-auto
  max_model_len: 32768
  gpu_memory_utilization: 0.85
  chat_template_kwargs:
    enable_thinking: false

qwen3.5-9b-base:
''')
    p.write_text(s, encoding="utf-8")
p = T / "runner/src/models.ts"
s = p.read_text(encoding="utf-8")
if 'name: "qwen3.5-9b",' not in s:
    anchor = '''  {
    name: "qwen3.5-9b-base",'''
    s = sub(s, anchor, f'''  {{
    name: "qwen3.5-9b",
    modelId: "Qwen/Qwen3.5-9B",
    useLocal: true,
    profile: "qwen3.5-9b",
    revision: "{REV}",
  }},
''' + anchor)
    p.write_text(s, encoding="utf-8")

s = (A / "tab_jlens.py").read_text(encoding="utf-8")
s = sub(s, 'os.environ.get("CUDA_VISIBLE_DEVICES") == "2"', 'os.environ.get("CUDA_VISIBLE_DEVICES") == "0"')
s = sub(s, 'log("must run with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=2")', 'log("must run with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")')
s = sub(s, 'profile = get_profile("qwen3.5-4b")', 'profile = get_profile("qwen3.5-9b")')
s = sub(s, '"4c593ff4" not in str(torch.cuda.get_device_properties(0).uuid)', '"c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid)')
s = sub(s, '    steps = sorted(steps, key=prio)', '''    steps = sorted(steps, key=prio)
    if os.environ.get("JL_SPLIT"):
        wi, wn = (int(x) for x in os.environ["JL_SPLIT"].split("/"))
        steps = [x for i, x in enumerate(steps) if i % wn == wi]''')
(Q / "tab_jlens_q9.py").write_text(s, encoding="utf-8")

s = (A / "tab_analyze.py").read_text(encoding="utf-8")
s = sub(s, 'tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")',
        f'tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B", revision="{REV}")')
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_q9/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/report"', 'OUT = ROOT / "ops/analysis_q9/report"')
s = sub(s, "(Qwen3.5-4B, greedy)", "(Qwen3.5-9B, J++ lens, greedy)")
(Q / "tab_analyze_q9.py").write_text(s, encoding="utf-8")

s = (A / "ta_causal.py").read_text(encoding="utf-8")
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_q9/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/causal"', 'OUT = ROOT / "ops/analysis_q9/causal"')
s = sub(s, 'RES = ROOT / "runner/results/qwen35-greedy"', 'RES = ROOT / "runner/results/qwen9-greedy"')
s = sub(s, 'os.environ.get("CUDA_VISIBLE_DEVICES") != "2"', 'os.environ.get("CUDA_VISIBLE_DEVICES") != "0"')
s = sub(s, 'log("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=2")', 'log("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")')
s = sub(s, '"4c593ff4" not in str(torch.cuda.get_device_properties(0).uuid)', '"c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid)')
s = sub(s, 'prof = get_profile("qwen3.5-4b")', 'prof = get_profile("qwen3.5-9b")')
s = sub(s, "# CAUSAL-1: mean-matching at the tool-name position", "# CAUSAL-1 (Qwen3.5-9B, J++ lens): mean-matching at the tool-name position")
(Q / "ta_causal_q9.py").write_text(s, encoding="utf-8")

s = (A / "ta_causal2.py").read_text(encoding="utf-8")
s = sub(s, 'C1 = ROOT / "ops/analysis/causal"', 'C1 = ROOT / "ops/analysis_q9/causal"')
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_q9/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/causal2"', 'OUT = ROOT / "ops/analysis_q9/causal2"')
s = sub(s, 'RES = ROOT / "runner/results/qwen35-greedy"', 'RES = ROOT / "runner/results/qwen9-greedy"')
s = sub(s, 'GPUS = {"0": "c27bc2d7", "1": "bf42d0ab", "2": "4c593ff4"}', 'GPUS = {"0": "c27bc2d7"}')
s = sub(s, 'prof = get_profile("qwen3.5-4b")', 'prof = get_profile("qwen3.5-9b")')
s = sub(s, '''            for ename, layers in extra.items():
                cfgs.append((ename, {("attn", l): setter(mu_attn[l]) for l in layers}))''',
'''            for ename, layers in extra.items():
                cfgs.append((ename, {("attn", l): setter(mu_attn[l]) for l in layers}))
        if os.environ.get("C2_CTRL") == "1":
            ltypes = model.config.get_text_config().layer_types
            band = list(range(12, 21))
            outside = [l for l in range(nl) if l not in band]
            full_in = [l for l in band if ltypes[l] == "full_attention"]
            full_out = [l for l in outside if ltypes[l] == "full_attention"]
            for d in range(3):
                r = random.Random(1000 + d)
                lb = sorted(r.sample(outside, len(band)))
                fo = sorted(r.sample(full_out, len(full_in)))
                cfgs.append((f"attn_rand9_d{d}", {("attn", l): setter(mu_attn[l]) for l in lb}))
                cfgs.append((f"attn_randfull_d{d}", {("attn", l): setter(mu_attn[l]) for l in fo}))
            b2 = list(range(16, 21))
            cfgs.append(("attn_band_16_20_onset", {("attn", l): setter(mu_attn[l]) for l in b2}, "onset"))
            cfgs.append(("attn_band_16_20_after", {("attn", l): setter(mu_attn[l]) for l in b2}, "after"))
            if kind == "reference":
                ti = [idx[x["uid"]] for x in targets if x["domain"] != u["domain"] and x["risk"] != "aligned"]
                if ti:
                    mt_attn = attn[ti].mean(0)
                    cfgs.append(("rev_attn_band_16_20", {("attn", l): setter(mt_attn[l]) for l in b2}))
                    cfgs.append((f"rev_attn_full_{'_'.join(map(str, full_in))}", {("attn", l): setter(mt_attn[l]) for l in full_in}))
        cfgs = [c if len(c) == 3 else (c[0], c[1], "all") for c in cfgs]''')
s = sub(s, '''            cid = hashlib.md5((u["uid"] + ("|x" if os.environ.get("C2_EXTRA") == "1" else "")).encode()).hexdigest()''',
        '''            cid = hashlib.md5((u["uid"] + ("|x" if os.environ.get("C2_EXTRA") == "1" else "") + ("|c" if os.environ.get("C2_CTRL") == "1" else "")).encode()).hexdigest()''')
s = sub(s, '''            for cname, od in cfgs:
                cache = copy.deepcopy(cache0)
                H.ops = od
''', '''            for cname, od, when in cfgs:
                cache = copy.deepcopy(cache0)
''')
s = sub(s, '''                for t in range(budget):
                    o = H.lm(''', '''                for t in range(budget):
                    H.ops = od if (when == "all" or (when == "onset" and t == 0) or (when == "after" and t > 0)) else {}
                    o = H.lm(''')
s = sub(s, '''    md = ["# CAUSAL-2: interventions over the whole response, greedy regeneration", "",
          f"- base reproduces the original tool: targets {len(ok_t)}/{nt}, references {len(ok_r)}/{nr}. Only reproducing units are scored.", "",''',
'''    excl = {}
    for r in base.values():
        if r["set"] == "target":
            k = r["risk"]
            excl.setdefault(k, [0, 0])
            excl[k][1] += 1
            excl[k][0] += r["uid"] not in ok_t
    md = ["# CAUSAL-2 (Qwen3.5-9B, J++ lens): interventions over the whole response, greedy regeneration", "",
          f"- base reproduces the original tool: targets {len(ok_t)}/{nt}, references {len(ok_r)}/{nr}. Only reproducing units are scored.",
          "- targets excluded (base did not reproduce), by risk: " + ", ".join(f"{k} {a}/{b}" for k, (a, b) in sorted(excl.items())),
          "- rev_* rows are on references only: 'refs kept' = still writeInternalLog; 1 - kept = deviation caused by the target-mean attention.", "",''')
(Q / "ta_causal2_q9.py").write_text(s, encoding="utf-8")

g = (T / "ops/analysis_gemma/g1_split_g.py").read_text(encoding="utf-8")
g = sub(g, 'G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_gemma")', 'G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_q9")')
(Q / "g1_split_q9.py").write_text(g, encoding="utf-8")
m = (T / "ops/analysis_gemma/merge_points_g.py").read_text(encoding="utf-8")
m = sub(m, 'G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_gemma")', 'G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_q9")')
(Q / "merge_points_q9.py").write_text(m, encoding="utf-8")
print("written:", sorted(x.name for x in Q.glob("*.py")))
