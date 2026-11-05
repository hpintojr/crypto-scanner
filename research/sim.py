"""$1,000 paper simulation. Places orders on Alpaca's PAPER endpoint only, never live.

One new position a trading day, chosen at 3:30 PM ET from that day's signals. 10% of equity per trade
($100 at the start, so gains are reinvested). Exit at -5%, +10%, or after 7 calendar days.
Create a file named SIM_STOP in the repo to stop all new orders.
"""
import csv, json, os, urllib.error, urllib.request
from datetime import date, timedelta
from . import core, form4, stocks

PAPER_URL = "https://paper-api.alpaca.markets"  # the only place orders can go
START_CASH = 1000.0
TRADE_FRACTION = 0.10
STOP_PCT, TARGET_PCT, MAX_HOLD_DAYS = -5.0, 10.0, 7
MAX_OPEN = 10
ENTRY_MINUTE = 15 * 60 + 30
FORM4_MAX_AGE_DAYS = 3
CHECKPOINTS = (14, 30)
TRADE_FIELDS = ["symbol", "source", "opened", "entry", "closed", "exit", "qty", "cost", "proceeds", "pnl",
                "return_pct", "exit_reason", "thesis", "against"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _state_path():
    return os.path.join(core.DATA, "sim-state.json")


def _load():
    try:
        with open(_state_path()) as f:
            return json.load(f)
    except OSError:
        return None


def _save(s):
    os.makedirs(core.DATA, exist_ok=True)
    with open(_state_path(), "w") as f:
        json.dump(s, f, indent=1)


def _post_order(creds, body):
    req = urllib.request.Request(PAPER_URL + "/v2/orders", data=json.dumps(body).encode(), method="POST",
                                 headers={**creds, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _price(creds, sym):
    t = stocks._get(stocks.DATA_URL, f"/v2/stocks/{sym}/trades/latest", creds, feed="iex").get("trade") or {}
    return t.get("p")


def _order(creds, cid):
    return stocks._get(PAPER_URL, "/v2/orders:by_client_order_id", creds, client_order_id=cid)


def _sync(s, creds):
    """Apply fills from Alpaca. The ledger only ever uses the price Alpaca actually filled at."""
    for p in list(s["positions"]):
        if p["status"] not in ("buying", "selling"):
            continue
        o = _order(creds, p["sell_id"] if p["status"] == "selling" else p["buy_id"])
        state = o.get("status")
        if state == "filled":
            qty, px = float(o["filled_qty"]), float(o["filled_avg_price"])
            if p["status"] == "buying":
                s["cash"] += p["notional"] - qty * px
                p.update(status="open", qty=o["filled_qty"], entry=px, cost=round(qty * px, 4),
                         opened=core.now().strftime(core.FMT))
            else:
                s["cash"] += qty * px
                _close(p, px, qty)
                s["positions"].remove(p)
        elif state in ("canceled", "expired", "rejected"):
            if p["status"] == "buying":
                s["cash"] += p["notional"]
                s["positions"].remove(p)
            else:
                p["status"] = "open"  # a sell that didn't fill: try again next cycle


def _close(p, px, qty):
    proceeds = qty * px
    row = {"symbol": p["symbol"], "source": p["source"], "opened": p["opened"], "entry": p["entry"],
           "closed": core.now().strftime(core.FMT), "exit": px, "qty": p["qty"], "cost": p["cost"],
           "proceeds": round(proceeds, 4), "pnl": round(proceeds - p["cost"], 4),
           "return_pct": round((proceeds / p["cost"] - 1) * 100, 3), "exit_reason": p.get("exit_reason", ""),
           "thesis": p["thesis"], "against": p["against"]}
    core._append("sim-trades.csv", TRADE_FIELDS, [row])


def _exits(s, creds, prices, today):
    for p in s["positions"]:
        if p["status"] != "open" or p["symbol"] not in prices:
            continue
        move = (prices[p["symbol"]] / p["entry"] - 1) * 100
        held = (today - date.fromisoformat(p["opened"][:10])).days
        reason = "stop" if move <= STOP_PCT else "target" if move >= TARGET_PCT else \
            "time" if held >= MAX_HOLD_DAYS else None
        if reason:
            p["sell_id"] = f"sim-sell-{p['symbol']}-{core.now():%Y%m%d%H%M}"
            _post_order(creds, {"symbol": p["symbol"], "qty": p["qty"], "side": "sell", "type": "market",
                                "time_in_force": "day", "client_order_id": p["sell_id"]})
            p.update(status="selling", exit_reason=reason)


def candidates(today, held):
    """Today's choices, best first. A qualifying Form 4 outranks a mover; movers rank by volume then move."""
    out = []
    oldest = (today - timedelta(days=FORM4_MAX_AGE_DAYS)).isoformat()
    for r in form4._rows():
        if r["qualifies"] == "yes" and r["verified"] == "yes" and oldest <= r["filing_date"] and r["ticker"] not in held:
            value = float(r["dollar_value"])
            out.append((2, value, r["ticker"], "form4",
                        f"{r['role']} bought ${value:,.0f} on the open market ({r['url']})",
                        "Insider buys often take months to pay off, and this exit is days."))
    stamp = today.isoformat()
    for r in core.read("signals.csv"):
        if (r["market"] == "stocks" and r["time"][:10] == stamp and r["passed"] == "1" and r.get("signal_type") == "move_1h"
                and float(r["move_1h_pct"]) > 0 and r["symbol"] not in held):
            ratio = float(r["volume_ratio"])
            out.append((1, ratio * float(r["move_1h_pct"]), r["symbol"], "mover",
                        f"Up {float(r['move_1h_pct']):.1f}% in an hour on {ratio:.1f}x usual volume",
                        "The move may already be over, and this signal has no proven edge yet."))
    return sorted(out, key=lambda c: (c[0], c[1]), reverse=True)


def _enter(s, creds, prices, today):
    held = {p["symbol"] for p in s["positions"]}
    equity = _equity(s, prices)
    notional = round(min(equity * TRADE_FRACTION, s["cash"]), 2)
    if len(s["positions"]) >= MAX_OPEN or notional < 1:
        return
    if not str(stocks._get(PAPER_URL, "/v2/account", creds).get("account_number", "")).startswith("PA"):
        raise RuntimeError("account is not a paper account, refusing to trade")
    for _, _, sym, source, thesis, against in candidates(today, held):
        asset = stocks._get(PAPER_URL, f"/v2/assets/{sym}", creds)
        if not (asset.get("tradable") and asset.get("fractionable")):
            continue
        cid = f"sim-buy-{sym}-{today:%Y%m%d}"
        _post_order(creds, {"symbol": sym, "notional": str(notional), "side": "buy", "type": "market",
                            "time_in_force": "day", "client_order_id": cid})
        s["cash"] -= notional
        s["positions"].append({"symbol": sym, "source": source, "status": "buying", "buy_id": cid, "notional": notional,
                               "thesis": thesis, "against": against + f" Exit: {STOP_PCT:g}%, +{TARGET_PCT:g}%, or {MAX_HOLD_DAYS} days."})
        s["last_trade_day"] = today.isoformat()
        return


def _equity(s, prices):
    total = s["cash"]
    for p in s["positions"]:
        if p["status"] == "buying":
            total += p["notional"]
        else:
            total += float(p["qty"]) * prices.get(p["symbol"], p["entry"])
    return total


def _report(s, prices):
    today = core.now().astimezone(stocks.ET).date()
    equity = _equity(s, prices)
    spy_now = prices.get(stocks.BENCH)
    spy_value = START_CASH * spy_now / s["spy_start"] if spy_now and s.get("spy_start") else None
    rows = core.read("sim-equity.csv")
    row = {"date": today.isoformat(), "equity": round(equity, 2), "cash": round(s["cash"], 2),
           "spy_equivalent": round(spy_value, 2) if spy_value else ""}
    rows = [r for r in rows if r["date"] != row["date"]] + [row]
    with open(os.path.join(core.DATA, "sim-equity.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        w.writeheader()
        w.writerows(rows)
    trades = core.read("sim-trades.csv")
    wins = sum(float(t["pnl"]) > 0 for t in trades)
    start = date.fromisoformat(s["start"])
    lines = ["# $1,000 paper simulation", "", "Paper money with simulated fills. No real money, no real fills.", "",
             f"- Started: {s['start']}", f"- Value now: ${equity:,.2f} ({(equity / START_CASH - 1) * 100:+.2f}%)",
             f"- Same $1,000 in SPY: " + (f"${spy_value:,.2f}" if spy_value else "not available yet"),
             f"- Cash: ${s['cash']:,.2f}", f"- Open positions: {len(s['positions'])}",
             f"- Closed trades: {len(trades)}, {wins} winners", ""]
    for days in CHECKPOINTS:
        due = (start + timedelta(days=days)).isoformat()
        hit = next((r for r in rows if r["date"] >= due), None)
        lines.append(f"- {days}-day checkpoint ({due}): " + (f"${float(hit['equity']):,.2f}, SPY ${hit['spy_equivalent']}" if hit else "not reached"))
    lines += ["", "Rules: one position a day at 3:30 PM ET, 10% of equity, -5% stop, +10% target, 7-day limit. "
              "No trade on a day with no signal. Trade data is in sim-trades.csv."]
    with open(os.path.join(core.DATA, "sim.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return equity


def cycle(state, errors, creds):
    if not creds:
        return
    try:
        s = _load()
        clock = stocks._get(PAPER_URL, "/v2/clock", creds)
        is_open = clock.get("is_open")
        if s is None:
            if not is_open:
                state["last_sim"] = "starts at the next market open"
                return
            s = {"start": core.now().astimezone(stocks.ET).date().isoformat(), "cash": START_CASH, "positions": [],
                 "spy_start": _price(creds, stocks.BENCH), "last_trade_day": None}
        _sync(s, creds)
        syms = {p["symbol"] for p in s["positions"]} | {stocks.BENCH}
        prices = {sym: px for sym in syms if (px := _price(creds, sym))}
        et = core.now().astimezone(stocks.ET)
        today = et.date()
        stopped = os.path.exists(os.path.join(ROOT, "SIM_STOP"))
        if is_open and not stopped:
            _exits(s, creds, prices, today)
            if et.hour * 60 + et.minute >= ENTRY_MINUTE and s.get("last_trade_day") != today.isoformat():
                _enter(s, creds, prices, today)
        _save(s)
        equity = _report(s, prices)
        state["last_sim"] = (f"value ${equity:,.2f}, {len(s['positions'])} open, cash ${s['cash']:,.2f}"
                             + (", STOPPED by SIM_STOP" if stopped else ""))
    except urllib.error.HTTPError as e:
        errors.append(f"simulation: HTTP {e.code} {e.url.split('?')[0]}")
    except Exception as e:
        errors.append(f"simulation: {type(e).__name__}: {e}")
