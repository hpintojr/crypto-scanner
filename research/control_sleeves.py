"""Virtual control sleeves: what $2,000 would be worth in (a) holding SPY and (b) the SPY 200-day trend rule since the freeze.
Paper bookkeeping only. Places NO orders and touches neither PLAN nor sim.py. The scanner calls cycle() once a day after the close, so no separate scheduled job is needed.
Manual run: python3 -m research.control_sleeves
Writes data/control-sleeves.md. Reuses the rules and cost model from research/candidate_test.py.
"""
import os
from datetime import date, timedelta
from . import backtest, candidate_test as ct, core, stocks

PAPER_URL = stocks.PAPER_URL  # read only, for the market clock

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


def write_for(creds, end):
    """Fetch SPY through `end`, write data/control-sleeves.md, return the text and the last bar date."""
    first = FREEZE_START - timedelta(days=420)
    raw = backtest._daily_closes(creds, "/v2/stocks/bars", ["SPY"], first, end, feed="iex", adjustment="all")
    bars = sorted(raw.get("SPY", {}).items())
    if len(bars) < 250:
        raise RuntimeError("not enough SPY history")
    dates, closes = [d for d, _ in bars], [c for _, c in bars]
    text = report(sleeves(dates, closes), FREEZE_START.isoformat(), dates[-1])
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "control-sleeves.md"), "w") as f:
        f.write(text)
    return text, dates[-1]


def due_day(now_et, market_open, done_day):
    """The trading day to write, or None. Only after the close and only once per day, like the laggards note."""
    if market_open:
        return None
    day = now_et.date() if now_et.hour >= 17 else now_et.date() - timedelta(days=1)
    if day.weekday() >= 5 or day.isoformat() == done_day:
        return None
    return day


def cycle(state, errors, creds):
    """Called from the scanner's research steps. Research only: reads prices, writes one file, places no orders."""
    if not creds:
        return
    try:
        clock = stocks._get(PAPER_URL, "/v2/clock", creds)
        day = due_day(core.now().astimezone(stocks.ET), bool(clock.get("is_open")), state.get("control_sleeves_day"))
        if not day:
            return
        _, last = write_for(creds, day)
        if last != day.isoformat():
            return  # holiday or the close is not published yet; try again next cycle
        state["control_sleeves_day"] = last
        state["last_control_sleeves"] = f"{last}: written"
    except Exception as e:
        errors.append(f"control sleeves: {type(e).__name__}: {e}")


def main():
    text, _ = write_for(stocks.credentials(), date.today())
    print(text)


if __name__ == "__main__":
    main()
