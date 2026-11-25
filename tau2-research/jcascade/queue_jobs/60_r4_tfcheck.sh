#!/bin/bash
source /home/project-b/LJW/tau2-steer/probe/jcascade/jc_env.sh
cd $J
JC_OUTSUB=out/review JC_PHASE=tfcheck nice -n 5 $PYV -u stage2b_regen.py
