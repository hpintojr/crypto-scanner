"""Previous-session point of control (POC) research log. No orders.

Tests the one testable idea from the volume-profile shorts: the price where the most volume traded in the
previous session, and what price does when it comes back to it. Every rule here is ours, written down so it can
be scored: the shorts never define a "reaction". Stock bars are the IEX feed, which carries only a small share of
total volume, so a stock POC is an estimate. Crypto bars are Alpaca's own venue.

Signal (one per symbol per side per 4 hours): the latest completed 5-minute bar touches yesterday's POC.
- Reaction held (passed=1): price came from one side, touched the POC, and closed back on that side.
- Broke through (passed=0): it closed on the other side. This is the comparison group.
- The sign of move_1h_pct is the side the close ended on, so scoring reads it as the expected direction.
- Sweep: in the hour before the touch, price broke the previous session's low (or high) and closed back inside.
- detail carries POC, value area, sweep, and the stop and 3:1 target a risk-based exit would use, for a later test.
"""
import os
from datetime import timedelta
from . import core, stocks

COINS = ["BTC/USD", "ETH/USD"]
COIN_IDS = {"BTC/USD": "bitcoin", "ETH/USD": "ethereum"}
VALUE_AREA = 0.70
BIN_PCT = 0.001       # price bins of 0.1%
SWEEP_BARS = 12       # one hour of 5-minute bars
MAX_STOCKS = 20       # signals per cycle, so a busy day can't flood the log
LAST_BARS = [None, None]  # (time, {symbol: bars}) left by the stock scan, so no second fetch


def profile(bars):
    """POC and value area from bars, volume binned by each bar's typical price."""
    if not bars:
        return None
    width = max((sum(b["c"] for b in bars) / len(bars)) * BIN_PCT, 1e-9)
    vol = {}
    for b in bars:
        k = round(((b["h"] + b["l"] + b["c"]) / 3) / width)
        vol[k] = vol.get(k, 0) + b["v"]
    if sum(vol.values()) <= 0:
        return None
    keys = sorted(vol)
    top = max(keys, key=lambda k: vol[k])
    total, inside, lo, hi = sum(vol.values()), vol[top], top, top
    while inside < VALUE_AREA * total and (lo > keys[0] or hi < keys[-1]):
        below = vol.get(lo - 1, 0) if lo > keys[0] else -1
        above = vol.get(hi + 1, 0) if hi < keys[-1] else -1
        if above >= below:
            hi, inside = hi + 1, inside + above
        else:
            lo, inside = lo - 1, inside + below
    return {"poc": top * width, "vah": (hi + 0.5) * width, "val": (lo - 0.5) * width,
            "low": min(b["l"] for b in bars), "high": max(b["h"] for b in bars)}


def _session_date(bar, market):
    t = stocks._bar_time(bar)
    return t.astimezone(stocks.ET).date() if market == "stocks" else t.date()


def _in_hours(bar, market):
    if market != "stocks":
        return True
    e = stocks._bar_time(bar).astimezone(stocks.ET)
    return (9, 30) <= (e.hour, e.minute) < (16, 0)


def touch(bars, market):
    """The signal for one symbol from its bars, or None."""
    bars = [b for b in bars if _in_hours(b, market)]
    if len(bars) < SWEEP_BARS + 3:
        return None
    today = _session_date(bars[-1], market)
    sessions = sorted({_session_date(b, market) for b in bars} - {today})
    if not sessions:
        return None
    prev = [b for b in bars if _session_date(b, market) == sessions[-1]]
    prof = profile(prev)
    if not prof or len(prev) < 6:
        return None
    cur, last, before = [b for b in bars if _session_date(b, market) == today], bars[-1], bars[-2]
    poc = prof["poc"]
    if not (last["l"] <= poc <= last["h"]) or before["c"] == poc or last["c"] == poc:
        return None
    came_from_above = before["c"] > poc
    held = (last["c"] > poc) == came_from_above
    recent = cur[-SWEEP_BARS - 1:-1]
    if came_from_above:
        sweep = any(b["l"] < prof["low"] and b["c"] > prof["low"] for b in recent)
    else:
        sweep = any(b["h"] > prof["high"] and b["c"] < prof["high"] for b in recent)
    side = 1 if last["c"] > poc else -1
    stop = last["l"] if side > 0 else last["h"]
    risk = abs(last["c"] - stop)
    target = last["c"] + 3 * risk * side if risk > 0 else ""
    return {"price": last["c"], "move": (last["c"] / poc - 1) * 100, "held": held, "side": side,
            "detail": f"poc={poc:.6g};vah={prof['vah']:.6g};val={prof['val']:.6g};sweep={'yes' if sweep else 'no'};"
                      f"from={'above' if came_from_above else 'below'};stop={stop:.6g};target={target if target == '' else f'{target:.6g}'}",
            "volume": sum(b["v"] for b in prev)}


def _log(state, market, sym, asset_id, bench, bench_price, sig):
    return core.log_signal(state, market=market, symbol=sym, asset_id=asset_id, name=sym, price=sig["price"],
                           benchmark=bench, benchmark_price=bench_price, move=sig["move"], volume=sig["volume"],
                           baseline=0, ratio=0, passed=sig["held"], signal_type="poc_touch", detail=sig["detail"])


def _crypto_bars(creds):
    end = core.now()
    out, token = {}, None
    while True:
        params = dict(symbols=",".join(COINS), timeframe="5Min", start=stocks._stamp(end - timedelta(days=2)),
                      end=stocks._stamp(end), limit=10000, sort="asc")
        if token:
            params["page_token"] = token
        page = stocks._get(stocks.DATA_URL, "/v1beta3/crypto/us/bars", creds, **params)
        for sym, bars in (page.get("bars") or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = page.get("next_page_token")
        if not token:
            return out


def cycle(state, errors, creds):
    if not creds:
        return
    logged = 0
    try:
        when, data = LAST_BARS
        if data and core.now() - when < timedelta(minutes=10) and data.get(stocks.BENCH):
            spy = data[stocks.BENCH][-1]["c"]
            for sym, bars in data.items():
                if sym == stocks.BENCH or logged >= MAX_STOCKS:
                    continue
                if core.recently_logged(state, "stocks", sym, "poc_touch"):
                    continue
                sig = touch(bars, "stocks")
                if sig and _log(state, "stocks", sym, sym, stocks.BENCH, spy, sig):
                    logged += 1
        coins = _crypto_bars(creds)
        btc = (coins.get("BTC/USD") or [{}])[-1].get("c")
        for pair in COINS:
            sym = pair.split("/")[0]
            if not btc or core.recently_logged(state, "crypto", sym, "poc_touch"):
                continue
            sig = touch(coins.get(pair) or [], "crypto")
            if sig and _log(state, "crypto", sym, COIN_IDS[pair], "BTC", btc, sig):
                logged += 1
        state["last_poc"] = f"{core.now().strftime(core.FMT)}: {logged} POC touches logged"
    except Exception as e:
        errors.append(f"poc: {type(e).__name__}: {e}")
    write_report()


def write_report():
    """How a touch played out, in the direction the close pointed. Research only."""
    sigs = {s["signal_id"]: s for s in core.read("signals.csv") if s.get("signal_type") == "poc_touch"}
    groups = {}
    for o in core.read("outcomes.csv"):
        s = sigs.get(o["signal_id"])
        if not s or float(o["late_min"]) > core.MAX_LATE_MIN:
            continue
        side = 1 if float(s["move_1h_pct"]) >= 0 else -1
        sweep = "sweep" if "sweep=yes" in (s.get("detail") or "") else "no sweep"
        key = (s["market"], "held" if s["passed"] == "1" else "broke", sweep, o["horizon"])
        groups.setdefault(key, []).append(side * float(o["return_pct"]))
    lines = ["# Previous-session POC test", "",
             f"{len(sigs)} touches logged. Research only, no orders. Rules are in research/poc.py.", "",
             "Return is the move after the touch in the direction the closing bar pointed, before costs.",
             "'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.",
             "Treat any row under 30 signals as noise.", "",
             "| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |", "|---|---|---|---|--:|--:|--:|"]
    for key in sorted(groups):
        v = groups[key]
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {key[3]} | {len(v)} | {sum(v) / len(v):+.3f} | "
                     f"{100 * sum(x > 0 for x in v) / len(v):.0f} |")
    if not groups:
        lines.append("| no scored touches yet | | | | | | |")
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "poc.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
