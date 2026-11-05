"""Full-cycle test on simulated data. No network, no git. Run: python3 tests/test_cycle.py"""
import csv, io, json, os, shutil, sys, tempfile, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import scanner
from research import core, form4, sim, stocks, wallets

NOW = datetime.now(timezone.utc)
calls = []
MARKET_OPEN = [True]
FAIL = set()
ORDERS, ACCOUNT, FILL, LAST = {}, ["PA123"], [50.0], [50.0]
CRYPTO = [[]]


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
    if u.hostname.endswith("sec.gov"):
        return Resp(sec(u).encode())
    if "news.google" in u.hostname:
        return Resp(b"<rss><channel><item><title>Pump crypto price</title></item></channel></rss>")
    if req.get_method() == "POST":
        assert url == "https://paper-api.alpaca.markets/v2/orders", url
        order = json.loads(req.data)
        ORDERS[order["client_order_id"]] = order
        return Resp(json.dumps({"id": "1", "status": "accepted"}).encode())
    assert req.get_method() == "GET", "only GET and paper orders are allowed against Alpaca"
    assert "paper-api" in u.hostname or "data.alpaca" in u.hostname, url
    if u.path == "/v2/account":
        return Resp(json.dumps({"account_number": ACCOUNT[0]}).encode())
    if u.path == "/v2/assets":
        return Resp(json.dumps(CRYPTO[0]).encode())
    if u.path == "/v1beta3/crypto/us/bars":
        return Resp(json.dumps({"bars": {"BTC/USD": [{"c": 100}] * 12 + [{"c": 102}], "SOL/USD": [{"c": 100}] * 12 + [{"c": 120}]}}).encode())
    if u.path == "/v1beta3/crypto/us/latest/trades":
        return Resp(json.dumps({"trades": {q["symbols"][0]: {"p": LAST[0]}}}).encode())
    if u.path.startswith("/v2/positions/"):
        return Resp(json.dumps({"qty": "1.9"}).encode())
    if u.path.startswith("/v2/assets/"):
        return Resp(json.dumps({"tradable": True, "fractionable": True}).encode())
    if u.path == "/v2/orders:by_client_order_id":
        o = ORDERS[q["client_order_id"][0]]
        px = FILL[0]
        qty = o.get("qty") or str(float(o["notional"]) / px)
        return Resp(json.dumps({"status": "filled", "filled_qty": qty, "filled_avg_price": str(px)}).encode())
    if u.path.endswith("/trades/latest"):
        return Resp(json.dumps({"trade": {"p": LAST[0] if "SPY" not in u.path else 500}}).encode())
    if u.path == "/v2/clock":
        b = {"is_open": MARKET_OPEN[0]}
    elif u.path == "/v2/stocks/bars":
        b = {"bars": {s: bars(s) for s in q["symbols"][0].split(",")}, "next_page_token": None}
    elif u.path == "/v1beta1/news":
        b = {"news": [{"headline": "NVDA Q3 earnings beat"}, {}]}
    elif u.path.endswith("/bars"):
        sym = u.path.split("/")[3]
        if q.get("timeframe") == ["1Day"]:
            if q.get("feed") == ["sip"] and sym == "SMAL":
                raise urllib.error.HTTPError(url, 403, "plan", {}, None)
            b = {"bars": [{"t": "x", "c": 20 if sym == "SMAL" else 100}]}
        else:
            b = {"bars": [{"t": "x", "c": 105 if sym == "NVDA" else 500}]}
    else:
        raise AssertionError(url)
    return Resp(json.dumps(b).encode())


FORM4 = """<SEC-DOCUMENT>
<ACCEPTANCE-DATETIME>20261103173000
<XML>
<?xml version="1.0"?>
<ownershipDocument><documentType>4</documentType>
<issuer><issuerCik>0000555</issuerCik><issuerName>Small Co</issuerName><issuerTradingSymbol>SMAL</issuerTradingSymbol></issuer>
<reportingOwner><reportingOwnerId><rptOwnerCik>%s</rptOwnerCik><rptOwnerName>%s</rptOwnerName></reportingOwnerId>
<reportingOwnerRelationship><isOfficer>1</isOfficer><officerTitle>%s</officerTitle></reportingOwnerRelationship></reportingOwner>
<nonDerivativeTable>%s</nonDerivativeTable></ownershipDocument>
</XML></SEC-DOCUMENT>"""


def txn(code, shares, price, ad="A"):
    return (f"<nonDerivativeTransaction><transactionCoding><transactionCode>{code}</transactionCode></transactionCoding>"
            f"<transactionAmounts><transactionShares><value>{shares}</value></transactionShares>"
            f"<transactionPricePerShare><value>{price}</value></transactionPricePerShare>"
            f"<transactionAcquiredDisposedCode><value>{ad}</value></transactionAcquiredDisposedCode></transactionAmounts>"
            f"<ownershipNature><directOrIndirectOwnership><value>D</value></directOrIndirectOwnership></ownershipNature>"
            f"</nonDerivativeTransaction>")


DOCS = {
    "ceo.txt": FORM4 % ("900", "Jane CEO", "Chief Executive Officer", txn("P", 10000, 10) + txn("P", 10000, 12) + txn("M", 500, 1)),
    "cfo.txt": FORM4 % ("901", "Bob CFO", "CFO", txn("P", 50000, 10)),
    "grant.txt": FORM4 % ("902", "Ann VP", "VP", txn("A", 900, 0)),
    "tax.txt": FORM4 % ("902", "Ann VP", "VP", txn("F", 900, 10, "D")),
    "old.txt": FORM4 % ("900", "Jane CEO", "Chief Executive Officer", txn("P", 1000, 10)),
}


def sec(u):
    p = u.path
    if p.endswith("company_tickers.json"):
        return json.dumps({"0": {"cik_str": 320193, "ticker": "NVDA"}})
    if "/submissions/CIK0000320193" in p:
        today = NOW.strftime("%Y-%m-%d")
        return json.dumps({"filings": {"recent": {"form": ["8-K"], "filingDate": [today], "items": ["2.02,9.01"]}}})
    if "/submissions/" in p:
        return json.dumps({"filings": {"recent": {"form": ["4"], "filingDate": ["2020-01-01"], "accessionNumber": ["old"]}}})
    if "EntityPublicFloat" in p:
        return json.dumps({"units": {"USD": [{"end": "2025-06-30", "val": 300000000}]}})
    if p.endswith("old.txt"):
        return DOCS["old.txt"]
    if ".idx" in p:
        if "form.20261103" not in p and form4_days.get("only") and form4_days["only"] not in p:
            raise urllib.error.HTTPError(u.geturl(), 404, "none", {}, None)
        return ("Form Type  Company  CIK  Date  File Name\n-----\n"
                "4   Small Co   555   2026-11-03   edgar/data/555/ceo.txt\n"
                "4   Jane CEO   900   2026-11-03   edgar/data/555/ceo.txt\n"
                "4   Small Co   555   2026-11-03   edgar/data/555/cfo.txt\n"
                "4   Small Co   555   2026-11-03   edgar/data/555/grant.txt\n"
                "4/A Small Co   555   2026-11-03   edgar/data/555/amend.txt\n"
                "4   Small Co   555   2026-11-03   edgar/data/555/tax.txt\n")
    return DOCS[os.path.basename(p)]


form4_days = {"only": "form.20261103"}


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
    form4.LOG = os.path.join(tmp, "form4-log.csv")
    form4.edgar.CACHE = os.path.join(tmp, "cache")
    form4.edgar.time.sleep = lambda s: None
    state0 = {"buzz": {}, "form4": {"next_day": "2026-11-03", "offset": 0}}
    json.dump(state0, open(os.path.join(tmp, ".state.json"), "w"))
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
    assert by["NVDA"]["earnings"] == "yes", by["NVDA"]
    log = rows(form4.LOG)
    assert [r["insider"] for r in log] == ["Jane CEO", "Bob CFO"], log
    ceo, cfo = log
    assert float(ceo["shares"]) == 20000 and float(ceo["dollar_value"]) == 220000 and float(ceo["price"]) == 11, ceo
    assert ceo["large_vs_pattern"] == "yes" and ceo["prior_buys"] == "1" and ceo["small_company"] == "yes", ceo
    assert ceo["cluster"] == "no" and cfo["cluster"] == "yes", log
    assert ceo["after_close"] == "yes" and ceo["qualifies"] == "yes", ceo
    assert ceo["verified"] == "yes" and float(ceo["entry_close"]) == 20 and float(ceo["spy_entry"]) == 100, ceo
    assert "2 of 10 qualifying" in open(os.path.join(core.DATA, "report.md")).read()
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
    # at 10 qualifying signals the filter table appears, and reviews come due
    open(os.path.join(cfg, "paper.yaml"), "w").write(f"api_key: PKTEST\nsecret_key: {secret}\n")
    log = rows(form4.LOG)
    extra = [dict(log[0], accession=f"x{i}", url="https://www.sec.gov/Archives/edgar/data/555/ceo.txt",
                  filing_date="2026-01-05", entry_close="10", spy_entry="100") for i in range(8)]
    with open(form4.LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=form4.FIELDS)
        w.writeheader(); w.writerows(log + extra)
    scanner.errors.clear()
    scanner.main()
    assert scanner.errors == [], scanner.errors
    report = open(os.path.join(core.DATA, "report.md")).read()
    assert "| Cluster | yes |" in report and " / 7 " in report, report
    o = rows(os.path.join(core.DATA, "form4-outcomes.csv"))
    assert o and float(o[0]["return_pct"]) == 100 and o[0]["beat_spy"] == "yes", o[:1]

    # pre-market gap: closed market, next open today, 8:30 ET
    trade_t = NOW.strftime("%Y-%m-%dT%H:%M:%SZ")
    payload = {"AAPL": {"latestTrade": {"p": 106, "t": trade_t}, "dailyBar": {"c": 100, "t": "2026-01-02T05:00:00Z"}},
               "MSFT": {"latestTrade": {"p": 101, "t": trade_t}, "dailyBar": {"c": 100, "t": "2026-01-02T05:00:00Z"}},
               "SPY": {"latestTrade": {"p": 500, "t": trade_t}}}
    orig_get = stocks._get
    stocks._get = lambda b, r, c, **p: payload if "snapshots" in r else orig_get(b, r, c, **p)
    orig_now = core.now
    st = {"signal_seen": {}}
    core.now = lambda: NOW.astimezone(stocks.ET).replace(hour=8, minute=30)
    payload["AAPL"]["latestTrade"]["t"] = payload["MSFT"]["latestTrade"]["t"] = payload["SPY"]["latestTrade"]["t"] = \
        core.now().astimezone(timezone.utc).strftime(core.FMT)
    before = len(rows(os.path.join(core.DATA, "signals.csv")))
    stocks.premarket_gaps(st, {}, {"next_open": core.now().strftime("%Y-%m-%dT09:30:00-05:00")}, [])
    core.now, stocks._get = orig_now, orig_get
    after = rows(os.path.join(core.DATA, "signals.csv"))
    assert len(after) == before + 1 and after[-1]["symbol"] == "AAPL" and after[-1]["signal_type"] == "premarket_gap", after[-1]

    # paper simulation: buy at 3:30 ET, fill, reinvest, stop out, refuse a non-paper account, kill switch
    ORDERS.clear()
    state = {}
    for fn in ("sim-state.json", "sim-trades.csv"):
        if os.path.exists(os.path.join(core.DATA, fn)):
            os.remove(os.path.join(core.DATA, fn))
    et_clock = NOW.astimezone(stocks.ET).replace(hour=15, minute=35)
    day = et_clock.date()
    core.now = lambda: et_clock
    with open(os.path.join(core.DATA, "signals.csv"), "a", newline="") as f:
        csv.DictWriter(f, fieldnames=core.SIGNAL_FIELDS, restval="").writerow(
            {"market": "stocks", "symbol": "WIN", "time": day.isoformat() + "T15:00:00Z", "passed": 1,
             "signal_type": "move_1h", "move_1h_pct": 4, "volume_ratio": 3})
    open(form4.LOG, "w").write(",".join(form4.FIELDS) + "\n")
    MARKET_OPEN[0] = True
    creds = stocks.credentials()
    errs = []
    ACCOUNT[0] = "LIVE999"
    sim.cycle(state, errs, creds)
    assert not ORDERS and any("not a paper account" in e for e in errs), (ORDERS, errs)
    ACCOUNT[0] = "PA123"
    errs.clear()
    os.remove(os.path.join(core.DATA, "sim-state.json")) if os.path.exists(os.path.join(core.DATA, "sim-state.json")) else None
    sim.cycle(state, errs, creds)
    assert errs == [], errs
    buy = ORDERS[f"sim-buy-WIN-{day:%Y%m%d}"]
    assert buy["notional"] == "100.0" and buy["side"] == "buy", buy
    sim.cycle(state, errs, creds)  # fill arrives, and no second buy the same day
    assert len(ORDERS) == 1, ORDERS
    s = sim._load()
    assert s["positions"][0]["status"] == "open" and abs(s["cash"] - 900) < 1e-6, s
    LAST[0] = 56.0
    sim.cycle(state, errs, creds)  # +12% hits the target
    assert sum(o["side"] == "sell" for o in ORDERS.values()) == 1, ORDERS
    FILL[0] = 56.0
    sim.cycle(state, errs, creds)
    s = sim._load()
    assert not s["positions"] and abs(s["cash"] - 1012) < 1e-6, s
    t = rows(os.path.join(core.DATA, "sim-trades.csv"))[0]
    assert abs(float(t["pnl"]) - 12) < 1e-3 and t["exit_reason"] == "target" and t["thesis"] and t["against"], t
    assert errs == [], errs
    assert "$1,012.00" in open(os.path.join(core.DATA, "sim.md")).read()
    next_day = et_clock + timedelta(days=1)
    core.now = lambda: next_day
    open(os.path.join(tmp, "SIM_STOP"), "w").close()
    sim.ROOT = tmp
    n = len(ORDERS)
    sim.cycle(state, errs, creds)
    assert len(ORDERS) == n and "STOPPED" in state["last_sim"], state
    core.now = orig_now

    # crypto buys with the stock market closed, then sells what the account really holds
    os.remove(os.path.join(tmp, "SIM_STOP"))
    os.remove(os.path.join(core.DATA, "sim-state.json"))
    ORDERS.clear()
    CRYPTO[0] = [{"symbol": "SOL/USD", "tradable": True}, {"symbol": "BTC/USD", "tradable": True}, {"symbol": "USDC/USD", "tradable": True}]
    MARKET_OPEN[0] = False
    FILL[0], LAST[0] = 50.0, 50.0
    night = NOW.astimezone(stocks.ET).replace(hour=1, minute=0)
    core.now = lambda: night
    errs.clear()
    sim.cycle(state, errs, creds)
    assert errs == [], errs
    buy = [o for o in ORDERS.values() if o["side"] == "buy"]
    assert len(buy) == 1 and buy[0]["symbol"] == "SOL/USD" and buy[0]["time_in_force"] == "gtc", ORDERS
    sim.cycle(state, errs, creds)
    assert len(ORDERS) == 1, "one crypto buy a day"
    LAST[0] = 56.0
    sim.cycle(state, errs, creds)
    sell = [o for o in ORDERS.values() if o["side"] == "sell"]
    assert len(sell) == 1 and sell[0]["qty"] == "1.9" and sell[0]["time_in_force"] == "gtc", ORDERS
    FILL[0] = 56.0
    sim.cycle(state, errs, creds)
    assert errs == [] and not sim._load()["positions"], errs

    # a stock with no signal today falls back to the month's numbers, and only after 10:30 ET
    CRYPTO[0] = []
    MARKET_OPEN[0] = True
    os.remove(os.path.join(core.DATA, "sim-state.json"))
    with open(os.path.join(core.DATA, "signals.csv"), "w", newline="") as f:
        csv.DictWriter(f, fieldnames=core.SIGNAL_FIELDS).writeheader()
    ORDERS.clear()
    orig_daily = sim._daily_stock_closes
    sim._daily_stock_closes = lambda c, s, t: {"SPY": [100] * 19 + [101], "AAPL": [100] * 19 + [99], "MSFT": [100] * 19 + [115]}
    early = NOW.astimezone(stocks.ET).replace(hour=10, minute=0)
    core.now = lambda: early
    sim.cycle(state, errs, creds)
    assert not ORDERS, "too early"
    later = NOW.astimezone(stocks.ET).replace(hour=10, minute=35)
    core.now = lambda: later
    sim.cycle(state, errs, creds)
    assert errs == [], errs
    picked = list(ORDERS.values())
    assert len(picked) == 1 and picked[0]["symbol"] == "MSFT", ORDERS
    assert "month" in sim._load()["positions"][0]["thesis"]
    sim._daily_stock_closes = orig_daily
    core.now = orig_now

    # wallet watch: first look is a baseline, later only new moves log, and incomplete rows are refused
    addr = "bc1q" + "a" * 38
    fields = ["number", "owner", "category", "enabled", "chain", "address", "attribution_source", "last_verified", "profile", "notes"]
    wallets.LIST = os.path.join(tmp, "w.csv")
    with open(wallets.LIST, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, restval="")
        w.writeheader()
        w.writerow({"owner": "Good Co", "category": "company", "enabled": "yes", "chain": "bitcoin", "address": addr, "attribution_source": "filing", "last_verified": "2026-11-05"})
        w.writerow({"owner": "No Source", "enabled": "yes", "chain": "bitcoin", "address": addr})
        w.writerow({"owner": "Off", "enabled": "no"})
    feed = [[("t1", "in", 1.0, "BTC", 1)]]
    wallets.READERS["bitcoin"] = lambda a: feed[0]
    st, errs2 = {}, []
    wallets.cycle(st, errs2)
    assert not os.path.exists(os.path.join(core.DATA, "wallet-moves.csv")), "baseline must not log history"
    assert any("No Source" in e for e in errs2), errs2
    feed[0] = [("t2", "out", 2.5, "BTC", 2), ("t1", "in", 1.0, "BTC", 1)]
    wallets.cycle(st, [])
    moves = rows(os.path.join(core.DATA, "wallet-moves.csv"))
    assert [m["tx"] for m in moves] == ["t2"] and moves[0]["owner"] == "Good Co", moves
    assert wallets.admitted({"chain": "ethereum", "address": "0xabc", "attribution_source": "x", "last_verified": "y"})

    # measured schedule: runs five minutes apart report five
    s = {"last_run": (NOW - timedelta(minutes=5)).strftime(core.FMT)}
    assert scanner.cycle_minutes(s) == 5
    print(report)
    print("ALL PASSED", len(calls), "simulated requests")
    shutil.rmtree(tmp)


main()
