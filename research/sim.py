"""$2,000 paper simulation. Places orders on Alpaca's PAPER endpoint only, never live.

HOLD_MODE (Hamilton approved this allocation Nov 5, 2026, and returned to it Nov 6 after the growth mix tested worse):
money follows PLAN below. Long slices hold with no stop; mid slices follow the 100-day trend, checked weekly.
Positions from an older plan are sold. No short-term slice until a rule passes.
Older positions keep their normal exits, and their cash joins the plan. Set HOLD_MODE to False for the old picks.

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
from decimal import Decimal, ROUND_DOWN
from . import backtest, core, form4, metrics, stocks

PAPER_URL = "https://paper-api.alpaca.markets"  # the only place orders can go
START_CASH = 1000.0
TRADE_FRACTION = 0.10
STOP_PCT, TARGET_PCT, MAX_HOLD_DAYS = -5.0, 10.0, 7
REPEAT_MOMENTUM = True  # keep buying momentum picks until the cash is used
STALE_BUY_MINUTES = 15  # an unfilled buy older than this is canceled, and its cash returns
HOLD_MODE = True
order_errors = []  # refused orders this cycle, shown in status.md
PLAN = {"crypto": {"long": {"BTC/USD": 400, "ETH/USD": 200}, "mid": {"BTC/USD": 200, "ETH/USD": 200}},
        "stock": {"long": {"GLD": 300, "DBC": 250, "DBA": 75, "CPER": 75}, "mid": {"GLD": 75, "DBC": 75, "DBA": 75, "CPER": 75}}}
TREND_DAYS = 100
TREND_CHECK_DAYS = 7
RECONCILE_MAX_GAP = 0.01
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


class OrderRefused(Exception):
    """Alpaca said no. Carries its reason, because a bare status code doesn't say why."""


def _save(s):
    """Replaced whole, so a killed cycle can't leave it half-written."""
    os.makedirs(core.DATA, exist_ok=True)
    tmp = _state_path() + ".tmp"
    with open(tmp, "w") as f:
        json.dump(s, f, indent=1)
    os.replace(tmp, _state_path())


def _post_order(creds, body):
    req = urllib.request.Request(PAPER_URL + "/v2/orders", data=json.dumps(body).encode(), method="POST",
                                 headers={**creds, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise OrderRefused(f"{body.get('side')} {body.get('symbol')}: HTTP {e.code} {e.read().decode(errors='replace')[:200]}")


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
    """Orders carry their UTC placement time in the ID, such as sim-buy-POLUSD-202611051009."""
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
    return _smaller(fallback, held)


def _smaller(a, b):
    """Exact, because float rounding can turn a large coin balance into slightly more than the account holds."""
    return str(min(Decimal(str(a)), Decimal(str(b))))


def _reconcile_crypto(s, creds):
    """Crypto fees come out of the coins, so lots shrink slightly. Match each coin's lots to Alpaca's merged total.
    A gap over 1% isn't a fee, so it's left alone for the mismatch alert."""
    for sym in {p["symbol"] for p in s["positions"] if p.get("market") == "crypto"}:
        lots = [p for p in s["positions"] if p["symbol"] == sym]
        if any(p["status"] != "open" for p in lots):
            continue
        held = stocks._get(PAPER_URL, f"/v2/positions/{sym.replace('/', '')}", creds).get("qty")
        if not held:
            continue
        held, total = Decimal(str(held)), sum(Decimal(str(p["qty"])) for p in lots)
        if total and held != total and abs(held / total - 1) <= Decimal(str(RECONCILE_MAX_GAP)):
            left = held
            for p in lots[:-1]:
                share = (Decimal(str(p["qty"])) * held / total).quantize(Decimal("0.000000001"), rounding=ROUND_DOWN)
                p["qty"] = str(share)
                left -= share
            lots[-1]["qty"] = str(left)  # the lots add up to exactly what Alpaca holds


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
                if p.get("plan"):
                    s["plan_spent"][p["plan"]] -= p["notional"]
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
            _try_sell(s, creds, p, reason)


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


def _place_plan_buy(s, creds, market, sym, amount, key, hold):
    """One plan buy, in dollars where the asset allows it and whole shares where it doesn't."""
    crypto = market == "crypto"
    bucket = "cash" if crypto else "stock_cash"
    notional = round(min(amount, s[bucket]), 2)
    if notional < MIN_ORDER:
        return False
    _check_paper(creds)
    cid = f"sim-plan-{sym.replace('/', '')}-{core.now():%Y%m%d%H%M}"
    body = {"symbol": sym, "side": "buy", "type": "market", "time_in_force": "gtc" if crypto else "day", "client_order_id": cid}
    if crypto or stocks._get(PAPER_URL, f"/v2/assets/{sym}", creds).get("fractionable"):
        body["notional"] = str(notional)
    else:
        px = _price(creds, sym)
        shares = int(notional // px) if px else 0
        if not shares:
            return False
        body["qty"] = str(shares)
        notional = round(shares * px, 2)
    _post_order(creds, body)
    s[bucket] -= notional
    s["plan_spent"][key] = s["plan_spent"].get(key, 0) + notional
    s["positions"].append({"symbol": sym, "market": market, "source": key, "plan": key, "hold": True, "status": "buying", "buy_id": cid,
                           "notional": notional, "thesis": f"Approved allocation, {key}",
                           "against": "Long slices can fall a lot and stay down for years, with no stop by design. Mid slices lag the trend."})
    _save(s)  # recorded right away, so a later failure can't lose this order
    return True


def _update_trends(s, creds, today):
    """The mid slice's weekly check: in when the last close is above its 100-day average. Rechecked at once if the plan's assets change."""
    last = s.get("trend_checked")
    mids = sorted(sym for slices in PLAN.values() for sym in slices["mid"])
    if s.get("trend_assets") == mids and last and (today - date.fromisoformat(last)).days < TREND_CHECK_DAYS:
        return
    end, start = today - timedelta(days=1), today - timedelta(days=220)
    funds = sorted(PLAN["stock"]["mid"])
    closes = backtest._daily_closes(creds, "/v2/stocks/bars", funds, start, end, feed="iex", adjustment="all")
    closes.update(backtest._daily_closes(creds, "/v1beta3/crypto/us/bars", sorted(PLAN["crypto"]["mid"]), start, end))
    trends = s.setdefault("trends", {})
    for sym, by_day in closes.items():
        c = [by_day[d] for d in sorted(by_day)]
        if len(c) >= TREND_DAYS:
            trends[sym] = c[-1] > sum(c[-TREND_DAYS:]) / TREND_DAYS
    s["trend_checked"], s["trend_assets"] = today.isoformat(), mids


def _sell_position(s, creds, p, reason):
    crypto = p.get("market") == "crypto"
    sell_id = f"sim-sell-{p['symbol'].replace('/', '')}-{core.now():%Y%m%d%H%M}"
    qty = p["qty"]
    if crypto:
        held_qty = stocks._get(PAPER_URL, f"/v2/positions/{p['symbol'].replace('/', '')}", creds).get("qty")
        qty = _smaller(qty, held_qty or qty)
    _post_order(creds, {"symbol": p["symbol"], "qty": qty, "side": "sell", "type": "market",
                        "time_in_force": "gtc" if crypto else "day", "client_order_id": sell_id})
    p.update(status="selling", exit_reason=reason, sell_id=sell_id)
    _save(s)  # recorded right away, so a later failure can't lose this order


def _try_sell(s, creds, p, reason):
    """One refused sell must not stop the other sells, the plan, or saving. It tries again next cycle."""
    try:
        _sell_position(s, creds, p, reason)
        return True
    except Exception as e:
        order_errors.append(f"{p['symbol']} {reason} sell failed: {e}")
        return False


def _run_plan(s, creds, today, is_open):
    """Applies the approved allocation. Long slice first, then mid, at most one buy per market per cycle."""
    s.setdefault("plan_spent", {})
    _update_trends(s, creds, today)
    trends = s.get("trends", {})
    for market, slices in PLAN.items():
        if market == "stock" and not is_open:
            continue
        keys = {f"{sl}:{sym}" for sl, targets in slices.items() for sym in targets}
        for p in s["positions"]:  # positions from an older plan are sold, and their cash joins this one
            key = p.get("plan", "")
            if p.get("market") == market and key and key not in keys and p["status"] == "open" and _try_sell(s, creds, p, "plan change"):
                s["plan_spent"].pop(key, None)
        for p in s["positions"]:  # the mid slice sells when its trend turns down
            key = p.get("plan", "")
            if p.get("market") == market and key.startswith("mid:") and p["status"] == "open" and trends.get(p["symbol"]) is False:
                if _try_sell(s, creds, p, "trend"):
                    s["plan_spent"][key] = 0
        placed = False
        for sym, target in slices["long"].items():
            key = f"long:{sym}"
            left = target - s["plan_spent"].get(key, 0)
            if left >= MIN_ORDER and not any(x.get("plan") == key and x["status"] == "buying" for x in s["positions"]):
                placed = _place_plan_buy(s, creds, market, sym, left, key, True)
                if placed:
                    break
        if placed:
            continue
        for sym, target in slices["mid"].items():
            key = f"mid:{sym}"
            busy = any(x.get("plan") == key and x["status"] in ("buying", "selling") for x in s["positions"])
            left = target - s["plan_spent"].get(key, 0)
            if trends.get(sym) and not busy and left >= MIN_ORDER and _place_plan_buy(s, creds, market, sym, left, key, True):
                break


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
            f.write("# Next picks\n\nApproved allocation: see PLAN in research/sim.py. Buys go long slice first, then mid when its 100-day trend is up (checked weekly), as cash allows.\n")
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
    lines = ["# $2,000 paper simulation", "", "Paper money with simulated fills. No real money, no real fills.", "",
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
    lines += ["", "Rules: approved allocation. Commodities: long $700 in GLD, DBC, DBA and CPER, mid $300 by 100-day trend. "
              "Crypto: long $600 in BTC and ETH, mid $400 by 100-day trend, checked weekly. Positions from an older plan are sold. No short-term slice. No margin. "
              "Trade data is in sim-trades.csv."]
    with open(os.path.join(core.DATA, "sim.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    s["flags"] = metrics.write(s, prices, rows)
    return equity


def cycle(state, errors, creds):
    if not creds:
        return
    try:
        os.makedirs(core.DATA, exist_ok=True)  # the simulation now runs before any step that makes it
        s = _load()
        clock = stocks._get(PAPER_URL, "/v2/clock", creds)
        is_open = clock.get("is_open")
        if s is None:
            s = {"start": core.now().astimezone(stocks.ET).date().isoformat(), "cash": START_CASH, "stock_cash": START_CASH, "positions": [],
                 "spy_start": _price(creds, stocks.BENCH), "last_trade_day": None}
        s.setdefault("stock_cash", START_CASH)  # the crypto budget keeps its history, stocks start fresh
        _sync(s, creds)
        _reconcile_crypto(s, creds)
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
                try:
                    _run_plan(s, creds, today, is_open)
                except OrderRefused as e:
                    order_errors.append(f"plan buy failed: {e}")
            else:
                _buy(s, creds, prices, today, "crypto", True)
                if is_open:
                    _buy(s, creds, prices, today, "stock", et.hour * 60 + et.minute >= ENTRY_MINUTE)
        errors.extend(order_errors)
        order_errors.clear()
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
