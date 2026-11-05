"""Read-only SEC EDGAR client. SEC asks for a contact in the User-Agent and at most 10 requests a second."""
import json, os, time, urllib.request
from datetime import timedelta
from . import core

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, ".edgar-cache")  # git-ignored
DEFAULT_AGENT = "crypto-scanner-research/1.0"


def agent():
    """SEC_USER_AGENT, or .sec-user-agent beside the repo (outside it, so a contact stays off GitHub)."""
    if os.environ.get("SEC_USER_AGENT"):
        return os.environ["SEC_USER_AGENT"]
    try:
        with open(os.path.join(os.path.dirname(ROOT), ".sec-user-agent")) as f:
            return f.read().strip() or DEFAULT_AGENT
    except OSError:
        return DEFAULT_AGENT


def get(url, raw=False):
    time.sleep(0.15)
    req = urllib.request.Request(url, headers={"User-Agent": agent(), "Accept": "*/*"}, method="GET")
    with urllib.request.urlopen(req, timeout=30) as r:
        body = r.read()
    return body.decode("utf-8", "replace") if raw else json.loads(body)


def submissions(cik):
    d = get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json")
    return d.get("filings", {}).get("recent", {})


def ticker_cik(ticker):
    """Ticker to CIK, with the SEC's list cached for a week."""
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "company_tickers.json")
    if not os.path.exists(path) or time.time() - os.path.getmtime(path) > 7 * 86400:
        with open(path, "w") as f:
            json.dump(get("https://www.sec.gov/files/company_tickers.json"), f)
    with open(path) as f:
        data = json.load(f)
    want = ticker.upper().replace(".", "-")
    for row in data.values():
        if row["ticker"].upper() == want:
            return row["cik_str"]
    return None


def recent_earnings_8k(ticker, days=3):
    """True if the company filed an 8-K item 2.02 (results of operations) in the last few days."""
    cik = ticker_cik(ticker)
    if not cik:
        return False
    rec = submissions(cik)
    cutoff = (core.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    for form, date, items in zip(rec.get("form", []), rec.get("filingDate", []), rec.get("items", [])):
        if form == "8-K" and date >= cutoff and "2.02" in (items or ""):
            return True
    return False


def public_float(cik):
    """Latest public float from the company's XBRL cover page, or None."""
    d = get(f"https://data.sec.gov/api/xbrl/companyconcept/CIK{int(cik):010d}/dei/EntityPublicFloat.json")
    rows = d.get("units", {}).get("USD", [])
    return max(rows, key=lambda r: r.get("end", ""))["val"] if rows else None
