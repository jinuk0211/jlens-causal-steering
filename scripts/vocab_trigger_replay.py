"""Prefix-replay experiment for vocabulary-triggered J-lens steering on tau2 airline.

For each selected agent turn the exact logged ``input_ids`` are re-fed to
Qwen3.5-4B and only that turn is regenerated (greedy), once per condition:

* ``off``      detect only (baseline regeneration)
* ``trigger``  steer along the safe-minus-risk J-lens direction if the
               decision-point trigger fires
* ``random``   same trigger timing and dose, random direction

The prompt minus its last token is prefilled once; every condition continues
from a copy of that cache, so detection always sees the decision position and
conditions differ only by the hooks.  The regenerated tool calls are labelled
against the task's gold actions.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import time
from pathlib import Path

import torch

from jlens_causal.vocab_trigger import (
    ReadoutHead,
    TriggerSpec,
    concept_direction,
    label_calls,
    random_direction,
    vocab_trigger_steering,
)

CALL_RE = re.compile(r"<tool_call>\s*<function=([^>\n]+)>(.*?)</function>\s*</tool_call>", re.S)
PARAM_RE = re.compile(r"<parameter=([^>\n]+)>\n?(.*?)\n?</parameter>", re.S)


def parse_tool_calls(text: str) -> list[dict]:
    calls = []
    for name, body in CALL_RE.findall(text):
        arguments = {}
        for key, raw in PARAM_RE.findall(body):
            value = raw.strip()
            try:
                arguments[key.strip()] = json.loads(value)
            except json.JSONDecodeError:
                arguments[key.strip()] = value
        calls.append({"name": name.strip(), "arguments": arguments})
    return calls


def load_bf16_storage_fp32_compute(model_dir: Path) -> tuple:
    """Keep Linear/Embedding weights in bf16 (the checkpoint's own precision) and
    compute in float32: each layer upcasts its weight just for the call.

    Used on CPUs without bf16 GEMM, where a float32 copy of the 4B model would
    not fit in memory and bf16 matmuls are impractically slow.
    """
    import torch.nn.functional as F
    from transformers import AutoTokenizer, Qwen3_5Config, Qwen3_5ForCausalLM

    def linear_forward(self, x):  # noqa: ANN001
        bias = None if self.bias is None else self.bias.to(x.dtype)
        rows = self.weight.shape[0]
        if rows <= 65536:
            return F.linear(x, self.weight.to(x.dtype), bias)
        # Unembedding (248k rows): upcast in slices to bound temporary memory.
        chunk = 16384
        parts = [
            F.linear(x, self.weight[i : i + chunk].to(x.dtype),
                     None if bias is None else bias[i : i + chunk])
            for i in range(0, rows, chunk)
        ]
        return torch.cat(parts, dim=-1)

    def embedding_forward(self, ids):  # noqa: ANN001
        return F.embedding(ids, self.weight, self.padding_idx).float()

    tokenizer = AutoTokenizer.from_pretrained(model_dir)
    config = Qwen3_5Config.from_pretrained(model_dir).text_config
    model = Qwen3_5ForCausalLM.from_pretrained(
        model_dir, config=config, dtype=torch.bfloat16,
        key_mapping={r"^model\.language_model\.": "model."},
    ).eval()
    for module in model.modules():
        if isinstance(module, torch.nn.Linear):
            module.forward = linear_forward.__get__(module)
        elif isinstance(module, torch.nn.Embedding):
            module.forward = embedding_forward.__get__(module)
        else:
            for _, parameter in list(module.named_parameters(recurse=False)):
                parameter.data = parameter.data.float()
            for name, buffer in list(module.named_buffers(recurse=False)):
                if buffer.is_floating_point():
                    setattr(module, name, buffer.float())
    return model, tokenizer


def load_record(path: str, record_id: str) -> dict:
    for line in open(path, encoding="utf-8"):
        record = json.loads(line)
        if record["record_id"] == record_id:
            return record
    raise KeyError(record_id)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("selection", type=Path, help="JSONL of turns (telemetry_path, record_id, task_id, label)")
    parser.add_argument("trigger", type=Path)
    parser.add_argument("tasks", type=Path)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--lens", type=Path, required=True)
    parser.add_argument("--control-layer", type=int, default=20)
    parser.add_argument("--alphas", type=float, nargs="*", default=[0.1, 0.2],
                        help="trigger-gated doses; negative values push toward the risk vocabulary")
    parser.add_argument("--random-alpha", type=float, default=0.2)
    parser.add_argument("--random-alphas", type=float, nargs="+",
                        help="several random-direction doses (overrides --random-alpha)")
    parser.add_argument("--always-alphas", type=float, nargs="*", default=[],
                        help="steer every turn regardless of the trigger at these doses")
    parser.add_argument("--max-new-tokens", type=int, default=160)
    parser.add_argument("--threads", type=int, default=8)
    parser.add_argument("--precision", choices=["bf16-storage", "fp32", "cuda-bf16", "cuda-fp32"],
                        default="bf16-storage",
                        help="cuda-* on a GPU host (cuda-fp32 for pre-Ampere GPUs); the CPU options keep fp32 compute")
    parser.add_argument("--limit", type=int, help="replay only the first N selected turns")
    parser.add_argument("--prefill-chunk", type=int, default=2048)
    parser.add_argument("--cap-to-logged", action="store_true",
                        help="stop at the logged completion length + 24 tokens")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    import jlens

    torch.set_num_threads(args.threads)
    tasks = {str(t["id"]): t for t in json.loads(args.tasks.read_text(encoding="utf-8"))}
    spec = TriggerSpec.load(args.trigger)
    if args.precision in {"fp32", "cuda-bf16", "cuda-fp32"}:
        from jlens_causal.modeling import load_hf_runtime

        runtime = load_hf_runtime({
            "model_id": "Qwen/Qwen3.5-4B", "local_path": str(args.model_dir), "text_only": True,
            "dtype": "bfloat16" if args.precision == "cuda-bf16" else "float32",
            "device": "cpu" if args.precision == "fp32" else "cuda",
        })
        model, tokenizer = runtime.hf_model, runtime.tokenizer
    else:
        model, tokenizer = load_bf16_storage_fp32_compute(args.model_dir)
    device = next(model.parameters()).device
    lens = jlens.JacobianLens.load(str(args.lens))
    text_model = model.model
    # The unembedding stays in the model's storage dtype; logits are computed in fp32.
    head = ReadoutHead(
        norm_weight=text_model.norm.weight.detach().float(),
        eps=float(model.config.rms_norm_eps),
        unembed=model.get_output_embeddings().weight.detach(),
    )
    direction = concept_direction(lens, head, spec, args.control_layer)
    # Only the observation layer's Jacobian is needed from here on.
    lens.jacobians = {spec.observe_layer: lens.jacobians[spec.observe_layer]}
    rand = random_direction(direction, seed=0)
    # Negative alphas push toward the risk vocabulary (the sign control).
    conditions = [("off", 0.0, direction)] + [("trigger", a, direction) for a in args.alphas]
    random_alphas = args.random_alphas if args.random_alphas is not None else [args.random_alpha]
    conditions += [("random", a, rand) for a in random_alphas]
    conditions += [("always", a, direction) for a in args.always_alphas]

    done = set()
    if args.output.is_file():
        rows = [json.loads(line) for line in open(args.output, encoding="utf-8")]
        done = {(row["record_id"], row["condition"]) for row in rows}
    selection = [json.loads(line) for line in open(args.selection, encoding="utf-8")]
    if args.limit:
        selection = selection[: args.limit]
    eos = [tokenizer.convert_tokens_to_ids("<|im_end|>"), tokenizer.eos_token_id]
    for turn in selection:
        record = load_record(turn["telemetry_path"], turn["record_id"])
        gold = tasks[str(record["task_id"])]["evaluation_criteria"]["actions"]
        prompt = torch.tensor([record["input_ids"]], device=device)
        # Enough tokens to reproduce the logged action (plus slack), capped.
        max_new = min(args.max_new_tokens, len(record["generated_ids"]) + 24) if args.cap_to_logged \
            else args.max_new_tokens
        pending = [c for c in conditions if (record["record_id"], f"{c[0]}@{c[1]}") not in done]
        if not pending:
            continue
        started = time.time()
        cache = None
        with torch.no_grad():
            # Chunked prefill: full-attention layers on CPU otherwise materialise a
            # [heads, T, T] score matrix, which exhausts memory for ~10k-token prompts.
            body = prompt[:, :-1]
            for start in range(0, body.shape[1], args.prefill_chunk):
                cache = model(
                    input_ids=body[:, start : start + args.prefill_chunk],
                    past_key_values=cache, use_cache=True, logits_to_keep=1,
                ).past_key_values
        prefill_seconds = time.time() - started
        for mode, alpha, vector in pending:
            started = time.time()
            with torch.no_grad(), vocab_trigger_steering(
                model, lens, head, spec, mode=mode, control_layer=args.control_layer,
                direction=vector, alpha=alpha,
            ) as trace:
                output = model.generate(
                    input_ids=prompt, past_key_values=copy.deepcopy(cache),
                    max_new_tokens=max_new, do_sample=False, eos_token_id=eos,
                )
            generated = output[0, prompt.shape[1]:].tolist()
            text = tokenizer.decode(generated, skip_special_tokens=False)
            calls = parse_tool_calls(text)
            row = {
                "record_id": record["record_id"],
                "task_id": record["task_id"],
                "turn_index": record["turn_index"],
                "logged_label": turn["label"],
                "condition": f"{mode}@{alpha}",
                "mode": mode,
                "alpha": alpha,
                "trigger_score": trace["score"],
                "triggered": trace["triggered"],
                "steered_positions": trace["steered_positions"],
                "label": label_calls(calls, gold),
                "tool_calls": calls,
                "asks_question": "?" in text and not calls,
                "text": text,
                "matches_logged": generated[: len(record["generated_ids"])] == record["generated_ids"][: len(generated)],
                "prompt_tokens": int(prompt.shape[1]),
                "prefill_seconds": round(prefill_seconds, 1),
                "decode_seconds": round(time.time() - started, 1),
            }
            with args.output.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(f"{record['task_id']:>3} t{record['turn_index']:<3} {row['condition']:<12} "
                  f"score={trace['score']:.2f} fired={trace['triggered']} -> {row['label']:<10} "
                  f"{[c['name'] for c in calls]} ({row['decode_seconds']}s)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
