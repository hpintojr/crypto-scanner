# Previous-session POC test

130 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 7 | -0.182 | 29 |
| crypto | broke | no sweep | 24h | 5 | -0.384 | 40 |
| crypto | broke | no sweep | 4h | 7 | -0.144 | 43 |
| crypto | held | no sweep | 1h | 10 | -0.005 | 20 |
| crypto | held | no sweep | 24h | 8 | +1.682 | 62 |
| crypto | held | no sweep | 4h | 9 | -0.190 | 0 |
| stocks | broke | no sweep | 1d | 23 | +0.220 | 52 |
| stocks | broke | no sweep | 1h | 58 | +0.127 | 53 |
| stocks | broke | sweep | 1h | 1 | -0.209 | 0 |
| stocks | held | no sweep | 1d | 21 | -0.313 | 52 |
| stocks | held | no sweep | 1h | 52 | +0.058 | 50 |
| stocks | held | sweep | 1h | 1 | +0.496 | 100 |
