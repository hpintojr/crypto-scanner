# Growth mix test

Backtest of the growth mix in research/sim.py PLAN, from research/growth_test.py. Places no orders. Past results don't guarantee future ones.

Mix: BTC/USD $500, ETH/USD $333, SOL/USD $167, QQQ $715, VTI $285 ($2,000). Each asset is held only while its previous close is above its 100-close average, otherwise cash at 0%.

Period: 2021-01-04 to 2026-11-05. First half 2021-01-04 to 2023-12-06, second half 2023-12-06 to 2026-11-05. Cost: 0.1% of the sleeve per buy or sell. Total % counts costs from $2,000; half and drop columns are from each part's start.

| Test | $2,000 became | Total % | Worst drop % | 1st half % | 1st half worst drop % | 2nd half % | 2nd half worst drop % |
|---|--:|--:|--:|--:|--:|--:|--:|
| Daily check, no costs | $3,415 | +70.7 | -40.4 | +12.0 | -40.4 | +53.7 | -18.4 |
| Daily check, 0.1% per trade | $3,180 | +59.0 | -41.3 | +7.9 | -41.3 | +48.6 | -19.0 |
| Weekly check, no costs | $3,139 | +56.9 | -47.6 | +11.1 | -47.6 | +42.3 | -18.1 |
| Weekly check, 0.1% per trade | $3,055 | +52.7 | -47.9 | +9.5 | -47.9 | +40.7 | -18.3 |
| Hold SPY, no costs | $4,294 | +114.7 | -24.5 | +28.9 | -24.5 | +66.6 | -18.7 |
| Hold SPY, 0.1% on the one buy | $4,289 | +114.5 | -24.5 | +28.9 | -24.5 | +66.6 | -18.7 |

## Trades

A trade is one buy or one sell. In / out counts the times the trend check switched the asset in and out.

| Asset | Daily: trades | Daily: in / out | Weekly: trades | Weekly: in / out |
|---|--:|--:|--:|--:|
| BTC/USD | 79 | 40 / 39 | 33 | 17 / 16 |
| ETH/USD | 103 | 52 / 51 | 38 | 19 / 19 |
| SOL/USD | 78 | 39 / 39 | 36 | 18 / 18 |
| QQQ | 64 | 32 / 32 | 24 | 12 / 12 |
| VTI | 45 | 23 / 22 | 20 | 10 / 10 |
| Total | 369 | 186 / 183 | 151 | 76 / 75 |

Daily check: about 63 trades a year across the mix. Weekly: about 26.

## Limits

- Fills at the close the signal uses. The sim buys during the next cycle, at that moment's price.
- Sleeves don't rebalance; the sim caps rebuys at the PLAN dollars, so after big gains they differ.
- Cash earns 0%. Assets are today's survivors, which flatters the result.
- Gaps over 7 days in a price history are held in cash: SOL/USD 2023-07-06 to 2024-08-26.
- Halves are cut from one run, so the second half starts with whatever positions the first ended on.
