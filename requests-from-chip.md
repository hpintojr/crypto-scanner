# Requests from Chip

Chip: write new requests below, one per dated heading. This is the scanner's only inbox.

## 2026-11-04 (PT)
Switch the cycle interval from 15 minutes to 5 minutes. Keep the scanner thresholds, buzz scoring, and watchlist rules exactly the same. Confirm the new interval in status.md on the next run.

## 2026-11-04 23:45 (PT)
Hamilton approved in chat: set scanner to 5 min. Change the Otto schedule itself to every 5 minutes. He accepts the cost of about 288 agent runs a day. Confirm in status.md once the next-run time shows 5-minute spacing.

## 2026-11-10 (PT)
Hamilton asked Chip to review the sim strategy with Otto and propose fixes. Findings from the repo data: (1) the crypto-momentum slice lost 8 of 8 trades, all stopped out at -5% to -6.5% within hours on Nov 5-6, and the backtest already showed crypto momentum at -0.97% per trade with a 34% win rate, so the rule is negative expectancy, not just a bad week; (2) the signal has no follow-through, crypto passed signals average +0.01% at 1h and -6.88% at 24h, moves reverse within a day; (3) the allocation plan changed on day 2 (Nov 6), closing all 15 allocation positions at a loss, which resets the 90-day unchanged-plan clock; (4) the premarket gap signal is the only one with positive follow-through at 1h and 1d, but on small samples. Proposed fixes: stop the crypto-momentum slice from opening new sim orders and demote it to research-only until a rule with positive backtest expectancy exists; freeze the allocation plan with no further changes so the 90-day clock can run; backtest the premarket gap signal before adopting it live; keep Form 4 logging going. Do NOT change the strategy yet. Write the proposed changes and the evidence for each in answers-to-chip.md, and Hamilton will approve before anything changes.
