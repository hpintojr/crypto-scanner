# Strategy test on SPY

2024-11-08 to 2026-11-06, 500 trading days. Returns are after an assumed 0.02% round-trip cost. Past results don't guarantee future ones.

A strategy is only worth paper testing if it makes money in both halves and beats simply holding.

| Strategy | Trades | Win % | Avg % per trade | Total % | Worst drop % | First half % | Second half % |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hold overnight, close to next open | 499 | 57 | 0.024 | 11.4 | -16.5 | 2.2 | 9.0 |
| After 15 min, if up, buy and hold 20 min | 257 | 49 | -0.009 | -2.4 | -3.5 | -2.1 | -0.4 |
| After 15 min, if down, buy and hold 20 min | 243 | 46 | -0.018 | -4.4 | -4.8 | -0.8 | -3.6 |
| Buy the open, sell 20 min later | 500 | 47 | -0.015 | -7.3 | -8.1 | -4.7 | -2.7 |
| Hold open to close, daily | 500 | 50 | -0.011 | -7.3 | -12.9 | 0.9 | -8.1 |
| Last 30 min, if up on the day | 267 | 33 | -0.039 | -10.1 | -11.0 | -3.7 | -6.6 |
| Opening range breakout, sell by close | 370 | 43 | -0.028 | -10.2 | -13.5 | -2.5 | -7.9 |
| Buy at 9:30 AM Pacific, sell 20 min later | 500 | 41 | -0.024 | -11.3 | -11.3 | -5.2 | -6.4 |

**Simply holding SPY the whole time: +26.2%.** That's the number to beat.

## Live pick rules on past prices

These replay the month-long momentum pick and its -5%, +10% and time exits, using daily closes and leaving out the news check. A stop can really fill worse than its daily close. The stock list is today's large companies, which flatters the past, because it leaves out companies that fell away.

### Stocks, after an assumed 0.05% cost

- Trades: 481, one new pick a day, so holding periods overlap
- Win rate: 48%
- Average per trade after costs: +0.49%
- Average beat over SPY on the same days: +0.31%
- That beat in the first half: -0.39%, second half: +1.00%

### Crypto, after an assumed 0.5% cost

- Trades: 708, one new pick a day, so holding periods overlap
- Win rate: 34%
- Average per trade after costs: -0.91%
- Average beat over BTC on the same days: -0.69%
- That beat in the first half: -1.34%, second half: -0.05%

