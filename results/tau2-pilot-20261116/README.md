# tau2-bench steering pilot (2026-11-16)

Updated 2026-11-16 16:13 KST automatically when an experiment block finishes.

- Agent: Qwen3.5-4B, greedy; user simulator: the same model in-process.
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
