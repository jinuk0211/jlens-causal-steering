#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench/runner
export MAX_CONCURRENCY=16 TIMEOUT_SECONDS=1800
bun run src/index.ts --models qwen3.5-4b --scenario-types both \
  --conditions boldly-with-reasoning,boldly-without-reasoning,tamely-with-reasoning,tamely-without-reasoning \
  --runs 1 --output-dir results/qwen35-greedy
echo "FULL_DONE rc=$? $(date '+%F %T')"
