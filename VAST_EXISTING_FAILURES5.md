# Existing-failure five-method steering run

This workflow reuses the completed TauBench baseline and reviewed trajectories
under `/workspace/tau2-bench/data/simulations/failure-steering`. It does not run
the baseline simulations again.

The pooled `agent_behavior_error` dataset uses localized, steerable events from:

- `missed_required_action`
- `guideline_violation`
- `incorrect_interpretation`
- `wrong_sequence`
- `irrelevant_tool_call`
- `repeated_tool_call`
- `tool_call_error`

`task_failure_unlocalized` is excluded because it has no causal assistant message
index. Previously validated `tool_call_error` repairs are reused as seeds. The
runner fills a diverse quota of four train and four validation repairs, extracts
CAA, MERA, SADI, ITI, and AUSteer artifacts, runs three validation strengths for
each method, selects one strength per method, and runs the frozen evaluation set.

## Vast command

```bash
cd /workspace/jlens-causal-steering
git pull --ff-only origin agent/jlens-thought-steering
source .venv/bin/activate

export HF_TOKEN='YOUR_HF_TOKEN'
export OPENAI_API_KEY='YOUR_OPENAI_API_KEY'
export SIMULATION_TIMEOUT_SECONDS=1200

bash scripts/run_taubench_existing_failures5.sh
```

The run is restartable. Re-running the same command preserves validated repairs,
existing artifacts, completed simulations, and completed reviews.

Progress logs:

```bash
tail -f /workspace/taubench-behavior5.log
tail -f /workspace/jlens-remote-worker-behavior5.log
```

Outputs:

- repair pairs: `/workspace/jlens-causal-steering/outputs/taubench-airline-behavior-repair-pairs.jsonl`
- artifacts: `/workspace/jlens-artifacts/taubench-airline/agent-behavior-error/`
- simulations: `/workspace/tau2-bench/data/simulations/failure-steering-behavior5-v1/`
- analysis: `/workspace/tau2-bench/data/analysis/failure-steering-behavior5-v1/`
- selected conditions: `/workspace/baselines5-selected-conditions.txt`

The default repair quota can be reduced to the extractor minimum for a cheaper,
weaker smoke run:

```bash
export REPAIR_MINIMUM_PER_SPLIT=2
export REPAIR_MAX_PER_SPLIT=2
bash scripts/run_taubench_existing_failures5.sh
```
