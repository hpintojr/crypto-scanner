# Previous-session POC test

10 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 4 | -0.069 | 50 |
| crypto | broke | no sweep | 24h | 1 | -3.900 | 0 |
| crypto | broke | no sweep | 4h | 3 | -0.324 | 33 |
| crypto | held | no sweep | 1h | 6 | -0.179 | 0 |
| crypto | held | no sweep | 24h | 2 | +5.211 | 100 |
| crypto | held | no sweep | 4h | 5 | -0.101 | 0 |
