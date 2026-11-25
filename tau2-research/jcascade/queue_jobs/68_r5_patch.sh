#!/bin/bash
source /home/project-b/LJW/tau2-steer/probe/jcascade/jc_env.sh
cd $J
nice -n 5 $PYV -u patch_p1.py
