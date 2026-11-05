"""Profit and risk numbers for the simulation, in data/metrics.md. Flags problems but never changes a trade."""
import os
from . import core

START = 1000.0
MIN_TRADES = 30  # below this, the numbers are too few to judge
MAX_DRAWDOWN_FLAG = 10.0


def trade_stats(trades):
    """Win rate, average win and loss, expectancy (average profit per trade) and profit factor."""
    pnl = [float(t["pnl"]) for t in trades]
    wins = [p for p in pnl if p > 0]
    losses = [p for p in pnl if p <= 0]
    return {"n": len(pnl), "win": 100 * len(wins) / len(pnl) if pnl else 0,
            "avg_win": sum(wins) / len(wins) if wins else 0, "avg_loss": sum(losses) / len(losses) if losses else 0,
            "expectancy": sum(pnl) / len(pnl) if pnl else 0, "total": sum(pnl),
            "profit_factor": sum(wins) / -sum(losses) if sum(losses) else None}


def drawdown(values):
    """Largest fall from a peak, and the current fall, in percent."""
    peak, worst, now = 0.0, 0.0, 0.0
    for v in values:
        peak = max(peak, v)
        now = (v / peak - 1) * 100 if peak else 0
        worst = min(worst, now)
    return worst, now


def _market(t):
    return "Crypto" if "/" in t["symbol"] else "Stocks"


def _row(name, s):
    pf = f"{s['profit_factor']:.2f}" if s["profit_factor"] is not None else "n/a"
    return f"| {name} | {s['n']} | {s['win']:.0f} | ${s['avg_win']:.2f} | ${s['avg_loss']:.2f} | ${s['expectancy']:.2f} | {pf} | ${s['total']:.2f} |"


def flags(by_market, worst):
    out = []
    for name, s in by_market.items():
        if s["n"] >= MIN_TRADES and s["expectancy"] < 0:
            out.append(f"{name}: losing money per trade over {s['n']} trades")
        if s["n"] >= MIN_TRADES and s["profit_factor"] is not None and s["profit_factor"] < 1.2:
            out.append(f"{name}: profit factor under 1.2, a thin margin")
    if worst <= -MAX_DRAWDOWN_FLAG:
        out.append(f"Total value fell {abs(worst):.1f}% from its peak")
    return out


def write(s, prices, equity_rows):
    trades = core.read("sim-trades.csv")
    markets = {m: [t for t in trades if _market(t) == m] for m in ("Crypto", "Stocks")}
    by_market = {m: trade_stats(v) for m, v in markets.items()}
    worst, current = drawdown([float(r["equity"]) for r in equity_rows])
    lines = ["# Simulation metrics", "", "Paper money. Expectancy is average profit per closed trade. Profit factor is total wins "
             "divided by total losses, and above 1 means making money. "
             f"Treat anything under {MIN_TRADES} trades as too early to judge.", "",
             "## Closed trades", "", "| Group | Trades | Win % | Avg win | Avg loss | Expectancy | Profit factor | Total |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    lines += [_row(m, by_market[m]) for m in by_market]
    groups = {}
    for t in trades:
        groups.setdefault(t["source"], []).append(t)
        groups.setdefault(f"Exit: {t['exit_reason']}", []).append(t)
    lines += [_row(k, trade_stats(groups[k])) for k in sorted(groups)]
    lines += ["", "## Open positions", "", "| Symbol | Cost | Value | Profit or loss | % |", "|---|---:|---:|---:|---:|"]
    held = 0.0
    for p in s["positions"]:
        if p["status"] != "open" or p["symbol"] not in prices:
            continue
        value = float(p["qty"]) * prices[p["symbol"]]
        held += value
        lines.append(f"| {p['symbol']} | ${p['cost']:.2f} | ${value:.2f} | ${value - p['cost']:.2f} | {(value / p['cost'] - 1) * 100:+.2f} |")
    btc_now = prices.get("BTC/USD")
    total = float(equity_rows[-1]["equity"]) if equity_rows else START * 2
    lines += ["", "## Risk", "", f"- Largest fall from peak: {worst:.2f}%", f"- Currently below peak: {current:.2f}%",
              f"- Money in open positions: ${held:,.2f} of ${total:,.2f}"]
    if btc_now and s.get("btc_start"):
        lines.append(f"- BTC since start: {(btc_now / s['btc_start'] - 1) * 100:+.2f}%")
    if s.get("spy_start") and prices.get("SPY"):
        lines.append(f"- SPY since start: {(prices['SPY'] / s['spy_start'] - 1) * 100:+.2f}%")
    found = flags(by_market, worst)
    lines += ["", "## Flags", ""] + ([f"- {f}" for f in found] or ["None so far."])
    with open(os.path.join(core.DATA, "metrics.md"), "w") as f:
        f.write("\n".join(lines) + "\n")
    return found
