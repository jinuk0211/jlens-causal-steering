#!/bin/bash
# X20 chain: bash ds_chain.sh MK "slack workspace" [INJ]
#   MK = 4b | 9b | 27b; INJ = all (default) or a comma list of injection task numbers (the same for every suite given).
#   Lanes: AB_DS_LANES="GPU:PORT GPU:PORT ..." (default from dojo_suite.MODELS); capture GPU: AB_DS_CAPGPU (default likewise).
#   27B: on the rented 80 GB box, AB_PLATFORM=a80 AB_ROOT=<same tree> AB_DS_LANES="0:18420" AB_DS_CAPGPU=0.
# A. weights, tasks, base episodes for every suite (lanes), base gate (ASR >= 15 %)
# B. per suite that passed: units -> render -> reqparity -> residual capture -> compare (misaligned vs aligned, after attention
#    and after the MLP) -> X15 capture -> cross-fit arms -> smoke (one GPU step at a time, lanes stopped)
# C. arm episodes for every suite that passed B (lanes), futility check every 5 min (AB_DS_FUTILITY=0 turns it off), reports.
# Stop: touch ana/ds/STOP or ana/ds/MK/STOP (lanes finish their current job). Log: ana/ds/MK/chain.log
MK=$1; SUITES=$2; INJ=${3:-all}
B=${AB_ROOT:-/home/project-b/LJW/agentbench2}
A=$B/ana
D=$A/ds
source $B/ops/env_ab.sh
eval "$(python3 $A/dojo_suite.py env $MK)" || exit 1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True CUDA_DEVICE_ORDER=PCI_BUS_ID AB_PLATFORM=${AB_PLATFORM:-projectb}
export PYTHONDONTWRITEBYTECODE=1 TOKENIZERS_PARALLELISM=false
V=${AB_TORCH_PY:-/home/project-b/LJW/tau2-steer/.venv/bin/python}
ADV=${AB_DOJO_PY:-$B/.venv/bin/python}
LANES=${AB_DS_LANES:-$(python3 $A/dojo_suite.py cfg $MK lanes)}
CAPG=${AB_DS_CAPGPU:-$(python3 $A/dojo_suite.py cfg $MK cap)}
mkdir -p $D/$MK/logs
LG=$D/$MK/chain.log
say() { echo "$(date '+%F %T') $*" >> $LG; }
stopped() { [ -f $D/STOP ] || [ -f $D/$MK/STOP ]; }
DS="python3 $A/dojo_suite.py"
FUT=""

run_lanes() {
  local PIDS="" p g port alive n=0
  for ln in $LANES; do
    g=${ln%%:*}; port=${ln##*:}
    setsid bash $A/ds_lane.sh $MK $g $port >> $D/$MK/logs/lane_$port.out 2>&1 < /dev/null &
    PIDS="$PIDS $!"
  done
  say "lanes started:$PIDS ($LANES)"
  while :; do
    alive=0
    for p in $PIDS; do kill -0 $p 2>/dev/null && alive=1; done
    [ $alive = 0 ] && break
    n=$((n + 1))
    if [ "$1" = arms ] && [ "${AB_DS_FUTILITY:-1}" = 1 ] && [ $((n % 5)) = 0 ]; then
      for S in $OKS; do
        case " $FUT " in *" $S "*) continue;; esac
        R=$($DS interim $MK $S)
        case "$R" in FUTILE*) FUT="$FUT $S"; $DS drop $MK $S >> $LG; say "$S futility stop: $R";; esac
      done
    fi
    sleep 60
  done
  say "lanes done"
}

queue_until_done() {  # STAGE SUITES: queue missing slices, run lanes, at most 3 rounds
  local stage=$1 suites=$2 r q n out
  for r in 1 2 3; do
    stopped && return 1
    q=0
    for S in $suites; do
      case " $FUT " in *" $S "*) continue;; esac
      out=$($DS queue $MK $S $stage 2>&1); say "$out"
      n=$(echo "$out" | awk '/^QUEUED/ {print $2}')
      q=$((q + ${n:-0}))
    done
    [ $q = 0 ] && return 0
    run_lanes $stage
  done
}

gpu_step() {  # NAME COMMAND...: one GPU step on the capture GPU, its own log
  local name=$1; shift
  CUDA_VISIBLE_DEVICES=$CAPG $V -u $A/dojo_suite.py "$@" > $D/$MK/logs/$name.log 2>&1
  local rc=$?
  say "$name rc=$rc $(tail -1 $D/$MK/logs/$name.log | cut -c1-300)"
  return $rc
}

say "chain start: $MK suites [$SUITES] inj $INJ lanes [$LANES] capture GPU $CAPG platform $AB_PLATFORM"
stopped && { say STOP; exit 0; }
$V $A/dojo_suite.py fetch $MK >> $LG 2>&1 || { say "CHAIN_STOPPED fetch"; exit 1; }
for S in $SUITES; do
  $ADV $A/dojo_suite.py tasks $MK $S $INJ >> $LG 2>&1 || { say "CHAIN_STOPPED tasks $S"; exit 1; }
  $DS plan $MK $S >> $LG
done

# A. base
queue_until_done base "$SUITES" || { say STOP; exit 0; }
BOK=""
for S in $SUITES; do
  R=$($DS basecheck $MK $S); say "$R"
  case "$R" in BASE_OK*) BOK="$BOK $S";; esac
done
[ -z "$BOK" ] && { say "CHAIN_DONE no suite passed the base gate"; exit 0; }

# B. units, comparison, selection, smoke
OKS=""
for S in $BOK; do
  stopped && { say STOP; exit 0; }
  P=$D/$MK/$S
  U=$($DS unitsready $MK $S)
  UF=$($DS path $MK $S units); BL=$($DS path $MK $S base); RQ=$($DS path $MK $S reqlogs)
  if [ "$U" = MISSING ]; then
    (cd $B && RENDER_LATER=1 $ADV $A/units_dojo_x19.py $B/runs/$BL /nonexistent $UF $S) > $D/$MK/logs/units_$S.log 2>&1 \
      || { say "$S units failed: $(tail -1 $D/$MK/logs/units_$S.log)"; continue; }
    say "$S units: $(tr -d '\n' < $D/$MK/logs/units_$S.log | cut -c1-300)"
    U=RENDER
  fi
  if [ "$U" = RENDER ]; then
    $V -u $A/ab_xfit.py render $UF > $D/$MK/logs/render_$S.log 2>&1 || { say "$S render failed"; continue; }
    say "$S $(tail -1 $D/$MK/logs/render_$S.log)"
    python3 $A/ab_xfit.py reqparity $UF $RQ > $D/$MK/logs/reqparity_$S.log 2>&1 || { say "$S reqparity failed: $(tail -2 $D/$MK/logs/reqparity_$S.log | tr '\n' ' ')"; continue; }
    say "$S $(tail -1 $D/$MK/logs/reqparity_$S.log)"
  fi
  gpu_step rescap_$S rescap $MK $S || continue
  $V -u $A/dojo_suite.py compare $MK $S > $D/$MK/logs/compare_$S.log 2>&1 || { say "$S compare failed"; continue; }
  say "$S compare: $P/compare.md"
  gpu_step readcap_$S readcap $MK $S || continue
  if [ ! -f $P/arms.json ]; then
    $V -u $A/dojo_suite.py arms $MK $S > $D/$MK/logs/arms_$S.log 2>&1 || { say "$S arms failed: $(tail -1 $D/$MK/logs/arms_$S.log)"; continue; }
  fi
  say "$S $(tail -1 $D/$MK/logs/arms_$S.log)"
  gpu_step smoke_$S smoke $MK $S || continue
  OKS="$OKS $S"
done
[ -z "$OKS" ] && { say "CHAIN_DONE no suite reached the arm episodes"; exit 0; }

# C. arm episodes and reports
queue_until_done arms "$OKS" || { say STOP; exit 0; }
for S in $OKS; do
  $DS report $MK $S > $D/$MK/logs/report_$S.log 2>&1
  say "$S $(tail -1 $D/$MK/logs/report_$S.log)"
done
say "CHAIN_DONE"
