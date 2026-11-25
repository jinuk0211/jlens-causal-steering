#!/bin/bash
# GPU-0 job queue for J-Cascade exploration: runs queue/pending/*.sh in name order, at most MAXJ at once, only when GPU 0 has room.
J=/home/project-b/LJW/tau2-steer/probe/jcascade
Q=$J/queue
MAXJ=${MAXJ:-3}
mkdir -p $Q/pending $Q/running $Q/done $Q/failed
echo "$(date '+%F %T') queue start pid $$" >> $Q/queue.log
while [ ! -f $Q/STOP ]; do
  n=$(ls $Q/running | wc -l)
  free=$(nvidia-smi --id=0 --query-gpu=memory.free --format=csv,noheader,nounits | tr -d ' ')
  next=$(ls $Q/pending 2>/dev/null | sort | head -1)
  if [ -n "$next" ] && [ "$n" -lt "$MAXJ" ] && [ "${free:-0}" -gt 15000 ]; then
    mv $Q/pending/$next $Q/running/$next
    echo "$(date '+%F %T') start $next (running $((n+1)), free ${free} MiB)" >> $Q/queue.log
    ( bash $Q/running/$next > $J/logs/q_${next%.sh}.log 2>&1; rc=$?
      if [ $rc -eq 0 ]; then mv $Q/running/$next $Q/done/$next; else mv $Q/running/$next $Q/failed/$next; fi
      echo "$(date '+%F %T') end $next rc $rc" >> $Q/queue.log ) &
    sleep 45
  else
    sleep 20
  fi
done
echo "$(date '+%F %T') queue stop" >> $Q/queue.log
