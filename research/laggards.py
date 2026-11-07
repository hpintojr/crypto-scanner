"""S&P 500 correlation and laggards watch. Research only, no orders, no signals.

Thesis under test (from a Sept 2026 reel, unverified attribution to Goldman Sachs): index correlation is near
historic lows; past lows (2007, 2018) were followed by volatility after the midterms; when it comes, beaten-down
laggards re-correlate with the market and outperform. The Nov 5, 2026 selloff is the live test.

Once per trading day after the close, this logs closes and day changes for the index funds, the named laggards,
the named sectors, SPY against equal-weight RSP (the free stand-in for correlation), breadth across the fixed
stock list, and a mechanical verdict. VIX itself isn't on the free feed, so VIXY (a VIX futures fund) is the
stand-in and SPY's 20-day realized volatility is logged beside it. A failed fetch leaves the day blank; nothing
is ever invented.
"""
import csv, math, os
from datetime import date, timedelta
from . import backtest, core, stocks

PAPER_URL = stocks.PAPER_URL  # read only here, for the market clock
REFERENCE = "2026-11-05"      # the selloff the thesis is measured from
INDEX = ["SPY", "RSP", "QQQ", "DIA", "VIXY"]
LAGGARDS = ["INTU", "BSX", "NKE", "MCD"]
SECTORS = ["XLC", "XLY", "XLF"]
VERDICT_POINTS = 1.0          # laggard basket vs SPY since the reference, in percentage points
LOG = "laggards.csv"
FIELDS = ["date", "spy", "spy_day_pct", "rsp_day_pct", "rsp_minus_spy_since", "qqq_day_pct", "dia_day_pct",
          "vixy_day_pct", "spy_vol_20d", "laggards_since_pct", "laggards_minus_spy_since", "sectors_since_pct",
          "advancers", "decliners", "big_move", "verdict"]


def _pct(a, b):
    return (a / b - 1) * 100 if a and b else None


def _since(closes, sym, day):
    by = closes.get(sym) or {}
    ref = by.get(REFERENCE)
    return _pct(by.get(day), ref) if ref else None


def _day(closes, sym, days):
    by = closes.get(sym) or {}
    if len(days) < 2 or days[-1] not in by or days[-2] not in by:
        return None
    return _pct(by[days[-1]], by[days[-2]])


def _realized_vol(by, days, n=20):
    c = [by[d] for d in days if d in by][-(n + 1):]
    if len(c) < n + 1:
        return None
    r = [math.log(c[i] / c[i - 1]) for i in range(1, len(c))]
    m = sum(r) / len(r)
    return math.sqrt(sum((x - m) ** 2 for x in r) / (len(r) - 1)) * math.sqrt(252) * 100


def _avg(vals):
    vals = [v for v in vals if v is not None]
    return sum(vals) / len(vals) if vals else None


def build_row(closes, universe_closes, day):
    days = sorted(d for d in (closes.get("SPY") or {}) if d <= day)
    if not days or days[-1] != day:
        return None
    spy_day = _day(closes, "SPY", days)
    lag_since = _avg([_since(closes, s, day) for s in LAGGARDS])
    spy_since = _since(closes, "SPY", day)
    rsp_since = _since(closes, "RSP", day)
    adv = dec = 0
    for sym, by in universe_closes.items():
        d = _day({sym: by}, sym, days)
        if d is not None:
            adv += d > 0
            dec += d < 0
    diff = lag_since - spy_since if lag_since is not None and spy_since is not None else None
    verdict = "undecided" if diff is None or abs(diff) < VERDICT_POINTS else "holding" if diff > 0 else "weakening"
    f = lambda v, n=2: "" if v is None else round(v, n)
    return {"date": day, "spy": f((closes.get("SPY") or {}).get(day)), "spy_day_pct": f(spy_day),
            "rsp_day_pct": f(_day(closes, "RSP", days)),
            "rsp_minus_spy_since": f(rsp_since - spy_since) if rsp_since is not None and spy_since is not None else "",
            "qqq_day_pct": f(_day(closes, "QQQ", days)), "dia_day_pct": f(_day(closes, "DIA", days)),
            "vixy_day_pct": f(_day(closes, "VIXY", days)), "spy_vol_20d": f(_realized_vol(closes.get("SPY") or {}, days), 1),
            "laggards_since_pct": f(lag_since), "laggards_minus_spy_since": f(diff),
            "sectors_since_pct": f(_avg([_since(closes, s, day) for s in SECTORS])),
            "advancers": adv, "decliners": dec,
            "big_move": "yes" if spy_day is not None and abs(spy_day) > 2 else "no", "verdict": verdict}


def cycle(state, errors, creds):
    if not creds:
        return
    try:
        clock = stocks._get(PAPER_URL, "/v2/clock", creds)
        if clock.get("is_open"):
            return  # the day's note is written after the close
        et = core.now().astimezone(stocks.ET)
        day = et.date() if et.hour >= 17 else et.date() - timedelta(days=1)
        rows = core.read(LOG)
        if any(r["date"] == day.isoformat() for r in rows):
            return
        start = day - timedelta(days=45)
        symbols = sorted(set(INDEX + LAGGARDS + SECTORS))
        closes = backtest._daily_closes(creds, "/v2/stocks/bars", symbols, start, day, feed="iex", adjustment="all")
        if day.isoformat() not in (closes.get("SPY") or {}):
            return  # not a trading day, or the close isn't published yet
        uni = backtest._daily_closes(creds, "/v2/stocks/bars", stocks.universe(), day - timedelta(days=7), day, feed="iex", adjustment="all")
        row = build_row(closes, uni, day.isoformat())
        if row:
            core._append(LOG, FIELDS, [row])
            write_report(core.read(LOG))
            state["last_laggards"] = f"{day.isoformat()}: {row['verdict']}, laggards vs SPY since {REFERENCE} {row['laggards_minus_spy_since']} pts"
    except Exception as e:
        errors.append(f"laggards: {type(e).__name__}: {e}")


def write_report(rows):
    lines = ["# S&P 500 correlation and laggards watch", "",
             f"Research only, no orders. Tests whether beaten-down laggards ({', '.join(LAGGARDS)}) re-correlate with the "
             f"market after the {REFERENCE} selloff, and whether volatility continues. Sectors: {', '.join(SECTORS)}. "
             "RSP minus SPY is the free stand-in for correlation: equal weight beating cap weight means dispersion is "
             "normalizing. VIXY stands in for VIX. Breadth is across the fixed 100-stock list, not the whole market. "
             "The reel's Goldman Sachs attribution is unverified. First verdict due 2026-11-18.", "",
             "Verdict rule: 'holding' when the laggard basket leads SPY by over 1 point since the reference, 'weakening' "
             "when it trails by over 1 point, otherwise 'undecided'. One selloff proves nothing.", "",
             "| Date | SPY | SPY day % | RSP day % | RSP-SPY since | VIXY day % | SPY 20d vol | Laggards since % | Lag-SPY since | Sectors since % | Adv/Dec | >2% day | Verdict |",
             "|---|--:|--:|--:|--:|--:|--:|--:|--:|--:|--:|---|---|"]
    for r in rows[-40:]:
        lines.append(f"| {r['date']} | {r['spy']} | {r['spy_day_pct']} | {r['rsp_day_pct']} | {r['rsp_minus_spy_since']} | "
                     f"{r['vixy_day_pct']} | {r['spy_vol_20d']} | {r['laggards_since_pct']} | {r['laggards_minus_spy_since']} | "
                     f"{r['sectors_since_pct']} | {r['advancers']}/{r['decliners']} | {r['big_move']} | {r['verdict']} |")
    os.makedirs(core.DATA, exist_ok=True)
    with open(os.path.join(core.DATA, "laggards.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
