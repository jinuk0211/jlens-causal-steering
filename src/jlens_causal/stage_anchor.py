"""Stage-anchored J-lens repair ("Stage-Anchor").

Why (vast-backup analysis, 2026-11-18)
--------------------------------------
* Qwen3.5 mixes linear-attention and full-attention blocks; full attention sits at
  every 4th block (``(i + 1) % 4 == 0``: 3, 7, ..., 31).  The J-lens readout gains
  information in steps exactly there: next-token recall and tool-name rank jump at
  L15 / L19 / L23 / L27 / L31 (0.8B: L11 / L15 / L19).
* The stages are ordered: speech act (L15) -> stance (L19, mostly Chinese latent
  words) -> action / tool choice (L23) -> argument values and numbers (L27) -> output.
* Agent errors look like binding failures: the right item is the mid-stage top-1
  and is overwritten when the action commits (airline task 18: ``each`` is top-1 at
  L16-20, ``all`` wins from L24 on, and one card is copied to every reservation).
  Wrong tools also commit later than right ones.
* The old vocabulary trigger edited the speech-act / stance stage with a fixed word
  list, so it could only defer a write, never change its arguments.

Method
------
Detect, at every generated position inside a gated span (tool argument values, and
optionally the function name): read the residual after a mid block and after a
commit block through the lens, take the top *content* token of each
(``b`` = mid winner, ``a`` = commit winner) and score how far the pair's preference
reversed between the two stages::

    s = (z_mid[b] - z_mid[a]) + (z_com[a] - z_com[b])

It fires when ``a`` and ``b`` differ after normalisation (case, leading space) and
``s >= threshold``.

Repair, at that one position only: move the commit-block output along the lens
direction from ``a`` to ``b``::

    d = normalize(J_com^T (W_U[b] - W_U[a]));   h <- h + alpha * ||h|| * d

``alpha`` is the smallest dose in the ladder whose post-edit commit readout prefers
``b`` (minimum edit), else the largest dose ("unresolved").

Conditions: ``off`` (detect and log only), ``anchor``, ``reverse`` (same dose toward
``a``: an edit that should change nothing) and ``random`` (same gating and dose,
random direction).

Detection and repair happen in one forward pass: the mid block's output is cached
by a hook, and the commit block's hook scores and edits its own output, so the edit
reaches every later block.  The same code reads (mid, commit) = (23, 27) to target
argument values instead of the tool choice.
"""

from __future__ import annotations

import math
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Any

import torch

from jlens_causal.vocab_trigger import ReadoutHead, _blocks

MODES = ("off", "anchor", "reverse", "random")
GATES = ("args", "args+name", "all")


# --------------------------------------------------------------------------- layers


def full_attention_layers(config: Any = None, *, n_layers: int | None = None, interval: int = 4) -> list[int]:
    """Indices of full-attention blocks (``layer_types`` if the config has it)."""
    text_config = getattr(config, "text_config", config)
    layer_types = getattr(text_config, "layer_types", None)
    if layer_types:
        return [i for i, kind in enumerate(layer_types) if kind == "full_attention"]
    if n_layers is None:
        n_layers = int(text_config.num_hidden_layers)
    return [i for i in range(n_layers) if (i + 1) % interval == 0]


# --------------------------------------------------------------------------- spec


@dataclass
class StageAnchorSpec:
    mid_layer: int = 19
    commit_layer: int = 23
    # Calibrate on good turns (an `off` replay): e.g. the 95th percentile of s over
    # contested positions of correct calls.
    threshold: float = 2.0
    contest_k: int = 10
    # Unembedding cosine at or above which two winners count as the same word
    # (cross-lingual / morphological variants); tune from the logged `cos` values.
    same_cos: float = 0.4
    alphas: tuple[float, ...] = (0.05, 0.1, 0.2, 0.3)
    gate: str = "args"
    max_edits_per_turn: int = 8
    seed: int = 0
    notes: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.commit_layer <= self.mid_layer:
            raise ValueError("commit_layer must come after mid_layer")
        if self.gate not in GATES:
            raise ValueError(f"gate must be one of {GATES}")
        self.alphas = tuple(sorted(float(a) for a in self.alphas))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- vocabulary


_EDGE = " \t\r\n_-=#*.,:;!?'\"`()[]{}<>/\\|"


def normalise_piece(piece: str) -> str:
    """Case-, space- and edge-punctuation-insensitive form ('_Credit' == ' credit')."""
    return piece.strip(_EDGE).lower()


def is_content_piece(piece: str, allow_digits: bool = False) -> bool:
    """Word piece; special tokens, escapes, punctuation runs and (by default) digits are not content.

    Digits are excluded because the mid stage does not yet hold the specific digits
    of an identifier (copying resolves at L27+), so digit "reversals" are noise.
    """
    stripped = piece.strip()
    if not stripped or (stripped.startswith("<") and stripped.endswith(">")) or "\\" in stripped:
        return False
    norm = normalise_piece(piece)
    if not norm:
        return False
    if norm.isdigit():
        return allow_digits
    alnum = sum(ch.isalnum() for ch in norm)
    return len(norm) >= 2 and alnum / len(norm) >= 0.6


def script_of(piece: str) -> str:
    """Coarse writing system, to spot cross-lingual synonyms (但由于 / however)."""
    for ch in piece:
        code = ord(ch)
        if 0x4E00 <= code <= 0x9FFF:
            return "cjk"
        if 0x3040 <= code <= 0x30FF:
            return "kana"
        if 0x0400 <= code <= 0x04FF:
            return "cyrillic"
        if 0xAC00 <= code <= 0xD7AF:
            return "hangul"
    return "latin"


@dataclass
class ContentVocab:
    mask: torch.Tensor  # bool [vocab]: content tokens
    canon: torch.Tensor  # long [vocab]: id of the normalised string class
    pieces: list[str]

    def to(self, device: Any) -> ContentVocab:
        return ContentVocab(self.mask.to(device), self.canon.to(device), self.pieces)


def build_content_vocab(pieces: Sequence[str], special_ids: Sequence[int] = ()) -> ContentVocab:
    classes: dict[str, int] = {}
    canon = []
    mask = []
    special = set(special_ids)
    for index, piece in enumerate(pieces):
        canon.append(classes.setdefault(normalise_piece(piece), len(classes)))
        mask.append(index not in special and is_content_piece(piece))
    return ContentVocab(torch.tensor(mask, dtype=torch.bool), torch.tensor(canon, dtype=torch.long), list(pieces))


def content_vocab_from_tokenizer(tokenizer: Any, vocab_size: int) -> ContentVocab:
    pieces = tokenizer.batch_decode([[i] for i in range(vocab_size)], skip_special_tokens=False)
    return build_content_vocab(pieces, getattr(tokenizer, "all_special_ids", ()))


# --------------------------------------------------------------------------- scoring


def reversal(z_mid: torch.Tensor, z_com: torch.Tensor, vocab: ContentVocab, contest_k: int = 10,
             unembed: torch.Tensor | None = None, same_cos: float = 0.4) -> dict[str, Any]:
    """Mid top-1 ``b`` vs commit top-1 ``a`` and the reversal score.

    A position counts as *contested* only when both winners are content tokens,
    they are not the same word (normalised string, or unembedding cosine
    ``>= same_cos`` so that 'both'/'оба' and 'however'/'但由于' agree), ``a`` is
    already a top-``contest_k`` candidate at the mid layer and ``b`` is still one
    at the commit layer: the two stages rank the same candidates in opposite
    order (task 18: ``each`` vs ``all``).  An unrelated mid-layer word (stance,
    Chinese latent word) is not a reversal.
    """
    z_mid = z_mid.float().reshape(-1)
    z_com = z_com.float().reshape(-1)
    b = int(z_mid.argmax())
    a = int(z_com.argmax())
    rank_mid_a = int((z_mid > z_mid[a]).sum())
    rank_com_b = int((z_com > z_com[b]).sum())
    content = bool(vocab.mask[a]) and bool(vocab.mask[b])
    same = bool(vocab.canon[a] == vocab.canon[b])
    cos = None
    if not same and unembed is not None:
        ua, ub = unembed[a].float(), unembed[b].float()
        cos = float(ua @ ub / (ua.norm() * ub.norm()))
        same = cos >= same_cos
    contested = content and not same and rank_mid_a < contest_k and rank_com_b < contest_k
    mid_margin = float(z_mid[b] - z_mid[a])
    com_margin = float(z_com[a] - z_com[b])
    return {
        "a": a, "b": b, "same": same, "cos": cos, "content": content, "contested": contested,
        "rank_mid_a": rank_mid_a, "rank_com_b": rank_com_b,
        "mid_margin": mid_margin, "com_margin": com_margin,
        "score": mid_margin + com_margin if contested else 0.0,
    }


# --------------------------------------------------------------------------- span gate


def span_active(text: str, gate: str) -> bool:
    """Whether the next generated token belongs to a gated span of a Qwen3.5 tool call.

    Format: ``<tool_call>\\n<function=NAME>\\n<parameter=KEY>\\nVALUE\\n</parameter>...``
    """
    if gate == "all":
        return True
    open_at = text.rfind("<parameter=")
    if open_at > text.rfind("</parameter>") and ">" in text[open_at:]:
        return True
    if gate == "args+name":
        function_at = text.rfind("<function=")
        if function_at >= 0 and ">" not in text[function_at:]:
            return True
    return False


class SpanGate:
    """Follows the tokens fed to the model during ``generate``.

    The first forward of a turn carries the prompt (or its last token after a
    prefix cache) and is skipped; every later forward carries the token sampled
    last, whose position predicts the next one.
    """

    def __init__(self, tokenizer: Any, gate: str) -> None:
        self.tokenizer = tokenizer
        self.gate = gate
        self.generated: list[int] = []
        self.forwards = 0
        self.active = False

    def feed(self, ids: Sequence[int]) -> None:
        self.forwards += 1
        if self.forwards > 1:
            self.generated.extend(int(i) for i in ids)
        text = self.tokenizer.decode(self.generated, skip_special_tokens=False) if self.generated else ""
        self.active = span_active(text, self.gate)


# --------------------------------------------------------------------------- hook


class _Lens:
    """Jacobians for two layers and the unembedding, resident on the model device."""

    def __init__(self, lens: Any, head: ReadoutHead, layers: Sequence[int], device: Any, dtype: Any) -> None:
        self.J = {layer: lens.jacobians[layer].to(device=device, dtype=torch.float32) for layer in layers}
        self.head = head
        self.U = head.unembed.to(device=device, dtype=dtype)

    def normed(self, hidden: torch.Tensor, layer: int) -> torch.Tensor:
        return self.head.norm(hidden.float() @ self.J[layer].T)

    def logits(self, hidden: torch.Tensor, layer: int) -> torch.Tensor:
        return (self.normed(hidden, layer).to(self.U.dtype) @ self.U.T).float()

    def pair(self, hidden: torch.Tensor, layer: int, a: int, b: int) -> tuple[float, float]:
        normed = self.normed(hidden, layer)
        z = self.U[[a, b]].float() @ normed.reshape(-1)
        return float(z[0]), float(z[1])

    def direction(self, layer: int, toward: int, away: int) -> torch.Tensor:
        target = self.U[toward].float() - self.U[away].float()
        d = self.J[layer].T @ target
        return d / d.norm()


def _choose_alpha(fast: _Lens, spec: StageAnchorSpec, h: torch.Tensor, d: torch.Tensor,
                  a: int, b: int) -> tuple[float, bool]:
    """Smallest dose whose post-edit commit readout prefers ``b``."""
    scale = h.float().norm()
    for alpha in spec.alphas:
        za, zb = fast.pair(h.float() + alpha * scale * d, spec.commit_layer, a, b)
        if zb >= za:
            return alpha, True
    return spec.alphas[-1], False


@contextmanager
def stage_anchor_steering(
    model: Any,
    lens: Any,
    head: ReadoutHead,
    spec: StageAnchorSpec,
    vocab: ContentVocab,
    tokenizer: Any,
    *,
    mode: str,
) -> Iterator[dict[str, Any]]:
    """Score every gated position during ``generate`` and, unless ``mode='off'``, edit it.

    ``trace["events"]`` holds one entry per gated position: the two winners, the
    reversal score, whether it fired and the dose applied.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}")
    blocks = _blocks(model)
    param = next(model.parameters())
    fast = _Lens(lens, head, [spec.mid_layer, spec.commit_layer], param.device, param.dtype)
    vocab = vocab.to(param.device)
    gate = SpanGate(tokenizer, spec.gate)
    generator = torch.Generator().manual_seed(spec.seed)
    trace: dict[str, Any] = {"mode": mode, "spec": spec.to_dict(), "events": [], "edits": 0, "gated": 0}
    state: dict[str, Any] = {"mid": None}

    def feed(module: Any, args: Any) -> None:  # noqa: ARG001
        ids = args[0]
        if torch.is_tensor(ids) and ids.dtype in (torch.long, torch.int):
            gate.feed(ids[0].tolist())

    def keep_mid(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
        hidden = output if torch.is_tensor(output) else output[0]
        state["mid"] = hidden[0, -1].detach()

    def commit(module: Any, args: Any, output: Any) -> Any:  # noqa: ARG001
        if not gate.active or state["mid"] is None:
            return output
        hidden = output if torch.is_tensor(output) else output[0]
        h = hidden[0, -1].detach()
        trace["gated"] += 1
        score = reversal(fast.logits(state["mid"], spec.mid_layer), fast.logits(h, spec.commit_layer),
                         vocab, spec.contest_k, fast.U, spec.same_cos)
        fired = score["contested"] and score["score"] >= spec.threshold
        event = {"step": len(gate.generated), "a": score["a"], "b": score["b"], "same": score["same"],
                 "cos": None if score["cos"] is None else round(score["cos"], 3),
                 "contested": score["contested"], "rank_mid_a": score["rank_mid_a"],
                 "rank_com_b": score["rank_com_b"], "score": round(score["score"], 3),
                 "mid_margin": round(score["mid_margin"], 3), "com_margin": round(score["com_margin"], 3),
                 "fired": fired, "alpha": 0.0, "resolved": None}
        trace["events"].append(event)
        if not fired or mode == "off" or trace["edits"] >= spec.max_edits_per_turn:
            return output
        d = fast.direction(spec.commit_layer, toward=score["b"], away=score["a"])
        alpha, resolved = _choose_alpha(fast, spec, h, d, score["a"], score["b"])
        if mode == "reverse":
            d = -d
        elif mode == "random":
            r = torch.randn(d.shape, generator=generator)
            d = (r / r.norm()).to(d.device)
        edited = hidden.clone()
        edited[0, -1] = (h.float() + alpha * h.float().norm() * d).to(hidden.dtype)
        trace["edits"] += 1
        event.update(alpha=alpha, resolved=resolved)
        return edited if torch.is_tensor(output) else (edited, *output[1:])

    handles = [
        model.get_input_embeddings().register_forward_pre_hook(feed),
        blocks[spec.mid_layer].register_forward_hook(keep_mid),
        blocks[spec.commit_layer].register_forward_hook(commit),
    ]
    try:
        yield trace
    finally:
        for handle in handles:
            handle.remove()


def summarise_events(events: Sequence[dict[str, Any]], pieces: Sequence[str] | None = None,
                     top: int = 5) -> dict[str, Any]:
    """Compact per-turn summary: counts, the max score and the strongest reversals."""
    scores = [e["score"] for e in events if e["contested"]]
    best = sorted((e for e in events if e["contested"]), key=lambda e: -e["score"])[:top]
    if pieces is not None:
        best = [{**e, "a_str": pieces[e["a"]], "b_str": pieces[e["b"]]} for e in best]
    return {
        "gated": len(events),
        "contested": len(scores),
        "fired": sum(e["fired"] for e in events),
        "max_score": max(scores) if scores else 0.0,
        "mean_score": (sum(scores) / len(scores)) if scores else 0.0,
        "edits": sum(e["alpha"] > 0 for e in events),
        "unresolved": sum(e["resolved"] is False for e in events),
        "top": best,
    }


def rank_reversal_score(rank_mid_of_a: float, rank_com_of_b: float) -> float:
    """Offline proxy when only ranks are stored (0 = top-1): log(1+r_mid(a)) + log(1+r_com(b))."""
    return math.log1p(max(rank_mid_of_a, 0.0)) + math.log1p(max(rank_com_of_b, 0.0))
