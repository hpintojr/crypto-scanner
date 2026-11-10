## Bottom line

The frozen plan is behind holding SPY since the Nov 7 freeze: plan -1.83% vs SPY +1.88% (data/sim.md), a gap of 3.71 percentage points, or 3.81 points against the hold_spy sleeve's +1.98% (data/control-sleeves.md). At 3 days of 90 it is too early to judge.

## Numbers

As of 2026-11-10. Paper money only. Percentages since the 2026-11-07 freeze.

| | Since freeze % | Worst drop so far | Source |
|---|--:|--:|---|
| Frozen plan | -1.83 | -1.83% | data/sim.md |
| hold_spy | +1.98 | not reported | data/control-sleeves.md |
| spy_trend_200 | +1.98 | not reported | data/control-sleeves.md |

- The SPY since-freeze % differs between files: +1.88% (data/sim.md) and +1.98% (data/control-sleeves.md).
- data/sim.md lists SPY's worst drop since the freeze as -0.37%. data/control-sleeves.md has no worst-drop column.
- Sleeve values: hold_spy $2,039.52 and spy_trend_200 $2,039.52, each from a $2,000 start on 2026-11-07 (data/control-sleeves.md).
- Whole simulation: $1,884.73 of $2,000 (-5.76%) since it started on 2026-11-05, including the older plan before the freeze (data/sim.md).

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

- Scanner cycles today: 167 started, 166 finished (scanner.log)
- Skipped for time today: allocation, backtest, holdings, laggards, movers (status.md history)

Since the previous report (commit 38689b8):

- Sim errors: none. status.md shows "Simulation flags: none" and "Errors this cycle: 0".
- Quantity mismatches: none (data/sim.md, 3 clean days).
- Failed orders: none found in data/sim-trades.csv.
- Data gaps:
  - No scanner cycle has started since 2026-11-10T22:15:06Z (scanner.log, checked at 22:28Z); the 22:20 and 22:25 cycles are missing.
  - Form 4: paused until 2026-11-11T01:40:49Z after SEC said HTTP 403 (status.md).

## Next dates

- 2026-11-18: first laggards verdict (data/laggards.md).
- 2026-11-19: 14-day checkpoint (data/sim.md).
- 2026-12-05: 30-day checkpoint (data/sim.md).
- 2027-02-05: end of the 90-day freeze (docs/STRATEGY_FREEZE.md).
