# Previous-session POC test

12 touches logged. Research only, no orders. Rules are in research/poc.py.

Return is the move after the touch in the direction the closing bar pointed, before costs.
'Held' means the touch bounced; 'broke' means price closed through the POC. Stock volume is IEX only.
Treat any row under 30 signals as noise.

| Market | Touch | Sweep | Horizon | Signals | Avg return % | Went that way % |
|---|---|---|---|--:|--:|--:|
| crypto | broke | no sweep | 1h | 4 | -0.069 | 50 |
| crypto | broke | no sweep | 24h | 1 | -3.900 | 0 |
| crypto | broke | no sweep | 4h | 4 | -0.042 | 50 |
| crypto | held | no sweep | 1h | 7 | -0.149 | 14 |
| crypto | held | no sweep | 24h | 3 | +4.316 | 100 |
| crypto | held | no sweep | 4h | 6 | -0.097 | 0 |
