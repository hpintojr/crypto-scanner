# What is published and what our own tests show

Paper only. No strategy here is guaranteed. Not financial advice. Published results are before the costs and taxes you pay,
and edges tend to shrink after they become well known.

## Published strategies (from my knowledge; I could not open the papers this session, so check the citations before relying on numbers)
| Idea | Source | What it claims | Main weakness |
|---|---|---|---|
| Buy and hold a broad index | Decades of manager-vs-index studies | Most active managers trail the index after fees | Full drop in a crash (-50% or worse) |
| Trend filter, 10-month average | Faber (2007), "A Quantitative Approach to Tactical Asset Allocation" | Similar return to buy and hold with much smaller drops | Lags in strong bull markets, whipsaws in sideways ones |
| Time-series momentum | Moskowitz, Ooi, Pedersen (2012) | Own what has risen over 12 months across many assets | Needs many markets and futures; weak in choppy years |
| Cross-sectional momentum | Jegadeesh and Titman (1993) | Last year's winners beat losers | Sharp reversals; edge has shrunk |
| Dual momentum | Antonacci | Stocks vs foreign stocks, bonds when both fall | Few trades, so luck matters; many parameters in published versions |
| Diversified mixes (60/40, all weather) | Common practice | Smaller swings than stocks alone | 2022 showed stocks and bonds can fall together |

## Our own test 1: century of S&P 500 data (research/century_trend_check.py, run this session)
Monthly index plus dividends, 1901 to Sep 2026, 10-month average rule, cash at 0%, 0.1% cost per switch.

| Period | Rule %/yr | Rule worst drop | Hold %/yr | Hold worst drop |
|---|--:|--:|--:|--:|
| 1901-2026 | 10.3 | -46% | 10.0 | -82% |
| 1901-1950 | 9.6 | -46% | 7.8 | -82% |
| 1951-2000 | 11.0 | -16% | 12.8 | -39% |
| 2001-2026 | 10.0 | -19% | 8.8 | -49% |
| 1929-1940 | 4.5 | -46% | -1.1 | -82% |
| 2000-2012 | 5.7 | -11% | 1.8 | -49% |
| 2020-2026 | 12.8 | -19% | 14.9 | -19% |

Read it honestly: the rule roughly matched buy and hold on return and cut the worst drops by about half to two thirds.
It lost to buy and hold in the long 1951-2000 bull market and in 2020-2026. It is a risk reducer, not a way to beat the market.
Flaws: newest dividend rows are zero (understates both lines), cash earns 0%, monthly index not a tradable fund, and the
1901-1930 data is reconstructed. This also is not a test of your ETFs.

## Our own test 2: the ETF candidates
research/candidate_test.py compares hold SPY, SPY 200-day trend, top-2 rotation, dual momentum, Faber 5-asset, 60/40 and an
all-weather mix on Alpaca daily data from 2017. I could not run it this session (price data is not reachable from here).
Otto runs it and writes data/candidate-test.md. Until that file exists there is no ETF result to quote.

## What this means for the $2,000 sim
- Realistic goal: SPY-like return with smaller drops, not beating SPY.
- A 5% annual edge on $2,000 is $100 a year. Judge the work by what it teaches and by drawdown, not by dollars.
