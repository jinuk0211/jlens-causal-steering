"""CPU check of ab_core batching with a tiny random Qwen3.5 text model: batched rows without edits equal single-row greedy,
row pruning keeps the survivors equal, edits change only their own row, seeded Gumbel rows with the same seed agree."""
import os
import sys

os.environ.setdefault("CUDA_VISIBLE_DEVICES", "")
import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ab_core as C
from transformers import AutoTokenizer
from transformers.models.qwen3_5.configuration_qwen3_5 import Qwen3_5TextConfig
from transformers.models.qwen3_5.modeling_qwen3_5 import Qwen3_5ForCausalLM

torch.manual_seed(0)
C.patch_gdn()
cfg = Qwen3_5TextConfig(vocab_size=248320, hidden_size=64, intermediate_size=96, num_hidden_layers=4, num_attention_heads=4,
                        num_key_value_heads=2, head_dim=16, linear_num_key_heads=2, linear_num_value_heads=4,
                        linear_key_head_dim=16, linear_value_head_dim=16, layer_types=["linear_attention", "linear_attention", "linear_attention", "full_attention"])
model = Qwen3_5ForCausalLM(cfg).eval()
tok = AutoTokenizer.from_pretrained(C.MODEL, revision=C.REV)
H = C.Hooked(model)
torch.manual_seed(1)
prompt = torch.randint(100, 5000, (300,)).tolist()
never = lambda text, r: False


def single(edits, seed=None):
    return C.regen(model, tok, H, prompt, [edits], 40, never, sample=None if seed is None else [seed])[0]


base = single({})
mu = torch.randn(64)
ed = {("attn", 1): C.Edit("set", vec=mu)}
edited = single(ed)
rows = [{}, ed, {}, {("mlp", 2): C.Edit("add", vec=torch.randn(64), alpha=3.0)}]
out = C.regen(model, tok, H, prompt, rows, 40, never)
print("base==row0", out[0]["ids"] == base["ids"], "base==row2", out[2]["ids"] == base["ids"])
print("edited==row1", out[1]["ids"] == edited["ids"], "edit changed", edited["ids"] != base["ids"])
stop_at = {0: 10, 2: 25}
cnt = {"n": 0}


def stop_some(text, r):
    return False


class StopAfter:
    def __init__(self):
        self.calls = {}

    def __call__(self, text, r):
        n = len(tok.encode(text, add_special_tokens=False))
        return r == 0 and n >= 16


o2 = C.regen(model, tok, H, prompt, [{}, ed, {}], 40, StopAfter(), watch=8)
print("pruned: row1==edited", o2[1]["ids"] == edited["ids"], "row2==base", o2[2]["ids"] == base["ids"], "row0 len", o2[0]["n"], o2[0]["end"])
s1 = C.regen(model, tok, H, prompt, [{}, {}, ed], 40, never, sample=[7, 7, 7])
s0 = single({}, seed=7)
print("gumbel same seed rows equal", s1[0]["ids"] == s1[1]["ids"] == s0["ids"], "edited row shares prefix",
      sum(a == b for a, b in zip(s1[0]["ids"], s1[2]["ids"])), "/", len(s1[0]["ids"]))
g = C.Gate(tok, ["commit"], "<function=")
ids = tok.encode("hello <tool_call>\n<function=send_money>\n", add_special_tokens=False)
print("gate", [g(t, 0, ids[:t]) for t in range(len(ids))], [tok.decode([i]) for i in ids])
_, cache = C.prefill(model, prompt[:-1])
H.cap = {"mode": "pos", "pos": [5, 10], "kinds": {"res", "attn", "act"}}
H.store = {}
model(input_ids=torch.tensor([prompt]), use_cache=False)
H.cap = None
print("capture", {k: tuple(v.shape) for k, v in list(H.store.items())[:4]})
print("TEST_DONE")
