#!/bin/bash
cd /home/project-b/LJW/tau2-steer/probe/circuit
S=$(pgrep -f "python -u c1m_dom.py" | head -1)
while [ -n "$S" ] && kill -0 "$S" 2>/dev/null; do sleep 20; done
if ! grep -q "C1M_DONE" logs/c1m_smoke.log; then echo "$(date +%T) smoke did not finish cleanly; stop" >> logs/after_c1m.log; exit 1; fi
echo "$(date +%T) smoke done; select phase starts" >> logs/after_c1m.log
C1M_PHASE=select ./run_c0.sh c1m_dom.py > logs/c1m_select.log 2>&1
echo "$(date +%T) select exit $?" >> logs/after_c1m.log
PICK=$(/home/project-b/LJW/tau2-steer/.venv/bin/python c1m_pick.py 2>> logs/after_c1m.log)
echo "$(date +%T) pick=$PICK" >> logs/after_c1m.log
if [ "$PICK" != "NONE" ] && [ -n "$PICK" ]; then
  C1M_PHASE=confirm C1M_SETTING=$PICK ./run_c0.sh c1m_dom.py > logs/c1m_confirm.log 2>&1
  echo "$(date +%T) confirm exit $?" >> logs/after_c1m.log
fi
