# Market research and paper simulation

Otto runs everything here on its own schedule. Otto is the only trading bot. Paper only, no real money.

## Each cycle (`scanner.py`)

- **Crypto:** logs top-100 movers over 3% in an hour, including those that fail the 2x volume check.
- **Stocks:** during market hours, logs moves of 2% or more in an hour across `research/stock_universe.txt`. Checks pre-market gaps of 3% or more from 8:00 to 9:30 AM ET.
- **Insider sales:** logs open-market sales of $1M or more to `research/form4-sales.csv`, with the 10b5-1 plan flag. Research only.
- **Form 4:** logs code P open-market buys from SEC EDGAR to `research/form4-log.csv`. Reviews against SPY at 30, 90 and 180 days.
- **POC touches:** logs when price returns to the previous session's point of control (the price with the most volume), for the stock list and BTC and ETH, with whether the level held or broke. Stock bars are IEX only. Scored in `data/poc.md`. Research only, no orders.
- **Simulation:** runs the $1,000 paper simulation in `research/sim.py`.
- **Hold test:** tracks a separate buy-and-hold of a private coin list at simulated cost, with no orders. The list and dollar values stay beside the repo on Otto, and `status.md` shows only a percentage.
- **Wallet watch:** logs moves by enabled wallets in `research/wallets.csv` to `data/wallet-moves.csv`. Reads native BTC, ETH and XRP, plus major Ethereum tokens by contract address (USDT, USDC, DAI, WETH, WBTC, RLUSD, AAVE, UNI, LDO, CRV, ARB). Log only, nothing trades on it. A wallet needs a full address, chain, attribution source and verification date before it can be enabled.

## Simulation rules

**Current rule: approved allocation.** Hamilton approved this on Nov 5, 2026. Commodities: long $700 (GLD $300, DBC $250, DBA $75, CPER $75), mid $300 ($75 each, in or out by the 100-day average, checked weekly). Crypto: long $600 (BTC $400, ETH $200), mid $400 ($200 each, same rule). No short-term slice until a rule passes. Older crypto positions keep their exits, and that cash joins the plan. The rules below apply only if `HOLD_MODE` is turned off. Research and the strategy tests keep running.

- Budget: $1,000 for crypto and $1,000 for stocks, kept separate. No limit on the number of trades. Cash can't go below zero, and there's no margin.
- Every signal can trade while there's cash: qualifying Form 4 buys and up movers on at least 2x volume. At most one buy per market per cycle, and nothing is bought twice in a day.
- Keeps buying until the cash is used: when there's no signal, the best remaining pick from the past month's returns against SPY or BTC plus news. Crypto runs 24/7. Stocks run in market hours, with these picks from 10:30 AM ET (7:30 AM PT).
- A buy with nothing filled after 15 minutes is canceled, and its cash returns. It isn't bought again that day.
- Crypto buys need neutral or better news tone. Stablecoins and gold-backed tokens are never bought.
- News comes from Alpaca's news feed and Google News. X.com is not included. Momentum picks must score above zero.
- Each trade is 10% of current value, $100 at the start, so gains are reinvested.
- Sell at -5%, +10%, or after 7 days.
- Cash only: no margin, shorting or options.
- Hamilton lifted the crypto pause on Nov 5.

## Where to look

| File | What it shows |
|---|---|
| `status.md` | Latest cycle, errors, measured time between runs |
| `data/sim.md` | Simulation value, comparison with SPY, checkpoints |
| `data/movers.md` | Hourly list of biggest gainers and losers over 1 to 24 hours, with streaks. No orders |
| `data/metrics.md` | Win rate, profit per trade, profit factor, open positions, and drawdown, with flags |
| `data/allocation-test.md` | Long, mid and short-term rules tested on commodity funds and crypto. No orders |
| `data/poc.md` | How previous-session POC touches played out, held vs broke, with and without a liquidity sweep. No orders |
| `data/backtest.md` | SPY strategies tested on past prices. No orders |
| `data/sim-next.md` | Hourly preview of what the rules would buy next. No orders |
| `data/sim-trades.csv` | Each closed trade with its thesis and argument against |
| `research/wallets.csv` | The wallet collection: who, chain, address, source, and date last confirmed |
| `data/wallet-moves.csv` | New moves by enabled wallets |
| `data/report.md` | Whether signals kept moving, plus the Form 4 review |

## Adding wallets

Add one row per address in `research/wallets.csv`, reusing the owner's name for extra addresses. Fill in the chain, full address, source link and date confirmed, then set `enabled` to yes. Recheck labels and old lists over time. Use free sources the owner published themselves, such as an exchange's own wallet list or an official filing. Don't scrape Arkham: its terms prohibit it, so new Arkham data only comes through its official API.

## Safety

- Create a file named `SIM_STOP` in the repo to stop new orders and automatic exits. Open positions stay open until it's removed.
- Orders can only go to Alpaca's paper endpoint, and the simulation refuses a non-paper account.
- Keys and contact details stay outside this repo, beside it on Otto. Never commit them.
- The simulation's cash and holdings must match Alpaca's charges and positions. Alpaca is the source of truth.
- Run one scheduler only. Don't run `run.sh` or cron alongside the Otto schedule.
- Test changes with `python3 tests/test_cycle.py`.
