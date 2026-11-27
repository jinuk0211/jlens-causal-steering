#!/bin/bash
# CROSS AM chain on GPU 0 (CROSS.md): S2 capture + selection, U-AM dose calibration (worker u0), then S2 test workers.
cd /home/project-b/LJW/agentbench2/ana
LG=logs/cross_chain.log
echo "$(date '+%F %T') g0 chain start" >> $LG
setsid bash t9d_worker.sh crossuam_cal 0 u0 16000 12 10 > /dev/null 2>&1 < /dev/null &
bash ne_one.sh 0 cross_amemcap amemcap
grep -q "rc=0" logs/cross_amemcap.log || { echo "$(date '+%F %T') amemcap failed" >> $LG; exit 1; }
AB_PLATFORM=projectb /home/project-b/LJW/tau2-steer/.venv/bin/python ab_ne.py amemsets crossam > logs/cross_amemsets.log 2>&1 || { echo "$(date '+%F %T') amemsets failed" >> $LG; exit 1; }
echo "$(date '+%F %T') S2 sets written; starting S2 test worker p0 (seeds 17000-17003)" >> $LG
bash t9d_worker.sh crossam 0 p0 17000 4 12
echo "$(date '+%F %T') S2 worker p0 done" >> $LG
