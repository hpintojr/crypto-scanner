"""Watch publicly attributed crypto wallets and log their moves. Log only: nothing here trades.

A wallet is only watched when research/wallets.csv has enabled=yes plus a full address, chain,
attribution source and last_verified date. A label is a claim, not proof of who controls an address.
Elon Musk's personal wallet stays off the list because it is unverified; Tesla and SpaceX are companies.
"""
import csv, json, os, re, urllib.request
from . import core

LIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wallets.csv")
FIELDS = ["seen_at", "owner", "category", "chain", "address", "tx", "direction", "amount", "asset", "tx_time", "source"]
MAX_PER_CYCLE = 25
KEEP_SEEN = 50
PATTERNS = {"bitcoin": r"(bc1[a-z0-9]{20,60}|[13][a-km-zA-HJ-NP-Z1-9]{25,34})",
            "ethereum": r"0x[0-9a-fA-F]{40}", "xrp": r"r[1-9A-HJ-NP-Za-km-z]{24,34}"}
UA = {"User-Agent": "crypto-scanner-research/1.0", "Content-Type": "application/json"}


def _json(url, body=None):
    req = urllib.request.Request(url, headers=UA, data=json.dumps(body).encode() if body else None)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def _bitcoin(addr):
    out = []
    for t in _json(f"https://mempool.space/api/address/{addr}/txs"):
        spent = sum(i["prevout"]["value"] for i in t.get("vin", []) if (i.get("prevout") or {}).get("scriptpubkey_address") == addr)
        got = sum(o["value"] for o in t.get("vout", []) if o.get("scriptpubkey_address") == addr)
        net = got - spent
        out.append((t["txid"], "in" if net >= 0 else "out", abs(net) / 1e8, "BTC", t.get("status", {}).get("block_time", "")))
    return out


def _ethereum(addr):
    """Native ETH only. Token transfers aren't included yet."""
    out = []
    for t in _json(f"https://eth.blockscout.com/api/v2/addresses/{addr}/transactions").get("items", []):
        sender = (t.get("from") or {}).get("hash", "").lower()
        out.append((t["hash"], "out" if sender == addr.lower() else "in", int(t.get("value") or 0) / 1e18, "ETH", t.get("timestamp", "")))
    return out


def _xrp(addr):
    d = _json("https://s1.ripple.com:51234/", {"method": "account_tx", "params": [{"account": addr, "limit": 20}]})
    out = []
    for item in d.get("result", {}).get("transactions", []):
        t = item.get("tx") or item.get("tx_json") or {}
        amount = t.get("Amount") or t.get("DeliverMax")
        if t.get("TransactionType") == "Payment" and isinstance(amount, str):
            out.append((t.get("hash") or item.get("hash"), "out" if t.get("Account") == addr else "in", int(amount) / 1e6, "XRP", t.get("date", "")))
    return out


READERS = {"bitcoin": _bitcoin, "ethereum": _ethereum, "xrp": _xrp}


def admitted(row):
    """Why a row can't be watched, or None if it can."""
    chain = row["chain"].strip().lower()
    if chain not in READERS:
        return f"unsupported chain {chain or '(blank)'}"
    if not re.fullmatch(PATTERNS[chain], row["address"].strip()):
        return "not a full valid address"
    if not row["attribution_source"].strip() or not row["last_verified"].strip():
        return "missing attribution source or verification date"
    return None


def cycle(state, errors):
    try:
        with open(LIST, newline="") as f:
            enabled = [r for r in csv.DictReader(f) if r["enabled"].strip().lower() == "yes"]
    except OSError:
        return
    seen = state.setdefault("wallets_seen", {})
    watched = added = 0
    for row in enabled[:MAX_PER_CYCLE]:
        why = admitted(row)
        if why:
            errors.append(f"wallet {row['owner']}: {why}")
            continue
        addr, chain = row["address"].strip(), row["chain"].strip().lower()
        try:
            txs = READERS[chain](addr)
        except Exception as e:
            errors.append(f"wallet {row['owner']}: {type(e).__name__}: {e}")
            continue
        watched += 1
        first = addr not in seen  # first look sets a baseline, so old history isn't logged as new
        known = set(seen.get(addr, []))
        new = [] if first else [t for t in txs if t[0] not in known]
        core._append("wallet-moves.csv", FIELDS, [{
            "seen_at": core.now().strftime(core.FMT), "owner": row["owner"], "category": row["category"], "chain": chain,
            "address": addr, "tx": t[0], "direction": t[1], "amount": t[2], "asset": t[3], "tx_time": t[4],
            "source": row["attribution_source"]} for t in new])
        added += len(new)
        seen[addr] = ([t[0] for t in txs] + [k for k in seen.get(addr, []) if k not in {t[0] for t in txs}])[:KEEP_SEEN]
    state["last_wallets"] = f"{watched} of {len(enabled)} enabled wallets checked, {added} new moves"
