# Strategy test on SPY

2024-11-11 to 2026-11-10, 501 trading days. Returns are after an assumed 0.02% round-trip cost. Past results don't guarantee future ones.

A strategy is only worth paper testing if it makes money in both halves and beats simply holding.

| Strategy | Trades | Win % | Avg % per trade | Total % | Worst drop % | First half % | Second half % |
|---|---:|---:|---:|---:|---:|---:|---:|
| Hold overnight, close to next open | 500 | 57 | 0.024 | 11.4 | -16.5 | 2.7 | 8.5 |
| After 15 min, if up, buy and hold 20 min | 258 | 49 | -0.007 | -1.9 | -3.5 | -1.6 | -0.3 |
| After 15 min, if down, buy and hold 20 min | 243 | 46 | -0.018 | -4.4 | -4.8 | -0.8 | -3.6 |
| Hold open to close, daily | 501 | 50 | -0.009 | -6.0 | -12.9 | 1.1 | -7.1 |
| Buy the open, sell 20 min later | 501 | 47 | -0.014 | -6.7 | -8.1 | -4.6 | -2.1 |
| Opening range breakout, sell by close | 371 | 43 | -0.028 | -10.2 | -13.5 | -2.9 | -7.5 |
| Last 30 min, if up on the day | 268 | 33 | -0.040 | -10.3 | -11.3 | -3.8 | -6.8 |
| Buy at 9:30 AM Pacific, sell 20 min later | 501 | 41 | -0.024 | -11.5 | -11.5 | -5.1 | -6.8 |

**Simply holding SPY the whole time: +27.9%.** That's the number to beat.

## Live pick rules on past prices

These replay the month-long momentum pick and its -5%, +10% and time exits, using daily closes and leaving out the news check. A stop can really fill worse than its daily close. The stock list is today's large companies, which flatters the past, because it leaves out companies that fell away.

### Stocks, after an assumed 0.05% cost

- Trades: 479, one new pick a day, so holding periods overlap
- Win rate: 48%
- Average per trade after costs: +0.48%
- Average beat over SPY on the same days: +0.27%
- That beat in the first half: -0.39%, second half: +0.93%

### Crypto, after an assumed 0.5% cost

- Trades: 708, one new pick a day, so holding periods overlap
- Win rate: 34%
- Average per trade after costs: -0.95%
- Average beat over BTC on the same days: -0.72%
- That beat in the first half: -1.49%, second half: +0.06%

