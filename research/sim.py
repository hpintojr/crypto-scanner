"""$1,000 paper simulation. Places orders on Alpaca's PAPER endpoint only, never live.

One stock buy a trading day at 10:30 AM ET and one crypto buy a day, sharing one $1,000 budget.
Picks use today's signals first, then the past month's numbers plus news. 10% of equity per trade
($100 at the start, so gains are reinvested). Exit at -5%, +10%, or after 7 calendar days.
Create a file named SIM_STOP in the repo to stop all new orders.
"""
import csv, json, os, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from . import core, form4, stocks

PAPER_URL = "https://paper-api.alpaca.markets"  # the only place orders can go
START_CASH = 1000.0
TRADE_FRACTION = 0.10
STOP_PCT, TARGET_PCT, MAX_HOLD_DAYS = -5.0, 10.0, 7
MAX_OPEN = 10
MIN_EXACT_PRICE = 0.01  # below this, Alpaca's reported fill price can be rounded
ENTRY_MINUTE = 10 * 60 + 30
LOOKBACK_DAYS = 20  # trading sessions of history in the momentum score
SHORTLIST = 8  # names checked for news each day
STABLECOINS = {"USDC", "USDT", "USDG", "DAI", "PYUSD", "BUSD", "TUSD", "FDUSD"}
GOOD_WORDS = ("beat", "beats", "surge", "soar", "rally", "upgrade", "record", "raises", "wins", "partnership", "approval", "gains")
BAD_WORDS = ("miss", "misses", "plunge", "tumble", "downgrade", "lawsuit", "probe", "fraud", "hack", "cuts", "falls", "recall", "sec charges")
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


def _crypto_price(creds, sym):
    d = stocks._get(stocks.DATA_URL, "/v1beta3/crypto/us/latest/trades", creds, symbols=sym)
    return ((d.get("trades") or {}).get(sym) or {}).get("p")


def _position_price(creds, p):
    return _crypto_price(creds, p["symbol"]) if p.get("market") == "crypto" else _price(creds, p["symbol"])


def _price(creds, sym):
    t = stocks._get(stocks.DATA_URL, f"/v2/stocks/{sym}/trades/latest", creds, feed="iex").get("trade") or {}
    return t.get("p")


def _order(creds, cid):
    return stocks._get(PAPER_URL, "/v2/orders:by_client_order_id", creds, client_order_id=cid)


def _sync(s, creds):
    """Apply fills from Alpaca."""
    for p in s["positions"]:  # repair a position recorded before the rounding fix
        if p["status"] == "open" and p.get("cost", p["notional"]) < p["notional"] * 0.995:
            s["cash"] -= p["notional"] - p["cost"]
            p.update(cost=p["notional"], entry=p["notional"] / float(p["qty"]))
    for p in list(s["positions"]):
        if p["status"] not in ("buying", "selling"):
            continue
        o = _order(creds, p["sell_id"] if p["status"] == "selling" else p["buy_id"])
        state = o.get("status")
        if state == "filled":
            qty, px = float(o["filled_qty"]), float(o["filled_avg_price"])
            if p["status"] == "buying":
                # Very small prices come back rounded, so a dollar-sized buy costs its full amount.
                p.update(status="open", qty=o["filled_qty"], entry=p["notional"] / qty, cost=p["notional"],
                         opened=core.now().strftime(core.FMT))
            else:
                if px < MIN_EXACT_PRICE:
                    px = _position_price(creds, p) or px  # same rounding on the way out
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


def _exits(s, creds, prices, today, is_open):
    for p in s["positions"]:
        crypto = p.get("market") == "crypto"
        if p["status"] != "open" or p["symbol"] not in prices or not (crypto or is_open):
            continue
        move = (prices[p["symbol"]] / p["entry"] - 1) * 100
        held = (today - date.fromisoformat(p["opened"][:10])).days
        reason = "stop" if move <= STOP_PCT else "target" if move >= TARGET_PCT else \
            "time" if held >= MAX_HOLD_DAYS else None
        if reason:
            p["sell_id"] = f"sim-sell-{p['symbol'].replace('/', '')}-{core.now():%Y%m%d%H%M}"
            qty = p["qty"]
            if crypto:  # any crypto fee comes out of the coins, so sell what the account really holds
                held_qty = stocks._get(PAPER_URL, f"/v2/positions/{p['symbol'].replace('/', '')}", creds).get("qty")
                qty = str(min(float(qty), float(held_qty or qty)))
            _post_order(creds, {"symbol": p["symbol"], "qty": qty, "side": "sell", "type": "market",
                                "time_in_force": "gtc" if crypto else "day", "client_order_id": p["sell_id"]})
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


def _news_score(creds, sym, query):
    """Headlines from the last day via Alpaca news and Google News. Returns (count, good minus bad)."""
    titles = []
    start = (core.now() - timedelta(hours=24)).strftime(core.FMT)
    try:
        items = stocks._get(stocks.DATA_URL, "/v1beta1/news", creds, symbols=sym.replace("/", ""), limit=50, start=start)
        titles += [i.get("headline") or "" for i in items.get("news") or []]
    except Exception:
        pass
    try:
        url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
            {"q": f"{query} when:1d", "hl": "en-US", "gl": "US", "ceid": "US:en"})
        req = urllib.request.Request(url, headers={"User-Agent": "crypto-scanner-research/1.0"}, method="GET")
        with urllib.request.urlopen(req, timeout=20) as r:
            titles += [i.findtext("title") or "" for i in ET.fromstring(r.read()).iter("item")]
    except Exception:
        pass
    low = [t.lower() for t in titles]
    good = sum(any(w in t for w in GOOD_WORDS) for t in low)
    bad = sum(any(w in t for w in BAD_WORDS) for t in low)
    return len(low), good - bad


def _rank(creds, closes, bench, held, query_fn, label):
    """Score = month return vs benchmark + half the 5-day return + a capped news nudge. Best first, positive only."""
    if len(closes.get(bench) or []) < LOOKBACK_DAYS / 2:
        return []
    b = closes[bench]
    bench_ret = (b[-1] / b[0] - 1) * 100
    scored = []
    for sym, c in closes.items():
        if sym in held or len(c) < LOOKBACK_DAYS / 2 or c[0] <= 0 or c[-6:][0] <= 0:
            continue
        month = (c[-1] / c[0] - 1) * 100
        week = (c[-1] / c[-6:][0] - 1) * 100
        scored.append((month - bench_ret + week / 2, sym, month, week))
    out = []
    for base, sym, month, week in sorted(scored, reverse=True)[:SHORTLIST]:
        count, tone = _news_score(creds, sym, query_fn(sym))
        score = base + max(-5, min(5, tone))
        if score > 0:
            out.append((0, score, sym, label,
                        f"Up {month:.1f}% over about a month ({month - bench_ret:+.1f}% vs {bench}), {week:+.1f}% this week, "
                        f"{count} headlines in the last day, news tone {tone:+d}",
                        "Past gains may not continue, and headline tone is a rough measure."))
    return sorted(out, key=lambda c: c[1], reverse=True)


def _daily_stock_closes(creds, symbols, today):
    start = (today - timedelta(days=LOOKBACK_DAYS * 2)).isoformat()
    end = (today - timedelta(days=1)).isoformat()
    for feed in ("sip", "iex"):
        try:
            closes, token = {}, None
            while True:
                params = dict(symbols=",".join(symbols), timeframe="1Day", start=start, end=end, feed=feed,
                              limit=10000, adjustment="split")
                if token:
                    params["page_token"] = token
                page = stocks._get(stocks.DATA_URL, "/v2/stocks/bars", creds, **params)
                for sym, bars in (page.get("bars") or {}).items():
                    closes.setdefault(sym, []).extend(b["c"] for b in bars)
                token = page.get("next_page_token")
                if not token:
                    return {k: v[-LOOKBACK_DAYS:] for k, v in closes.items()}
        except urllib.error.HTTPError as e:
            if e.code not in (403, 422) or feed == "iex":
                raise
    return {}


def _stock_momentum(creds, today, held):
    closes = _daily_stock_closes(creds, stocks.universe() + [stocks.BENCH], today)
    return _rank(creds, closes, stocks.BENCH, held, lambda s: f"{s} stock", "stock-momentum")


def _crypto_candidates(creds, today, held):
    """A coin that passed today's mover check first, then the past month's numbers plus news."""
    assets = stocks._get(PAPER_URL, "/v2/assets", creds, asset_class="crypto", status="active") or []
    pairs = [a["symbol"] for a in assets if a.get("tradable") and a["symbol"].endswith("/USD")
             and a["symbol"].split("/")[0] not in STABLECOINS]
    if not pairs:
        return []
    out = []
    for r in core.read("signals.csv"):
        pair = f"{r['symbol']}/USD"
        if (r["market"] == "crypto" and r["time"][:10] == today.isoformat() and r["passed"] == "1"
                and float(r["move_1h_pct"]) > 0 and pair in pairs and pair not in held):
            out.append((1, float(r["volume_ratio"]), pair, "crypto-mover",
                        f"Up {float(r['move_1h_pct']):.1f}% in an hour on {float(r['volume_ratio']):.1f}x usual volume",
                        "The move may already be over, and this signal has no proven edge yet."))
    if out:
        return sorted(out, key=lambda c: c[1], reverse=True)
    page = stocks._get(stocks.DATA_URL, "/v1beta3/crypto/us/bars", creds, symbols=",".join(pairs), timeframe="1Day",
                       start=(today - timedelta(days=LOOKBACK_DAYS)).isoformat(), limit=10000)
    closes = {k: [b["c"] for b in v] for k, v in (page.get("bars") or {}).items()}
    return _rank(creds, closes, "BTC/USD", held, lambda s: f"{s.split('/')[0]} crypto", "crypto-momentum")


def _check_paper(creds):
    if not str(stocks._get(PAPER_URL, "/v2/account", creds).get("account_number", "")).startswith("PA"):
        raise RuntimeError("account is not a paper account, refusing to trade")


def _buy(s, creds, prices, today, market):
    """Place today's buy for this market. Returns True once an order goes in."""
    held = {p["symbol"] for p in s["positions"]}
    equity = _equity(s, prices)
    notional = round(min(equity * TRADE_FRACTION, s["cash"]), 2)
    if len(s["positions"]) >= MAX_OPEN or notional < 1:
        return
    _check_paper(creds)
    crypto = market == "crypto"
    if crypto:
        picks = _crypto_candidates(creds, today, held)
    else:
        picks = candidates(today, held) or _stock_momentum(creds, today, held)
    for _, _, sym, source, thesis, against in picks:
        if not crypto:
            asset = stocks._get(PAPER_URL, f"/v2/assets/{sym}", creds)
            if not (asset.get("tradable") and asset.get("fractionable")):
                continue
        cid = f"sim-buy-{sym.replace('/', '')}-{today:%Y%m%d}"
        _post_order(creds, {"symbol": sym, "notional": str(notional), "side": "buy", "type": "market",
                            "time_in_force": "gtc" if crypto else "day", "client_order_id": cid})
        s["cash"] -= notional
        s["positions"].append({"symbol": sym, "market": market, "source": source, "status": "buying", "buy_id": cid, "notional": notional,
                               "thesis": thesis, "against": against + f" Exit: {STOP_PCT:g}%, +{TARGET_PCT:g}%, or {MAX_HOLD_DAYS} days."})
        s["last_crypto_day" if crypto else "last_trade_day"] = today.isoformat()
        return True
    return False


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
    lines += ["", "Rules: one stock buy a trading day at 10:30 AM ET and one crypto buy a day, 10% of equity each, "
              "-5% stop, +10% target, 7-day limit. No buy if nothing scores above zero. Trade data is in sim-trades.csv."]
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
            s = {"start": core.now().astimezone(stocks.ET).date().isoformat(), "cash": START_CASH, "positions": [],
                 "spy_start": _price(creds, stocks.BENCH), "last_trade_day": None}
        _sync(s, creds)
        prices = {stocks.BENCH: _price(creds, stocks.BENCH)}
        for p in s["positions"]:
            prices[p["symbol"]] = _position_price(creds, p)
        prices = {k: v for k, v in prices.items() if v}
        et = core.now().astimezone(stocks.ET)
        today = et.date()
        stopped = os.path.exists(os.path.join(ROOT, "SIM_STOP"))
        if not stopped:
            _exits(s, creds, prices, today, is_open)
            if s.get("last_crypto_day") != today.isoformat():
                _buy(s, creds, prices, today, "crypto")
            if is_open and et.hour * 60 + et.minute >= ENTRY_MINUTE and s.get("last_trade_day") != today.isoformat():
                _buy(s, creds, prices, today, "stock")
        _save(s)
        equity = _report(s, prices)
        state["last_sim"] = (f"value ${equity:,.2f}, {len(s['positions'])} open, cash ${s['cash']:,.2f}"
                             + (", STOPPED by SIM_STOP" if stopped else ""))
    except urllib.error.HTTPError as e:
        errors.append(f"simulation: HTTP {e.code} {e.url.split('?')[0]}")
    except Exception as e:
        errors.append(f"simulation: {type(e).__name__}: {e}")
