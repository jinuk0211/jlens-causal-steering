#!/bin/bash
# Runs comparison 1 per benchmark as soon as its files are all on D (puller logs show nothing left).
PY=~/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe
CODE="C:/Users/h/Documents/ChatGPT/vlm interpretability/work/agentbench2-research/code/cap"
OUT=/d/agentbench2_cap/cmp1
drained() { for f in "$@"; do tail -1 "$f" | grep -q "queue 0 busy 0 .*remote pending 0," || return 1; done; return 0; }
for b in ta dojo am; do
  case $b in ta) L=(/d/agentbench2_cap/ta/puller.log); C=ta_type;; dojo) L=(/d/agentbench2_cap/dojo/puller.log); C=dojo;; am) L=(/d/agentbench2_cap/am/puller_0of4.log /d/agentbench2_cap/am/puller_1of4.log /d/agentbench2_cap/am/puller_2of4.log /d/agentbench2_cap/am/puller_3of4.log); C=am;; esac
  until drained "${L[@]}"; do sleep 30; done
  echo "$(date '+%T') $b drained; features" >> $OUT/run.log
  $PY "$CODE/cmp1_features.py" $b D:/agentbench2_cap/$b D:/agentbench2_cap/cmp1/segs.json D:/agentbench2_cap/cmp1/feat_$b.npz >> $OUT/feat_$b.log 2>&1
  echo "$(date '+%T') $b features rc $?" >> $OUT/run.log
  $PY "$CODE/cmp1_report.py" $b D:/agentbench2_cap/cmp1/feat_$b.npz D:/agentbench2_cap/cmp1/report_$b.md $C > $OUT/report_$b.log 2>&1
  echo "$(date '+%T') $b report rc $?" >> $OUT/run.log
done
echo "$(date '+%T') CMP1_DONE" >> $OUT/run.log
