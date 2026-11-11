# Previous-session POC test

163 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 7 | -0.182 | 29 |
| crypto | broke | no sweep | 24h | 7 | +0.520 | 57 |
| crypto | broke | no sweep | 4h | 7 | -0.144 | 43 |
| crypto | held | no sweep | 1h | 10 | -0.005 | 20 |
| crypto | held | no sweep | 24h | 8 | +1.682 | 62 |
| crypto | held | no sweep | 4h | 10 | -0.031 | 10 |
| stocks | broke | no sweep | 1d | 27 | +0.076 | 44 |
| stocks | broke | no sweep | 1h | 74 | +0.083 | 49 |
| stocks | broke | sweep | 1d | 1 | -0.031 | 0 |
| stocks | broke | sweep | 1h | 1 | -0.209 | 0 |
| stocks | held | no sweep | 1d | 28 | -0.175 | 54 |
| stocks | held | no sweep | 1h | 70 | +0.024 | 47 |
| stocks | held | sweep | 1h | 2 | +0.735 | 100 |
