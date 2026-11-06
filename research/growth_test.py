"""Backtest of the growth mix in research/sim.py PLAN. Places no orders. Writes data/growth-mix-test.md.

Run from the repo root: python3 -m research.growth_test
Not part of scanner.py's cycle.

Model, kept close to the sim:
- Each asset is its own sleeve with its PLAN dollars, on its own calendar (crypto 7 days a week, funds on trading days).
- A sleeve is in the asset when the previous close is above the average of the last 100 closes, else in cash at 0%.
- Daily check: decided every bar. Weekly check: decided on the first bar of each ISO week, held until the next.
- A trade is one buy or one sell. Each costs COST_PCT of the sleeve's value.
- Sleeves don't rebalance against each other, so gains stay in the asset that made them. The live sim caps rebuys
  at the PLAN dollars, so after big gains the two differ.
- Halves are judged on the portfolio value at the date that splits the period, not rerun from scratch.
- A hole in a price history longer than MAX_GAP_DAYS (Alpaca has no SOL from 2023-07-06 to 2024-08-26) sends that
  sleeve to cash across it, and its trend check waits for 100 fresh closes after it.
Coin and fund lists are today's survivors, and fills are at the close, so results flatter the rule.
"""
import os
from datetime import date, timedelta
from . import backtest, core, sim, stocks

START, END = date(2021, 1, 1), date.today() - timedelta(days=1)
WARMUP_DAYS = 220  # calendar days fetched before START so the 100-close average exists on day one
COST_PCT = 0.1
MAX_GAP_DAYS = 7
PLAN = {sym: amt for slices in sim.PLAN.values() for targets in slices.values() for sym, amt in targets.items()}
TOTAL = sum(PLAN.values())


def _closes(creds):
    first = START - timedelta(days=WARMUP_DAYS)
    funds = sorted(s for s in PLAN if "/" not in s) + [stocks.BENCH]
    coins = sorted(s for s in PLAN if "/" in s)
    out = backtest._daily_closes(creds, "/v2/stocks/bars", funds, first, END, feed="iex", adjustment="all")
    out.update(backtest._daily_closes(creds, "/v1beta3/crypto/us/bars", coins, first, END))
    return {sym: sorted(by_day.items()) for sym, by_day in out.items()}


def _sleeve(bars, dollars, weekly, cost):
    """{date: value} from START, plus trade count and how many times it switched in and out."""
    days = sim.TREND_DAYS
    value, inside, trades, ins, outs, out, week, fresh = dollars, False, 0, 0, 0, {}, None, 0
    for i in range(1, len(bars)):
        d, close = bars[i]
        prev = bars[i - 1][1]
        if (date.fromisoformat(d) - date.fromisoformat(bars[i - 1][0])).days > MAX_GAP_DAYS:
            fresh = i  # no prices across the hole: out at its start, and the average starts over
            if inside and d >= START.isoformat():
                value *= 1 - cost / 100
                trades, outs, inside = trades + 1, outs + 1, False
            elif inside:
                inside = False
        if d < START.isoformat():
            continue
        if i - fresh >= days:
            avg = sum(c for _, c in bars[i - days:i]) / days
            wk = date.fromisoformat(d).isocalendar()[:2]
            if not weekly or wk != week:
                week = wk
                want = prev > avg
                if want != inside:
                    value *= 1 - cost / 100
                    trades += 1
                    ins, outs = ins + want, outs + (not want)
                    inside = want
        if inside:
            value *= close / prev
        out[d] = value
    return out, trades, ins, outs


def _portfolio(sleeves):
    """Summed value on every date any sleeve has, carrying each sleeve's last value forward."""
    dates = sorted(set().union(*sleeves))
    last, out = [None] * len(sleeves), []
    for d in dates:
        for k, s in enumerate(sleeves):
            if d in s:
                last[k] = s[d]
        if all(v is not None for v in last):
            out.append((d, sum(last)))
    return out


def _stats(series):
    start = series[0][1]
    peak, worst = start, 0.0
    for _, v in series:
        peak = max(peak, v)
        worst = min(worst, v / peak - 1)
    return (series[-1][1] / start - 1) * 100, worst * 100


def _split(series):
    mid = len(series) // 2
    return series[:mid + 1], series[mid:]


def run(closes, weekly, cost):
    sleeves, trades, ins, outs = [], {}, {}, {}
    for sym, dollars in PLAN.items():
        s, trades[sym], ins[sym], outs[sym] = _sleeve(closes[sym], dollars, weekly, cost)
        sleeves.append(s)
    return _portfolio(sleeves), trades, ins, outs


def spy(closes, cost):
    bars = [(d, c) for d, c in closes[stocks.BENCH] if d >= START.isoformat()]
    v0 = TOTAL * (1 - cost / 100)
    return [(d, v0 * c / bars[0][1]) for d, c in bars]


def _row(name, series, start_value):
    total, drop = _stats(series)
    a, b = _split(series)
    ta, da = _stats(a)
    tb, db = _stats(b)
    became = series[-1][1] * TOTAL / start_value
    return f"| {name} | ${became:,.0f} | {(became / TOTAL - 1) * 100:+.1f} | {drop:.1f} | {ta:+.1f} | {da:.1f} | {tb:+.1f} | {db:.1f} |"


def main():
    closes = _closes(stocks.credentials())
    missing = [s for s in list(PLAN) + [stocks.BENCH] if not closes.get(s)]
    if missing:
        raise SystemExit(f"no price data for {missing}")
    runs = {(w, c): run(closes, w, c) for w in (False, True) for c in (0.0, COST_PCT)}
    daily = runs[(False, 0.0)][0]
    first, last = daily[0][0], daily[-1][0]
    mid = _split(daily)[1][0][0]
    lines = ["# Growth mix test", "",
             "Backtest of the growth mix in research/sim.py PLAN, from research/growth_test.py. Places no orders. "
             "Past results don't guarantee future ones.", "",
             "Mix: " + ", ".join(f"{s} ${a:,.0f}" for s, a in PLAN.items()) + f" (${TOTAL:,.0f}). "
             f"Each asset is held only while its previous close is above its {sim.TREND_DAYS}-close average, otherwise cash at 0%.", "",
             f"Period: {first} to {last}. First half {first} to {mid}, second half {mid} to {last}. "
             f"Cost: {COST_PCT}% of the sleeve per buy or sell. Total % counts costs from $2,000; half and drop columns are from each part's start.", "",
             "| Test | $2,000 became | Total % | Worst drop % | 1st half % | 1st half worst drop % | 2nd half % | 2nd half worst drop % |",
             "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for w in (False, True):
        for c in (0.0, COST_PCT):
            name = f"{'Weekly' if w else 'Daily'} check, {f'{c}% per trade' if c else 'no costs'}"
            lines.append(_row(name, runs[(w, c)][0], TOTAL))
    for c in (0.0, COST_PCT):
        lines.append(_row(f"Hold SPY, {f'{c}% on the one buy' if c else 'no costs'}", spy(closes, c), TOTAL))
    lines += ["", "## Trades", "",
              "A trade is one buy or one sell. In / out counts the times the trend check switched the asset in and out.", "",
              "| Asset | Daily: trades | Daily: in / out | Weekly: trades | Weekly: in / out |", "|---|--:|--:|--:|--:|"]
    _, dt, di, do = runs[(False, COST_PCT)]
    _, wt, wi, wo = runs[(True, COST_PCT)]
    for s in PLAN:
        lines.append(f"| {s} | {dt[s]} | {di[s]} / {do[s]} | {wt[s]} | {wi[s]} / {wo[s]} |")
    lines.append(f"| Total | {sum(dt.values())} | {sum(di.values())} / {sum(do.values())} | "
                 f"{sum(wt.values())} | {sum(wi.values())} / {sum(wo.values())} |")
    gaps = [f"{s} {closes[s][i - 1][0]} to {closes[s][i][0]}" for s in PLAN for i in range(1, len(closes[s]))
            if closes[s][i][0] >= START.isoformat()
            and (date.fromisoformat(closes[s][i][0]) - date.fromisoformat(closes[s][i - 1][0])).days > MAX_GAP_DAYS]
    yrs = (date.fromisoformat(last) - date.fromisoformat(first)).days / 365.25
    lines += ["", f"Daily check: about {sum(dt.values()) / yrs:.0f} trades a year across the mix. "
              f"Weekly: about {sum(wt.values()) / yrs:.0f}.", "",
              "## Limits", "",
              "- Fills at the close the signal uses. The sim buys during the next cycle, at that moment's price.",
              "- Sleeves don't rebalance; the sim caps rebuys at the PLAN dollars, so after big gains they differ.",
              "- Cash earns 0%. Assets are today's survivors, which flatters the result.",
              f"- Gaps over {MAX_GAP_DAYS} days in a price history are held in cash: " + (", ".join(gaps) or "none") + ".",
              "- Halves are cut from one run, so the second half starts with whatever positions the first ended on.", ""]
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "growth-mix-test.md"), "w") as f:
        f.write("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
