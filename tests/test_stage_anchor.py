"""CPU tests for Stage-Anchor on a toy residual stack (no checkpoint needed)."""

from __future__ import annotations

import torch
from torch import nn

from jlens_causal.stage_anchor import (
    StageAnchorSpec,
    build_content_vocab,
    full_attention_layers,
    is_content_piece,
    normalise_piece,
    reversal,
    span_active,
    stage_anchor_steering,
)
from jlens_causal.vocab_trigger import ReadoutHead

PIECES = ["<|im_end|>", "<parameter=", "pay", ">", "\n", " each", " all", " gift", " credit", "_", "1", "x"]
V = D = len(PIECES)
EACH, ALL = 5, 6


class Tokenizer:
    all_special_ids = [0]

    def decode(self, ids, skip_special_tokens=False):  # noqa: ANN001, ARG002
        return "".join(PIECES[int(i)] for i in ids)

    def batch_decode(self, batch, skip_special_tokens=False):  # noqa: ANN001, ARG002
        return [self.decode(ids) for ids in batch]


class Block(nn.Module):
    def __init__(self, bias: torch.Tensor) -> None:
        super().__init__()
        self.register_buffer("bias", bias)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor]:
        return (x + self.bias,)


class Toy(nn.Module):
    """Mid block (1) prefers ' each' over ' all'; commit block (2) reverses it."""

    def __init__(self) -> None:
        super().__init__()
        e = torch.eye(D)
        self.model = nn.Module()
        self.model.embed_tokens = nn.Embedding(V, D)
        nn.init.zeros_(self.model.embed_tokens.weight)
        self.model.layers = nn.ModuleList([
            Block(torch.zeros(D)), Block(5 * e[EACH] + 3 * e[ALL]), Block(6 * e[ALL]), Block(torch.zeros(D)),
        ])

    def get_input_embeddings(self) -> nn.Module:
        return self.model.embed_tokens

    def forward(self, ids: torch.Tensor) -> torch.Tensor:
        x = self.model.embed_tokens(ids)
        for block in self.model.layers:
            x = block(x)[0]
        return x


class Lens:
    jacobians = {1: torch.eye(D), 2: torch.eye(D)}


def head() -> ReadoutHead:
    return ReadoutHead(norm_weight=torch.zeros(D), eps=1e-6, unembed=torch.eye(D))


def run(mode: str, feed: list[int]) -> tuple[dict, torch.Tensor]:
    model, spec = Toy(), StageAnchorSpec(mid_layer=1, commit_layer=2, threshold=0.1, alphas=(0.1, 0.3, 0.5))
    vocab = build_content_vocab(PIECES, [0])
    with torch.no_grad(), stage_anchor_steering(model, Lens(), head(), spec, vocab, Tokenizer(), mode=mode) as trace:
        model(torch.tensor([[11]]))  # prompt forward: skipped by the gate
        out = None
        for token in feed:
            out = model(torch.tensor([[token]]))
    return trace, out[0, -1]


def test_layers_and_pieces() -> None:
    assert full_attention_layers(n_layers=32) == [3, 7, 11, 15, 19, 23, 27, 31]
    assert normalise_piece("_Credit") == normalise_piece(" credit") == "credit"
    assert is_content_piece(" each") and not is_content_piece("<|im_end|>")
    assert not is_content_piece("\\n") and not is_content_piece("7") and is_content_piece("7", allow_digits=True)


def test_span_gate() -> None:
    assert not span_active("Sure, let me check.", "args")
    assert span_active("<tool_call>\n<function=cancel>\n<parameter=reservation_id>\nAB", "args")
    assert not span_active("<parameter=reservation_id>\nAB\n</parameter>\n", "args")
    assert span_active("<tool_call>\n<function=can", "args+name")
    assert not span_active("<tool_call>\n<function=can", "args")


def test_reversal_contested_and_synonyms() -> None:
    vocab = build_content_vocab(PIECES, [0])
    z_mid = torch.zeros(V)
    z_mid[EACH], z_mid[ALL] = 5.0, 3.0
    z_com = torch.zeros(V)
    z_com[EACH], z_com[ALL] = 5.0, 9.0
    hit = reversal(z_mid, z_com, vocab)
    assert hit["b"] == EACH and hit["a"] == ALL and hit["contested"] and hit["score"] == 2.0 + 4.0
    # Same words by unembedding cosine are not a reversal.
    synonyms = torch.eye(V)
    synonyms[ALL] = synonyms[EACH]
    assert not reversal(z_mid, z_com, vocab, unembed=synonyms)["contested"]
    # A commit winner that the mid stage does not even rank is not contested.
    z_mid_far = torch.arange(V, dtype=torch.float32)
    z_mid_far[EACH], z_mid_far[ALL] = 100.0, -100.0
    assert not reversal(z_mid_far, z_com, vocab, contest_k=3)["contested"]


def test_hook_detects_only_inside_arguments() -> None:
    trace, _ = run("off", [2, 3])  # "pay>" : not inside a parameter value
    assert trace["gated"] == 0 and trace["events"] == []


def test_anchor_flips_commit_readout_and_controls() -> None:
    feed = [1, 2, 3, 4]  # "<parameter=pay>" and "\n": both positions predict value tokens
    off, h_off = run("off", feed)
    assert [e["fired"] for e in off["events"]] == [True, True] and off["edits"] == 0
    assert h_off[ALL] > h_off[EACH]
    anchor, h_anchor = run("anchor", feed)
    assert anchor["edits"] == 2 and anchor["events"][-1]["resolved"] is True
    assert h_anchor[EACH] >= h_anchor[ALL]
    reverse, h_reverse = run("reverse", feed)
    assert reverse["events"][-1]["alpha"] == anchor["events"][-1]["alpha"]
    assert h_reverse[ALL] - h_reverse[EACH] > h_off[ALL] - h_off[EACH]
    random, h_random = run("random", feed)
    assert random["edits"] == 2 and not torch.allclose(h_random, h_off)
