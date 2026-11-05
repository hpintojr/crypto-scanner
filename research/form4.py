"""Form 4 insider-buy research log. Logs code P open-market buys from EDGAR and scores them. No orders.

CLUSTER_DAYS, LARGE_* and SMALL_FLOAT are choices made where the brief left a number open.
Politician trades don't appear here: they aren't filed on Form 4.
"""
import csv, os, re, statistics, time, urllib.error
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from . import core, edgar, stocks

CLUSTER_DAYS = 14          # another insider's buy at the same company in the prior 14 days
LARGE_VS_MEDIAN = 2.0      # at least 2x this insider's median earlier buy
LARGE_NO_HISTORY = 100_000 # with no earlier buys, $100k or more counts as large
SMALL_FLOAT = 2_000_000_000
TARGET = 10
MAX_FILINGS = 120
MAX_SECONDS = 60
REVIEWS = {"30d": 30, "90d": 90, "180d": 180}
ET_ZONE = ZoneInfo("America/New_York")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "research", "form4-log.csv")
FIELDS = ["filing_date", "accepted_et", "after_close", "ticker", "issuer", "issuer_cik", "insider", "insider_cik",
          "role", "ceo_cfo", "shares", "price", "dollar_value", "ownership", "prior_buys", "median_prior_value",
          "large_vs_pattern", "cluster", "public_float", "small_company", "qualifies", "entry_close", "spy_entry",
          "verified", "accession", "url"]
OUT_FIELDS = ["accession", "review", "due", "close", "spy_close", "return_pct", "spy_return_pct", "beat_spy"]
CEO_CFO = re.compile(r"\b(CEO|CFO)\b|CHIEF EXECUTIVE|CHIEF FINANCIAL|PRINCIPAL EXECUTIVE|PRINCIPAL FINANCIAL", re.I)


def _rows():
    if not os.path.exists(LOG):
        return []
    with open(LOG, newline="") as f:
        return list(csv.DictReader(f))


def _save(rows):
    with open(LOG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)


def _val(node, path):
    return (node.findtext(path + "/value") or node.findtext(path) or "").strip() if node is not None else ""


def parse_filing(text):
    """Parse a Form 4 full-submission file. Returns the summed code P buys, or None if there are none."""
    m = re.search(r"<XML>(.*?)</XML>", text, re.S)
    if not m:
        return None
    doc = ET.fromstring(m.group(1).strip().encode())
    if (doc.findtext("documentType") or "").strip() != "4":
        return None
    shares = value = 0.0
    kinds = set()
    for t in doc.findall("nonDerivativeTable/nonDerivativeTransaction"):
        code = (t.findtext("transactionCoding/transactionCode") or "").strip()
        if code != "P" or _val(t, "transactionAmounts/transactionAcquiredDisposedCode") != "A":
            continue  # P only, which leaves out exercises (M), grants (A) and tax withholding (F)
        s = float(_val(t, "transactionAmounts/transactionShares") or 0)
        p = float(_val(t, "transactionAmounts/transactionPricePerShare") or 0)
        if s > 0 and p > 0:
            shares += s
            value += s * p
            kinds.add(_val(t, "ownershipNature/directOrIndirectOwnership"))
    if shares <= 0:
        return None
    owners = doc.findall("reportingOwner")
    owner = next((o for o in owners if CEO_CFO.search(o.findtext("reportingOwnerRelationship/officerTitle") or "")), owners[0])
    rel = owner.find("reportingOwnerRelationship")
    role = (rel.findtext("officerTitle") or "").strip()
    if not role:
        flags = {"isDirector": "Director", "isTenPercentOwner": "10% owner", "isOfficer": "Officer"}
        role = ", ".join(n for k, n in flags.items() if (rel.findtext(k) or "").strip().lower() in ("1", "true"))
    a = re.search(r"<ACCEPTANCE-DATETIME>(\d{14})", text)
    accepted = datetime.strptime(a.group(1), "%Y%m%d%H%M%S") if a else None
    return {"ticker": (doc.findtext("issuer/issuerTradingSymbol") or "").strip().upper(),
            "issuer": (doc.findtext("issuer/issuerName") or "").strip(),
            "issuer_cik": (doc.findtext("issuer/issuerCik") or "").strip().lstrip("0"),
            "insider": (owner.findtext("reportingOwnerId/rptOwnerName") or "").strip(),
            "insider_cik": (owner.findtext("reportingOwnerId/rptOwnerCik") or "").strip().lstrip("0"),
            "role": role, "ceo_cfo": "yes" if CEO_CFO.search(role) else "no",
            "shares": shares, "price": round(value / shares, 4), "dollar_value": round(value, 2),
            "ownership": "/".join(sorted(k for k in kinds if k)),
            "accepted_et": accepted.strftime("%Y-%m-%d %H:%M") if accepted else "",
            "after_close": "" if not accepted else "yes" if accepted.time() >= datetime(2000, 1, 1, 16).time() else "no"}


def _pattern(buy, filing_date):
    """Earlier code P buys by this insider at this company, from their last 15 Form 4s."""
    rec = edgar.submissions(buy["insider_cik"])
    values, checked = [], 0
    for form, when, acc in zip(rec.get("form", []), rec.get("filingDate", []), rec.get("accessionNumber", [])):
        if form != "4" or when >= filing_date or checked >= 15:
            continue
        checked += 1
        old = parse_filing(edgar.get(f"https://www.sec.gov/Archives/edgar/data/{buy['insider_cik']}/{acc}.txt", raw=True))
        if old and old["issuer_cik"] == buy["issuer_cik"]:
            values.append(old["dollar_value"])
    median = statistics.median(values) if values else ""
    large = buy["dollar_value"] >= (LARGE_VS_MEDIAN * median if values else LARGE_NO_HISTORY)
    return len(values), median, "yes" if large else "no"


def _enrich(buy, filing_date, rows):
    buy["filing_date"] = filing_date
    start = (date.fromisoformat(filing_date) - timedelta(days=CLUSTER_DAYS)).isoformat()
    others = {r["insider_cik"] for r in rows if r["issuer_cik"] == buy["issuer_cik"]
              and start <= r["filing_date"] <= filing_date and r["insider_cik"] != buy["insider_cik"]}
    buy["cluster"] = "yes" if others else "no"
    buy.update(prior_buys="", median_prior_value="", large_vs_pattern="", public_float="", small_company="")
    if buy["ceo_cfo"] == "yes":  # history and float lookups only where the filter can matter
        buy["prior_buys"], buy["median_prior_value"], buy["large_vs_pattern"] = _pattern(buy, filing_date)
        try:
            pf = edgar.public_float(buy["issuer_cik"])
        except urllib.error.HTTPError:
            pf = None
        if pf:
            buy["public_float"], buy["small_company"] = pf, "yes" if pf < SMALL_FLOAT else "no"
    buy["qualifies"] = "yes" if (buy["ceo_cfo"] == "yes" and buy["large_vs_pattern"] == "yes"
                                 and buy["small_company"] == "yes") else "no"
    buy["entry_close"] = buy["spy_entry"] = buy["verified"] = ""


def _load_index(day):
    """Accession paths for all Form 4s filed that day, cached so a cycle can resume."""
    os.makedirs(edgar.CACHE, exist_ok=True)
    path = os.path.join(edgar.CACHE, f"form4-{day:%Y%m%d}.txt")
    if not os.path.exists(path):
        q = (day.month - 1) // 3 + 1
        text = edgar.get(f"https://www.sec.gov/Archives/edgar/daily-index/{day.year}/QTR{q}/form.{day:%Y%m%d}.idx", raw=True)
        seen = {}
        for line in text.splitlines():
            parts = line.split()
            if len(parts) > 3 and parts[0] == "4" and parts[-1].startswith("edgar/data/"):
                seen.setdefault(os.path.basename(parts[-1]), parts[-1])
        with open(path, "w") as f:
            f.write("\n".join(seen.values()))
    with open(path) as f:
        return f.read().split()


def _collect(state, errors):
    st = state.setdefault("form4", {})
    today = core.now().astimezone(ET_ZONE).date()
    day = date.fromisoformat(st["next_day"]) if st.get("next_day") else today - timedelta(days=3)
    offset = st.get("offset", 0)
    started, handled, added = time.time(), 0, 0
    rows = _rows()
    known = {r["accession"] for r in rows}
    while day < today and handled < MAX_FILINGS and time.time() - started < MAX_SECONDS:
        try:
            paths = _load_index(day)
        except urllib.error.HTTPError as e:
            if e.code == 404 and (day.weekday() >= 5 or today - day > timedelta(days=2)):
                day, offset = day + timedelta(days=1), 0  # weekend or holiday: no index that day
                continue
            if e.code != 404:
                raise
            break  # today's newest index isn't published yet
        while offset < len(paths) and handled < MAX_FILINGS and time.time() - started < MAX_SECONDS:
            p = paths[offset]
            offset += 1
            handled += 1
            acc = os.path.basename(p)[:-4]
            if acc in known:
                continue
            try:
                buy = parse_filing(edgar.get("https://www.sec.gov/Archives/" + p, raw=True))
            except ET.ParseError:
                continue
            if not buy or not buy["ticker"] or buy["ticker"] in ("NONE", "N/A", "NA"):
                continue
            _enrich(buy, day.isoformat(), rows)
            buy["accession"], buy["url"] = acc, "https://www.sec.gov/Archives/" + p
            rows.append(buy)
            known.add(acc)
            added += 1
            _save(rows)
        st["next_day"], st["offset"] = day.isoformat(), offset
        if offset >= len(paths):
            day, offset = day + timedelta(days=1), 0
            st["next_day"], st["offset"] = day.isoformat(), 0
    st["next_day"], st["offset"] = day.isoformat(), offset
    state["last_form4"] = (f"{core.now().strftime(core.FMT)}: {handled} filings read, {added} code P buys added, "
                           f"working on {day.isoformat()}, {len(rows)} logged, "
                           f"{sum(r['qualifies'] == 'yes' for r in rows)} qualifying")


def _verify(rows):
    """Second read of each new row from EDGAR. Only verified rows count in the review."""
    changed = False
    for r in [r for r in rows if not r["verified"]][:20]:
        again = parse_filing(edgar.get(r["url"], raw=True))
        ok = bool(again) and again["ticker"] == r["ticker"] and again["insider_cik"] == r["insider_cik"] \
            and abs(again["shares"] - float(r["shares"])) < 1e-6 and abs(again["price"] - float(r["price"])) < 1e-3
        r["verified"] = "yes" if ok else "no"
        changed = True
    return changed


def _close(creds, sym, day):
    """Last official daily close on or before day. Consolidated feed first, IEX if the plan refuses it."""
    for feed in ("sip", "iex"):
        try:
            page = stocks._get(stocks.DATA_URL, f"/v2/stocks/{sym}/bars", creds, timeframe="1Day",
                               feed=feed, sort="desc", limit=1, adjustment="split",
                               start=(day - timedelta(days=7)).isoformat(), end=day.isoformat())
        except urllib.error.HTTPError as e:
            if e.code in (403, 422) and feed == "sip":
                continue
            raise
        bars = page.get("bars") or []
        if bars:
            return bars[0]["c"]
    return None


def _prices(rows, creds):
    changed = False
    today = core.now().astimezone(ET_ZONE).date()
    for r in [r for r in rows if not r["entry_close"]][:20]:
        day = date.fromisoformat(r["filing_date"])
        if day >= today:
            continue  # the filing day's close isn't final yet
        close, spy = _close(creds, r["ticker"], day), _close(creds, stocks.BENCH, day)
        if close and spy:
            r["entry_close"], r["spy_entry"] = close, spy
            changed = True
    return changed


def _outcomes():
    return core.read("form4-outcomes.csv")


def _review(rows, creds):
    done = {(o["accession"], o["review"]) for o in _outcomes()}
    today = core.now().astimezone(ET_ZONE).date()
    new, calls = [], 0
    for r in rows:
        if not r["entry_close"]:
            continue
        for name, days in REVIEWS.items():
            due = date.fromisoformat(r["filing_date"]) + timedelta(days=days)
            if due >= today or (r["accession"], name) in done or calls >= 20:
                continue
            calls += 1
            close, spy = _close(creds, r["ticker"], due), _close(creds, stocks.BENCH, due)
            if close and spy:
                ret = (close / float(r["entry_close"]) - 1) * 100
                bench = (spy / float(r["spy_entry"]) - 1) * 100
                new.append({"accession": r["accession"], "review": name, "due": due.isoformat(), "close": close,
                            "spy_close": spy, "return_pct": round(ret, 3), "spy_return_pct": round(bench, 3),
                            "beat_spy": "yes" if ret > bench else "no"})
    core._append("form4-outcomes.csv", OUT_FIELDS, new)


def cycle(state, errors, creds):
    try:
        _collect(state, errors)
        rows = _rows()
        if _verify(rows):
            _save(rows)
        if creds:
            if _prices(rows, creds):
                _save(rows)
            _review(rows, creds)
    except urllib.error.HTTPError as e:
        if e.code in (403, 429):
            state["last_form4"] = (f"{core.now().strftime(core.FMT)}: blocked by SEC (HTTP {e.code}). "
                                   "SEC wants a contact in the User-Agent, set it in .sec-user-agent beside the repo")
        errors.append(f"form4: HTTP {e.code} {e.url.split('?')[0]}")
    except Exception as e:
        errors.append(f"form4: {type(e).__name__}: {e}")


def append_report():
    rows = [r for r in _rows() if r["verified"] == "yes"]
    signals = [r for r in rows if r["qualifies"] == "yes"]
    out = _outcomes()
    lines = ["", "## Form 4 insider buys", "",
             f"{len(rows)} verified code P buys logged. {len(signals)} of {TARGET} qualifying signals "
             "(CEO or CFO, large vs their pattern, small company). Entry is the close on filing day, against SPY.",
             f"{sum(r['after_close'] == 'yes' for r in signals)} of the qualifying signals were filed after the close, "
             "so that entry price could not really have been traded."]
    if len(signals) < TARGET:
        lines += ["", f"The filter breakdown starts at {TARGET} qualifying signals."]
    else:
        by = {(o["accession"], o["review"]): o["beat_spy"] for o in out}
        filters = [("CEO or CFO", "ceo_cfo"), ("Large vs pattern", "large_vs_pattern"), ("Cluster", "cluster"),
                   ("Small company", "small_company"), ("Filed after close", "after_close")]
        lines += ["", "Beat SPY, one filter at a time, across all verified buys:", "",
                  "| Filter | Value | 90d beat / reviewed | 180d beat / reviewed |", "|---|---|---:|---:|"]
        for label, col in filters:
            for v in ("yes", "no"):
                cells = []
                for rev in ("90d", "180d"):
                    res = [by[(r["accession"], rev)] for r in rows if r[col] == v and (r["accession"], rev) in by]
                    cells.append(f"{res.count('yes')} / {len(res)}")
                lines.append(f"| {label} | {v} | {cells[0]} | {cells[1]} |")
    with open(os.path.join(core.DATA, "report.md"), "a") as f:
        f.write("\n".join(lines) + "\n")
