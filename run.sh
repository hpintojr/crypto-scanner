#!/usr/bin/env bash
# Loop runner: one cycle every 5 minutes. No sudo needed.
# Do not run this alongside the Otto schedule, or cycles will double up.
cd "$(dirname "$0")"
while true; do
  python3 scanner.py >> scanner.out 2>&1
  sleep 300
done
