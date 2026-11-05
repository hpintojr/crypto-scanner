"""Biggest gainers and losers over each time window, with hourly streaks. Research only, no orders.

Writes data/movers.md once an hour. Crypto covers CoinGecko's top 100. Stocks cover the fixed list and only
trade part of the day, so their windows reach back to the last price at or before that time.
"""
import json, os, urllib.request
from datetime import timedelta
from . import core, stocks

WINDOWS = (1, 2, 4, 6, 8, 12, 16, 20, 24)
TOP = 5
CG_URL = ("https://api.coingecko.com/api/v3/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1"
          "&sparkline=true")
PEGGED = {"usdt", "usdc", "dai", "usde", "usds", "fdusd", "tusd", "usdg", "pyusd", "rlusd", "busd", "usd1", "usdd",
          "gusd", "frax", "paxg", "xaut", "wbtc", "steth", "wsteth", "weth", "cbbtc", "weeth", "reth", "wbeth"}


def streak(closes):
    """Consecutive up (+) or down (-) hours ending at the latest close."""
    run = 0
    for a, b in zip(reversed(closes[:-1]), reversed(closes)):
        step = 1 if b > a else -1 if b < a else 0
        if step == 0 or (run and (step > 0) != (run > 0)):
            break
        run += step
    return run


def rank(series):
    """series is {symbol: [(hours_ago, close), ...]}, oldest first. Returns {window: (gainers, losers)}."""
    out = {}
    for w in WINDOWS:
        rows = []
        for sym, pts in series.items():
            past = [c for ago, c in pts if ago >= w]
            if past and past[-1] > 0:
                closes = [c for _, c in pts]
                rows.append((sym, (closes[-1] / past[-1] - 1) * 100, streak(closes)))
        rows.sort(key=lambda r: r[1], reverse=True)
        out[w] = ([r for r in rows[:TOP] if r[1] > 0], [r for r in rows[::-1][:TOP] if r[1] < 0])
    return out


def _table(title, ranked):
    fmt = lambda rs: ", ".join(f"{s} {m:+.1f}% ({'+' if k > 0 else ''}{k}h)" for s, m, k in rs) or "none"
    lines = [f"## {title}", "", "| Window | Biggest gainers | Biggest losers |", "|---|---|---|"]
    lines += [f"| {w}h | {fmt(ranked[w][0])} | {fmt(ranked[w][1])} |" for w in WINDOWS]
    return lines + [""]


def _crypto():
    req = urllib.request.Request(CG_URL, headers={"User-Agent": "crypto-scanner-research/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        coins = json.loads(r.read())
    series = {}
    for c in coins:
        prices = (c.get("sparkline_in_7d") or {}).get("price") or []
        if c.get("symbol", "").lower() in PEGGED or len(prices) < 30:
            continue
        hourly = (len(prices) - 1) / 168 if len(prices) > 1 else 1  # about one point an hour over 7 days
        step = max(hourly, 1e-9)
        n = len(prices)
        series[c["symbol"].upper()] = [((n - 1 - i) / step, p) for i, p in enumerate(prices) if (n - 1 - i) / step <= 48]
    return series


def _stocks(creds):
    t = core.now()
    symbols = stocks.universe()
    data, token = {}, None
    while True:
        params = dict(symbols=",".join(symbols), timeframe="1Hour", start=stocks._stamp(t - timedelta(days=5)),
                      end=stocks._stamp(t), feed="iex", limit=10000, sort="asc", adjustment="split")
        if token:
            params["page_token"] = token
        page = stocks._get(stocks.DATA_URL, "/v2/stocks/bars", creds, **params)
        for sym, bars in (page.get("bars") or {}).items():
            data.setdefault(sym, []).extend(bars)
        token = page.get("next_page_token")
        if not token:
            break
    # a bar closes an hour after it opens, and hours_ago counts back from the latest close
    return {s: [((stocks._bar_time(b[-1]) - stocks._bar_time(x)).total_seconds() / 3600, x["c"]) for x in b]
            for s, b in data.items() if len(b) > 1}


def cycle(state, errors, creds):
    last = state.get("movers_checked")
    if last and core.now() - core.parse(last) < timedelta(minutes=55):
        return
    lines = ["# Biggest movers", "", f"As of {core.now().strftime(core.FMT)}. In brackets: the hourly streak, so (+3h) means three "
             "up hours in a row, and (-2h) two down hours. Research only, no orders. Past moves don't predict the next one.", ""]
    ok = False
    for title, fn in (("Crypto, top 100", _crypto), ("Stocks, fixed list", (lambda: _stocks(creds)) if creds else None)):
        if not fn:
            continue
        try:
            lines += _table(title, rank(fn()))
            ok = True
        except Exception as e:
            errors.append(f"movers ({title}): {type(e).__name__}: {e}")
    if ok:
        os.makedirs(core.DATA, exist_ok=True)
        with open(os.path.join(core.DATA, "movers.md"), "w") as f:
            f.write("\n".join(lines) + "\n")
        state["movers_checked"] = core.now().strftime(core.FMT)
