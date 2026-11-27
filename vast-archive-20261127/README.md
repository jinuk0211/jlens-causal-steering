# vast.ai box 2 backup (11-27, incomplete)

User request (11-27 16:3x): back up everything on one vast instance to the PC and delete it; the user chose box 2
(instance 62631064, 2080 Ti, ssh <vast-box>, /workspace/amflow).

What happened:
- 16:40 a streamed tar of /workspace (without .hf_home, amflow/.venv, __pycache__; 1,911 entries, 9.4 GB) started.
- 16:42 the box closed the ssh connection after 365 MB. Since then every ssh attempt is closed before the SSH banner
  (TCP connects, sshd does not answer), checked every 30 s until 16:58. The instance-scoped API key on the boxes cannot
  list instances, so its state (stopped, restarting, destroyed) could not be read from here.
- The instance was NOT destroyed by this session.

Files here:
- partial_stream_1642.tgz.incomplete: the first 59 entries only (about 400 MB): 30 amflow/flow npz files, amflow/cache,
  parity, setup and capture logs. The main results (amflow/abl, taabl, tanew, comp, an_*.md) are not in it.
- partial_list.txt: the entries in the partial file.

Copies of box 2 material that already exist elsewhere on the PC:
- work/agentbench2-research/results_mirror/flow_temporal (11-26 14:14): an_leakEA_* reports and the flow scripts.
- C:/Users/h/AppData/Local/Temp/claude/36145b4db1347ff5/36485149-62e8-440b-a2d9-4343046e1d68/scratchpad/tanew_src
  (11-27 12:4x): tanew PROTOCOL.md and code, confirm/vecs.npz, src/calls.json, taabl/ta_ablate.py, ITERATE.md, units.json.

Plan once the box answers again: build the archive on the box in 400 MB parts (script ready: /root/arch/mk.sh was not
written, the connection had already closed), download the parts with retries, check md5 per part and the entry count,
then destroy with `vastai destroy instance $CONTAINER_ID` from inside.
