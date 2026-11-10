"""Virtual control sleeves: what $2,000 would be worth in (a) holding SPY and (b) the SPY 200-day trend rule since the freeze.
Paper bookkeeping only. Places NO orders and touches neither PLAN nor sim.py. Run daily: python3 -m research.control_sleeves
Writes data/control-sleeves.md. Reuses the rules and cost model from research/candidate_test.py.
"""
import os
from datetime import date, timedelta
from . import backtest, candidate_test as ct, core, stocks

FREEZE_START = date(2026, 11, 7)
CASH = 2000.0
COST_PCT = ct.COST_PCT


def sleeves(dates, closes, start=FREEZE_START.isoformat()):
    """{name: (final dollars, percent, rebalances)} from the last close on or before `start`."""
    base = max(i for i, d in enumerate(dates) if d <= start)
    hist = {"SPY": closes}
    out = {}
    for name, rule in (("hold_spy", ct.hold_spy), ("spy_trend_200", ct.spy_trend_200)):
        if base + 1 >= len(dates):
            out[name] = (CASH, 0.0, 0)  # no bar after the freeze yet
            continue
        curve, trades = ct.simulate(dates, hist, rule, COST_PCT, start=dates[base + 1])  # value is 1.0 at the freeze close
        value = curve[-1][1] if curve else 1.0
        out[name] = (CASH * value, (value - 1) * 100, trades)
    return out


def report(res, first, last):
    h, t = res["hold_spy"], res["spy_trend_200"]
    return "\n".join([
        "# Control sleeves (virtual, no orders)", "",
        f"From the freeze ({first}) to {last}. Starting $2,000 each. Cost {COST_PCT}% per trade, one-day signal delay. "
        "These are paper bookkeeping only and are not the frozen plan.", "",
        "| Sleeve | Value $ | Since freeze % | Rebalances |", "|---|--:|--:|--:|",
        f"| hold_spy | {h[0]:,.2f} | {h[1]:+.2f} | {h[2]} |",
        f"| spy_trend_200 | {t[0]:,.2f} | {t[1]:+.2f} | {t[2]} |", "",
        "Compare the frozen plan with hold_spy on the graduation checklist. A few weeks says nothing about an edge.", ""])


def main():
    creds = stocks.credentials()
    first = FREEZE_START - timedelta(days=420)
    raw = backtest._daily_closes(creds, "/v2/stocks/bars", ["SPY"], first, date.today(), feed="iex", adjustment="all")
    bars = sorted(raw.get("SPY", {}).items())
    if len(bars) < 250:
        raise SystemExit("not enough SPY history")
    dates, closes = [d for d, _ in bars], [c for _, c in bars]
    text = report(sleeves(dates, closes), FREEZE_START.isoformat(), dates[-1])
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "control-sleeves.md"), "w") as f:
        f.write(text)
    print(text)


if __name__ == "__main__":
    main()
