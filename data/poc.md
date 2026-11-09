# Previous-session POC test

53 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 5 | -0.110 | 40 |
| crypto | broke | no sweep | 24h | 1 | -3.900 | 0 |
| crypto | broke | no sweep | 4h | 5 | -0.012 | 60 |
| crypto | held | no sweep | 1h | 7 | -0.149 | 14 |
| crypto | held | no sweep | 24h | 4 | +3.744 | 100 |
| crypto | held | no sweep | 4h | 7 | -0.182 | 0 |
