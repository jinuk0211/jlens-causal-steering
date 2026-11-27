#!/bin/bash
cd /workspace/tj/ne_x/am_steer
echo "$(date +%F_%T) F1 resume" >> chain.log
python3 -u am_focus_runner.py . F1 arms_f1.json 100-107 8192 f1_rows.jsonl murder_ >> f1.log 2>&1
echo "$(date +%F_%T) F1 exit $?" >> chain.log
grep -q "STAGE_DONE F1" f1.log && echo "$(date +%F_%T) F1_DONE" >> chain.log
