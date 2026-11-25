#!/bin/bash
# AM TEST worker on the 2x RTX 3090 box: only the units in am/c2/remote_test_uids.txt (assigned on project-b).
# usage: bash r3090_test.sh GPU   (GPU 0 or 1). The guard refuses a GPU that already has any process.
G=$1
W=/workspace/agentbench2
A=$W/ana
cd $A
export HF_HOME=/workspace/.hf_home HF_HUB_OFFLINE=1 TOKENIZERS_PARALLELISM=false PYTHONDONTWRITEBYTECODE=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=$G AB_PLATFORM=r3090
export AB_BATCH=${AB_BATCH:-36} AB_ROWS_SUFFIX=_r3090g$G AB_ONLY_UIDS=$A/am/c2/remote_test_uids.txt PYTHONPATH=$A/pydeps
echo "$(date '+%F %T') gpu $G start" >> $A/logs/r3090_test.log
$W/.venv/bin/python -u ab_regen.py test am $A/am/units.json $A/am/c2 > $A/logs/r3090_test_g$G.log 2>&1
RC=$?
echo "$(date '+%F %T') gpu $G rc=$RC" >> $A/logs/r3090_test.log
[ $RC -eq 0 ] && grep -q TEST_DONE $A/logs/r3090_test_g$G.log && touch $A/am/c2/REMOTE_TEST_DONE
