J=/home/project-b/LJW/tau2-steer/probe/jcascade
source /home/project-b/LJW/tau2-steer/env.sh
export CUDA_DEVICE_ORDER=PCI_BUS_ID CUDA_VISIBLE_DEVICES=0 JC_GPU_UUID=c27bc2d7 JC_DIR=$J PYTHONDONTWRITEBYTECODE=1
export JC_MODEL=/home/project-b/LJW/.cache/huggingface/hub/models--Qwen--Qwen3.5-4B/snapshots/851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a
export JC_LENS=$(cat /home/project-b/LJW/tau2-steer/lens_path.txt) PYTHONPATH=$J/data TRITON_CACHE_DIR=/home/project-b/LJW/.cache/triton
PYV=/home/project-b/LJW/tau2-steer/.venv/bin/python
