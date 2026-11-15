# Official baselines on τ²-bench airline

The six steering baselines (CAA, CAST, MERA, SADI, ITI, AUSteer) used to be
re-implemented from scratch in `src/jlens_causal/baselines.py`.  The
`official` implementation instead runs each paper's **own code at a pinned
commit** and only adds the glue needed for Qwen3.5-4B and Tau2.  The older
re-implementation is untouched and remains selectable
(`"implementation": "reimplementation"`, the default).

## Pinned sources

| Method | Repository | Commit | License |
|---|---|---|---|
| CAA | nrimsky/CAA | `5dabbbd9a0bca5f25e174501e959de378806aa48` | MIT |
| CAST | IBM/activation-steering | `52be60235ee309b46c49d6d5877f36e20c52e6ab` | Apache-2.0 |
| MERA | annahedstroem/MERA-steering | `1a1e6880e885ef9905815baed065e0cbbeed70c7` | none published |
| SADI | weixuan-wang123/SADI | `47b11e4f0818ce4ca625f0c86e59f882ddb0656b` | none published |
| ITI | likenneth/honest_llama | `2c6b2179be7b5aa8f0a171688cf9e01b812ca327` | MIT |
| AUSteer | zijian678/AUSteer | `d6573876734f662824062a69c5b9dee31ae57f81` | none published |

Each repository is a **git submodule** under `third_party/upstream/`, pinned
to the commit above. A submodule records only the URL and the commit, so **no
upstream code is copied into this repository**; that matters because three
of the six publish no license.

Get the exact original code in one of two ways:

* `git clone --recurse-submodules …`, or `git submodule update --init` in an
  existing clone;
* `scripts/fetch_official_upstreams.sh`, which makes shallow clones and skips
  CAA's ~280 MB of result files.

At import time,
`jlens_causal.official.upstream` refuses any checkout that is not at the
pinned commit.  Every artifact records the SHA-256 of each upstream file that
produced it.

## What runs unchanged, and what the adapter supplies

Common to all methods: the data comes from Tau2 repair pairs
(`agent-failure-repair-pair-v1`).  The prompt is the exact chat-template
rendering that the Tau2 backend passes to `model.generate`: same airline
tools, `enable_thinking=False`, ending in the assistant header.  The answers
are the rendered repaired action (positive) and failed action (negative).
Steering runs only on the turns whose boundary matches the failure category,
as in the existing matrix.

| Method | Upstream code called as-is | Adapter (and why) |
|---|---|---|
| **CAA** | `generate_vectors.generate_save_vectors_for_behavior` (token −2 = answer letter, `mean(pos−neg)`); `utils.helpers.find_instruction_end_postion` and `add_vector_from_position` (adds the vector from the last instruction-end token onward, prefill + decode) | A/B items are built from repair pairs. The Qwen template replaces `tokenize_llama_chat`. Hook-based stand-ins replace `LlamaWrapper`, whose block wrapper assumes Llama tuples and `self_attn` on every layer. The instruction-end marker is `<|im_start|>assistant\n`. `official_options.vector_layer` (13) fixes which vector is added, so the wrong-layer control injects that vector at layer 4, like `prompting_with_steering.py`'s `override_vector`. |
| **CAST** | `SteeringDataset` and `SteeringVector.train` (`pca_pairwise`); `MalleableModel.find_best_condition_point`; `MalleableModel`/`LeashLayer` at generation | Pre-rendered strings are passed with `use_chat_template=False`. The behavior window is the last *k* response tokens. A hidden-state view keeps fp32 and only the last logit (the upstream calls `.numpy()` on bf16 and would build full-vocabulary logits). A `respond` override keeps rendered prompts intact. The threshold grid step is 1e-3, because the upstream returns `round(threshold, 3)`. As upstream, vectors are read at block outputs and added at block inputs (a one-layer offset). |
| **MERA** | `probes_train.train_probes`; `probes_utils.postprocess_df_probes` and `get_best_coefficients`; `steering.by_mera.MERA` (`optimal_probe`, its own `post_attention_layernorm` hooks). Derivation flags follow the authors' runner (`steering_run.py` `with_both`: sigmoid and logit), and the alpha candidates come from its `linspace(1e-3, 0.99, 10)` grid. The class defaults (`sigmoid=False`) remain selectable. | Probe data: one example per pair, at the first token where the repaired and failed actions diverge. The error target is `1 − p(repaired)/(p(repaired)+p(failed))`, which is MERA's restricted-softmax error. The estimator and metric dicts that live in `__main__` are copied, using `root_mean_squared_error`. A float32 cast around `steer` is added. Alpha is selected by Tau2 validation success, falling back to no steering if it loses to the baseline, as MERA's own rule does. |
| **SADI** | `steering.select_heads_acts_actups`, compiled from the pinned source with two asserted text patches (the 700-token skip is parameterised; `.to('cuda')` becomes the model device); `util.nethook.TraceDict` for the edit | `get_out`/`make_inputs` are rewritten for Qwen3.5 module names. The `trace_neuron_patch` rule is reproduced on the prefill forward: a clean pass, selected units × strength, and the last prompt position of every layer overwritten. Variant `hiddens` (MLP output) is the default. The upstream join `f'{q.strip()} {a.strip()}'` is kept, so at fit time the template's trailing newlines become a space. |
| **ITI** | `interveners.Collector` and `ITI_Intervener`; `utils.get_com_directions`, `get_top_heads` and `train_probes` | Forward pre-hooks on `o_proj` of the full-attention layers replace pyvene. The split and direction assembly are transcribed from `validate_2fold.py` (L143–144, L160–175), which lives in `main()`. The std tuning set mirrors the upstream default `activations_dataset='tqa_gen_end_q'`: activations at the last token of each training prompt, i.e. the generation position. TruthfulQA, baukit and openai imports are stubbed only when unavailable, because they are never called. |
| **AUSteer** | `steer.MFU_screening` (β = signed sign consistency) and `steer.set_MFU` (global Top-K by \|β\|, `alpha·β` masks) | `obtain_act` is swapped in for the fit: same sites, but without the 512-token truncation that would cut every Tau2 prompt. Both upstream sites are fitted. `attention` (o_proj input; proxy exposes full-attention layers only; mask line `rmodels/modeling_qwen3.py:287` in an `o_proj` pre-hook) is the default. `ffn` (MLP output on all layers; line 102 in an `mlp` hook) is chosen with `official_options.applied_module`. Hooks are used because the forked modeling file needs transformers 4.51. Pairs that would hit the screening's dataset-specific refusal rule are rejected. The fit records how many units tie at the top \|β\|. |

## Unavoidable differences to state in the paper

Each artifact stores the full list under `deviations` and in its `.json`
sidecar.  The ones that change behavior relative to the papers:

* **Qwen3.5 is hybrid.** Only 8 of its 32 layers (3, 7, …, 31) are softmax
  attention with `o_proj`. ITI and AUSteer select heads/units among those
  layers only. ITI's K is scaled from 48/1024 heads to 6/128.
* **The data is not the papers' data.** Contrasts come from validated Tau2
  repair pairs. CAA uses an A/B wrapper around them. MERA labels come from the
  model's own restricted next-token distribution at the divergence token.
* **Generation scope.**
  * SADI edits only the prefill, because the upstream has no decode loop.
  * ITI edits decode steps only, matching pyvene `generate`'s default
    `intervene_on_prompt=False`.
  * MERA edits every position.
  * CAA edits from the instruction end onward.
  * CAST edits every position once its gate fires.
  * AUSteer edits every position.
* **Hyperparameter selection** uses the Tau2 validation split. That is MERA's
  rule (task accuracy on held-out data); for the others it replaces sweeps
  that the original papers reported on their test sets.
* **MERA runs with the authors' runner flags (`with_both`).** These compare
  σ(wᵀh) with logit(α), so α ≤ 0.5 always fires and α ≥ 0.731 never fires.
  This is what produced the paper's numbers. The class defaults implement the
  paper's equation (wᵀh vs logit α) and can be selected instead.

## Running on a vast.ai GPU

```bash
cd /workspace/jlens-causal-steering
bash scripts/fetch_official_upstreams.sh
python -m pip install -e ".[official]"
# full protocol (needs the no-steering train/validation collections, HF_TOKEN, OPENAI_API_KEY)
bash scripts/run_taubench_official_baselines.sh
```

To fit the artifacts alone:

```bash
python -m jlens_causal.official.fit_cli all \
  configs/taubench_airline_official_baselines_qwen35_4b.json \
  outputs/taubench-airline-repair-pairs.jsonl \
  --condition-pairs outputs/taubench-airline-cast-conditions.jsonl
```

The Tau2 side needs `jinuk0211/tau2-bench` with the `implementation:
"official"` dispatch in `src/tau2/agent/jlens_backend.py`. Both repositories
are installed into the same virtualenv, as the existing setup scripts do.

## Tests

`tests/test_official_baselines.py` builds a tiny random Qwen3.5 model. On a
machine with the upstreams fetched, it fits and applies every method end to
end.  Parts that need neither the upstreams nor a GPU (rendering, artifact
round-trip, manifest compilation) always run.
