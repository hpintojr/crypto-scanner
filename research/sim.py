"""$1,000 paper simulation. Places orders on Alpaca's PAPER endpoint only, never live.

HOLD_MODE (Hamilton's rule, Nov 5, 2026): no unproven picks. New money only buys and holds SPY or BTC, with no exits.
Older positions keep their normal exits, and their cash moves into the hold. Set HOLD_MODE to False for the old picks.

Two separate budgets, $1,000 for crypto and $1,000 for stocks. No limit on the number of trades, only on
money: no margin, and neither budget can spend the other's cash.
Keeps buying until the budget is used: signals first, then the best remaining pick from the past month's
numbers plus news (crypto 24/7, stocks from 10:30 AM ET). At most one buy per market per cycle, and a coin
or stock isn't bought twice in a day. 10% of equity per trade
($100 at the start, so gains are reinvested). Exit at -5%, +10%, or after 7 calendar days.
Create a file named SIM_STOP in the repo to stop all new orders.
"""
import csv, json, os, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from . import core, form4, metrics, stocks

PAPER_URL = "https://paper-api.alpaca.markets"  # the only place orders can go
START_CASH = 1000.0
TRADE_FRACTION = 0.10
STOP_PCT, TARGET_PCT, MAX_HOLD_DAYS = -5.0, 10.0, 7
REPEAT_MOMENTUM = True  # keep buying momentum picks until the cash is used
STALE_BUY_MINUTES = 15  # an unfilled buy older than this is canceled, and its cash returns
HOLD_MODE = True
MIN_ORDER = 10.0  # smaller orders can be refused, and cash that low is effectively used up
PEPE_ACTUAL_COST, PEPE_ACTUAL_ENTRY = 98.0546, 4.99e-06  # Alpaca cash fell from $100,000 to $99,901.95
ENTRY_MINUTE = 10 * 60 + 30
LOOKBACK_DAYS = 20  # trading sessions of history in the momentum score
SHORTLIST = 8  # names checked for news each day
# Pegged to a dollar or to gold, so they don't fit a momentum strategy
STABLECOINS = {"USDC", "USDT", "USDG", "DAI", "PYUSD", "BUSD", "TUSD", "FDUSD", "RLUSD", "PAXG", "XAUT", "XAUM"}
GOOD_WORDS = ("beat", "beats", "surge", "soar", "rally", "upgrade", "record", "raises", "wins", "partnership", "approval", "gains")
BAD_WORDS = ("miss", "misses", "plunge", "tumble", "downgrade", "lawsuit", "probe", "fraud", "hack", "cuts", "falls", "recall", "sec charges")
FORM4_MAX_AGE_DAYS = 3
CHECKPOINTS = (14, 30)
TRADE_FIELDS = ["symbol", "source", "opened", "entry", "closed", "exit", "qty", "cost", "proceeds", "pnl",
                "return_pct", "exit_reason", "thesis", "against"]
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _bucket(p):
    return "cash" if p.get("market") == "crypto" else "stock_cash"


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


def _cancel_order(creds, order_id):
    """Cancels one simulation order on the paper account. There's no cancel-all here."""
    req = urllib.request.Request(f"{PAPER_URL}/v2/orders/{order_id}", headers=creds, method="DELETE")
    with urllib.request.urlopen(req, timeout=30):
        pass


def _order_age_minutes(cid):
    """Orders carry their UTC placement time in the ID: sim-buy-POLUSD-202611051009."""
    placed = datetime.strptime(cid.rsplit("-", 1)[-1], "%Y%m%d%H%M").replace(tzinfo=timezone.utc)
    return (core.now() - placed).total_seconds() / 60


def _price(creds, sym):
    t = stocks._get(stocks.DATA_URL, f"/v2/stocks/{sym}/trades/latest", creds, feed="iex").get("trade") or {}
    return t.get("p")


def _order(creds, cid):
    return stocks._get(PAPER_URL, "/v2/orders:by_client_order_id", creds, client_order_id=cid)


def _held_qty(creds, p, fallback):
    if p.get("market") != "crypto":
        return fallback
    # Alpaca merges all of a coin into one position, so never record more than this order filled.
    held = stocks._get(PAPER_URL, f"/v2/positions/{p['symbol'].replace('/', '')}", creds).get("qty") or fallback
    return str(min(float(fallback), float(held)))


def _sync(s, creds):
    """Apply fills from Alpaca."""
    for p in s["positions"]:  # one-time correction: match the first PEPE buy to Alpaca's actual charge
        if p.get("buy_id") == "sim-buy-PEPEUSD-20261105" and p["status"] == "open" and not p.get("reconciled"):
            s["cash"] = s["cash"] + p.get("cost", p["notional"]) - PEPE_ACTUAL_COST
            p.update(cost=PEPE_ACTUAL_COST, entry=PEPE_ACTUAL_ENTRY, qty=_held_qty(creds, p, p["qty"]), reconciled=True)
    for p in list(s["positions"]):
        if p["status"] not in ("buying", "selling"):
            continue
        o = _order(creds, p["sell_id"] if p["status"] == "selling" else p["buy_id"])
        state = o.get("status")
        if state == "filled":
            qty, px = float(o["filled_qty"]), float(o["filled_avg_price"])
            if p["status"] == "buying":
                # Alpaca's account charge is the truth: filled quantity times fill price.
                # A crypto fee comes out of the coins, so record what the account really holds.
                cost = qty * px
                s[_bucket(p)] += p["notional"] - cost
                p.update(status="open", qty=_held_qty(creds, p, o["filled_qty"]), entry=px, cost=round(cost, 4),
                         opened=core.now().strftime(core.FMT))
            else:
                s[_bucket(p)] += qty * px
                _close(p, px, qty)
                s["positions"].remove(p)
        elif p["status"] == "buying" and state in ("new", "accepted", "pending_new") \
                and not float(o.get("filled_qty") or 0) and _order_age_minutes(p["buy_id"]) > STALE_BUY_MINUTES:
            _cancel_order(creds, o["id"])  # the cash comes back once Alpaca reports it canceled
        elif state in ("canceled", "expired", "rejected"):
            if p["status"] == "buying":
                s[_bucket(p)] += p["notional"]
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
        if p.get("hold") or p["status"] != "open" or p["symbol"] not in prices or not (crypto or is_open):
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


def _rank(creds, closes, bench, held, query_fn, label, min_tone=None):
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
        if score > 0 and (min_tone is None or tone >= min_tone):
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


def _crypto_candidates(creds, today, held, momentum_ok=True):
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
                and float(r["move_1h_pct"]) > 0 and pair in pairs and pair not in held
                and _news_score(creds, pair, f"{r['symbol']} crypto")[1] >= 0):
            out.append((1, float(r["volume_ratio"]), pair, "crypto-mover",
                        f"Up {float(r['move_1h_pct']):.1f}% in an hour on {float(r['volume_ratio']):.1f}x usual volume",
                        "The move may already be over, and this signal has no proven edge yet."))
    if out or not momentum_ok:
        return sorted(out, key=lambda c: c[1], reverse=True)
    page = stocks._get(stocks.DATA_URL, "/v1beta3/crypto/us/bars", creds, symbols=",".join(pairs), timeframe="1Day",
                       start=(today - timedelta(days=LOOKBACK_DAYS)).isoformat(), limit=10000)
    closes = {k: [b["c"] for b in v] for k, v in (page.get("bars") or {}).items()}
    return _rank(creds, closes, "BTC/USD", held, lambda s: f"{s.split('/')[0]} crypto", "crypto-momentum", min_tone=0)


def _check_paper(creds):
    if not str(stocks._get(PAPER_URL, "/v2/account", creds).get("account_number", "")).startswith("PA"):
        raise RuntimeError("account is not a paper account, refusing to trade")


def _hold_buy(s, creds, market):
    """Puts all of a budget's free cash into its index or coin, to hold."""
    crypto = market == "crypto"
    bucket, sym = ("cash", "BTC/USD") if crypto else ("stock_cash", stocks.BENCH)
    notional = round(s[bucket], 2)
    if notional < MIN_ORDER or any(p["symbol"] == sym and p["status"] == "buying" for p in s["positions"]):
        return False
    _check_paper(creds)
    cid = f"sim-hold-{sym.replace('/', '')}-{core.now():%Y%m%d%H%M}"
    _post_order(creds, {"symbol": sym, "notional": str(notional), "side": "buy", "type": "market",
                        "time_in_force": "gtc" if crypto else "day", "client_order_id": cid})
    s[bucket] -= notional
    s["positions"].append({"symbol": sym, "market": market, "source": "hold", "hold": True, "status": "buying", "buy_id": cid,
                           "notional": notional, "thesis": f"Long-term hold of {sym}, the benchmark for this budget",
                           "against": "Can fall a lot and stay down for years. No stop, by design."})
    return True


def _buy(s, creds, prices, today, market, may_use_momentum):
    """Place one buy for this market if there's a pick and cash. Returns True once an order goes in."""
    day = today.isoformat()
    if s.get("bought_date") != day:
        s["bought_date"], s["bought_today"] = day, []
    held = {p["symbol"] for p in s["positions"]} | set(s["bought_today"])
    bucket = "cash" if market == "crypto" else "stock_cash"
    equity = _equity(s, prices, market)
    notional = round(min(equity * TRADE_FRACTION, s[bucket]), 2)
    if notional < MIN_ORDER:
        return False
    _check_paper(creds)
    crypto = market == "crypto"
    day_key = "last_crypto_day" if crypto else "last_trade_day"
    momentum_ok = may_use_momentum and (REPEAT_MOMENTUM or s.get(day_key) != day)
    if crypto:
        picks = _crypto_candidates(creds, today, held, momentum_ok)
    else:
        picks = candidates(today, held) or (_stock_momentum(creds, today, held) if momentum_ok else [])
    for _, _, sym, source, thesis, against in picks:
        if not crypto:
            asset = stocks._get(PAPER_URL, f"/v2/assets/{sym}", creds)
            if not (asset.get("tradable") and asset.get("fractionable")):
                continue
        cid = f"sim-buy-{sym.replace('/', '')}-{core.now():%Y%m%d%H%M}"
        _post_order(creds, {"symbol": sym, "notional": str(notional), "side": "buy", "type": "market",
                            "time_in_force": "gtc" if crypto else "day", "client_order_id": cid})
        s[bucket] -= notional
        s["positions"].append({"symbol": sym, "market": market, "source": source, "status": "buying", "buy_id": cid, "notional": notional,
                               "thesis": thesis, "against": against + f" Exit: {STOP_PCT:g}%, +{TARGET_PCT:g}%, or {MAX_HOLD_DAYS} days."})
        s[day_key] = day
        s["bought_today"].append(sym)
        return True
    return False


def _preview(s, creds, state, today, is_open):
    """Hourly list of what the rules would buy next, using the same picks as real buys. Places no orders."""
    if HOLD_MODE:
        with open(os.path.join(core.DATA, "sim-next.md"), "w") as f:
            f.write("# Next picks\n\nHold mode: crypto cash goes into BTC. The second $1,000 waits in cash for a tested commodities plan. No other picks.\n")
        return
    last = state.get("preview_checked")
    if last and core.now() - core.parse(last) < timedelta(minutes=55):
        return
    state["preview_checked"] = core.now().strftime(core.FMT)
    bought = set(s.get("bought_today") or []) if s.get("bought_date") == today.isoformat() else set()
    held = {p["symbol"] for p in s["positions"]} | bought
    signals = candidates(today, held)
    lines = ["# Next picks", "", f"As of {core.now().strftime(core.FMT)}. A preview, not a promise: prices and signals change, "
             "and a stock that can't be traded in fractions is skipped.", "",
             f"- Crypto cash ${s['cash']:,.2f}, stock cash ${s.get('stock_cash', 0):,.2f}", "",
             "## Stocks", "", "Form 4 and mover signals can buy from the open. Other picks start at 10:30 AM ET.", ""]
    picks = signals + _stock_momentum(creds, today, held)
    lines += [f"{i}. {c[2]} ({c[3]}): {c[4]}" for i, c in enumerate(picks[:6], 1)] or ["No stock scores above zero."]
    lines += ["", "## Crypto", ""]
    coins = _crypto_candidates(creds, today, held)
    lines += [f"{i}. {c[2]} ({c[3]}): {c[4]}" for i, c in enumerate(coins[:6], 1)] or ["No coin scores above zero."]
    with open(os.path.join(core.DATA, "sim-next.md"), "w") as f:
        f.write("\n".join(lines) + "\n")


def _equity(s, prices, market=None):
    """Value of one budget, or of both when no market is named."""
    total = 0.0
    if market in (None, "crypto"):
        total += s["cash"]
    if market in (None, "stock"):
        total += s.get("stock_cash", 0.0)
    for p in s["positions"]:
        if market and p.get("market", "stock") != market:
            continue
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
    crypto_value, stock_value = _equity(s, prices, "crypto"), _equity(s, prices, "stock")
    start_total = START_CASH * 2
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
             f"- Started: {s['start']}", f"- Total value: ${equity:,.2f} of ${start_total:,.0f} ({(equity / start_total - 1) * 100:+.2f}%)",
             f"- Crypto budget: ${crypto_value:,.2f} ({(crypto_value / START_CASH - 1) * 100:+.2f}%), cash ${s['cash']:,.2f}",
             f"- Stock budget: ${stock_value:,.2f} ({(stock_value / START_CASH - 1) * 100:+.2f}%), cash ${s.get('stock_cash', 0):,.2f}",
             f"- Same $1,000 in SPY: " + (f"${spy_value:,.2f}" if spy_value else "not available yet"),
             f"- Open positions: {len(s['positions'])}",
             f"- Closed trades: {len(trades)}, {wins} winners", ""]
    for days in CHECKPOINTS:
        due = (start + timedelta(days=days)).isoformat()
        hit = next((r for r in rows if r["date"] >= due), None)
        lines.append(f"- {days}-day checkpoint ({due}): " + (f"${float(hit['equity']):,.2f}, SPY ${hit['spy_equivalent']}" if hit else "not reached"))
    lines += ["", "Rules: hold mode. The second $1,000 waits in cash for a commodities plan, and crypto cash buys and holds BTC, with no exits. "
              "Older crypto positions keep their -5%, +10% and 7-day exits, and that cash moves into BTC. No margin. "
              "Trade data is in sim-trades.csv."]
    with open(os.path.join(core.DATA, "sim.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    s["flags"] = metrics.write(s, prices, rows)
    return equity


def cycle(state, errors, creds):
    if not creds:
        return
    try:
        s = _load()
        clock = stocks._get(PAPER_URL, "/v2/clock", creds)
        is_open = clock.get("is_open")
        if s is None:
            s = {"start": core.now().astimezone(stocks.ET).date().isoformat(), "cash": START_CASH, "stock_cash": START_CASH, "positions": [],
                 "spy_start": _price(creds, stocks.BENCH), "last_trade_day": None}
        s.setdefault("stock_cash", START_CASH)  # the crypto budget keeps its history, stocks start fresh
        _sync(s, creds)
        prices = {stocks.BENCH: _price(creds, stocks.BENCH), "BTC/USD": _crypto_price(creds, "BTC/USD")}
        s.setdefault("btc_start", prices["BTC/USD"])
        for p in s["positions"]:
            prices[p["symbol"]] = _position_price(creds, p)
        prices = {k: v for k, v in prices.items() if v}
        et = core.now().astimezone(stocks.ET)
        today = et.date()
        stopped = os.path.exists(os.path.join(ROOT, "SIM_STOP"))
        if not stopped:
            _exits(s, creds, prices, today, is_open)
            if HOLD_MODE:
                _hold_buy(s, creds, "crypto")
                # The stock budget waits: Hamilton moved it to commodities, and those rules aren't tested yet.
            else:
                _buy(s, creds, prices, today, "crypto", True)
                if is_open:
                    _buy(s, creds, prices, today, "stock", et.hour * 60 + et.minute >= ENTRY_MINUTE)
        equity = _report(s, prices)
        _save(s)
        state["last_flags"] = "; ".join(s.get("flags") or []) or "none"
        _preview(s, creds, state, today, is_open)
        state["last_sim"] = (f"value ${equity:,.2f} of $2,000, {len(s['positions'])} open, crypto cash ${s['cash']:,.2f}, "
                             f"stock cash ${s['stock_cash']:,.2f}"
                             + (", STOPPED by SIM_STOP" if stopped else ""))
    except urllib.error.HTTPError as e:
        errors.append(f"simulation: HTTP {e.code} {e.url.split('?')[0]}")
    except Exception as e:
        errors.append(f"simulation: {type(e).__name__}: {e}")
