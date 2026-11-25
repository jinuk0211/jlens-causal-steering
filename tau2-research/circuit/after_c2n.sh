#!/bin/bash
cd /home/project-b/LJW/tau2-steer/probe/circuit
echo "$(date +%T) C2-N select starts" >> logs/after_c2n.log
C2N_PHASE=select ./run_c0.sh c2n_neuron.py > logs/c2n_select.log 2>&1
echo "$(date +%T) select exit $?" >> logs/after_c2n.log
PICK=$(/home/project-b/LJW/tau2-steer/.venv/bin/python c2n_pick.py 2>> logs/after_c2n.log)
echo "$(date +%T) pick=$PICK" >> logs/after_c2n.log
if [ "$PICK" != "NONE" ] && [ -n "$PICK" ]; then
  C2N_PHASE=confirm C2N_SETTING=$PICK ./run_c0.sh c2n_neuron.py > logs/c2n_confirm.log 2>&1
  echo "$(date +%T) confirm exit $?" >> logs/after_c2n.log
fi
