"""Backtest of candidate ETF rules against holding SPY. Places no orders. Writes data/candidate-test.md.

Run from the repo root: python3 -m research.candidate_test
Not part of scanner.py's cycle, and it never changes PLAN or the frozen plan.

Candidates (stocks and ETFs only, daily closes):
- hold_spy: the benchmark every candidate has to beat.
- spy_trend_200: in SPY while the close is above its 200-close average (checked on the first bar of each week), else cash.
- rotation_top2: monthly, rank SPY, QQQ, IWM, EFA, TLT, GLD, DBC by return from 12 months ago to 1 month ago.
  Hold the top 2 that are above zero, equal weight, the rest in cash.

Model:
- A weight is decided from closes up to day t and traded at the close of day t + LAG (default 1 extra day), so a signal never
  trades on the bar that created it. Earnings are close to close.
- Cost is COST_PCT of the traded amount (sum of weight changes) at each rebalance. Cash earns 0%.
- Halves are cut at the middle date of the one run, so they are not re-optimized. Nothing here is tuned on the test period:
  the lookbacks (200, 12-1 months, top 2) are fixed in advance, and rules are not to be changed after seeing results.
- The ETF list is today's survivors, and the free IEX feed is one exchange, so results still flatter reality.
Judge a candidate only if it beats hold_spy after costs, in both halves, with a smaller worst drop, and the result holds
at 2x and 5x the cost. One backtest is a screen, not proof.
"""
import math
import os
from datetime import date, timedelta
from . import backtest, core, stocks

START, END = date(2017, 1, 1), date.today() - timedelta(days=1)
WARMUP_DAYS = 420
COST_PCT = 0.05
COST_STEPS = (0.0, COST_PCT, COST_PCT * 2, COST_PCT * 5)
LAG = 1
UNIVERSE = ["SPY", "QQQ", "IWM", "EFA", "TLT", "GLD", "DBC"]
TREND_DAYS = 200
LOOKBACK, SKIP, TOP = 252, 21, 2


def hold_spy(hist, t, dates, prev):
    return {"SPY": 1.0}


def spy_trend_200(hist, t, dates, prev):
    wk = date.fromisoformat(dates[t]).isocalendar()[:2]
    if prev is not None and date.fromisoformat(dates[t - 1]).isocalendar()[:2] == wk:
        return prev  # decided once a week, on the first bar of the week
    if t < TREND_DAYS:
        return {}
    c = hist["SPY"]
    return {"SPY": 1.0} if c[t] > sum(c[t - TREND_DAYS + 1:t + 1]) / TREND_DAYS else {}


def rotation_top2(hist, t, dates, prev):
    mon = date.fromisoformat(dates[t]).month
    if prev is not None and date.fromisoformat(dates[t - 1]).month == mon:
        return prev  # decided once a month, on the first bar of the month
    if t < LOOKBACK:
        return {}
    scores = {s: hist[s][t - SKIP] / hist[s][t - LOOKBACK] - 1 for s in hist}
    picks = [s for s, v in sorted(scores.items(), key=lambda kv: -kv[1])[:TOP] if v > 0]
    return {s: 1.0 / TOP for s in picks}


RULES = {"hold_spy": hold_spy, "spy_trend_200": spy_trend_200, "rotation_top2": rotation_top2}


def align(closes):
    """Dates where every symbol has a close, and {sym: [close]} on those dates."""
    by = {s: dict(bars) for s, bars in closes.items()}
    dates = sorted(set.intersection(*(set(d) for d in by.values())))
    return dates, {s: [by[s][d] for d in dates] for s in by}


def simulate(dates, hist, rule, cost_pct, start=None, lag=LAG):
    """[(date, value)] from `start`, value starting at 1.0, plus the number of rebalances."""
    start = start or START.isoformat()
    weights, cur, value, out, trades, prev = {}, {}, 1.0, [], 0, None
    for t in range(1, len(dates)):
        decided = rule(hist, t, dates, prev)  # uses closes up to t only
        prev = decided
        weights[t] = decided
        use = weights.get(t - 1 - lag, {})  # trades at close t - 1 on a signal from t - 1 - lag
        if use != cur:
            turnover = sum(abs(use.get(s, 0) - cur.get(s, 0)) for s in set(use) | set(cur))
            if dates[t - 1] >= start:
                value *= 1 - turnover * cost_pct / 100
                trades += 1
            cur = use
        if dates[t] < start:
            continue
        value *= 1 + sum(w * (hist[s][t] / hist[s][t - 1] - 1) for s, w in cur.items())
        out.append((dates[t], value))
    return out, trades


def metrics(curve):
    vals = [v for _, v in curve]
    peak, dd = 0.0, 0.0
    for v in vals:
        peak = max(peak, v)
        dd = min(dd, v / peak - 1)
    rets = [b / a - 1 for a, b in zip(vals, vals[1:])]
    mean = sum(rets) / len(rets) if rets else 0
    sd = math.sqrt(sum((r - mean) ** 2 for r in rets) / len(rets)) if rets else 0
    years = max((date.fromisoformat(curve[-1][0]) - date.fromisoformat(curve[0][0])).days / 365.25, 1e-9)
    return {"total": (vals[-1] - 1) * 100, "cagr": (vals[-1] ** (1 / years) - 1) * 100, "drop": dd * 100,
            "sharpe": mean / sd * math.sqrt(252) if sd else 0.0}


def halves(curve):
    mid = len(curve) // 2
    return curve[:mid], curve[mid:]


def part_return(part):
    return (part[-1][1] / part[0][1] - 1) * 100 if len(part) > 1 else 0.0


def evaluate(dates, hist):
    """{rule: {cost: (curve, trades)}}"""
    return {name: {c: simulate(dates, hist, rule, c) for c in COST_STEPS} for name, rule in RULES.items()}


def verdict(res):
    """Plain screen for each candidate against hold_spy at the base cost. Not proof of anything."""
    base = res["hold_spy"][COST_PCT][0]
    bm = metrics(base)
    b1, b2 = (part_return(p) for p in halves(base))
    out = {}
    for name in RULES:
        if name == "hold_spy":
            continue
        curve = res[name][COST_PCT][0]
        m = metrics(curve)
        h1, h2 = (part_return(p) for p in halves(curve))
        stress = res[name][COST_PCT * 5][0]
        checks = {"beats SPY after costs": m["total"] > bm["total"],
                  "beats SPY in both halves": h1 > b1 and h2 > b2,
                  "smaller worst drop than SPY": m["drop"] > bm["drop"],
                  "still beats SPY at 5x cost": metrics(stress)["total"] > bm["total"]}
        out[name] = checks
    return out


def report(res, dates):
    base = {n: res[n][COST_PCT][0] for n in RULES}
    first, last = base["hold_spy"][0][0], base["hold_spy"][-1][0]
    lines = ["# Candidate test", "",
             "Backtest of candidate ETF rules against holding SPY, from research/candidate_test.py. Places no orders and does not "
             "touch the frozen plan. Past results don't guarantee future ones.", "",
             f"Period: {first} to {last}. Cost {COST_PCT}% of the traded amount, one extra day of delay between signal and trade. "
             "Halves are cut at the middle of the run. ETF list is today's survivors on the IEX feed.", "",
             "| Rule | Total % | Per year % | Worst drop % | Sharpe | 1st half % | 2nd half % | Rebalances |",
             "|---|--:|--:|--:|--:|--:|--:|--:|"]
    for name in RULES:
        m = metrics(base[name])
        h1, h2 = (part_return(p) for p in halves(base[name]))
        lines.append(f"| {name} | {m['total']:.1f} | {m['cagr']:.1f} | {m['drop']:.1f} | {m['sharpe']:.2f} | "
                     f"{h1:.1f} | {h2:.1f} | {res[name][COST_PCT][1]} |")
    lines += ["", "## Cost stress (total %)", "", "| Rule | " + " | ".join(f"{c:g}%" for c in COST_STEPS) + " |",
              "|---|" + "--:|" * len(COST_STEPS)]
    for name in RULES:
        lines.append(f"| {name} | " + " | ".join(f"{metrics(res[name][c][0])['total']:.1f}" for c in COST_STEPS) + " |")
    lines += ["", "## Screen against hold_spy", "", "A candidate is only worth paper testing if every line is yes.", ""]
    for name, checks in verdict(res).items():
        lines.append(f"**{name}**: " + "; ".join(f"{k}: {'yes' if v else 'no'}" for k, v in checks.items()))
        lines.append("")
    lines += ["## Limits", "",
              "- One backtest is a screen, not proof. A few years can be luck, and the 2017 start has one long bull market in it.",
              "- Survivor ETFs, IEX-only prices, close fills and 0% on cash all flatter the result.",
              "- Rules and lookbacks were fixed before the run. Changing them after seeing this table is how a rule gets overfit.",
              "- No candidate trades. Promotion to paper needs Hamilton's written approval and restarts nothing in the frozen plan."]
    return "\n".join(lines) + "\n"


def main():
    first = START - timedelta(days=WARMUP_DAYS)
    raw = backtest._daily_closes(stocks.credentials(), "/v2/stocks/bars", UNIVERSE, first, END, feed="iex", adjustment="all")
    missing = [s for s in UNIVERSE if not raw.get(s)]
    if missing:
        raise SystemExit(f"no price data for {missing}")
    dates, hist = align({s: sorted(by_day.items()) for s, by_day in raw.items()})
    res = evaluate(dates, hist)
    os.makedirs(core.DATA, exist_ok=True)
    text = report(res, dates)
    with open(os.path.join(core.DATA, "candidate-test.md"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
