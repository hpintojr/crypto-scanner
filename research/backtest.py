"""Tests simple strategies against past prices. Places no orders and changes no rules.

Results go to data/backtest.md, once a trading day after the close. Assumed costs are one number, so
they're easy to question. Testing many ideas makes some look good by luck, so a strategy should hold
up in both halves of the period before anyone trusts it.
"""
import os
from datetime import timedelta
from . import core, stocks

COST_PCT = 0.02  # assumed round-trip cost on SPY, in percent
LOOKBACK_DAYS = 730
MIN = lambda h, m: h * 60 + m


def _sessions(creds):
    """SPY 5-minute regular-hours bars, grouped by day as {date: {minute: bar}}."""
    end = core.now() - timedelta(minutes=20)
    start = end - timedelta(days=LOOKBACK_DAYS)
    days, token, feed = {}, None, "sip"
    while True:
        params = dict(timeframe="5Min", start=stocks._stamp(start), end=stocks._stamp(end), feed=feed, limit=10000,
                      adjustment="all", sort="asc")
        if token:
            params["page_token"] = token
        page = stocks._get(stocks.DATA_URL, f"/v2/stocks/{stocks.BENCH}/bars", creds, **params)
        for b in page.get("bars") or []:
            t = stocks._bar_time(b).astimezone(stocks.ET)
            m = t.hour * 60 + t.minute
            if MIN(9, 30) <= m < MIN(16, 0):
                days.setdefault(t.date(), {})[m] = b
        token = page.get("next_page_token")
        if not token:
            return days


def _hold(day, buy, sell):
    """Percent return buying at the open of one 5-minute bar and selling at the open of a later one."""
    a, b = day.get(buy), day.get(sell)
    return (b["o"] / a["o"] - 1) * 100 if a and b else None


def run_all(days):
    """Returns {strategy: [(date, percent return before costs), ...]}."""
    o = MIN(9, 30)
    out = {k: [] for k in ("Buy the open, sell 20 min later", "After 15 min, if up, buy and hold 20 min",
                           "After 15 min, if down, buy and hold 20 min", "Buy at 9:30 AM Pacific, sell 20 min later",
                           "Opening range breakout, sell by close", "Last 30 min, if up on the day",
                           "Hold overnight, close to next open", "Hold open to close, daily")}
    dates = sorted(days)
    for i, d in enumerate(dates):
        day = days[d]
        if o not in day or MIN(15, 55) not in day:
            continue  # short or incomplete session
        add = lambda name, r: r is not None and out[name].append((d, r))
        add("Buy the open, sell 20 min later", _hold(day, o, o + 20))
        q = _hold(day, o, o + 15)
        if q is not None:
            name = "After 15 min, if up, buy and hold 20 min" if q > 0 else "After 15 min, if down, buy and hold 20 min"
            add(name, _hold(day, o + 15, o + 35))
        add("Buy at 9:30 AM Pacific, sell 20 min later", _hold(day, MIN(12, 30), MIN(12, 50)))
        first = [day[m] for m in sorted(day) if m < o + 30]
        if first:
            high, low = max(b["h"] for b in first), min(b["l"] for b in first)
            for m in sorted(x for x in day if x >= o + 30):
                if day[m]["h"] > high:  # filled at the breakout level, stop at the range low, else sold at the close
                    later = [day[x] for x in sorted(day) if x >= m]
                    stopped = any(b["l"] <= low for b in later)
                    add("Opening range breakout, sell by close", ((low if stopped else later[-1]["c"]) / high - 1) * 100)
                    break
        late = day.get(MIN(15, 30))
        if late and late["o"] > day[o]["o"]:
            last = day[max(day)]
            add("Last 30 min, if up on the day", (last["c"] / late["o"] - 1) * 100)
        add("Hold open to close, daily", (day[max(day)]["c"] / day[o]["o"] - 1) * 100)
        if i + 1 < len(dates) and o in days[dates[i + 1]]:
            add("Hold overnight, close to next open", (days[dates[i + 1]][o]["o"] / day[max(day)]["c"] - 1) * 100)
    return out


def stats(rows):
    """Summary after costs. Each half is reported so a result that only worked once stands out."""
    net = [r - COST_PCT for _, r in rows]
    growth, peak, worst = 1.0, 1.0, 0.0
    for r in net:
        growth *= 1 + r / 100
        peak = max(peak, growth)
        worst = min(worst, growth / peak - 1)
    half = len(net) // 2
    total = lambda v: (__import__("math").prod(1 + r / 100 for r in v) - 1) * 100
    return {"n": len(net), "win": 100 * sum(r > 0 for r in net) / len(net) if net else 0,
            "avg": sum(net) / len(net) if net else 0, "total": (growth - 1) * 100, "drawdown": worst * 100,
            "first": total(net[:half]), "second": total(net[half:])}


def write_report(results, first_day, last_day, days_count):
    lines = ["# Strategy test on SPY", "", f"{first_day} to {last_day}, {days_count} trading days. "
             f"Returns are after an assumed {COST_PCT}% round-trip cost. Past results don't guarantee future ones.", "",
             "A strategy is only worth paper testing if it makes money in both halves and beats simply holding.", "",
             "| Strategy | Trades | Win % | Avg % per trade | Total % | Worst drop % | First half % | Second half % |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    summary = {k: stats(v) for k, v in results.items() if v}
    for name, s in sorted(summary.items(), key=lambda kv: -kv[1]["total"]):
        lines.append(f"| {name} | {s['n']} | {s['win']:.0f} | {s['avg']:.3f} | {s['total']:.1f} | {s['drawdown']:.1f} | "
                     f"{s['first']:.1f} | {s['second']:.1f} |")
    lines += ["", "Daily strategies only hold SPY part of the time, so compare them with \"Hold open to close\" plus "
              "\"Hold overnight\", which together are about the same as holding SPY all the time."]
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "backtest.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def cycle(state, errors, creds):
    if not creds:
        return
    et = core.now().astimezone(stocks.ET)
    today = et.date().isoformat()
    # first run as soon as this loads, then once a day after the close
    if state.get("backtest_date") == today or (state.get("backtest_date") and et.hour < 17):
        return
    try:
        days = _sessions(creds)
        if not days:
            raise ValueError("no SPY history returned")
        write_report(run_all(days), min(days), max(days), len(days))
        state["backtest_date"] = today
        state["last_backtest"] = f"{today}: {len(days)} trading days tested, see data/backtest.md"
    except Exception as e:
        errors.append(f"strategy test: {type(e).__name__}: {e}")
