#!/usr/bin/env bash
# Fallback loop runner for when the Otto scheduler isn't dispatching: one cycle on each 5-minute mark.
# Do not run this alongside a working Otto schedule, or cycles will double up. Stop it with: pkill -f run.sh
cd "$(dirname "$0")"
while true; do
  timeout 290 python3 scanner.py >> scanner.out 2>&1
  sleep $((300 - $(date +%s) % 300))
done
