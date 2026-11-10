"""Offline tests for research/candidate_test.py on made-up prices. No network, no orders.
Run from the repo root: python3 tests/test_candidates.py
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from research import candidate_test as ct  # noqa: E402


def make_dates(n, start=date(2016, 1, 4)):
    out, d = [], start
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def series(n, daily):
    v, out = 100.0, []
    for i in range(n):
        v *= 1 + daily(i)
        out.append(v)
    return out


N = 1200
DATES = make_dates(N)
START = DATES[300]


def hist_with(spy):
    h = {s: series(N, lambda i: 0.0002) for s in ct.UNIVERSE}
    h["SPY"] = spy
    return h


checks = 0


def check(cond, msg):
    global checks
    assert cond, msg
    checks += 1


# 1. Hold on a steady riser matches the price path after one day of delay, and costs only on entry.
up = hist_with(series(N, lambda i: 0.001))
curve, trades = ct.simulate(DATES, up, ct.hold_spy, 0.0, start=START)
exp = up["SPY"][-1] / up["SPY"][299]
check(abs(curve[-1][1] - exp) < 1e-9, "hold at 0 cost equals SPY path")
check(trades == 0, "entry happened before start, so no trade is counted")
c_cost, _ = ct.simulate(DATES, up, ct.hold_spy, 1.0, start=DATES[0])
c_free, _ = ct.simulate(DATES, up, ct.hold_spy, 0.0, start=DATES[0])
check(c_cost[-1][1] < c_free[-1][1], "cost lowers the result")

# 2. No look-ahead: changing the future must not change earlier weights.
a = hist_with(series(N, lambda i: 0.0005))
b = hist_with(series(N, lambda i: 0.0005 if i < 800 else -0.01))
for rule in (ct.spy_trend_200, ct.rotation_top2):
    pa = pb = None
    for t in range(1, 800):
        pa, pb = rule(a, t, DATES, pa), rule(b, t, DATES, pb)
        check(pa == pb, f"{rule.__name__} used future data at {t}")

# 3. A crash: trend rule leaves SPY after it falls and avoids most of the drop that hold takes.
crash = hist_with(series(N, lambda i: 0.0008 if i < 700 else (-0.01 if i < 800 else 0.0)))
h_curve, _ = ct.simulate(DATES, crash, ct.hold_spy, 0.05, start=START)
t_curve, t_trades = ct.simulate(DATES, crash, ct.spy_trend_200, 0.05, start=START)
check(ct.metrics(t_curve)["drop"] > ct.metrics(h_curve)["drop"], "trend has smaller worst drop in a crash")
check(t_trades >= 1, "trend rule traded")

# 4. Rotation holds only positive-score names, at most TOP of them, and goes to cash when all are down.
down = {s: series(N, lambda i: -0.001) for s in ct.UNIVERSE}
w = ct.rotation_top2(down, 600, DATES, None)
check(w == {}, "all falling means cash")
mixed = {s: series(N, lambda i: 0.0001) for s in ct.UNIVERSE}
mixed["GLD"] = series(N, lambda i: 0.002)
mixed["QQQ"] = series(N, lambda i: 0.001)
w = ct.rotation_top2(mixed, 600, DATES, None)
check(set(w) == {"GLD", "QQQ"} and abs(sum(w.values()) - 1) < 1e-9, "top 2 equal weight")

# 5. Monthly and weekly rules hold their decision within the period.
prev = ct.rotation_top2(mixed, 600, DATES, None)
same_month = [t for t in range(601, 700) if DATES[t][:7] == DATES[t - 1][:7]][0]
check(ct.rotation_top2(mixed, same_month, DATES, prev) is prev, "monthly rule keeps weights mid-month")

# 6. Metrics and the screen.
flat = [(d, 1.0) for d in DATES[:10]]
check(ct.metrics(flat)["total"] == 0 and ct.metrics(flat)["drop"] == 0, "flat curve metrics")
dd = [("2020-01-01", 1.0), ("2020-01-02", 2.0), ("2020-01-03", 1.0), ("2020-12-31", 1.5)]
check(abs(ct.metrics(dd)["drop"] + 50.0) < 1e-9, "drawdown is the drop from the peak")

# 7. Full report builds on made-up data and carries the honest limits.
res = ct.evaluate(DATES, crash)
text = ct.report(res, DATES)
check("## Limits" in text and "Screen against hold_spy" in text, "report has limits and screen")
check(set(ct.verdict(res)) == {"spy_trend_200", "rotation_top2"}, "screen covers both candidates")

# 8. Alignment keeps only shared dates.
al_d, al_h = ct.align({"A": [("2020-01-01", 1), ("2020-01-02", 2)], "B": [("2020-01-02", 5), ("2020-01-03", 6)]})
check(al_d == ["2020-01-02"] and al_h == {"A": [2], "B": [5]}, "align uses shared dates")

print(f"ALL PASSED {checks} checks")
