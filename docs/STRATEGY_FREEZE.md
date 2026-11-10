# Strategy freeze

Paper only. No real money.

- The plan in research/sim.py (PLAN) is frozen for 90 days from 2026-11-07, matching the graduation checklist in data/sim.md.
- Every report is compared with holding SPY. A plan has to beat it after costs.
- New ideas go in research/ as log-only signals. They are scored at 30+ signals each and never go into PLAN directly.
- A plan change needs Hamilton's written approval and restarts the 90 day clock.
- Trading code changes go through Claude, not Otto.

Open decisions for Hamilton (not applied):
- Keep or drop the old momentum picks. Eight of eight hit the -5% stop, and the backtest shows about -0.97% per trade after costs.
- Crypto is half the plan and its own test shows a -66.6% worst drop.
- Daily trend checks traded 369 times in the backtest versus 151 weekly, with similar results.
- The backtests use today's surviving coins and stocks, which flatters them.
