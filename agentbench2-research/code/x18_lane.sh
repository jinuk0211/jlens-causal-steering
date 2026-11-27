#!/bin/bash
# X18 / X19 lane (PLAN.md Log 11-27): bash x18_lane.sh GPU PORT
# Pops the first runnable job of x18_queue.txt (under a lock) and runs it with one ab_serve_steer.py server on GPU:PORT.
# Job line: NEED|ARMFILE ARM SUITE MODE "user tasks" TAG REQLOG   (NEED = a file that must exist, or -; ARMFILE / REQLOG = name or -)
# Stops when the queue is empty or ana/X18_STOP exists.
cd /home/project-b/LJW/agentbench2/ana
G=$1; PORT=$2
Q=x18_queue.txt
LG=logs/x18_lanes.log
while true; do
  [ -f X18_STOP ] && break
  JOB=$(flock x18_queue.lock python3 - "$Q" <<'PY'
import os
import sys
q = sys.argv[1]
lines = [l for l in open(q).read().splitlines() if l.strip()]
out = None
for i, l in enumerate(lines):
    need, job = l.split("|", 1)
    if need == "-" or os.path.exists(need):
        out = job
        del lines[i]
        break
open(q, "w").write("\n".join(lines) + ("\n" if lines else ""))
print(out if out else ("WAIT" if lines else "EMPTY"))
PY
)
  if [ "$JOB" = EMPTY ] || [ -z "$JOB" ]; then break; fi
  if [ "$JOB" = WAIT ]; then sleep 30; continue; fi
  echo "$(date '+%F %T') lane $G:$PORT start: $JOB" >> $LG
  eval "set -- $JOB"
  AB_ARMFILE=$1 AB_REQLOG=$7 bash run_steer_slice2.sh $2 $PORT $G $3 $4 "$5" important_instructions none $6
  echo "$(date '+%F %T') lane $G:$PORT done: $JOB" >> $LG
done
echo "$(date '+%F %T') lane $G:$PORT exit" >> $LG
