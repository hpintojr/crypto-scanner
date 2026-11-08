# Previous-session POC test

7 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 2 | +0.001 | 50 |
| crypto | broke | no sweep | 4h | 1 | -0.063 | 0 |
| crypto | held | no sweep | 1h | 5 | -0.155 | 0 |
| crypto | held | no sweep | 4h | 5 | -0.101 | 0 |
