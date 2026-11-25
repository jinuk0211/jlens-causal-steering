#!/bin/bash
source /home/project-b/LJW/tau2-steer/probe/jcascade/jc_env.sh
cd $J
nice -n 5 $PYV -u review_denial_extract.py
