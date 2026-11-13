"""Where, and in what form, do the failure-predicting J-lens words appear?

1. Layer profile: at every available layer, mine a risk/safe vocabulary on the
   train split (same rule as vocab_trigger_mine.py) and report held-out AUC and
   the top tokens.
2. Token families: for the risk/safe tokens of the best layer, the nearest
   neighbours in unembedding space and how enriched those neighbours are.
3. Rank trajectories: mean rank of each selected token at every layer, for
   bad-write turns versus all other turns.

Residuals come from the telemetry (decision point, layers 8/16/31) or, with
``--recompute``, from a fresh forward pass that records every layer (GPU).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from collections import Counter
from pathlib import Path

import torch

from jlens_causal.vocab_trigger import ReadoutHead, load_readout_head


def _mine_module():
    path = Path(__file__).with_name("vocab_trigger_mine.py")
    spec = importlib.util.spec_from_file_location("vocab_trigger_mine", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def recompute_residuals(turns: list[dict], model_dir: Path, device: str, dtype: str = "bfloat16",
                        stream: bool = False, chunk: int = 4096) -> tuple[list[int], ReadoutHead]:
    """Forward each turn's logged prompt once and keep the last position of every block.

    Also returns the model's own readout head, so ``--stream-weights`` hosts never
    need the checkpoint on disk.
    """
    from transformers import Qwen3_5Config, Qwen3_5ForCausalLM

    if stream:
        from jlens_causal.hf_stream import stream_qwen35_text_model

        model = stream_qwen35_text_model(
            "Qwen/Qwen3.5-4B", "851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a", model_dir,
            device=device, dtype=getattr(torch, dtype),
        )
    else:
        config = Qwen3_5Config.from_pretrained(model_dir).text_config
        model = Qwen3_5ForCausalLM.from_pretrained(
            model_dir, config=config, dtype=getattr(torch, dtype),
            key_mapping={r"^model\.language_model\.": "model."},
        ).to(device).eval()
    head = ReadoutHead(
        norm_weight=model.model.norm.weight.detach().float().cpu(),
        eps=float(model.config.rms_norm_eps),
        unembed=model.get_output_embeddings().weight.detach().to(torch.bfloat16).cpu(),
    )
    blocks = model.model.layers
    captured: dict[int, torch.Tensor] = {}

    def hook(index: int):
        def record(module, args, output):  # noqa: ANN001, ARG001
            hidden = output if torch.is_tensor(output) else output[0]
            captured[index] = hidden[0, -1].float().cpu()

        return record

    handles = [block.register_forward_hook(hook(i)) for i, block in enumerate(blocks)]
    try:
        with torch.no_grad():
            for number, turn in enumerate(turns, 1):
                record = next(json.loads(line) for line in open(turn["telemetry_path"], encoding="utf-8")
                              if json.loads(line)["record_id"] == turn["record_id"])
                ids = torch.tensor([record["input_ids"]], device=device)
                # Chunked with a cache: the hooks keep the last position of the final chunk,
                # and peak memory stays bounded for 10k+ token prompts.
                cache = None
                for start in range(0, ids.shape[1], chunk):
                    cache = model.model(input_ids=ids[:, start : start + chunk],
                                        past_key_values=cache, use_cache=True).past_key_values
                del cache
                for layer, value in captured.items():
                    turn["residuals"][("initial_decision", layer)] = value
                if number % 100 == 0:
                    print(f"recomputed {number}/{len(turns)}", flush=True)
    finally:
        for handle in handles:
            handle.remove()
    layers = list(range(len(blocks)))
    del model, blocks
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return layers, head


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("telemetry_root", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--lens", type=Path, required=True)
    parser.add_argument("--recompute", action="store_true", help="forward pass for all layers (GPU)")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--dtype", default="bfloat16", choices=["bfloat16", "float16", "float32"],
                        help="recompute precision (float32 on pre-Ampere GPUs)")
    parser.add_argument("--max-turns", type=int,
                        help="recompute on all bad writes plus a random sample of other turns")
    parser.add_argument("--stream-weights", action="store_true",
                        help="with --recompute: stream the weights from the Hub into GPU memory "
                             "(--model-dir then only needs config/tokenizer files)")
    parser.add_argument("--prefill-chunk", type=int, default=4096,
                        help="recompute forward in chunks of this many tokens (bounds GPU memory)")
    parser.add_argument("--top-k", type=int, default=50)
    parser.add_argument("--vocab-size", type=int, default=8)
    parser.add_argument("--min-support", type=int, default=3)
    parser.add_argument("--neighbours", type=int, default=6)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import jlens
    from transformers import AutoTokenizer

    mine = _mine_module()
    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    turns = mine.load_turns(args.telemetry_root, tasks)
    tokenizer = AutoTokenizer.from_pretrained(args.model_dir)
    if args.recompute:
        if args.max_turns:
            bad = [t for t in turns if t["label"] == "bad_write"]
            rest = [t for t in turns if t["label"] != "bad_write"]
            generator = torch.Generator().manual_seed(0)
            keep = torch.randperm(len(rest), generator=generator)[: max(0, args.max_turns - len(bad))].tolist()
            turns = bad + [rest[i] for i in sorted(keep)]
        # Compare against the telemetry's own layer-16 residual as a numerics check.
        reference = {t["record_id"]: t["residuals"].get(("initial_decision", 16)) for t in turns}
        # The forward passes are the expensive part: keep them (and the readout head) on disk.
        cache_path = args.output.with_suffix(".residuals.pt")
        if cache_path.is_file():
            saved = torch.load(cache_path)
            layers = saved["layers"]
            head = ReadoutHead(**saved["head"])
            rows = {rid: i for i, rid in enumerate(saved["record_ids"])}
            for turn in turns:
                stacked = saved["residuals"][rows[turn["record_id"]]]
                for layer in layers:
                    turn["residuals"][("initial_decision", layer)] = stacked[layer].float()
            print(f"loaded recomputed residuals from {cache_path}")
        else:
            layers, head = recompute_residuals(turns, args.model_dir, args.device, args.dtype,
                                               args.stream_weights, args.prefill_chunk)
            torch.save({
                "layers": layers,
                "record_ids": [t["record_id"] for t in turns],
                "residuals": torch.stack([torch.stack([t["residuals"][("initial_decision", layer)]
                                                       for layer in layers]) for t in turns]),
                "head": {"norm_weight": head.norm_weight, "eps": head.eps, "unembed": head.unembed},
            }, cache_path)
        sims = [float(torch.nn.functional.cosine_similarity(
                    t["residuals"][("initial_decision", 16)].float(), reference[t["record_id"]].float(), dim=0))
                for t in turns if reference[t["record_id"]] is not None]
        print(f"recomputed vs logged layer-16 residual: min cos {min(sims):.4f}, mean {sum(sims) / len(sims):.4f}")
    else:
        layers = sorted({layer for t in turns for (site, layer) in t["residuals"] if site == "initial_decision"})
        head = load_readout_head(args.model_dir)
    lens = jlens.JacobianLens.load(str(args.lens))
    device = args.device
    unembed = head.unembed.to(device=device, dtype=torch.float32)
    is_bad = torch.tensor([t["label"] == "bad_write" for t in turns])
    split = [t["split"] for t in turns]
    train_idx = [i for i, s in enumerate(split) if s == "train"]
    decode = {}

    def piece(token: int) -> str:
        if token not in decode:
            decode[token] = tokenizer.decode([token])
        return decode[token]

    report: dict = {"layers": {}, "turns": dict(Counter(f"{t['split']}/{t['label']}" for t in turns))}
    selected: dict[int, dict] = {}
    for layer in layers:
        residual = torch.stack([t["residuals"][("initial_decision", layer)] for t in turns]).float().to(device)
        transported = residual if layer == layers[-1] and layer not in lens.jacobians \
            else lens.transport(residual, layer)
        logits = head.norm(transported) @ unembed.T  # [turns, vocab]
        topk = torch.topk(logits, args.top_k, dim=-1).indices.cpu()
        bad_counts, rest_counts = Counter(), Counter()
        n_bad = n_rest = 0
        for i in train_idx:
            tokens = topk[i].tolist()
            if is_bad[i]:
                bad_counts.update(tokens)
                n_bad += 1
            else:
                rest_counts.update(tokens)
                n_rest += 1

        # Bind this layer's counts: the closure is reused after the loop (families).
        def log_odds(token: int, bad_counts=bad_counts, rest_counts=rest_counts,
                     n_bad=n_bad, n_rest=n_rest) -> float:
            a, b = bad_counts[token] + 0.5, rest_counts[token] + 0.5
            return math.log(a / (n_bad + 1)) - math.log(b / (n_rest + 1))

        candidates = [tok for tok in set(bad_counts) | set(rest_counts)
                      if bad_counts[tok] + rest_counts[tok] >= args.min_support and mine.word_like(piece(tok))]
        ranked = sorted(candidates, key=log_odds)
        risk = [tok for tok in reversed(ranked) if bad_counts[tok] >= args.min_support][: args.vocab_size]
        safe = [tok for tok in ranked if rest_counts[tok] >= args.min_support][: args.vocab_size]
        if not risk or not safe:
            continue
        scores = (torch.logsumexp(logits[:, risk], -1) - torch.logsumexp(logits[:, safe], -1)).cpu().tolist()
        aucs = {}
        for name in ("train", "validation", "evaluation"):
            idx = [i for i, s in enumerate(split) if s == name]
            aucs[name] = mine.auc([scores[i] for i in idx], [bool(is_bad[i]) for i in idx])
        report["layers"][layer] = {
            "auc": aucs,
            "risk": [(piece(t), round(log_odds(t), 2), bad_counts[t], rest_counts[t]) for t in risk],
            "safe": [(piece(t), round(log_odds(t), 2), bad_counts[t], rest_counts[t]) for t in safe],
        }
        selected[layer] = {"risk": risk, "safe": safe, "log_odds": log_odds}
        print(f"L{layer:2d} AUC train={aucs['train']:.3f} val={aucs['validation']:.3f} "
              f"eval={aucs['evaluation']:.3f} | risk {[piece(t) for t in risk[:5]]} | safe {[piece(t) for t in safe[:5]]}",
              flush=True)

    # Token families around the best layer's vocabulary (chosen by train AUC).
    best = max(report["layers"], key=lambda layer: report["layers"][layer]["auc"]["train"] or 0)
    report["best_layer_by_train_auc"] = best
    normed = torch.nn.functional.normalize(unembed.float(), dim=-1)
    families = {}
    for side in ("risk", "safe"):
        for token in selected[best][side]:
            sims = normed @ normed[token]
            sims[token] = -1
            neighbours = torch.topk(sims, args.neighbours).indices.tolist()
            families[piece(token)] = [
                (piece(n), round(float(sims[n]), 2), round(selected[best]["log_odds"](n), 2)) for n in neighbours
            ]
    report["families"] = families

    # Rank trajectories of the best layer's tokens across all layers.
    trajectory: dict[str, dict] = {}
    tokens = selected[best]["risk"] + selected[best]["safe"]
    for layer in layers:
        residual = torch.stack([t["residuals"][("initial_decision", layer)] for t in turns]).float().to(device)
        transported = residual if layer == layers[-1] and layer not in lens.jacobians \
            else lens.transport(residual, layer)
        logits = head.norm(transported) @ unembed.T
        for token in tokens:
            ranks = torch.cat([
                (chunk > chunk[:, token : token + 1]).sum(-1, dtype=torch.int32).float().cpu()
                for chunk in logits.split(64)
            ])
            entry = trajectory.setdefault(piece(token), {})
            entry[layer] = {"bad": round(float(ranks[is_bad].median()), 1),
                            "rest": round(float(ranks[~is_bad].median()), 1)}
    report["rank_trajectories"] = trajectory
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("best layer by train AUC:", best)
    for name, neighbours in families.items():
        print(f"  {name!r:>14} ~ {neighbours}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
