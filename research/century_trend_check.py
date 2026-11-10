"""Long-history check of the 10-month moving-average rule on the S&P 500 (monthly, 1901 to the latest month).
Research only, places no orders. Run: python3 -m research.century_trend_check  (needs raw.githubusercontent.com access)

Data: github.com/datasets/s-and-p-500 (monthly index level and dividends, Shiller-style).
Rule: hold the index while last month's close is above the average of the prior 10 month-ends, else cash at 0%.
Cost 0.1% per switch. Decision uses data up to the previous month-end only.
Known flaws: the dividend column is zero in the newest rows (understates both lines recently); cash earns 0%, which understates
the rule; a monthly index is not a tradable fund; the 10-month length was fixed in advance (Faber 2007), not tuned here.
"""
import csv
import io
import urllib.request

URL = "https://raw.githubusercontent.com/datasets/s-and-p-500/main/data/data.csv"
PERIODS = [("1901", "2026"), ("1901", "1950"), ("1951", "2000"), ("2001", "2026"), ("1929", "1940"), ("2000", "2012"), ("2020", "2026")]


def load(text):
    rows = list(csv.DictReader(io.StringIO(text)))
    d = [r["Date"] for r in rows]
    p = [float(r["SP500"]) for r in rows]
    dv = [float(r["Dividend"]) if r["Dividend"] else 0.0 for r in rows]
    tr = [0.0] + [(p[i] / p[i - 1] - 1) + dv[i - 1] / 12 / p[i - 1] for i in range(1, len(p))]
    return d, p, tr


def run(d, p, tr, start, end, n=10, cost=0.001):
    v = h = pv = hp = 1.0
    mdd = hdd = 0.0
    prev, sw, months = True, 0, 0
    for i in range(max(n, 12), len(p)):
        if not (start <= d[i][:4] <= end):
            continue
        inn = p[i - 1] > sum(p[i - n:i]) / n
        if inn != prev:
            v *= 1 - cost
            sw += 1
        prev = inn
        v *= (1 + tr[i]) if inn else 1.0
        h *= 1 + tr[i]
        months += 1
        pv, hp = max(pv, v), max(hp, h)
        mdd, hdd = min(mdd, v / pv - 1), min(hdd, h / hp - 1)
    yrs = max(months / 12, 1e-9)
    return {"rule": (v ** (1 / yrs) - 1) * 100, "rule_dd": mdd * 100, "hold": (h ** (1 / yrs) - 1) * 100, "hold_dd": hdd * 100, "switches": sw}


def main():
    text = urllib.request.urlopen(URL, timeout=30).read().decode()
    d, p, tr = load(text)
    print(f"Data {d[0]} to {d[-1]}")
    print("| Period | Rule %/yr | Rule worst drop % | Hold %/yr | Hold worst drop % | Switches |\n|---|--:|--:|--:|--:|--:|")
    for s, e in PERIODS:
        r = run(d, p, tr, s, e)
        print(f"| {s}-{e} | {r['rule']:.1f} | {r['rule_dd']:.0f} | {r['hold']:.1f} | {r['hold_dd']:.0f} | {r['switches']} |")


if __name__ == "__main__":
    main()
