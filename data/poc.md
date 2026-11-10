# Previous-session POC test

71 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 7 | -0.182 | 29 |
| crypto | broke | no sweep | 24h | 3 | -0.131 | 33 |
| crypto | broke | no sweep | 4h | 6 | -0.063 | 50 |
| crypto | held | no sweep | 1h | 8 | +0.007 | 25 |
| crypto | held | no sweep | 24h | 5 | +2.734 | 80 |
| crypto | held | no sweep | 4h | 8 | -0.162 | 0 |
| stocks | broke | no sweep | 1h | 27 | +0.673 | 67 |
| stocks | broke | sweep | 1h | 1 | -0.209 | 0 |
| stocks | held | no sweep | 1h | 28 | +0.119 | 54 |
