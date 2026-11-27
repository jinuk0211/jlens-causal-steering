#!/bin/bash
# usage: bash gpu_guard.sh <gpu_index>; exit 0 only if the GPU is allowed and every compute process on it is ours
# (its command line contains /LJW/agentbench2/, or it is the EngineCore of our vLLM on port 18230). Never share a GPU with anyone else (user rule, 11-25).
G="$1"
if [ -z "$G" ]; then echo "gpu_guard: no GPU index given"; exit 3; fi
case ",${AB_FORBIDDEN_GPUS:-0,1}," in *",$G,"*) echo "gpu_guard: GPU $G is forbidden (AB_FORBIDDEN_GPUS=${AB_FORBIDDEN_GPUS:-0,1})"; exit 3;; esac
UUID=$(nvidia-smi --query-gpu=uuid --format=csv,noheader -i "$G" 2>/dev/null)
if [ -z "$UUID" ]; then echo "gpu_guard: GPU $G not found"; exit 3; fi
for P in $(nvidia-smi --query-compute-apps=pid,gpu_uuid --format=csv,noheader | grep "$UUID" | cut -d, -f1 | tr -d ' '); do
  C=$(tr '\0' ' ' < /proc/$P/cmdline 2>/dev/null)
  PP=$(ps -o ppid= -p $P 2>/dev/null | tr -d ' ')
  PC=$(tr '\0' ' ' < /proc/$PP/cmdline 2>/dev/null)
  echo "$C" | grep -q "/LJW/agentbench2/" && continue
  echo "$C" | grep -q "^VLLM::EngineCore" && echo "$PC" | grep -q "vllm serve" && echo "$PC" | grep -q -- "--port 18230" && continue
  if true; then
    echo "gpu_guard: GPU $G ($UUID) has a process that is not ours: $P $(tr '\0' ' ' < /proc/$P/cmdline 2>/dev/null | cut -c1-100); refusing"
    exit 3
  fi
done
echo "gpu_guard: GPU $G ($UUID) has no foreign process"
