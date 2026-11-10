# Strategy spec: what we test next (paper only)

Status: proposal for Hamilton's approval. It changes nothing in the frozen plan (docs/STRATEGY_FREEZE.md) and places no orders.
No strategy here is proven. Nothing guarantees earnings. This is not financial advice.

## 1. Where things stand
- Frozen plan (commodities + crypto, 100-day trend rule) runs Nov 7, 2026 to Feb 5, 2027 and is not touched.
- Own evidence so far: holding SPY beat every active rule tested (SPY +28.4% over 500 days, all intraday rules lost,
  crypto momentum -0.97% per trade). The honest default is "hold SPY unless a rule beats it after costs".
- 90 days of paper trading cannot prove an edge. Historical tests screen ideas, paper trading checks execution.

## 2. Candidates (fixed in advance, run by `python3 -m research.candidate_test`)
| Name | Rule | Why it is on the list |
|---|---|---|
| hold_spy | Hold SPY | The benchmark. Everything else has to beat it. |
| spy_trend_200 | In SPY while close > 200-day average, checked weekly, else cash | Aims for a smaller worst drop, not more return |
| rotation_top2 | Monthly: rank SPY, QQQ, IWM, EFA, TLT, GLD, DBC by 12-1 month return, hold top 2 if above zero, else cash | Published, simple, few trades |
| dual_momentum | Monthly: better of SPY or EFA by 12-month return if above zero, else TLT | Antonacci |
| faber_5 | Monthly: 20% each in SPY, EFA, TLT, GLD, DBC while above its 210-day average, else cash | Faber 2007 |
| balanced_60_40 | 60% SPY, 40% TLT | Risk-reduction benchmark |
| all_weather | 30% SPY, 40% TLT, 15% GLD, 15% DBC | Risk-reduction benchmark |

Evidence and our long-history check are in docs/EVIDENCE.md.

Rejected for now: crypto momentum chasing (negative), intraday SPY rules (all lost), wallet moves and news tone (log only),
mean reversion (needs a regime test first), insider buys (keep logging, score at 30+ events against SPY).

## 3. Screen a candidate must pass before paper trading is even discussed
All of these, from data/candidate-test.md:
1. Beats hold_spy after costs over the whole period.
2. Beats hold_spy in both halves.
3. Smaller worst drop than hold_spy.
4. Still beats hold_spy at 5x the cost.
Then: Hamilton's written approval, a separate paper sleeve, and a 90-day forward test with its own clock. If it fails,
we hold SPY and say so. Do not change lookbacks after seeing results.

Known flattery in the test: today's surviving ETFs, IEX-only prices, cash earning 0%, close-to-close fills.

## 4. Risk limits for a NEW experimental sleeve only (never the frozen plan)
| Limit | Value | Note |
|---|---|---|
| Risk per trade | 0.25% of sleeve equity | The two source documents disagreed (0.50% vs 0.25%). Use the smaller. $5 on $2,000. |
| Daily loss pause | 1% | Pause new entries for the day |
| Drawdown pause | 10% | Pause new entries and review; not a guaranteed max loss |
| Crypto share | 20% max | Zero in the three candidates above |
| Leverage, shorting, averaging down | Never | |
| Data | No orders on missing, stale or inconsistent data | |
| Kill switch | SIM_STOP halts all order writers | |
Risk per trade is only meaningful for rules with stops. The three candidates above hold ETFs without stops, so the real
control there is position size and the drawdown pause. Gaps and slippage can exceed any stop.

## 5. Decisions only Hamilton can make
1. Formally drop the old momentum picks (recommended: yes, 8 of 8 hit the stop).
2. Confirm the 25% review limit on the frozen plan.
3. Keep crypto at half of the frozen plan or not (changing it restarts the clock).
4. Whether the screen above is the bar, and whether to open a small separate sleeve if a candidate passes.

## 6. What this does not do
It does not make the bot profitable on a schedule. The most likely finding is that holding SPY does as well or better.
If so, the right move is to stop paying costs and complexity for no gain.

## 7. Decision recorded Nov 10, 2026 (pending Hamilton's written yes on the open items)
Result of data/candidate-test.md (Jul 2020 to Nov 2026): no candidate beat hold_spy on return or Sharpe after costs.
Rules that cut the worst drop did it by giving up much of the return. Conclusion:
1. hold_spy is the control and the default answer. Nothing replaces it unless it passes section 3 AND a 90-day forward test.
2. research/control_sleeves.py keeps two virtual $2,000 sleeves from the freeze date: hold_spy and spy_trend_200. No orders,
   no change to PLAN or sim.py. Output: data/control-sleeves.md. spy_trend_200 is the "smaller drops" option, in shadow only.
3. The frozen commodities and crypto plan runs to Feb 5, 2027 and is judged against hold_spy on the graduation checklist.
4. Old momentum picks stay off.
5. Insider buys stay log-only until 30+ events are scored against SPY.
Real-money investing is Hamilton's decision, outside this repo. Nothing here is financial advice.
