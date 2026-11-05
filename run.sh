#!/usr/bin/env bash
# Loop runner: one cycle every 15 minutes. No sudo needed.
cd "$(dirname "$0")"
while true; do
  python3 scanner.py >> scanner.out 2>&1
  sleep 900
done
