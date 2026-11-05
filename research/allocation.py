"""Tests long, mid and short-term rules on commodity funds and crypto. Places no orders.

Alpaca has no futures, so commodities are tested through funds. Writes data/allocation-test.md.
Rules only use information from the close before each trade. Fund and coin lists are today's survivors.
"""
import os
from datetime import timedelta
from . import backtest, core, stocks

VERSION = 2
PLAN_WEIGHTS = {"Commodities": {"GLD": (.30, .075), "DBC": (.25, .075), "DBA": (.075, .075), "CPER": (.075, .075)},
                "Crypto": {"BTC/USD": (.40, .20), "ETH/USD": (.20, .20)}}  # (long share, mid share) of each $1,000
YEARS = 6
FUNDS = ["GLD", "SLV", "USO", "UNG", "CPER", "DBA", "DBC"]
COINS = ["BTC/USD", "ETH/USD"]
FUND_COST, COIN_COST = 0.05, 0.50  # assumed cost per round trip, in percent


def _avg(v):
    return sum(v) / len(v)


def long_hold(c):
    """Always in."""
    return [1] * len(c)


def trend(c, days=100, every=5):
    """Mid-term: in when the close is above its average, rechecked weekly."""
    out, pos = [], 0
    for i in range(len(c)):
        if i >= days and i % every == 0:
            pos = 1 if c[i] > _avg(c[i - days + 1:i + 1]) else 0
        out.append(pos)
    return out


def pullback(c, days=200, dip=-3.0, hold=5):
    """Short-term: after a 3-day drop in an uptrend, in for a week."""
    out, left = [], 0
    for i in range(len(c)):
        if left:
            left -= 1
        elif i >= days and c[i] > _avg(c[i - days + 1:i + 1]) and (c[i] / c[i - 3] - 1) * 100 <= dip:
            left = hold
        out.append(1 if left else 0)
    return out


def returns(c, positions, cost):
    """Daily percent returns: a position set at one close earns the next day's move. Half the cost per side."""
    out, prev = [], 0
    for i in range(len(c) - 1):
        pos = positions[i]
        r = (c[i + 1] / c[i] - 1) * 100 * pos
        if pos != prev:
            r -= cost / 2
        out.append(r)
        prev = pos
    return out


def summary(daily):
    g, peak, worst = 1.0, 1.0, 0.0
    half = len(daily) // 2
    first = second = 1.0
    for i, r in enumerate(daily):
        g *= 1 + r / 100
        peak = max(peak, g)
        worst = min(worst, g / peak - 1)
        if i < half:
            first *= 1 + r / 100
        else:
            second *= 1 + r / 100
    return {"total": (g - 1) * 100, "drop": worst * 100, "first": (first - 1) * 100, "second": (second - 1) * 100,
            "in_market": 0}


def basket(closes, symbols, rule, cost):
    """Equal money across symbols with enough history, rebalanced daily, with each one's own rule."""
    series = {s: sorted(closes[s]) for s in symbols if s in closes and len(closes[s]) > 250}
    if not series:
        return None
    all_dates = sorted({d for v in series.values() for d in v})
    rets = {}
    for s, dates in series.items():
        c = [closes[s][d] for d in dates]
        for d, r in zip(dates[1:], returns(c, rule(c), cost)):
            rets.setdefault(d, []).append(r)
    return summary([_avg(rets[d]) for d in all_dates if d in rets]), all_dates[0], all_dates[-1]


def plan_mix(closes, weights, cost):
    """The approved allocation as one portfolio, rebalanced daily, over the dates all its assets share."""
    shared = sorted(set.intersection(*[set(closes[s]) for s in weights]))
    if len(shared) < 250:
        return None
    daily = [0.0] * (len(shared) - 1)
    for sym, (long_w, mid_w) in weights.items():
        c = [closes[sym][d] for d in shared]
        for rule, w in ((long_hold, long_w), (trend, mid_w)):
            for i, r in enumerate(returns(c, rule(c), cost)):
                daily[i] += w * r
    return summary(daily), shared[0], shared[-1]


def _plan_row(closes, weights, cost):
    res = plan_mix(closes, weights, cost)
    if not res:
        return []
    s, a, b = res
    return ["| Rule | Total % | Worst drop % | First half % | Second half % |", "|---|---:|---:|---:|---:|",
            f"| Approved mix | {s['total']:.1f} | {s['drop']:.1f} | {s['first']:.1f} | {s['second']:.1f} |", "", f"Period: {a} to {b}.", ""]


def _lines(title, closes, symbols, cost):
    rows = [("Long: hold", long_hold), ("Mid: 100-day trend", trend), ("Short: buy dips in an uptrend", pullback)]
    out = [f"## {title}", "", "| Rule | Total % | Worst drop % | First half % | Second half % |", "|---|---:|---:|---:|---:|"]
    period = ""
    for name, rule in rows:
        res = basket(closes, symbols, rule, cost)
        if not res:
            continue
        s, a, b = res
        period = f"{a} to {b}"
        out.append(f"| {name} | {s['total']:.1f} | {s['drop']:.1f} | {s['first']:.1f} | {s['second']:.1f} |")
    for sym in symbols:
        res = basket(closes, [sym], long_hold, cost)
        if res:
            s = res[0]
            out.append(f"| {sym} held alone | {s['total']:.1f} | {s['drop']:.1f} | {s['first']:.1f} | {s['second']:.1f} |")
    return out + ["", f"Period: {period}, after an assumed {cost}% round-trip cost. Past results don't guarantee future ones.", ""]


def cycle(state, errors, creds):
    if not creds or state.get("allocation_version") == VERSION:
        return
    try:
        end = core.now().astimezone(stocks.ET).date() - timedelta(days=1)
        start = end - timedelta(days=365 * YEARS)
        f = backtest._daily_closes(creds, "/v2/stocks/bars", FUNDS, start, end, feed="iex", adjustment="all")
        c = backtest._daily_closes(creds, "/v1beta3/crypto/us/bars", COINS, start, end)
        lines = ["# Commodities and crypto test", "", "A rule is worth paper trading only if it makes money in both halves and has a better "
                 "return for its risk than holding. No orders come from this file.", ""]
        lines += _lines("Commodity funds", f, FUNDS, FUND_COST) + _lines("Crypto", c, COINS, COIN_COST)
        lines += ["## The approved allocation", "", "Commodities"] + _plan_row(f, PLAN_WEIGHTS["Commodities"], FUND_COST)
        lines += ["Crypto"] + _plan_row(c, PLAN_WEIGHTS["Crypto"], COIN_COST)
        with open(os.path.join(core.DATA, "allocation-test.md"), "w") as out:
            out.write("\n".join(lines) + "\n")
        state["allocation_version"] = VERSION
    except Exception as e:
        errors.append(f"allocation test: {type(e).__name__}: {e}")
