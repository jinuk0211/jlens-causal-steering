"""SADI (semantics-adaptive dynamic intervention) through weixuan-wang123/SADI.

The upstream is a set of scripts, not a library, and carries no license, so it
is fetched at its pinned commit and used as follows:

  * ``steering.select_heads_acts_actups`` (unit selection: last-token
    activations of ``q a`` for the correct and wrong answer, mean difference,
    global top values) is compiled from the pinned source text with exactly
    two textual patches, both asserted to match once/twice:
      - the hard-coded 700-token skip becomes a parameter (every Tau2 prompt
        exceeds 700 tokens, so the original would skip all pairs);
      - ``.to('cuda')`` becomes ``.to(model.device)``.
    ``make_inputs`` and ``get_out`` are injected: ``get_out`` reads the same
    modules (``mlp``, ``mlp.act_fn``, per-head ``o_proj`` input) on Qwen3.5.
  * ``util.nethook.TraceDict`` (imported unchanged) performs the edit at
    generation time, with the patch rule of ``trace_neuron_patch``: a clean
    pass over the prompt, selected units multiplied by ``strength``, and the
    last prompt position of every layer's module output overwritten with the
    edited clean values.  Decode steps are not edited (the upstream evaluates
    one teacher-forced pass and has no decode loop).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from jlens_causal.official import upstream
from jlens_causal.official.artifact import build_artifact, save_artifact
from jlens_causal.official.data import RenderedPair, pair_summary
from jlens_causal.official.modelparts import (
    attention_shape,
    decoder_layers,
    decoder_layers_prefix,
    first_tensor,
    full_attention_layers,
    hooks,
)

METHOD = "sadi"
UPSTREAM_FILES = ("steering.py", "trace.py", "util/nethook.py", "causal_trace.py")
VARIANT_MODULES = {"hiddens": "mlp", "neurons": "mlp.act_fn"}
SOURCE_PATCHES = (
    ("if len(inp[0]) > 700:", "if len(inp[0]) > SADI_MAX_TOKENS:", 1),
    (".to('cuda')", ".to(model.device)", 2),
)
DEVIATIONS = [
    "select_heads_acts_actups runs from the pinned source with the 700-token skip "
    "parameterised (disabled for Tau2) and '.to(\"cuda\")' replaced by the model device.",
    "make_inputs (ROME) and get_out are reimplemented for Qwen3.5 module names; head "
    "values of Gated DeltaNet layers are zero, so the 'heads' variant is not used.",
    "Generation applies the trace_neuron_patch rule on the prefill forward only; "
    "decode steps are unedited.",
]


def _make_inputs_factory(model_device_: Any) -> Any:
    """``causal_trace.make_inputs`` from ROME (left padding with id 0).

    ROME defaults ``device="cuda"``, i.e. the GPU holding the model; the default
    here is the model's own device so the selector also runs on CPU tests.
    """

    def make_inputs(tokenizer: Any, prompts: list[str], device: Any = model_device_) -> dict[str, Any]:
        import torch

        token_lists = [tokenizer.encode(p) for p in prompts]
        maxlen = max(len(t) for t in token_lists)
        if "[PAD]" in tokenizer.all_special_tokens:
            pad_id = tokenizer.all_special_ids[tokenizer.all_special_tokens.index("[PAD]")]
        else:
            pad_id = 0
        input_ids = [[pad_id] * (maxlen - len(t)) + t for t in token_lists]
        attention_mask = [[0] * (maxlen - len(t)) + [1] * len(t) for t in token_lists]
        return {
            "input_ids": torch.tensor(input_ids).to(device),
            "attention_mask": torch.tensor(attention_mask).to(device),
        }

    return make_inputs


def _get_out_factory(model: Any) -> Any:
    """``trace.get_out`` with the same 9-tuple layout for Qwen3.5 module names."""
    import numpy as np
    import torch

    blocks = decoder_layers(model)
    heads, head_dim = attention_shape(model)
    attention_layers = set(full_attention_layers(model))

    def get_out(model_: Any, prompt: Any, device: Any, index: int) -> tuple[Any, ...]:  # noqa: ARG001
        model_.eval()
        mlp: dict[int, Any] = {}
        act: dict[int, Any] = {}
        head: dict[int, Any] = {}

        def output_hook(store: dict[int, Any], layer: int):
            def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
                store[layer] = first_tensor(output)[0][index].detach().float().cpu().numpy()

            return hook

        def head_hook(layer: int):
            def hook(module: Any, args: Any) -> None:  # noqa: ARG001
                value = args[0][0][index].detach().float().cpu().numpy()
                head[layer] = value.reshape(heads, head_dim)

            return hook

        handles = []
        for layer, block in enumerate(blocks):
            handles.append(block.mlp.register_forward_hook(output_hook(mlp, layer)))
            handles.append(block.mlp.act_fn.register_forward_hook(output_hook(act, layer)))
            if layer in attention_layers:
                handles.append(block.self_attn.o_proj.register_forward_pre_hook(head_hook(layer)))
        with hooks(handles), torch.no_grad():
            model_(prompt, logits_to_keep=1)
        n_layers = len(blocks)
        head_value = [
            head.get(layer, np.zeros((heads, head_dim), dtype=np.float32)) for layer in range(n_layers)
        ]
        mlp_value = [mlp[layer] for layer in range(n_layers)]
        act_value = [act[layer] for layer in range(n_layers)]
        # ATT, MLP, MLP_up, MLP_down, ATT_post, HEAD, MLP_act, MLP_act_up, MLP_gate
        return None, mlp_value, None, None, None, head_value, act_value, None, None

    return get_out


def _compiled_selector(model: Any, max_tokens: int | None) -> tuple[Any, dict[str, Any]]:
    import numpy as np

    source = upstream.read_source(METHOD, "steering.py")
    tree = ast.parse(source)
    node = next(
        item
        for item in tree.body
        if isinstance(item, ast.FunctionDef) and item.name == "select_heads_acts_actups"
    )
    function_source = ast.get_source_segment(source, node)
    applied = []
    for old, new, expected in SOURCE_PATCHES:
        count = function_source.count(old)
        if count != expected:
            raise RuntimeError(f"SADI source patch {old!r} matched {count} times, expected {expected}")
        function_source = function_source.replace(old, new)
        applied.append({"old": old, "new": new, "count": count})
    namespace: dict[str, Any] = {
        "np": np,
        "make_inputs": _make_inputs_factory(next(model.parameters()).device),
        "get_out": _get_out_factory(model),
        "SADI_MAX_TOKENS": max_tokens if max_tokens is not None else float("inf"),
    }
    exec(compile(function_source, "SADI/steering.py:select_heads_acts_actups", "exec"), namespace)
    return namespace["select_heads_acts_actups"], {"patches": applied, "max_tokens": max_tokens}


def fit(
    runtime: Any,
    pairs: list[RenderedPair],
    *,
    max_tokens: int | None,
    output_path: Path,
    model_id: str,
    model_revision: str,
) -> Path:
    import torch

    train = [pair for pair in pairs if pair.split == "train"]
    if len(train) < 2:
        raise ValueError("SADI needs at least two training repair pairs")
    select, patch_record = _compiled_selector(runtime.hf_model, max_tokens)
    train_data = [[pair.prompt, pair.positive, pair.negative] for pair in train]
    max_heads, min_heads, max_acts, min_acts, max_hiddens, min_hiddens = select(
        runtime.hf_model, runtime.tokenizer, train_data
    )

    def as_tensor(units: list[list[Any]]) -> Any:
        return torch.tensor([[int(layer), int(index)] for layer, index in units], dtype=torch.long)

    artifact = build_artifact(
        method=METHOD,
        model_id=model_id,
        model_revision=model_revision,
        upstream=upstream.provenance(METHOD, UPSTREAM_FILES),
        fit={"source_patches": patch_record, "data": pair_summary(train), "used_pairs": len(train)},
        deviations=DEVIATIONS,
        state={
            "max_hiddens": as_tensor(max_hiddens),
            "min_hiddens": as_tensor(min_hiddens),
            "max_acts": as_tensor(max_acts),
            "min_acts": as_tensor(min_acts),
        },
    )
    return save_artifact(torch, artifact, output_path)


@contextmanager
def steer(
    model: Any,
    tokenizer: Any,  # noqa: ARG001
    artifact: dict[str, Any],
    *,
    strength: float,
    layer: int,  # noqa: ARG001  (units span several layers)
    prompt_ids: list[int],
    options: dict[str, Any],
) -> Iterator[dict[str, Any]]:
    import torch

    variant = str(options.get("variant", "hiddens"))
    if variant not in VARIANT_MODULES:
        raise ValueError(f"SADI variant must be one of {sorted(VARIANT_MODULES)}")
    top_k = int(options.get("top_k", 10))
    units = artifact["state"]["max_hiddens" if variant == "hiddens" else "max_acts"][:top_k].tolist()
    nethook = upstream.import_upstream(METHOD, "util.nethook")
    blocks = decoder_layers(model)
    prefix = decoder_layers_prefix(model)
    suffix = VARIANT_MODULES[variant]
    names = {f"{prefix}.{ly}.{suffix}": ly for ly in range(len(blocks))}
    ntoks = len(prompt_ids)

    # Clean pass over the prompt (steer_hiddens / steer_neurons: get_out(model, inp_q, ...)).
    clean: dict[int, Any] = {}

    def capture(ly: int):
        def hook(module: Any, args: Any, output: Any) -> None:  # noqa: ARG001
            clean[ly] = first_tensor(output)[0, -1].detach().float().cpu().numpy()

        return hook

    capture_handles = [
        model.get_submodule(name).register_forward_hook(capture(ly)) for name, ly in names.items()
    ]
    device = next(model.parameters()).device
    with hooks(capture_handles), torch.no_grad():
        model(input_ids=torch.tensor([prompt_ids], device=device), logits_to_keep=1)
    edit = {ly: value.copy() for ly, value in clean.items()}
    for layer_ind, unit_ind in units:
        edit[layer_ind][unit_ind] = strength * edit[layer_ind][unit_ind]

    trace = {"variant": variant, "top_k": top_k, "strength": float(strength),
             "units": [[int(a), int(b)] for a, b in units], "applied_edits": 0}

    def patch_rep(output: Any, layer: str) -> Any:
        # trace_neuron_patch.patch_rep: h[:, t, :] = torch.tensor(new_mlp_up[ly])
        h = first_tensor(output)
        if h.shape[1] != ntoks:  # decode step: the upstream never edits these
            return output
        ly = names[layer]
        h[:, ntoks - 1, :] = torch.tensor(edit[ly]).to(device=h.device, dtype=h.dtype)
        trace["applied_edits"] += 1  # last prompt position of one layer
        return output

    # retain_output=False: the upstream default keeps every full-sequence output alive.
    with nethook.TraceDict(model, list(names), retain_output=False, edit_output=patch_rep):
        yield trace
