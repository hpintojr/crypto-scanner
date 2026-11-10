# Shared board

One SQLite database where separate jobs read and write, instead of one big bot. Paper only. No keys.

- Database: `../data/board.db`, next to the repo and never committed. Schema: `board/schema.sql`.
- Every table is append-only: updates and deletes are refused. A change is a new row.
- Each row has an `id` and `created_at` (`orders` has `updated_at`). Copied rows carry a `source_key`, so the same thing can't be copied twice.
- Nothing reads from the board yet. No job starts reading it without Hamilton's approval.

## One writer per table

| Table | Writer | What goes in |
|---|---|---|
| signals | `mirror:scanner` (board/mirror.py) | Copies of data/signals.csv |
| proposed_orders | `mirror:sim` (board/mirror.py) | Copies of the sim's buys and sells from data/sim-trades.csv and data/sim-state.json |
| orders | Executor only | Nothing yet. No Executor exists, and the mirror never writes here |
| results | `mirror:sim`, `mirror:scanner` (board/mirror.py) | Daily paper equity and SPY equivalent for finished days; signal outcomes from data/outcomes.csv |
| messages | Any job, named in `from_job` | Notes between jobs |

When a real job replaces a mirror, it takes over that table and the mirror stops writing it.

## orders

- Only the Executor writes it.
- `client_order_id` is unique per status: a status change (sent, filled, ...) is a new row, and the same id with the same status is refused.
- One `client_order_id` can belong to only one proposed order; reuse for another is refused.

## Running

- `python3 -m board.mirror` from the repo root, after `scanner.py`. It reads the scanner's and sim's files and changes nothing they do.
- It writes `data/board-status.md` every run and `data/board-export.csv` once a day (signals and results only).
- It never reads `.holdings*` files.
