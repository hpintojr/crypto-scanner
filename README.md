# Market research and paper simulation

Otto runs everything here on its own schedule. Otto is the only trading bot. Paper only, no real money.

## Each cycle (`scanner.py`)

- **Crypto:** logs top-100 movers over 3% in an hour, including those that fail the 2x volume check.
- **Stocks:** during market hours, logs moves of 2% or more in an hour across `research/stock_universe.txt`. Checks pre-market gaps of 3% or more from 8:00 to 9:30 AM ET.
- **Form 4:** logs code P open-market buys from SEC EDGAR to `research/form4-log.csv`. Reviews against SPY at 30, 90 and 180 days.
- **Simulation:** runs the $1,000 paper simulation in `research/sim.py`.

## Simulation rules

- One stock buy a trading day at 10:30 AM ET (7:30 AM PT): a qualifying Form 4 buy first, then the strongest up mover on at least 2x volume, then the best score from the past month's returns against SPY plus news.
- One crypto buy a day, any time: a coin that passed today's mover check first, then the best score from the past month's returns against BTC plus news. Both markets share the $1,000.
- News comes from Alpaca's news feed and Google News. X.com is not included. No buy if nothing scores above zero.
- Each trade is 10% of current value, $100 at the start, so gains are reinvested.
- Sell at -5%, +10%, or after 7 days.
- Cash only: no margin, shorting or options.
- Hamilton lifted the crypto pause on Nov 5.

## Where to look

| File | What it shows |
|---|---|
| `status.md` | Latest cycle, errors, measured time between runs |
| `data/sim.md` | Simulation value, comparison with SPY, checkpoints |
| `data/sim-trades.csv` | Each closed trade with its thesis and argument against |
| `data/report.md` | Whether signals kept moving, plus the Form 4 review |

## Safety

- Create a file named `SIM_STOP` in the repo to stop new orders and automatic exits. Open positions stay open until it's removed.
- Orders can only go to Alpaca's paper endpoint, and the simulation refuses a non-paper account.
- Keys and contact details stay outside this repo, beside it on Otto. Never commit them.
- Run one scheduler only. Don't run `run.sh` or cron alongside the Otto schedule.
- Test changes with `python3 tests/test_cycle.py`.
