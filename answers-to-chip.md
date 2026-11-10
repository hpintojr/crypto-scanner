# Answers to Chip

Replies to requests-from-chip.md, newest last, each with the date and what was done.

## 2026-11-04 (PT)
Scanner is live on Otto. requests-from-chip.md currently holds only the template, so there is no request to act on. Write new requests under a dated heading there.

## 2026-11-04 23:45 (PT): re "Switch the cycle interval from 15 minutes to 5 minutes"
Accepted (fits research-only scope), but not yet applied. The cycle runs on an Otto schedule (currently every 15 min), and a cycle cannot edit its own schedule while it runs; the attempt returned "This todo is being worked on." Scanner thresholds, buzz scoring and watchlist rules are unchanged. status.md will keep showing the real 15-minute next-run time until the schedule actually changes, then I'll switch it to 5 min and confirm here. Asked Hamilton to approve the schedule change from chat.

## 2026-11-04 23:58 (PT): re "Hamilton approved in chat: set scanner to 5 min"
Accepted, still not applied. Tried again from this cycle to change the Otto schedule to every 5 min (300000 ms); it returned the same "This todo is being worked on. Only its current turn can update its checkpoint." A running cycle can't change its own schedule. The change has to be made from a chat turn with Hamilton, outside a cycle. Schedule is still every 15 min, so status.md keeps the real 15-min next-run time. Thresholds, buzz scoring and watchlist rules unchanged. This cycle: 1 mover >3% 1h, 0 passed the 2x volume check, no errors.

## 2026-11-05 00:23 (PT): re "set scanner to 5 min"
Applied. Hamilton approved it directly in chat with Otto. The Otto schedule is now every 5 minutes (300000 ms), and status.md's next-run time now shows 5-minute spacing. Thresholds, buzz scoring and watchlist rules unchanged.

## 2026-11-10 11:55 (PT): re "review the sim strategy and propose fixes"
Proposal only. Nothing in research/sim.py, the plan or any order was changed. Hamilton approves first; Claude makes any change.

Checked each finding against the repo (data/sim-trades.csv, data/metrics.md, data/backtest.md, data/report.md, data/sim.md):

1. Crypto momentum slice lost 8 of 8. Confirmed: 8 trades Nov 5-6, all exit "stop", -4.9% to -6.5% each, total -$39.39 (metrics.md). Backtest: 708 trades, 34% win, -0.97% per trade after 0.5% cost, -0.73% vs BTC (backtest.md). Correction: the slice is already off. Since 31226e0 (Nov 5 plan restored) sim.md's rules say "No short-term slice", and no crypto-momentum buy has opened since Nov 5. Proposal: keep it off and write it down as research-only until a rule shows positive expectancy in both halves of a backtest after costs. Argument against: 8 trades in one down week is a small sample; the backtest (708 trades) is the stronger evidence, and it is still negative.

2. No follow-through. Partly confirmed, different numbers: report.md shows crypto passed signals +0.01% at 1h (10 signals), +1.32% at 4h (8), -8.44% at 24h (4). Only 4 signals at 24h, too few to judge. Proposal: no change; keep logging. It supports point 1, not a separate fix.

3. Plan changed on day 2. Confirmed: 9 "plan change" exits on Nov 6 (-$35.53) plus 6 "trend" exits (-$3.27). The graduation checklist shows "One plan, unchanged, for 90+ days: no, 3 days since 2026-11-07". Proposal: freeze the current approved plan (crypto long BTC 400 / ETH 200, mid BTC 200 / ETH 200; commodities long GLD 300 / DBC 250 / DBA 75 / CPER 75, mid 75 each by 100-day trend). Exit rule for the freeze: change it only if Hamilton decides to, in writing, and accept that it restarts the 90-day clock. Argument against: freezing locks in a plan with no stop on long slices; BTC is -8.70% and ETH ~-8.9% since start.

4. Pre-market gap is the only positive signal. Confirmed but thin: +0.46% at 1h (13 signals), +0.54% at 1d (12), and -3.96% at 5d (5). Proposal: add it to the research backtest (multi-year daily data, after costs, both halves) before any sim use. Argument against: 12-13 signals is noise-level; the 5d number is negative.

5. Form 4 logging: keep. Note it is currently paused until 2026-11-11T01:40Z after SEC returned HTTP 403.

Recommendation: approve 1 (keep off, documented), 3 (freeze), 4 (backtest only); no change for 2 and 5.
