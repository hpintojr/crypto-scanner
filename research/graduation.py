"""Graduation checklist: the conditions Hamilton set before any real money, scored from the simulation's own data.

It reports, it never decides. Paper results flatter a strategy (easier fills, no slippage, no real fees),
so meeting every line is the minimum to start a conversation, not a green light. Not financial advice.
"""
import hashlib, json
from datetime import date

MIN_DAYS = 90            # one plan, unchanged, for at least this long
CLEAN_DAYS = 30          # consecutive days without a simulation error or a quantity mismatch
DRAWDOWN_LIMIT = 25.0    # worst peak-to-trough drop, in percent. Hamilton to confirm this number.
STRETCH_PCT = 5.0        # SPY must have both risen and fallen this much since the plan started


def plan_hash(plan):
    return hashlib.sha1(json.dumps(plan, sort_keys=True).encode()).hexdigest()[:10]


def track_plan(s, plan, today):
    """Restart the clock whenever the plan changes."""
    h = plan_hash(plan)
    if s.get("plan_hash") != h:
        s["plan_hash"], s["plan_since"] = h, today.isoformat()


def note_issue(s, today):
    s["last_issue"] = today.isoformat()


def _drawdown(values):
    peak, worst = None, 0.0
    for v in values:
        peak = v if peak is None else max(peak, v)
        worst = min(worst, (v / peak - 1) * 100)
    return worst


def _stretches(values):
    """Has the series both risen and fallen STRETCH_PCT from a prior low or high?"""
    lo = hi = values[0] if values else None
    up = down = False
    for v in values:
        lo, hi = min(lo, v), max(hi, v)
        up = up or (v / lo - 1) * 100 >= STRETCH_PCT
        down = down or (v / hi - 1) * 100 <= -STRETCH_PCT
    return up, down


def lines(s, equity_rows, today):
    since = s.get("plan_since") or s["start"]
    rows = [r for r in equity_rows if r["date"] >= since]
    eq = [float(r["equity"]) for r in rows]
    spy = [float(r["spy_equivalent"]) for r in rows if r.get("spy_equivalent")]
    days = (today - date.fromisoformat(since)).days
    ret = (eq[-1] / eq[0] - 1) * 100 if len(eq) > 1 else 0.0
    spy_ret = (spy[-1] / spy[0] - 1) * 100 if len(spy) > 1 else 0.0
    dd, spy_dd = _drawdown(eq) if eq else 0.0, _drawdown(spy) if spy else 0.0
    up, down = _stretches(spy) if spy else (False, False)
    issue = s.get("last_issue")
    clean = days if not issue or issue < since else (today - date.fromisoformat(issue)).days
    checks = [
        ("One plan, unchanged, for 90+ days", days >= MIN_DAYS, f"{days} days since {since}"),
        ("Beats the same money in SPY after costs", len(eq) > 1 and ret >= spy_ret, f"plan {ret:+.2f}% vs SPY {spy_ret:+.2f}%"),
        (f"30+ days without a simulation error or quantity mismatch", clean >= CLEAN_DAYS, f"{clean} clean days"),
        (f"Worst drop within {DRAWDOWN_LIMIT:.0f}% (Hamilton to confirm the limit)", dd >= -DRAWDOWN_LIMIT, f"plan {dd:.2f}%, SPY {spy_dd:.2f}%"),
        (f"Seen both a {STRETCH_PCT:.0f}% rise and a {STRETCH_PCT:.0f}% fall in SPY", up and down, f"rise {'yes' if up else 'no'}, fall {'yes' if down else 'no'}"),
    ]
    met = sum(ok for _, ok, _ in checks)
    out = ["", "## Graduation checklist", "",
           f"{met} of {len(checks)} met. Meeting all of them is the minimum before discussing real money, not a decision. "
           "Paper fills are better than real ones, so expect real results to be worse.", "",
           "| Condition | Met | Now |", "|---|---|---|"]
    out += [f"| {name} | {'yes' if ok else 'no'} | {now} |" for name, ok, now in checks]
    return out, met, len(checks)
