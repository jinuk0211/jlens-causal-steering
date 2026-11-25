# vast.ai instances archived and destroyed (11-25 21:1x KST)

User request: "vast ai 인스턴스 2x RTX 3090, 2x GTX 1080 Ti는 지우게 중요한 결과있으면 다 다운받고 stop 하고 delete좀".

Both instances were destroyed from inside with the instance-scoped key (`vastai destroy instance $CONTAINER_ID`).
Afterwards both refused connections.

| file | instance | contents | entries |
|---|---|---|---|
| box1080ti_workspace.tgz (850 MB) | 62304232, 2x GTX 1080 Ti, ssh <vast-box> (= <vast-host>) | /workspace: agentbench2 (runs = AgentDojo fp32 cross-check, partial, 267 attack episodes; dojo_hf*.py; ana; pydeps), fsteer (failure-turn steering loop: out, art, tau2-bench sims, toolalign, jlens-causal-steering), neuron-explorer (with .git), tau2x (out), tau2-bench (with .git and data), tj (session 609f19 partial trajectory scans), logs, tau2x_code_orig_20261124.tgz | 5634 (= count on the box) |
| box3090_workspace.tgz (598 MB) | 62507564, 2x RTX 3090, ssh <vast-box> | /workspace: tj (neuron-explorer traj and ce outputs, scripts), agentbench2/ana (AM TEST worker logs, rows_test_r3090g0/g1.jsonl = 56 rows, already imported to project-b as am/c2/rows_test_r3090.jsonl), setup_ab.sh | 294 (= count on the box) |

Not archived, because they can be rebuilt:
- the Python venvs (.venv, ne-venv, steer-venv);
- the HF cache .hf_home (Qwen3.5-4B rev 851bf6e, neuronpedia jacobian-lens a4114d77);
- the agentdojo checkout (git 089ed46);
- __pycache__;
- the 3090 copy of am/c2/stats.npz (the original is on project-b; md5 4ef0955e).

The 2080 Ti instance (ssh <vast-box>) was not touched; neuron-explorer is running there.
