# Strategy test on SPY

2024-11-05 to 2026-11-04, 501 trading days. Returns are after an assumed 0.02% round-trip cost. Past results don't guarantee future ones.

A strategy is only worth paper testing if it makes money in both halves and beats simply holding.

| Strategy | Trades | Win % | Avg % per trade | Total % | Worst drop % | First half % | Second half % |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hold overnight, close to next open | 500 | 57 | 0.029 | 14.3 | -16.5 | 5.4 | 8.4 |
| Hold open to close, daily | 501 | 51 | 0.001 | -1.5 | -11.2 | 2.8 | -4.2 |
| After 15 min, if up, buy and hold 20 min | 258 | 49 | -0.008 | -2.0 | -3.5 | -2.0 | 0.1 |
| After 15 min, if down, buy and hold 20 min | 243 | 46 | -0.016 | -4.0 | -5.0 | -1.0 | -3.0 |
| Buy the open, sell 20 min later | 501 | 47 | -0.014 | -6.9 | -7.9 | -4.4 | -2.6 |
| Opening range breakout, sell by close | 373 | 44 | -0.025 | -9.4 | -13.5 | -1.9 | -7.6 |
| Last 30 min, if up on the day | 269 | 33 | -0.038 | -9.7 | -10.7 | -3.3 | -6.6 |
| Buy at 9:30 AM Pacific, sell 20 min later | 501 | 42 | -0.022 | -10.6 | -10.8 | -5.0 | -5.9 |

Daily strategies only hold SPY part of the time, so compare them with "Hold open to close" plus "Hold overnight", which together are about the same as holding SPY all the time.
