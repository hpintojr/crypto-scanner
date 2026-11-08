# Scanner status

- Last run: 2026-11-08T22:58:01Z
- Host: otto-16usdmc576-067297
- Step seconds: simulation 3, crypto scan 16, buzz 0, watchlist 0, stocks 0, score crypto 0, score stocks 0, form 4 0, wallets 153, holdings 0, backtest 0, movers 0, allocation 0, poc 1, laggards 1
- Requests this cycle: api.coingecko.com 8, data.alpaca.markets 8, eth.blockscout.com 16, mempool.space 6, paper-api.alpaca.markets 4, s1.ripple.com 1
- Skipped for time: holdings, backtest, movers, allocation, laggards
- Last scan: 2026-11-08T22:55:26Z: 45 movers >3% 1h, 0 kept after 2x volume check
- Last flag: 2026-11-06T09:05:20Z CC
- Last stock scan: 2026-11-08T22:55:27Z: market closed
- Laggards watch: none yet
- Last POC log: 2026-11-08T22:55:27Z: 0 POC touches logged
- Last watchlist snapshot: 2026-11-08T22:00:16Z
- Last pre-market gap check: 2026-11-06T14:25:16Z: 7 of 100 stocks gapped 3%+ pre-market
- Last Form 4 run: 2026-11-08T18:20:17Z: paused until 2026-11-08T18:25:10Z after SEC said HTTP 403
- $2,000 paper simulation: value $1,903.60 of $2,000, 5 open, crypto cash $341.39, stock cash $367.07
- Simulation flags: none
- Graduation checklist: 1 of 5 conditions met (data/sim.md)
- Strategy test: 2026-11-08: 499 trading days tested, see data/backtest.md
- Hold test: -15.84% since 2026-11-05, BTC -7.76%
- Wallet watch: 13 checked this cycle, 63 enabled in rotation, 3 new moves
- Measured time between runs: 6 min
- Next run: ~2026-11-08T23:04:01Z
- Inbox: no pending requests
- Errors this cycle: 5
  - fetch failed https://api.coingecko.com/api/v3/coins/ether-fi/market_chart: HTTP Error 429: Too Many Requests
  - fetch failed https://api.coingecko.com/api/v3/coins/markets: HTTP Error 429: Too Many Requests
  - fetch failed https://api.coingecko.com/api/v3/simple/price: HTTP Error 429: Too Many Requests
  - wallet Change Invest: TimeoutError: The read operation timed out
  - wallet Binance: HTTPError: HTTP Error 500: Internal Server Error

Paper only, approved by Hamilton. No real money. No keys in this repo. Create SIM_STOP to stop new orders.
