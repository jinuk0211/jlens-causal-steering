#!/bin/bash
# L9 lens step (PLAN.md Log 11-27 13:3x): CPU dictionaries (layers 8-24) and the 4B lens check, then both 9B dictionaries.
B=/home/project-b/LJW/agentbench2
A=$B/ana
source $B/ops/env_ab.sh
export CUDA_VISIBLE_DEVICES="" PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false AB_THREADS=16 AB_PLATFORM=projectb
V=/home/project-b/LJW/tau2-steer/.venv/bin/python
S=$HF_HOME/hub/models--neuronpedia--jacobian-lens/snapshots
cd $A
LG=logs/l9_lens.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
R4=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
R9=c202236235762e1c871ad0ccb60c8ee5ba337b9a
say "lens step start"
[ -f ne9/dict_4b_j_cpu.npz ] || $V -u ab_dictcpu.py Qwen/Qwen3.5-4B $R4 $S/a4114d7752d11eb546e6cf372213d7e75526d3a1/qwen3.5-4b/jlens/Salesforce-wikitext/Qwen3.5-4B_jacobian_lens_n1000.pt ne9/dict_4b_j_cpu.npz >> $LG 2>&1
[ -f ne9/dict_4b_jpp_cpu.npz ] || $V -u ab_dictcpu.py Qwen/Qwen3.5-4B $R4 $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-4b/jpp/Salesforce-wikitext/Qwen3.5-4B_jpp_lens.pt ne9/dict_4b_jpp_cpu.npz >> $LG 2>&1
$V -u am9_lenscheck.py ne9/dict_4b_j_cpu.npz ne9/dict_4b_jpp_cpu.npz >> $LG 2>&1 || { say "lens check failed"; exit 1; }
[ -f ne9/dict_9b_jbase.npz ] || $V -u ab_dictcpu.py Qwen/Qwen3.5-9B $R9 $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-9b-pt/jlens/Salesforce-wikitext/Qwen3.5-9B-Base_jacobian_lens.pt ne9/dict_9b_jbase.npz >> $LG 2>&1
[ -f ne9/dict_9b_jpp.npz ] || $V -u ab_dictcpu.py Qwen/Qwen3.5-9B $R9 $S/d2527c3cdbaa60dd4b65cbca1604921f044e989a/qwen3.5-9b/jpp/Salesforce-wikitext/Qwen3.5-9B_jpp_lens.pt ne9/dict_9b_jpp.npz >> $LG 2>&1
[ -f ne9/dict_9b_jbase.npz ] && [ -f ne9/dict_9b_jpp.npz ] && say "LENS_DICTS_DONE"
