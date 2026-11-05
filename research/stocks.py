"""US stock mover scan from Alpaca's free IEX feed. Read-only: this module only ever sends GET."""
import json, os, urllib.parse, urllib.request
from datetime import timedelta
from zoneinfo import ZoneInfo
from . import core

DATA_URL = "https://data.alpaca.markets"
PAPER_URL = "https://paper-api.alpaca.markets"
ET = ZoneInfo("America/New_York")
BENCH = "SPY"
MOVE_PCT = 2.0
VOLUME_RATIO = 2.0
MAX_SCORES = 30  # outcome lookups per cycle
HERE = os.path.dirname(os.path.abspath(__file__))


def universe():
    with open(os.path.join(HERE, "stock_universe.txt")) as f:
        return f.read().split()


def _config_dir():
    d = os.environ.get("ALPACA_CONFIG_DIR")
    if d:
        return d
    p = os.path.dirname(HERE)
    for _ in range(4):  # the config folder sits beside the repo, never inside it
        p = os.path.dirname(p)
        if os.path.isdir(os.path.join(p, ".alpaca-config")):
            return os.path.join(p, ".alpaca-config")
    return os.path.expanduser("~/.config/alpaca")


def credentials():
    """Paper profile keys, or None. Refuses anything marked live."""
    if os.environ.get("ALPACA_API_KEY") and os.environ.get("ALPACA_SECRET_KEY"):
        key, secret = os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]
    else:
        try:
            with open(os.path.join(_config_dir(), "profiles", "paper.yaml")) as f:
                prof = dict(l.split(":", 1) for l in f.read().splitlines() if ":" in l)
        except OSError:
            return None
        prof = {k.strip(): v.strip().strip("'\"") for k, v in prof.items()}
        if prof.get("live_trade", "false").lower() == "true":
            return None
        key, secret = prof.get("api_key"), prof.get("secret_key")
    if not key or not secret or not key.startswith("PK"):
        return None
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}


def _get(base, route, creds, **params):
    url = base + route + ("?" + urllib.parse.urlencode(params) if params else "")
    req = urllib.request.Request(url, headers=creds, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _stamp(t):
    return t.strftime(core.FMT)


def _bar_time(bar):
    return core.parse(bar["t"][:19] + "Z")


def _bars(creds, symbols, start, end):
    out, token = {}, None
    while True:
        params = dict(symbols=",".join(symbols), timeframe="5Min", start=_stamp(start), end=_stamp(end),
                      feed="iex", limit=10000, sort="asc")
        if token:
            params["page_token"] = token
        page = _get(DATA_URL, "/v2/stocks/bars", creds, **params)
        for sym, bars in (page.get("bars") or {}).items():
            out.setdefault(sym, []).extend(bars)
        token = page.get("next_page_token")
        if not token:
            return out


def _measure(bars, t):
    """1h move and same-time-of-day volume ratio, IEX against IEX. None if data is too thin."""
    if not bars or t - _bar_time(bars[-1]) > timedelta(minutes=15):
        return None
    last = _bar_time(bars[-1])
    cutoff = last - timedelta(minutes=60)
    window = [b for b in bars if _bar_time(b) > cutoff]
    if len(window) < 6 or window[0]["o"] <= 0:
        return None
    et_last = last.astimezone(ET)
    today = et_last.date()
    end_min = et_last.hour * 60 + et_last.minute
    start_min = end_min - 60
    by_day = {}
    for b in bars:
        e = _bar_time(b).astimezone(ET)
        minute = e.hour * 60 + e.minute
        if e.date() != today and start_min < minute <= end_min:
            by_day[e.date()] = by_day.get(e.date(), 0) + b["v"]
    if len(by_day) < 3:
        return None
    baseline = sum(by_day.values()) / len(by_day)
    volume = sum(b["v"] for b in window)
    return {"price": window[-1]["c"], "move": (window[-1]["c"] / window[0]["o"] - 1) * 100,
            "volume": volume, "baseline": baseline, "ratio": volume / baseline if baseline else 0}


def scan(state, errors):
    creds = credentials()
    if not creds:
        state["last_stock_scan"] = f"{_stamp(core.now())}: skipped, no paper credentials readable"
        return None
    try:
        if not _get(PAPER_URL, "/v2/clock", creds).get("is_open"):
            state["last_stock_scan"] = f"{_stamp(core.now())}: market closed"
            return creds
        t = core.now()
        symbols = universe()
        data = _bars(creds, symbols + [BENCH], t - timedelta(days=9), t)
        spy = data.get(BENCH) or []
        if not spy:
            raise ValueError("no SPY bars")
        movers = kept = thin = 0
        for sym in symbols:
            m = _measure(data.get(sym), t)
            if not m:
                thin += 1
                continue
            if abs(m["move"]) < MOVE_PCT:
                continue
            movers += 1
            passed = m["ratio"] >= VOLUME_RATIO
            kept += passed
            news = ""
            try:
                news = len(_get(DATA_URL, "/v1beta1/news", creds, symbols=sym, limit=50,
                                start=_stamp(t - timedelta(hours=24))).get("news") or [])
            except Exception:
                pass  # optional feature, leave blank
            core.log_signal(state, market="stocks", symbol=sym, asset_id=sym, name=sym, price=m["price"],
                            benchmark=BENCH, benchmark_price=spy[-1]["c"], move=m["move"],
                            volume=m["volume"], baseline=m["baseline"], ratio=m["ratio"],
                            passed=passed, news=news)
        state["last_stock_scan"] = (f"{_stamp(t)}: {len(symbols)} stocks, {movers} movers over {MOVE_PCT}% 1h, "
                                    f"{kept} kept after {VOLUME_RATIO:g}x volume check, {thin} without enough data")
    except Exception as e:
        errors.append(f"stock scan: {type(e).__name__}: {e}")
    return creds


def _price_at(creds, sym, due, cache):
    if (sym, due) not in cache:
        page = _get(DATA_URL, f"/v2/stocks/{sym}/bars", creds, timeframe="5Min", feed="iex", sort="desc",
                    limit=1, start=_stamp(due - timedelta(days=6)), end=_stamp(due))
        bars = page.get("bars") or []
        cache[(sym, due)] = bars[0]["c"] if bars else None
    return cache[(sym, due)]


def score(creds, errors):
    if not creds:
        return
    cache = {}
    try:
        for sig, horizon, due in core.pending("stocks")[:MAX_SCORES]:
            price = _price_at(creds, sig["symbol"], due, cache)
            bench = _price_at(creds, sig["benchmark"], due, cache)
            if price and bench:
                core.record_outcome(sig, horizon, due, price, bench, as_of_due=True)
    except Exception as e:
        errors.append(f"stock scoring: {type(e).__name__}: {e}")
