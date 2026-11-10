# Candidate test

Backtest of candidate ETF rules against holding SPY, from research/candidate_test.py. Places no orders and does not touch the frozen plan. Past results don't guarantee future ones.

Period: 2020-07-28 to 2026-11-09. Cost 0.05% of the traded amount, one extra day of delay between signal and trade. Halves are cut at the middle of the run. ETF list is today's survivors on the IEX feed.

| Rule | Total % | Per year % | Worst drop % | Sharpe | 1st half % | 2nd half % | Rebalances |
|---|--:|--:|--:|--:|--:|--:|--:|
| hold_spy | 151.9 | 15.8 | -24.5 | 0.98 | 43.1 | 75.9 | 1 |
| spy_trend_200 | 73.0 | 9.1 | -12.8 | 0.87 | 18.9 | 45.4 | 15 |
| rotation_top2 | 96.4 | 11.3 | -20.4 | 0.84 | 8.9 | 80.5 | 32 |
| dual_momentum | 49.1 | 6.6 | -29.9 | 0.49 | -8.8 | 64.1 | 13 |
| faber_5 | 38.0 | 5.3 | -8.4 | 0.75 | 3.5 | 33.3 | 42 |
| balanced_60_40 | 46.0 | 6.2 | -27.2 | 0.57 | 2.2 | 42.4 | 1 |
| all_weather | 46.4 | 6.3 | -20.6 | 0.67 | 1.9 | 43.2 | 1 |

## Cost stress (total %)

| Rule | 0% | 0.05% | 0.1% | 0.25% |
|---|--:|--:|--:|--:|
| hold_spy | 152.0 | 151.9 | 151.8 | 151.4 |
| spy_trend_200 | 74.3 | 73.0 | 71.7 | 67.9 |
| rotation_top2 | 99.4 | 96.4 | 93.5 | 85.0 |
| dual_momentum | 51.0 | 49.1 | 47.3 | 41.8 |
| faber_5 | 38.9 | 38.0 | 37.1 | 34.6 |
| balanced_60_40 | 46.0 | 46.0 | 45.9 | 45.7 |
| all_weather | 46.5 | 46.4 | 46.3 | 46.1 |

## Screen against hold_spy

A candidate is an edge worth paper testing only if the first four lines are yes. One that fails those but wins on Sharpe and worst drop is a way to cut risk, not a way to beat SPY.

**spy_trend_200**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: yes; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

**rotation_top2**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: yes; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

**dual_momentum**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: no; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

**faber_5**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: yes; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

**balanced_60_40**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: no; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

**all_weather**: beats SPY after costs: no; beats SPY in both halves: no; smaller worst drop than SPY: yes; still beats SPY at 5x cost: no; higher Sharpe than SPY (info): no

## Limits

- One backtest is a screen, not proof. A few years can be luck, and the 2017 start has one long bull market in it.
- Survivor ETFs, IEX-only prices, close fills and 0% on cash all flatter the result.
- Rules and lookbacks were fixed before the run. Changing them after seeing this table is how a rule gets overfit.
- No candidate trades. Promotion to paper needs Hamilton's written approval and restarts nothing in the frozen plan.
