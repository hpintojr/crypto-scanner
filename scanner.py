#!/usr/bin/env python3
"""Market research agent: crypto and stock movers, Form 4 buys, $1,000 paper simulation. Paper only, no real money.
One invocation = one cycle. Run from the Otto schedule, or via run.sh or cron, never more than one."""
import csv, hashlib, json, os, re, subprocess, time, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from research import backtest as research_backtest, core as research_core, form4 as research_form4, holdings as research_holdings, movers as research_movers, sim as research_sim, stocks as research_stocks, wallets as research_wallets

REPO = os.path.dirname(os.path.abspath(__file__))
CG = "https://api.coingecko.com/api/v3"
WATCH = [("ripple", "XRP"), ("stellar", "XLM"), ("hedera-hashgraph", "HBAR"),
         ("xdce-crowd-sale", "XDC"), ("bitcoin", "BTC"), ("ethereum", "ETH"), ("solana", "SOL")]
CRYPTO_WORDS = ("crypto", "coin", "token", "price", "market", "trading")
errors = []


def now():
    return datetime.now(timezone.utc)


def iso(t=None):
    return (t or now()).strftime("%Y-%m-%dT%H:%M:%SZ")


def get(url, kind="json", retries=2):
    last = None
    for i in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "crypto-scanner-research/1.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                body = r.read()
            return json.loads(body) if kind == "json" else body
        except Exception as e:
            last = e
            time.sleep(8 * (i + 1))  # CoinGecko free tier rate limits
    errors.append(f"fetch failed {url.split('?')[0]}: {last}")
    return None


def path(n):
    return os.path.join(REPO, n)


def digest(name):
    if not os.path.exists(path(name)):
        return None
    return hashlib.sha256(open(path(name), "rb").read()).hexdigest()


def append_rows(name, header, rows):
    if not rows:
        return
    new = not os.path.exists(path(name))
    with open(path(name), "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(header)
        w.writerows(rows)


def read_rows(name):
    if not os.path.exists(path(name)):
        return []
    with open(path(name), newline="") as f:
        return list(csv.DictReader(f))


def load_state():
    try:
        return json.load(open(path(".state.json")))
    except Exception:
        return {"buzz": {}, "last_watch": None, "last_flag": None}


def scan(state):
    data = get(f"{CG}/coins/markets?vs_currency=usd&order=market_cap_desc&per_page=100&page=1&price_change_percentage=1h")
    if not data:
        return []
    movers = [c for c in data if c.get("price_change_percentage_1h_in_currency") is not None
              and abs(c["price_change_percentage_1h_in_currency"]) > 3]
    kept = []
    btc = next((c["current_price"] for c in data if c["id"] == "bitcoin"), None)
    for c in movers:
        time.sleep(3)
        ch = get(f"{CG}/coins/{c['id']}/market_chart?vs_currency=usd&days=7")
        if not ch or not ch.get("total_volumes"):
            continue
        # CoinGecko total_volumes are rolling-24h samples. The baseline leaves out the last 24h
        # so the current move can't inflate its own comparison; average one sample per UTC day.
        days = {}
        cutoff = now() - timedelta(hours=24)
        for ts, v in ch["total_volumes"]:
            sampled = datetime.fromtimestamp(ts / 1000, timezone.utc)
            if sampled < cutoff:
                days.setdefault(sampled.date(), []).append(v)
        daily = [sum(v) / len(v) for v in days.values()]
        avg = sum(daily) / len(daily) if daily else 0
        vol = c.get("total_volume") or 0
        if avg <= 0:
            continue
        passed = vol >= 2 * avg
        if btc:
            research_core.log_signal(state, market="crypto", symbol=c["symbol"].upper(), asset_id=c["id"],
                                     name=c["name"], price=c["current_price"], benchmark="BTC",
                                     benchmark_price=btc, move=c["price_change_percentage_1h_in_currency"],
                                     volume=vol, baseline=avg, ratio=vol / avg, passed=passed)
        if passed:
            kept.append((c, vol, avg, vol / avg))
    rows = [[iso(), c["id"], c["symbol"], c["name"], c["current_price"],
             round(c["price_change_percentage_1h_in_currency"], 3), vol, round(avg, 2), round(r, 3)]
            for c, vol, avg, r in kept]
    append_rows("scanner-log.csv", ["time", "coin_id", "symbol", "name", "price", "move_1h_pct",
                                    "volume_24h", "avg_daily_volume_7d", "volume_ratio"], rows)
    state["last_scan"] = f"{iso()}: {len(movers)} movers >3% 1h, {len(kept)} kept after 2x volume check"
    if kept:
        state["last_flag"] = f"{iso()} {', '.join(c['symbol'].upper() for c, *_ in kept)}"
    return [c for c, *_ in kept]


def buzz(flagged, state):
    if not flagged:
        return
    trending = get(f"{CG}/search/trending")
    ranks = {}
    if trending:
        for i, item in enumerate(trending.get("coins", []), 1):
            ranks[item["item"]["id"]] = i
    rows = {r["coin_id"]: r for r in read_rows("buzz.csv")}
    for c in flagged:
        last = state["buzz"].get(c["id"])
        if last and now() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < timedelta(hours=1):
            continue
        rank = ranks.get(c["id"])
        tp = 0 if rank is None else 6 if rank <= 3 else 5 if rank <= 6 else 4 if rank <= 9 else 3 if rank <= 12 else 2 if rank <= 15 else 0
        q = urllib.parse.quote(f'{c["name"]} crypto when:1d')
        xml = get(f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en", kind="raw")
        n = 0
        if xml:
            try:
                name, sym = c["name"].lower(), c["symbol"].lower()
                for item in ET.fromstring(xml).iter("item"):
                    s = (item.findtext("title") or "").lower()
                    if (name in s or re.search(rf"\b{re.escape(sym)}\b", s)) and any(w in s for w in CRYPTO_WORDS):
                        n += 1
            except Exception as e:
                errors.append(f"news parse {c['id']}: {e}")
        npts = 0 if n == 0 else 2 if n <= 2 else 4
        rows[c["id"]] = {"time": iso(), "coin_id": c["id"], "symbol": c["symbol"], "score": min(10, tp + npts),
                         "reason": f"trending rank {rank if rank else 'none'} ({tp} pts); {n} crypto news titles ({npts} pts)"}
        state["buzz"][c["id"]] = iso()
    with open(path("buzz.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["time", "coin_id", "symbol", "score", "reason"])
        w.writeheader()
        w.writerows(rows.values())


def watchlist(state):
    last = state.get("last_watch")
    if last and now() - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) < timedelta(minutes=55):
        return
    ids = ",".join(i for i, _ in WATCH)
    data = get(f"{CG}/coins/markets?vs_currency=usd&ids={ids}&price_change_percentage=1h,24h,7d")
    if not data:
        return
    by = {c["id"]: c for c in data}
    t = now()
    rows = []
    for cid, sym in WATCH:
        c = by.get(cid)
        if not c:
            errors.append(f"watchlist: {sym} ({cid}) missing from response, retry next hour")
            continue
        rows.append([t.strftime("%Y-%m-%d"), t.strftime("%H:%M:%S"), cid, sym, c["current_price"],
                     c.get("price_change_percentage_1h_in_currency"), c.get("price_change_percentage_24h_in_currency"),
                     c.get("price_change_percentage_7d_in_currency"), c.get("total_volume"), c.get("market_cap")])
    append_rows("watchlist-log.csv", ["date", "time_utc", "coin_id", "symbol", "price", "move_1h_pct",
                                      "move_24h_pct", "move_7d_pct", "volume_24h", "market_cap"], rows)
    if len(rows) == len(WATCH):
        state["last_watch"] = iso()


def score_crypto():
    """Fill in returns for crypto signals that have come due."""
    due = research_core.pending("crypto")
    if not due:
        return
    ids = sorted({s["asset_id"] for s, _, _ in due} | {"bitcoin"})[:100]
    prices = get(f"{CG}/simple/price?ids={','.join(ids)}&vs_currencies=usd")
    if not prices or "bitcoin" not in prices:
        return
    for sig, horizon, when in due:
        if sig["asset_id"] in prices:
            research_core.record_outcome(sig, horizon, when, prices[sig["asset_id"]]["usd"], prices["bitcoin"]["usd"])


def research(state):
    """Stock scan, outcome scoring and report. A failure here must not stop the crypto cycle."""
    try:
        creds = research_stocks.scan(state, errors)
        score_crypto()
        research_stocks.score(creds, errors)
        research_form4.cycle(state, errors, creds)
        research_sim.cycle(state, errors, creds)
        research_wallets.cycle(state, errors)
        research_holdings.cycle(state, errors)
        research_backtest.cycle(state, errors, creds)
        research_movers.cycle(state, errors, creds)
        research_core.write_report()
        research_form4.append_report()
    except Exception as e:
        errors.append(f"research: {type(e).__name__}: {e}")


def inbox(state):
    """requests-from-chip.md is the only inbox. A change marks it pending until
    answers-to-chip.md changes; replies are written by the agent, not this script."""
    req, ans = digest("requests-from-chip.md"), digest("answers-to-chip.md")
    if req and req != state.get("inbox_hash"):
        state["inbox_hash"], state["answers_hash"], state["pending_request"] = req, ans, True
    elif state.get("pending_request") and ans != state.get("answers_hash"):
        state["pending_request"] = False


def git(*args):
    return subprocess.run(["git", "-C", REPO, *args], capture_output=True, text=True)


def cycle_minutes(state):
    """Measured gap between the last two runs, so status.md reports the real schedule."""
    last, t = state.get("last_run"), now()
    if last:
        gap = (t - datetime.strptime(last, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
        if 1 <= gap <= 120:
            state["cycle_minutes"] = round(gap)
    state["last_run"] = iso(t)
    return state.get("cycle_minutes", 15)


def write_status(state, host, push_error=None):
    minutes = cycle_minutes(state)
    status = ["# Scanner status", "", f"- Last run: {iso()}", f"- Host: {host}",
              f"- Last scan: {state.get('last_scan') or 'none yet'}",
              f"- Last flag: {state.get('last_flag') or 'none yet'}",
              f"- Last stock scan: {state.get('last_stock_scan') or 'none yet'}",
              f"- Last watchlist snapshot: {state.get('last_watch') or 'none yet'}",
              f"- Last pre-market gap check: {state.get('last_gap_check') or 'none yet'}",
              f"- Last Form 4 run: {state.get('last_form4') or 'none yet'}",
              f"- $1,000 paper simulation: {state.get('last_sim') or 'not started'}",
              f"- Simulation flags: {state.get('last_flags') or 'none'}",
              f"- Strategy test: {state.get('last_backtest') or 'not run yet'}",
              f"- Hold test: {state.get('last_holdings') or 'not started'}",
              f"- Wallet watch: {state.get('last_wallets') or 'not started'}",
              f"- Measured time between runs: {minutes} min",
              f"- Next run: ~{iso(now() + timedelta(minutes=minutes))}",
              f"- Inbox: {'NEW request in requests-from-chip.md awaiting reply' if state.get('pending_request') else 'no pending requests'}",
              f"- Errors this cycle: {len(errors)}"]
    status += [f"  - {e}" for e in errors]
    if state.get("last_push_error"):
        status.append(f"- Previous push failed: {state['last_push_error']}")
    status += ["", "Paper only, approved by Hamilton. No real money. No keys in this repo. Create SIM_STOP to stop new orders."]
    open(path("status.md"), "w").write("\n".join(status) + "\n")
    json.dump(state, open(path(".state.json"), "w"), indent=1)


def publish(state):
    # pull first so Chip's edits to requests-from-chip.md are seen and we never conflict
    git("add", "-A")
    if git("diff", "--cached", "--quiet").returncode == 0:
        return
    git("commit", "-m", f"scanner cycle {iso()}\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>")
    git("pull", "--rebase", "-X", "theirs")
    p = git("push")
    state["last_push_error"] = p.stderr.strip().splitlines()[-1] if p.returncode != 0 else None
    json.dump(state, open(path(".state.json"), "w"), indent=1)
    if p.returncode != 0:
        print("push failed:", p.stderr)


def main():
    pull = git("pull", "--rebase", "--autostash")
    if pull.returncode != 0:
        errors.append(f"git pull failed: {pull.stderr.strip()[-200:]}")
    state = load_state()
    host = os.uname().nodename
    inbox(state)
    flagged = scan(state)
    buzz(flagged, state)
    watchlist(state)
    research(state)
    write_status(state, host)
    publish(state)
    print("cycle done", iso(), "flagged:", [c["symbol"] for c in flagged], "errors:", errors)


if __name__ == "__main__":
    main()
