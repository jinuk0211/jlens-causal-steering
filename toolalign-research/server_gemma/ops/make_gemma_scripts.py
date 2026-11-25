"""Create Gemma-4-E4B copies of the ToolAlign analysis scripts (originals stay untouched). Run on the server."""
from pathlib import Path

A = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis")
G = Path("/home/project-b/LJW/tau2-steer/ToolAlignBench/ops/analysis_gemma")
G.mkdir(exist_ok=True)


def sub(s, old, new, count=1):
    assert s.count(old) == count, (old[:80], s.count(old))
    return s.replace(old, new)


SOFTCAP_FN = '''

def _softcap(model):
    cfg = model.config.get_text_config() if hasattr(model.config, "get_text_config") else model.config
    return getattr(cfg, "final_logit_softcapping", None)


def capped(logits, cap):
    return logits if not cap else cap * torch.tanh(logits / cap)
'''

s = (A / "tab_jlens.py").read_text(encoding="utf-8")
s = sub(s, 'os.environ.get("CUDA_VISIBLE_DEVICES") == "2"', 'os.environ.get("CUDA_VISIBLE_DEVICES") == "0"')
s = sub(s, 'log("must run with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=2")', 'log("must run with CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")')
s = sub(s, 'profile = get_profile("qwen3.5-4b")', 'profile = get_profile("gemma-4-e4b")')
s = sub(s, '"4c593ff4" not in str(torch.cuda.get_device_properties(0).uuid)', '"c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid)')
s = sub(s, 'tc_id = tok.convert_tokens_to_ids("<tool_call>")', 'tc_id = tok.encode("<tool_call>", add_special_tokens=False)[0]')
s = sub(s, '        layers = list(range(31))', '        layers = list(range(41))')
(G / "tab_jlens_g.py").write_text(s, encoding="utf-8")

s = (A / "tab_analyze.py").read_text(encoding="utf-8")
s = sub(s, 'tok = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-4B", revision="851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a")',
        'tok = AutoTokenizer.from_pretrained("google/gemma-4-E4B-it", revision="ee0ef6023621cff504d758262d4e04895a5af4a2")')
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_gemma/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/report"', 'OUT = ROOT / "ops/analysis_gemma/report"')
s = sub(s, 'for x in ("12", "20", "26", "final")', 'for x in ("16", "26", "34", "final")', count=1)
s = sub(s, "Δ_email L12 / L20 / L26 / final | Δ_mis L12 / L20 / L26 / final", "Δ_email L16 / L26 / L34 / final | Δ_mis L16 / L26 / L34 / final")
s = sub(s, "for l in (10, 16, 20, 24, 28, nl - 1):", "for l in (13, 21, 26, 32, 37, nl - 1):")
s = sub(s, "(Qwen3.5-4B, greedy)", "(Gemma-4-E4B-it, base-fitted J-lens, greedy)")
(G / "tab_analyze_g.py").write_text(s, encoding="utf-8")

s = (A / "ta_causal.py").read_text(encoding="utf-8")
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_gemma/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/causal"', 'OUT = ROOT / "ops/analysis_gemma/causal"')
s = sub(s, 'RES = ROOT / "runner/results/qwen35-greedy"', 'RES = ROOT / "runner/results/gemma4-greedy"')
s = sub(s, 'GRID = list(range(2, 31, 2))', 'GRID = list(range(2, 41, 2))')
s = sub(s, 'BAND = list(range(12, 21))', 'BAND = list(range(16, 27))')
s = sub(s, 'os.environ.get("CUDA_VISIBLE_DEVICES") != "2"', 'os.environ.get("CUDA_VISIBLE_DEVICES") != "0"')
s = sub(s, 'log("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=2")', 'log("need CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0")')
s = sub(s, '"4c593ff4" not in str(torch.cuda.get_device_properties(0).uuid)', '"c27bc2d7" not in str(torch.cuda.get_device_properties(0).uuid)')
s = sub(s, 'prof = get_profile("qwen3.5-4b")', 'prof = get_profile("gemma-4-e4b")')
s = sub(s, "def log(m):", SOFTCAP_FN.strip("\n") + "\n\n\ndef log(m):")
s = sub(s, "    gamma = fnorm.weight.float()", "    CAP = _softcap(model)\n    gamma = fnorm.weight.float()")
s = sub(s, "lp = torch.log_softmax(model.lm_head(out.last_hidden_state[0, -1]).float(), -1)",
        "lp = torch.log_softmax(capped(model.lm_head(out.last_hidden_state[0, -1]).float(), CAP), -1)", count=2)
s = sub(s, "# CAUSAL-1: mean-matching at the tool-name position", "# CAUSAL-1 (Gemma-4-E4B-it): mean-matching at the tool-name position")
(G / "ta_causal_g.py").write_text(s, encoding="utf-8")

s = (A / "ta_causal2.py").read_text(encoding="utf-8")
s = sub(s, 'C1 = ROOT / "ops/analysis/causal"', 'C1 = ROOT / "ops/analysis_gemma/causal"')
s = sub(s, 'PTS = ROOT / "ops/analysis/jlens_points"', 'PTS = ROOT / "ops/analysis_gemma/jlens_points"')
s = sub(s, 'OUT = ROOT / "ops/analysis/causal2"', 'OUT = ROOT / "ops/analysis_gemma/causal2"')
s = sub(s, 'RES = ROOT / "runner/results/qwen35-greedy"', 'RES = ROOT / "runner/results/gemma4-greedy"')
s = sub(s, 'GPUS = {"0": "c27bc2d7", "1": "bf42d0ab", "2": "4c593ff4"}', 'GPUS = {"0": "c27bc2d7"}')
s = sub(s, 'BANDS = {"12_20": list(range(12, 21)), "21_29": list(range(21, 30))}', 'BANDS = {"16_26": list(range(16, 27)), "28_38": list(range(28, 39))}')
s = sub(s, 'prof = get_profile("qwen3.5-4b")', 'prof = get_profile("gemma-4-e4b")')
s = sub(s, "def log(m):", SOFTCAP_FN.strip("\n") + "\n\n\ndef log(m):")
s = sub(s, '    eos = {tok.eos_token_id, tok.convert_tokens_to_ids("<|im_end|>")}',
        '    ge = model.generation_config.eos_token_id\n    eos = {tok.eos_token_id} | set(ge if isinstance(ge, list) else [ge])\n    CAP = _softcap(model)')
s = sub(s, "cur = int(model.lm_head(o.last_hidden_state[0, -1]).argmax())", "cur = int(capped(model.lm_head(o.last_hidden_state[0, -1]).float(), CAP).argmax())")
s = sub(s, '''            full = [l for l in range(12, 21) if not hasattr(H.blocks[l], "linear_attn")]
            lin = [l for l in range(12, 21) if hasattr(H.blocks[l], "linear_attn")]
            extra = {"attn_band_3_11": list(range(3, 12)), f"attn_full_{'_'.join(map(str, full))}": full,
                     "attn_lin_12_20": lin, "attn_band_12_16": list(range(12, 17)), "attn_band_16_20": list(range(16, 21))}''',
        '''            ltypes = model.config.get_text_config().layer_types
            full = [l for l in range(16, 27) if ltypes[l] == "full_attention"]
            slid = [l for l in range(16, 27) if ltypes[l] != "full_attention"]
            extra = {"attn_band_4_14": list(range(4, 15)), f"attn_full_{'_'.join(map(str, full))}": full,
                     "attn_sliding_16_26": slid, "attn_band_16_21": list(range(16, 22)), "attn_band_21_26": list(range(21, 27))}''')
s = sub(s, 'for name in ("neur_top_64", "neur_rand_64", "neur_top_256", "neur_rand_256", "neur_top_1024", "neur_rand_1024",\n                     "neur_top_256_L12_20", "neur_rand_256_L12_20"):',
        'for name in ("neur_top_64", "neur_rand_64", "neur_top_256", "neur_rand_256", "neur_top_1024", "neur_rand_1024",\n                     "neur_top_256_L16_26", "neur_rand_256_L16_26"):')
s = sub(s, '        band = np.isin(lay, BANDS["12_20"])', '        band = np.isin(lay, BANDS["16_26"])')
s = sub(s, '        sets[(f, "neur_top_256_L12_20")] = top\n        sets[(f, "neur_rand_256_L12_20")] = (top // nn) * nn + rng.integers(0, nn, 256)',
        '        sets[(f, "neur_top_256_L16_26")] = top\n        sets[(f, "neur_rand_256_L16_26")] = (top // nn) * nn + rng.integers(0, nn, 256)')
s = sub(s, "# CAUSAL-2: interventions over the whole response, greedy regeneration", "# CAUSAL-2 (Gemma-4-E4B-it): interventions over the whole response, greedy regeneration")
(G / "ta_causal2_g.py").write_text(s, encoding="utf-8")
print("written:", sorted(p.name for p in G.glob("*_g.py")))
