## Bottom line

The frozen plan is behind holding SPY since the Nov 7 freeze: plan -1.83% vs SPY +1.88% (data/sim.md), a gap of 3.71 percentage points, or 3.81 points against the hold_spy sleeve's +1.98% (data/control-sleeves.md). At 3 days of 90 it is too early to judge.

## Numbers

As of 2026-11-10. Paper money only.

| | Value $ | Since freeze % | Worst drop so far | Source |
|---|--:|--:|--:|---|
| Frozen plan | 1,884.73 | -1.83 | -1.83% | data/sim.md |
| hold_spy | 2,039.52 | +1.98 | not reported | data/control-sleeves.md |
| spy_trend_200 | 2,039.52 | +1.98 | not reported | data/control-sleeves.md |

- The frozen plan's $1,884.73 is the whole $2,000 simulation since it started on 2026-11-05, including losses from the older plan before the freeze (data/sim.md). Its since-freeze % and worst drop come from the graduation checklist in data/sim.md.
- data/control-sleeves.md has no worst-drop column. data/sim.md lists SPY's worst drop since the freeze as -0.37%.
- The two files give different SPY numbers since the freeze: +1.88% (data/sim.md) and +1.98% (data/control-sleeves.md). I have not checked why; comparing the start price each file uses would settle it.

## Graduation checklist

From data/sim.md: 1 of 5 met. Day 3 of 90 (since 2026-11-07).

| Condition | Met | Now |
|---|---|---|
| One plan, unchanged, for 90+ days | no | 3 days since 2026-11-07 |
| Beats the same money in SPY after costs | no | plan -1.83% vs SPY +1.88% |
| 30+ days without a simulation error or quantity mismatch | no | 3 clean days |
| Worst drop within 25% (Hamilton to confirm the limit) | yes | plan -1.83%, SPY -0.37% |
| Seen both a 5% rise and a 5% fall in SPY | no | rise no, fall no |

## Problems

No earlier report exists, so this covers the freeze (2026-11-07) to 2026-11-10.

- Sim errors: none. data/sim.md shows 3 clean days; status.md shows "Simulation flags: none" and "Errors this cycle: 0" for the last run.
- Quantity mismatches: none (data/sim.md, 3 clean days).
- Failed orders: none found in data/sim-trades.csv.
- Data gaps:
  - Wallet watch: repeated HTTP 500 and read-timeout errors from the wallet data source across many cycles (status.md history). Log only; the sim does not use it.
  - Form 4: SEC returned HTTP 403; the step is paused until 2026-11-11T01:40:49Z (status.md).
  - CoinGecko: HTTP 429 (too many requests) errors in some cycles (status.md history).
  - Slow cycles: some cycles skipped research steps for time, for example "holdings, backtest, movers, allocation, laggards" (status.md history).
  - Unfinished cycles: 849 starts and 845 finishes logged since 2026-11-07 (scanner.log). The 2026-11-10T22:00 cycle was stopped at the 290-second limit and not committed.

## Next dates

- 2026-11-18: first laggards verdict (data/laggards.md).
- 2026-11-19: 14-day checkpoint (data/sim.md).
- 2026-12-05: 30-day checkpoint (data/sim.md).
- 2027-02-05: end of the 90-day freeze (docs/STRATEGY_FREEZE.md).
