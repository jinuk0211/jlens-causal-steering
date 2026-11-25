#!/bin/bash
source /home/project-b/LJW/tau2-steer/probe/jcascade/jc_env.sh
cd $J
JC_OUTSUB=out/review JC_PHASE=gen JC_CFGS=C0_r3 nice -n 5 $PYV -u stage2b_regen.py
