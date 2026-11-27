#!/bin/bash
# CROSS S1 lane (CROSS.md): bash cross_lane.sh GPU PORT. Copy of x18_lane.sh with its own queue (cross_queue.txt) and stop file (CROSS_STOP).
# Job line: NEED|ARMFILE ARM SUITE MODE "user tasks" TAG REQLOG
cd /home/project-b/LJW/agentbench2/ana
G=$1; PORT=$2
Q=cross_queue.txt
LG=logs/cross_lanes.log
while true; do
  [ -f CROSS_STOP ] && break
  JOB=$(flock cross_queue.lock python3 - "$Q" <<'PY'
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
