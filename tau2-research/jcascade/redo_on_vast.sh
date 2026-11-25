#!/bin/bash
# Re-run J-Cascade stage 1 on a fresh vast box from this PC (Git Bash).  usage: bash redo_on_vast.sh <port> <host>
# Needs: this PC's SSH key in the vast account. Uploads env setup, inputs and scripts, then starts both GPUs and the analysis.
set -e
P=$1; H=$2; D="$(cd "$(dirname "$0")" && pwd)"; M="$D/../mining"
SSH="ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new -p $P root@$H"
scp -q -o BatchMode=yes -o StrictHostKeyChecking=accept-new -P $P "$D/vast_setup.sh" "$D/jc_export.tgz" "$D/stage1_replay.py" "$D/stage1_analyze.py" "$M/cache_turns.json" "$M/vocab.json.gz" root@$H:/workspace/
$SSH 'set -e; mkdir -p /workspace/jc/data /workspace/jc/logs /workspace/jc/out; cd /workspace; sed -i "s/\r$//" vast_setup.sh
  mv stage1_replay.py stage1_analyze.py jc/; mv cache_turns.json vocab.json.gz jc/data/; tar xzf jc_export.tgz -C jc/data
  cat > jc/run_all.sh <<"EOS"
#!/bin/bash
cd /workspace && bash vast_setup.sh > jc/logs/setup.log 2>&1
cd /workspace/jc && . venv/bin/activate
export HF_HOME=/workspace/jc/hf HF_HUB_OFFLINE=1 JC_DTYPE=float16 TRITON_CACHE_DIR=/workspace/jc/triton PYTHONPATH=/workspace/jc/data
NG=$(nvidia-smi -L | wc -l)
for g in $(seq 0 $((NG-1))); do CUDA_VISIBLE_DEVICES=$g JC_SHARD=$g/$NG python -u stage1_replay.py > logs/stage1a_g$g.log 2>&1 & done
wait
CUDA_VISIBLE_DEVICES=0 python -u stage1_analyze.py > logs/stage1b.log 2>&1
echo ALL_DONE >> logs/stage1b.log
EOS
  setsid -f bash jc/run_all.sh > jc/logs/run_all.log 2>&1 < /dev/null; echo started'
