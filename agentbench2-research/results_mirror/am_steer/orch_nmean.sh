#!/bin/bash
cd /workspace/tj/ne_x/am_steer
log=orch.log
echo "$(date +%F_%T) orchestrator start (user: run the all-neuron harmful vs harmless comparison)" >> $log
for p in $(ps -eo pid,cmd | awk '/[r]un_f1.sh/ {print $1}'); do kill $p; echo "$(date +%F_%T) killed run_f1.sh wrapper $p" >> $log; done
touch STOP_F
while ps -eo cmd | grep -q "[a]m_focus_runner"; do sleep 10; done
mv STOP_F STOP_F_used_$(date +%H%M)
echo "$(date +%F_%T) F1 runner exited at a batch boundary" >> $log
for p in $(ps -eo pid,cmd | awk '/[e]xplorer\/ne_cases.py/ {print $1}'); do kill $p; echo "$(date +%F_%T) killed server $p" >> $log; done
sleep 6
cd /workspace/tj/ne_x && mv explorer.log explorer_$(date +%H%M).log && setsid -f bash -c "./run_explorer.sh > explorer.log 2>&1" < /dev/null > /dev/null 2>&1
for i in $(seq 1 60); do sleep 5; curl -s -m 5 -o /dev/null localhost:8791/api/cases && break; done
sleep 40
cd /workspace/tj/ne_x/am_steer
setsid -f bash -c "./run_f1b.sh" < /dev/null > /dev/null 2>&1
setsid -f bash -c "python3 -u nmean_am.py ../am_resp/am_resp_cases.json ../am/dump/nmean > nmean.log 2>&1" < /dev/null > /dev/null 2>&1
echo "$(date +%F_%T) server restarted with /api/nmean; F1 resumed (run_f1b.sh); nmean capture started" >> $log
echo "$(date +%F_%T) orchestrator: F1 paused at a batch boundary, server restarted with /api/nmean, F1 resumed, all-neuron capture of 600 AM responses started (user request)" >> changes.md
