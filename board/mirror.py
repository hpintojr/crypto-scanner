"""Copies what the scanner and the paper simulation already log into the shared board. Places no orders.

Run from the repo root after scanner.py: python3 -m board.mirror
Reads data/signals.csv, data/outcomes.csv, data/sim-trades.csv, data/sim-state.json and data/sim-equity.csv.
Never reads .holdings* files. Writes the database outside the repo (W/data/board.db), plus
data/board-status.md each run and data/board-export.csv once a day. Changes nothing the scanner or sim does.
"""
import csv, json, os, sqlite3, sys, time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
DB_DIR = os.path.join(os.path.dirname(ROOT), "data")  # outside the repo, never pushed
DB = os.path.join(DB_DIR, "board.db")
STATE = os.path.join(DB_DIR, "board-state.json")
SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "schema.sql")
PT = ZoneInfo("America/Los_Angeles")
TABLES = ("signals", "proposed_orders", "orders", "results", "messages")


def _rows(name):
    try:
        with open(os.path.join(DATA, name), newline="") as f:
            return list(csv.DictReader(f))
    except OSError:
        return []


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def connect():
    os.makedirs(DB_DIR, exist_ok=True)
    db = sqlite3.connect(DB)
    db.execute("PRAGMA foreign_keys = ON")
    with open(SCHEMA) as f:
        db.executescript(f.read())
    return db


def _insert(db, table, row):
    """True if new. A row already copied (same source_key) is skipped; anything else is raised."""
    cols = ", ".join(row)
    try:
        db.execute(f"INSERT INTO {table} ({cols}) VALUES ({', '.join('?' * len(row))})", list(row.values()))
        return True
    except sqlite3.IntegrityError as e:
        if "source_key" in str(e):
            return False
        raise


def mirror_signals(db):
    n = 0
    for r in _rows("signals.csv"):
        n += _insert(db, "signals", {
            "source_job": "mirror:scanner", "source_key": f"signal:{r['signal_id']}", "market": r.get("market"),
            "symbol": r["symbol"], "signal_type": r.get("signal_type") or "move_1h", "score": _num(r.get("move_1h_pct")),
            "payload_json": json.dumps(r, sort_keys=True), "created_at": r.get("time") or None})
    return n


def mirror_orders(db):
    """Copies the sim's buys and sells into proposed_orders. orders stays empty: only the Executor writes it."""
    n = 0
    def add(key, sym, side, amount, status, thesis, against, at):
        return _insert(db, "proposed_orders", {
            "source_job": "mirror:sim", "source_key": key, "symbol": sym, "side": side, "qty_or_dollars": amount,
            "thesis": thesis, "against": against, "status": status, "created_at": at})
    for t in _rows("sim-trades.csv"):
        n += add(f"buy:{t['symbol']}:{t['opened']}", t["symbol"], "buy", f"${float(t['cost']):.2f}", "filled",
                 t.get("thesis"), t.get("against"), t["opened"])
        n += add(f"sell:{t['symbol']}:{t['closed']}", t["symbol"], "sell", t["qty"], "filled",
                 f"exit: {t.get('exit_reason')}", None, t["closed"])
    try:
        with open(os.path.join(DATA, "sim-state.json")) as f:
            positions = json.load(f).get("positions", [])
    except (OSError, ValueError):
        positions = []
    for p in positions:
        if p.get("status") == "buying":
            n += add(f"buy-sent:{p.get('buy_id')}", p["symbol"], "buy", f"${float(p.get('notional') or 0):.2f}", "sent",
                     p.get("thesis"), p.get("against"), None)
        elif p.get("opened"):
            n += add(f"buy:{p['symbol']}:{p['opened']}", p["symbol"], "buy", f"${float(p.get('cost') or 0):.2f}", "filled",
                     p.get("thesis"), p.get("against"), p["opened"])
    return n


def mirror_results(db):
    n = 0
    today = datetime.now(PT).date().isoformat()
    for r in _rows("sim-equity.csv"):
        if r["date"] >= today:  # today's row still changes; it is copied once the day is over
            continue
        for metric, col in (("paper_equity", "equity"), ("spy_equivalent", "spy_equivalent")):
            n += _insert(db, "results", {"job": "mirror:sim", "source_key": f"{metric}:{r['date']}", "metric": metric,
                                         "value": _num(r.get(col)), "period": r["date"]})
    for r in _rows("outcomes.csv"):
        n += _insert(db, "results", {"job": "mirror:scanner", "source_key": f"outcome:{r['signal_id']}:{r['horizon']}",
                                     "metric": f"excess_pct_{r['horizon']}", "value": _num(r.get("excess_pct")),
                                     "period": r.get("scored_at"), "created_at": r.get("scored_at") or None})
    return n


def export(db):
    """Signals and results only. No keys, no hold-test data, no orders."""
    path = os.path.join(DATA, "board-export.csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["table", "id", "job", "market", "symbol", "type_or_metric", "value", "period", "created_at"])
        for r in db.execute("SELECT id, source_job, market, symbol, signal_type, score, created_at FROM signals ORDER BY id"):
            w.writerow(["signals", r[0], r[1], r[2], r[3], r[4], r[5], "", r[6]])
        for r in db.execute("SELECT id, job, metric, value, period, created_at FROM results ORDER BY id"):
            w.writerow(["results", r[0], r[1], "", "", r[2], r[3], r[4], r[5]])


def main():
    t0, errors, added = time.time(), [], {}
    try:
        db = connect()
        for name, fn in (("signals", mirror_signals), ("proposed_orders", mirror_orders), ("results", mirror_results)):
            try:
                with db:
                    added[name] = fn(db)
            except Exception as e:
                errors.append(f"{name}: {type(e).__name__}: {e}")
        try:
            with open(STATE) as f:
                state = json.load(f)
        except (OSError, ValueError):
            state = {}
        today = datetime.now(PT).date().isoformat()
        if state.get("exported") != today:
            export(db)
            state["exported"] = today
            with open(STATE, "w") as f:
                json.dump(state, f)
        counts = {t: db.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in TABLES}
    except Exception as e:
        errors.append(f"board: {type(e).__name__}: {e}")
        counts, state = {}, {}
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = ["# Board status", "", "Shared database, copy only. No job reads from it yet. Paper only.", "",
             f"- Last mirror: {now} ({time.time() - t0:.1f}s)",
             "- Tables: " + (", ".join(f"{t} {counts[t]}" for t in TABLES) if counts else "not readable"),
             "- Added this run: " + (", ".join(f"{k} {v}" for k, v in added.items()) or "none"),
             f"- Last export: {state.get('exported') or 'none'} (data/board-export.csv)",
             f"- Errors: {len(errors)}"] + [f"  - {e}" for e in errors]
    with open(os.path.join(DATA, "board-status.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
