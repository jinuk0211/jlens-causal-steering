#!/bin/bash
# CROSS S1 chain on GPU 2 (CROSS.md): fold-0 dose calibration -> dose rule -> fold-1 decision steps -> two episode lanes.
cd /home/project-b/LJW/agentbench2/ana
LG=logs/cross_chain.log
echo "$(date '+%F %T') g2 chain start" >> $LG
AB_NREF=41 bash ne_one.sh 2 cross_dcal steer dojo crossd_cal
grep -q "rc=0" logs/cross_dcal.log || { echo "$(date '+%F %T') calibration failed" >> $LG; exit 1; }
AB_PLATFORM=projectb /home/project-b/LJW/tau2-steer/.venv/bin/python ab_ne.py crossdose > logs/cross_dose.log 2>&1 || { echo "$(date '+%F %T') crossdose failed" >> $LG; exit 1; }
echo "$(date '+%F %T') dose chosen: $(grep '"dose"' logs/cross_dose.log | tail -1)" >> $LG
setsid bash cross_lane.sh 2 18311 > /dev/null 2>&1 < /dev/null &
bash ne_one.sh 2 cross_dt1 steer dojo crossd_t1
echo "$(date '+%F %T') fold-1 decision steps rc: $(tail -1 logs/cross_dt1.log)" >> $LG
setsid bash cross_lane.sh 2 18312 > /dev/null 2>&1 < /dev/null &
echo "$(date '+%F %T') g2 chain: lanes 2:18311, 2:18312 running" >> $LG
