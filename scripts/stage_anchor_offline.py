"""Offline Stage-Anchor scan over saved J-lens call viewers (CPU only, no model).

Each call directory holds ``meta.json`` (context pieces, layers, vocab),
``slice.bin`` (gzip of int32 top-k ids then int32 ranks, [ctx, layer, k]) and
optionally ``ranks/<token_id>.bin`` (gzip of int32 rank, [ctx, layer]) plus
``analysis.json`` (outcome / failure localisation).

At every assistant position inside a gated span (tool argument values, optionally
the tool name) it takes the top content token at the mid layer (b) and at the
commit layer (a).  When they differ it scores the reversal from ranks::

    s = log(1 + rank_mid(a)) + log(1 + rank_com(b))

(``rank`` 0 = top-1; a token absent from the stored ranks counts as rank top_k).
This is the offline proxy of the logit score used online in
``jlens_causal.stage_anchor``; use it to compare correct and failing calls, to
read the strongest reversals, and to pick layers before spending GPU time.

Example::

    python scripts/stage_anchor_offline.py D:/vast-backup/qwen4retail --mid 19 --commit 23 \
        --output results/stage_anchor/qwen4retail_19_23.jsonl --show 40
"""

from __future__ import annotations

import argparse
import gzip
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from jlens_causal.stage_anchor import (
    is_content_piece,
    normalise_piece,
    rank_reversal_score,
    script_of,
    span_active,
)


def harmony_args_active(text: str) -> bool:
    """GPT-OSS harmony tool call: inside the JSON body of a ``to=functions.*`` message."""
    to_at = text.rfind("to=functions.")
    message_at = text.rfind("<|message|>")
    return to_at >= 0 and message_at > to_at and text.rfind("<|call|>") < message_at


def gate_active(text: str, gate: str) -> bool:
    if gate == "all":
        return True
    return span_active(text, gate) or harmony_args_active(text)


class RankStore:
    def __init__(self, call_dir: Path, T: int, L: int) -> None:
        self.dir = call_dir / "ranks"
        self.T, self.L = T, L
        self.cache: dict[int, np.ndarray | None] = {}

    def get(self, token_id: int) -> np.ndarray | None:
        if token_id not in self.cache:
            path = self.dir / f"{token_id}.bin"
            if path.is_file():
                raw = gzip.decompress(path.read_bytes())
                self.cache[token_id] = np.frombuffer(raw, dtype=np.int32).reshape(self.T, self.L)
            else:
                self.cache[token_id] = None
        return self.cache[token_id]


def load_call(call_dir: Path) -> tuple[dict, dict, np.ndarray]:
    meta = json.loads((call_dir / "meta.json").read_text(encoding="utf-8"))
    analysis_path = call_dir / "analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8")) if analysis_path.is_file() else {}
    T, L, K = meta["T"], len(meta["layers"]), meta["top_n"]
    raw = gzip.decompress((call_dir / "slice.bin").read_bytes())
    ids = np.frombuffer(raw, dtype=np.int32, count=T * L * K).reshape(T, L, K)
    return meta, analysis, ids


def rank_of(token_id: int, t: int, li: int, ids: np.ndarray, store: RankStore, top_k: int) -> int:
    stored = store.get(token_id)
    if stored is not None:
        return int(stored[t, li])
    hits = np.nonzero(ids[t, li] == token_id)[0]
    return int(hits[0]) if len(hits) else top_k


def scan_call(call_dir: Path, mid: int, commit: int, gate: str, contest_k: int = 10) -> dict | None:
    meta, analysis, ids = load_call(call_dir)
    layers = meta["layers"]
    if mid not in layers or commit not in layers:
        raise SystemExit(f"{call_dir}: layers {layers} lack mid={mid} or commit={commit}")
    li_mid, li_com = layers.index(mid), layers.index(commit)
    vocab = meta["vocab"]
    offset = int(meta.get("ctx_offset") or 0)
    ctx = meta["ctx_strs"][offset:]
    segment = next((s for s in meta["segments"] if s["kind"] == "assistant"), None)
    if segment is None:
        return None
    start, end = segment["start"] - offset, segment["end"] - offset
    store = RankStore(call_dir, ids.shape[0], ids.shape[1])
    top_k = ids.shape[2]
    events = []
    # Position t predicts token t+1; the generated text so far is ctx[start : t+1].
    for t in range(max(start - 1, 0), min(end - 1, ids.shape[0] - 1)):
        text = "".join(ctx[start : t + 1])
        if not gate_active(text, gate):
            continue
        # Top-1 at each stage (as online); both must be content tokens.
        a, b = int(ids[t, li_com, 0]), int(ids[t, li_mid, 0])
        a_str, b_str = vocab.get(str(a), ""), vocab.get(str(b), "")
        content = is_content_piece(a_str) and is_content_piece(b_str)
        # No unembedding offline: a pair in two writing systems is taken as a
        # cross-lingual synonym (online, the unembedding cosine decides).
        same = normalise_piece(a_str) == normalise_piece(b_str) or script_of(a_str) != script_of(b_str)
        emitted = ctx[t + 1] if t + 1 < len(ctx) else ""
        event = {"t": t, "a": a_str, "b": b_str, "content": content, "same": same,
                 "contested": False, "emitted": emitted, "score": 0.0}
        if content and not same:
            r_mid_a = rank_of(a, t, li_mid, ids, store, top_k)
            r_com_b = rank_of(b, t, li_com, ids, store, top_k)
            contested = r_mid_a < contest_k and r_com_b < contest_k
            event.update(rank_mid_a=r_mid_a, rank_com_b=r_com_b, contested=contested, context=text[-80:])
            if contested:
                event["score"] = round(rank_reversal_score(r_mid_a, r_com_b), 3)
            norm_emit = normalise_piece(emitted)
            event["winner"] = ("commit" if norm_emit == normalise_piece(a_str)
                               else "mid" if norm_emit == normalise_piece(b_str) else "other")
        events.append(event)
    scores = [e["score"] for e in events if e["contested"]]
    rel = analysis.get("relative_to_failure")
    if analysis.get("outcome") == "success":
        group = "success"
    elif rel == 0:
        group = "failure_call"
    else:
        group = "failure_episode"
    return {
        "call_dir": call_dir.name, "task_id": analysis.get("task_id"), "call_id": analysis.get("call_id"),
        "outcome": analysis.get("outcome"), "relative_to_failure": rel,
        "failure_kind": analysis.get("failure_kind"), "group": group,
        "gated": len(events),
        "content_positions": sum(e["content"] for e in events),
        "contested": len(scores),
        "frac_contested": (len(scores) / len(events)) if events else 0.0,
        "max_score": max(scores) if scores else 0.0,
        "events": [e for e in events if e["content"] and not e["same"]],
    }


def auc(pos: list[float], neg: list[float]) -> float:
    if not pos or not neg:
        return float("nan")
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roots", nargs="+", type=Path, help="directories that contain task_*__call_* viewers")
    parser.add_argument("--mid", type=int, default=19)
    parser.add_argument("--commit", type=int, default=23)
    parser.add_argument("--gate", choices=["args", "args+name", "all"], default="args+name")
    parser.add_argument("--contest-k", type=int, default=10,
                        help="both winners must be top-k candidates at both layers (<= stored top_n)")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--show", type=int, default=30, help="print the N strongest reversals")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    calls = sorted({p for root in args.roots for p in root.iterdir()
                    if p.is_dir() and (p / "slice.bin").is_file() and (p / "meta.json").is_file()})
    if args.limit:
        calls = calls[: args.limit]
    rows = []
    for index, call_dir in enumerate(calls, 1):
        row = scan_call(call_dir, args.mid, args.commit, args.gate, args.contest_k)
        if row is not None:
            rows.append(row)
        if index % 50 == 0:
            print(f"scanned {index}/{len(calls)}", flush=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    by_group = defaultdict(list)
    for row in rows:
        if row["gated"]:
            by_group[row["group"]].append(row)
    print(f"\nmid=L{args.mid} commit=L{args.commit} gate={args.gate}  calls with gated positions: "
          + ", ".join(f"{g}={len(v)}" for g, v in sorted(by_group.items())))
    for group, members in sorted(by_group.items()):
        gated = sum(r["gated"] for r in members)
        content = sum(r["content_positions"] for r in members)
        contested = sum(r["contested"] for r in members)
        winners = defaultdict(int)
        for r in members:
            for e in r["events"]:
                if e["contested"]:
                    winners[e.get("winner", "?")] += 1
        print(f"  {group:16s} gated {gated:6d}  content {content:5d}  contested {contested:4d} "
              f"({contested / max(content, 1):.1%} of content)  emitted at contested = commit {winners['commit']}"
              f" / mid {winners['mid']} / other {winners['other']}")
    success = by_group.get("success", [])
    for group in ("failure_call", "failure_episode"):
        members = by_group.get(group, [])
        print(f"  AUC {group} vs success: max_score {auc([r['max_score'] for r in members], [r['max_score'] for r in success]):.3f}"
              f"  frac_contested {auc([r['frac_contested'] for r in members], [r['frac_contested'] for r in success]):.3f}")
    success_scores = [e["score"] for r in success for e in r["events"] if e["contested"]]
    if success_scores:
        q = np.percentile(success_scores, [50, 90, 95, 99])
        print(f"  contested score on success calls: p50 {q[0]:.2f} p90 {q[1]:.2f} p95 {q[2]:.2f} p99 {q[3]:.2f}")

    if args.show:
        events = [(e["score"], r, e) for r in rows for e in r["events"] if e["contested"]]
        events.sort(key=lambda x: -x[0])
        print(f"\nstrongest {args.show} reversals (b = mid winner, a = commit winner, emitted = actual next token)")
        for score, row, e in events[: args.show]:
            print(f"  {score:5.2f} {row['group']:15s} task {row['task_id']} call {row['call_id']} t{e['t']}: "
                  f"b={e['b']!r}(r_com {e['rank_com_b']}) a={e['a']!r}(r_mid {e['rank_mid_a']}) "
                  f"emitted={e['emitted']!r} [{e.get('winner')}] ...{e['context'][-60:]!r}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
