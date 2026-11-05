"""Full-cycle test on simulated data. No network, no git. Run: python3 tests/test_cycle.py"""
import csv, io, json, os, shutil, sys, tempfile, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scanner
from research import core, stocks

NOW = datetime.now(timezone.utc)
calls = []
MARKET_OPEN = [True]
FAIL = set()


def bars(sym):
    """Eight sessions of 5-min bars ending now. NVDA spikes up on 4x volume, AAPL moves on normal volume."""
    out, step = [], timedelta(minutes=5)
    for d in range(8, 0, -1):
        for i in range(12):
            t = NOW - timedelta(days=d) - step * (11 - i)
            out.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": 100, "c": 100, "v": 1000})
    for i in range(12):
        t = NOW - step * (11 - i)
        c = {"NVDA": 100 + i, "AAPL": 100 - i}.get(sym, 100)
        v = 4000 if sym == "NVDA" else 1000
        out.append({"t": t.strftime("%Y-%m-%dT%H:%M:%SZ"), "o": c, "c": c, "v": v})
    return out


class Resp(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake_urlopen(req, timeout=None):
    url = req.full_url if hasattr(req, "full_url") else req
    calls.append((getattr(req, "method", None) or "GET", url))
    u = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(u.query)
    if u.hostname in FAIL:
        raise OSError("simulated outage")
    if "coingecko" in u.hostname:
        if u.path.endswith("/coins/markets") and "ids" in q:
            b = [{"id": i, "current_price": 1, "total_volume": 1, "market_cap": 1} for i, _ in scanner.WATCH]
        elif u.path.endswith("/coins/markets"):
            b = [{"id": "bitcoin", "symbol": "btc", "name": "Bitcoin", "current_price": 80000, "total_volume": 10, "price_change_percentage_1h_in_currency": .1},
                 {"id": "pumpcoin", "symbol": "pump", "name": "Pump", "current_price": 2.0, "total_volume": 500, "price_change_percentage_1h_in_currency": 5.0},
                 {"id": "dullcoin", "symbol": "dull", "name": "Dull", "current_price": 1.0, "total_volume": 100, "price_change_percentage_1h_in_currency": -4.0}]
        elif "market_chart" in u.path:
            ms = lambda d: (NOW - timedelta(days=d)).timestamp() * 1000
            # the huge recent sample must not count toward the baseline
            b = {"total_volumes": [[ms(d), 100] for d in range(7, 1, -1)] + [[ms(.1), 5000]]}
        elif u.path.endswith("simple/price"):
            b = {"bitcoin": {"usd": 80800}, "pumpcoin": {"usd": 2.4}, "dullcoin": {"usd": 1.1}}
        elif u.path.endswith("trending"):
            b = {"coins": []}
        else:
            raise AssertionError(url)
        return Resp(json.dumps(b).encode())
    if "news.google" in u.hostname:
        return Resp(b"<rss><channel><item><title>Pump crypto price</title></item></channel></rss>")
    assert req.get_method() == "GET", "only GET is allowed against Alpaca"
    assert "paper-api" in u.hostname or "data.alpaca" in u.hostname, url
    if u.path == "/v2/clock":
        b = {"is_open": MARKET_OPEN[0]}
    elif u.path == "/v2/stocks/bars":
        b = {"bars": {s: bars(s) for s in q["symbols"][0].split(",")}, "next_page_token": None}
    elif u.path == "/v1beta1/news":
        b = {"news": [{}, {}]}
    elif u.path.endswith("/bars"):
        sym = u.path.split("/")[3]
        b = {"bars": [{"t": "x", "c": 105 if sym == "NVDA" else 500}]}
    else:
        raise AssertionError(url)
    return Resp(json.dumps(b).encode())


def rows(p):
    with open(p, newline="") as f:
        return list(csv.DictReader(f))


def main():
    tmp = tempfile.mkdtemp()
    cfg = os.path.join(tmp, ".alpaca-config", "profiles")
    os.makedirs(cfg)
    secret = "SECRETVALUE123"
    open(os.path.join(cfg, "paper.yaml"), "w").write(f"api_key: PKTEST\nsecret_key: {secret}\n")
    os.environ["ALPACA_CONFIG_DIR"] = os.path.dirname(cfg)
    scanner.REPO, core.DATA = tmp, os.path.join(tmp, "data")
    scanner.time.sleep = lambda s: None
    scanner.git = lambda *a: type("R", (), {"returncode": 0, "stderr": "", "stdout": ""})()
    urllib.request.urlopen = fake_urlopen

    scanner.errors.clear()
    scanner.main()
    assert scanner.errors == [], scanner.errors
    sig = rows(os.path.join(core.DATA, "signals.csv"))
    by = {s["symbol"]: s for s in sig}
    assert by["PUMP"]["passed"] == "1" and float(by["PUMP"]["baseline_volume"]) == 100, by["PUMP"]
    assert by["DULL"]["passed"] == "0", "reject must be logged"
    assert by["NVDA"]["passed"] == "1" and by["NVDA"]["news_24h"] == "2", by["NVDA"]
    assert by["AAPL"]["passed"] == "0", by["AAPL"]
    assert "MSFT" not in by, "non-movers are not signals"
    assert any("when%3A1d" in u for _, u in calls), "news must be date-limited"

    n = len(sig)
    scanner.errors.clear()
    scanner.main()
    assert len(rows(os.path.join(core.DATA, "signals.csv"))) == n, "cooldown must stop duplicates"

    # age signals so every horizon is due, then score
    p = os.path.join(core.DATA, "signals.csv")
    old = rows(p)
    for s in old:
        s["time"] = (NOW - timedelta(days=6)).strftime(core.FMT)
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=core.SIGNAL_FIELDS)
        w.writeheader(); w.writerows(old)
    MARKET_OPEN[0] = False
    scanner.errors.clear()
    scanner.main()
    assert scanner.errors == [], scanner.errors
    out = rows(os.path.join(core.DATA, "outcomes.csv"))
    pump = [o for o in out if o["signal_id"] == by["PUMP"]["signal_id"]]
    assert len(pump) == 3 and float(pump[0]["return_pct"]) == 20 and float(pump[0]["excess_pct"]) == 19, pump
    assert float(pump[0]["late_min"]) > 60, "late crypto outcomes must be flagged"
    nv = [o for o in out if o["signal_id"] == by["NVDA"]["signal_id"]]
    assert len(nv) == 3 and float(nv[0]["late_min"]) == 0, nv
    report = open(os.path.join(core.DATA, "report.md")).read()
    assert "stocks | passed" in report, report
    scanner.errors.clear()
    n_out = len(out)
    scanner.main()
    assert len(rows(os.path.join(core.DATA, "outcomes.csv"))) == n_out, "outcomes must not repeat"

    # outage: Alpaca down must not stop crypto; missing keys must not error
    MARKET_OPEN[0] = True
    FAIL.add("paper-api.alpaca.markets")
    scanner.errors.clear()
    scanner.main()
    assert any("stock scan" in e for e in scanner.errors), scanner.errors
    assert "Last stock scan" in open(os.path.join(tmp, "status.md")).read()
    assert os.path.exists(os.path.join(tmp, "watchlist-log.csv"))
    FAIL.clear()
    shutil.move(os.path.dirname(cfg), tmp + "/moved")
    scanner.errors.clear()
    scanner.main()
    assert scanner.errors == [], scanner.errors
    assert "no paper credentials" in open(os.path.join(tmp, "status.md")).read()

    # a live profile must be refused
    os.makedirs(cfg)
    open(os.path.join(cfg, "paper.yaml"), "w").write(f"api_key: AKLIVE\nsecret_key: x\nlive_trade: true\n")
    assert stocks.credentials() is None

    # the secret must never reach anything written to disk
    for dp, _, fs in os.walk(tmp):
        if "moved" in dp or ".alpaca-config" in dp:
            continue
        for fn in fs:
            assert secret not in open(os.path.join(dp, fn), errors="ignore").read(), fn
    print(report)
    print("ALL PASSED", len(calls), "simulated requests")
    shutil.rmtree(tmp)


main()
