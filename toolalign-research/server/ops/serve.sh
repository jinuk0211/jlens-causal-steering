#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench/inference
exec /home/project-b/LJW/ontoloop/.venv/bin/python -u serve_batched.py --model qwen3.5-4b --host 127.0.0.1 --port 18200
