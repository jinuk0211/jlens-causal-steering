#!/bin/bash
# L9 lens step, parallel version (PLAN.md Log 11-27 13:3x): the four CPU dictionaries at once (10 threads each), then the 4B check.
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_THREADS=10 AB_PLATFORM=projectb
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
S=$HF_HOME/hub/models--neuronpedia--jacobian-lens/snapshots
cd $A
LG=logs/l9_lens.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
R4=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
R9=c202236235762e1c871ad0ccb60c8ee5ba337b9a
say "lens step v2 start (parallel)"
run() { [ -f ne9/$3 ] || $V -u ab_dictcpu.py $1 $2 $4 ne9/$3 > logs/l9_lens_$3.log 2>&1; say "$3 rc=$? $(tail -1 logs/l9_lens_$3.log | cut -c1-120)"; }
run Qwen/Qwen3.5-4B $R4 dict_4b_j_cpu.npz $S/a4114d7752d11eb546e6cf372213d7e75526d3a1/qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt &
run Qwen/Qwen3.5-4B $R4 dict_4b_jpp_cpu.npz $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-4b/jpp/Salesforce-wikitext/Qwen3.5-4B_jpp_lens.pt &
run Qwen/Qwen3.5-9B $R9 dict_9b_jbase.npz $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-9b-pt/jlens/Salesforce-wikitext/Qwen3.5-9B-Base_jacobian_lens.pt &
run Qwen/Qwen3.5-9B $R9 dict_9b_jpp.npz $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-9b/jpp/Salesforce-wikitext/Qwen3.5-9B_jpp_lens.pt &
wait
$V -u am9_lenscheck.py ne9/dict_4b_j_cpu.npz ne9/dict_4b_jpp_cpu.npz > logs/l9_lenscheck.log 2>&1
RC=$?
say "lens check rc=$RC $(tail -1 logs/l9_lenscheck.log | cut -c1-120)"
[ $RC -ne 0 ] && { say "lens check failed (MISMATCH or error, see logs/l9_lenscheck.log)"; exit 1; }
[ -f ne9/dict_9b_jbase.npz ] && [ -f ne9/dict_9b_jpp.npz ] && say "LENS_DICTS_DONE"
