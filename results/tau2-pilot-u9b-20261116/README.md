# tau2-bench steering pilot, Qwen3.5-9B user simulator (2026-11-16)

Updated 2026-11-17 06:45 KST automatically when an experiment block finishes.

- Agent: Qwen3.5-4B, greedy; user simulator: Qwen3.5-9B (greedy; sampled at T=0.7 for fitx) served from one GPU.
  The earlier run with a Qwen3.5-4B user simulator is in results/tau2-pilot-20261116.
- Retail rewards with NL assertions are DB-only for now (NL assertions graded offline later).
- Domains: airline (50 tasks), retail (50 tasks).
- Conditions: detect (unsteered, trigger only), fitx (extra unsteered train episodes),
  steered conditions (J-lens and the CAA / SADI / ITI / AUSteer baselines) as listed in queue.txt.
- Code: branch agent/official-baselines-tau2 (843b76e).

Files
- summary.txt: pass rates and progress per domain and condition (pilot/summary.py)
- progress.json: block status (done / skipped as identical to detect / failed / total)
- queue.txt: the pilot's unit queue
- simulations/: tau2 results.json per episode
- artifacts/: baseline fits (steering vectors and their metadata)
- failvocab/: failure-vocabulary report (lens readouts of unsteered episodes, fail vs pass)
- simulations-9b/: Qwen3.5-9B unsteered episodes, when present
