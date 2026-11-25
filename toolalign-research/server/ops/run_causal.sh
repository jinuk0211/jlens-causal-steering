#!/bin/bash
source /home/project-b/LJW/tau2-steer/ToolAlignBench/ops/env.sh
cd /home/project-b/LJW/tau2-steer/ToolAlignBench
exec nice -n 5 /home/project-b/LJW/tau2-steer/.venv/bin/python -u ops/analysis/ta_causal.py
