"""Shared signal log, outcome scoring and report. Research only."""
import csv, hashlib, os, statistics
from datetime import datetime, timezone, timedelta

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
FMT = "%Y-%m-%dT%H:%M:%SZ"
COOLDOWN = timedelta(hours=4)  # a persisting move is one event, not one per cycle
MAX_LATE_MIN = 60  # outcomes scored later than this are kept but left out of the report
SIGNAL_FIELDS = ["signal_id", "time", "market", "symbol", "asset_id", "name", "price", "benchmark",
                 "benchmark_price", "move_1h_pct", "volume", "baseline_volume", "volume_ratio",
                 "passed", "news_24h"]
OUTCOME_FIELDS = ["signal_id", "horizon", "due", "scored_at", "late_min", "price", "benchmark_price",
                  "return_pct", "benchmark_return_pct", "excess_pct"]
HORIZONS = {
    "crypto": {"1h": timedelta(hours=1), "4h": timedelta(hours=4), "24h": timedelta(hours=24)},
    "stocks": {"1h": timedelta(hours=1), "1d": timedelta(days=1), "5d": timedelta(days=5)},
}


def now():
    return datetime.now(timezone.utc)


def parse(s):
    return datetime.strptime(s, FMT).replace(tzinfo=timezone.utc)


def _path(name):
    return os.path.join(DATA, name)


def read(name):
    if not os.path.exists(_path(name)):
        return []
    with open(_path(name), newline="") as f:
        return list(csv.DictReader(f))


def _append(name, fields, rows):
    if not rows:
        return
    os.makedirs(DATA, exist_ok=True)
    new = not os.path.exists(_path(name))
    with open(_path(name), "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        if new:
            w.writeheader()
        w.writerows(rows)


def log_signal(state, *, market, symbol, asset_id, name, price, benchmark, benchmark_price,
               move, volume, baseline, ratio, passed, news=""):
    """Record a mover, passed or rejected. Rejects are the comparison group."""
    seen = state.setdefault("signal_seen", {})
    t = now()
    for k in [k for k, v in seen.items() if t - parse(v) > COOLDOWN]:
        del seen[k]
    key = f"{market}:{symbol}:{int(bool(passed))}"
    if key in seen:
        return False
    stamp = t.strftime(FMT)
    seen[key] = stamp
    _append("signals.csv", SIGNAL_FIELDS, [{
        "signal_id": hashlib.sha1(f"{stamp}{market}{symbol}{passed}".encode()).hexdigest()[:12],
        "time": stamp, "market": market, "symbol": symbol, "asset_id": asset_id, "name": name,
        "price": price, "benchmark": benchmark, "benchmark_price": benchmark_price,
        "move_1h_pct": round(move, 3), "volume": volume, "baseline_volume": round(baseline, 2),
        "volume_ratio": round(ratio, 3), "passed": int(bool(passed)), "news_24h": news}])
    return True


def pending(market):
    """(signal, horizon, due) for every outcome that is due and not yet scored."""
    done = {(o["signal_id"], o["horizon"]) for o in read("outcomes.csv")}
    t = now()
    out = []
    for s in read("signals.csv"):
        if s["market"] != market:
            continue
        for h, delta in HORIZONS[market].items():
            due = parse(s["time"]) + delta
            if due <= t and (s["signal_id"], h) not in done:
                out.append((s, h, due))
    return out


def record_outcome(sig, horizon, due, price, bench_price, as_of_due=False):
    p0, b0 = float(sig["price"]), float(sig["benchmark_price"])
    if not (p0 > 0 and b0 > 0 and price > 0 and bench_price > 0):
        return
    t = now()
    ret = (price / p0 - 1) * 100
    bret = (bench_price / b0 - 1) * 100
    _append("outcomes.csv", OUTCOME_FIELDS, [{
        "signal_id": sig["signal_id"], "horizon": horizon, "due": due.strftime(FMT),
        "scored_at": t.strftime(FMT),
        "late_min": 0 if as_of_due else round((t - due).total_seconds() / 60, 1),
        "price": price, "benchmark_price": bench_price, "return_pct": round(ret, 4),
        "benchmark_return_pct": round(bret, 4), "excess_pct": round(ret - bret, 4)}])


def write_report():
    """Did the move continue, net of the benchmark? Positive = it kept going."""
    signals = {s["signal_id"]: s for s in read("signals.csv")}
    groups = {}
    for o in read("outcomes.csv"):
        s = signals.get(o["signal_id"])
        if not s or float(o["late_min"]) > MAX_LATE_MIN or s["symbol"] == s["benchmark"]:
            continue
        direction = 1 if float(s["move_1h_pct"]) >= 0 else -1
        key = (s["market"], "passed" if s["passed"] == "1" else "rejected", o["horizon"])
        groups.setdefault(key, []).append(direction * float(o["excess_pct"]))
    n_sig = len(signals)
    n_pass = sum(s["passed"] == "1" for s in signals.values())
    lines = ["# Research report", "",
             f"{n_sig} movers logged, {n_pass} passed the volume check. Research only, no orders.", "",
             "Follow-through is the return after the signal, net of BTC or SPY, in the direction of",
             "the original move. Positive means the move kept going. Compare passed against rejected.",
             "Costs and slippage are not included. Treat any row under 30 signals as noise.", "",
             "| Market | Group | Horizon | Signals | Avg follow-through % | Median % | Continued % |",
             "|---|---|---|---:|---:|---:|---:|"]
    order = {"1h": 0, "4h": 1, "1d": 2, "24h": 2, "5d": 3}
    for key in sorted(groups, key=lambda k: (k[0], k[1] != "passed", order[k[2]])):
        v = groups[key]
        lines.append(f"| {key[0]} | {key[1]} | {key[2]} | {len(v)} | {statistics.mean(v):.2f} | "
                     f"{statistics.median(v):.2f} | {100 * sum(x > 0 for x in v) / len(v):.0f} |")
    if not groups:
        lines.append("| none yet | | | | | | |")
    os.makedirs(DATA, exist_ok=True)
    with open(_path("report.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
