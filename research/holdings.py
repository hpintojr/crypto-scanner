"""Tracks a buy-and-hold of Hamilton's real coin amounts at simulated cost. No orders, nothing sold.

The list and results stay beside the repo on Otto, never in it, because the repo is public.
status.md only ever shows a percentage. Prices come from CoinGecko, once an hour.
"""
import csv, json, os, urllib.request
from datetime import timedelta
from . import core

DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FIELDS = ["date", "value_usd", "return_pct", "btc_equivalent_usd"]


def cycle(state, errors):
    path = os.path.join(DIR, ".holdings.csv")
    if not os.path.exists(path):
        state["last_holdings"] = "not set up"
        return
    last = state.get("holdings_checked")
    if last and core.now() - core.parse(last) < timedelta(minutes=55):
        return
    try:
        with open(path, newline="") as f:
            coins = list(csv.DictReader(f))
        ids = ",".join(sorted({c["coin_id"].strip() for c in coins} | {"bitcoin"}))
        req = urllib.request.Request(f"https://api.coingecko.com/api/v3/simple/price?ids={ids}&vs_currencies=usd",
                                     headers={"User-Agent": "crypto-scanner-research/1.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            prices = json.loads(r.read())
        missing = sum(c["coin_id"].strip() not in prices for c in coins)
        if missing or "bitcoin" not in prices:
            # status.md is public, so errors never name a coin from the private list
            errors.append(f"hold test: {missing or 1} coin(s) have no price, check the CoinGecko ids in .holdings.csv")
            return
        base_path = os.path.join(DIR, ".holdings-baseline.json")
        if os.path.exists(base_path):
            with open(base_path) as f:
                base = json.load(f)
        else:  # the simulated purchase: every coin bought at this moment's price
            base = {"date": core.now().strftime("%Y-%m-%d"), "btc": prices["bitcoin"]["usd"],
                    "prices": {c["coin_id"].strip(): prices[c["coin_id"].strip()]["usd"] for c in coins}}
            with open(base_path, "w") as f:
                json.dump(base, f)
        qty = {c["coin_id"].strip(): float(c["quantity"]) for c in coins}
        start = sum(q * base["prices"][k] for k, q in qty.items())
        value = sum(q * prices[k]["usd"] for k, q in qty.items())
        ret = (value / start - 1) * 100
        row = {"date": core.now().strftime("%Y-%m-%d"), "value_usd": round(value, 2), "return_pct": round(ret, 3),
               "btc_equivalent_usd": round(start * prices["bitcoin"]["usd"] / base["btc"], 2)}
        hist = os.path.join(DIR, ".holdings-history.csv")
        rows = []
        if os.path.exists(hist):
            with open(hist, newline="") as f:
                rows = [r for r in csv.DictReader(f) if r["date"] != row["date"]]
        with open(hist, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(rows + [row])
        state["holdings_checked"] = core.now().strftime(core.FMT)
        state["last_holdings"] = f"{ret:+.2f}% since {base['date']}, BTC {(prices['bitcoin']['usd'] / base['btc'] - 1) * 100:+.2f}%"
    except Exception as e:
        errors.append(f"hold test: {type(e).__name__}")  # the details could include the private list
