# Shared board

One SQLite database where separate jobs read and write, instead of one big bot. Paper only. No keys.

- Database: `../data/board.db`, next to the repo and never committed. Schema: `board/schema.sql`.
- Every table is append-only: updates and deletes are refused. A change is a new row.
- One exception: `messages.status` (new, read, done) can be updated, so a message can be marked read or done. Every other `messages` column stays locked, and deletes are still refused.
- No overwrites: an insert whose `id` or other unique key (`source_key`; `client_order_id` + `status` on `orders`) already exists is refused, including `INSERT OR REPLACE`, `REPLACE` and upserts. This holds on every connection; it does not depend on `PRAGMA recursive_triggers`. A plain duplicate still fails as before: an IntegrityError naming the column.
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

## Migrations

- `board/schema.sql` builds a fresh database. `CREATE ... IF NOT EXISTS` does not change an existing trigger, so changes to an existing database go in `board/migrations/` as numbered `.sql` files.
- `python3 -m board.migrate` applies them to the real board; `python3 -m board.migrate PATH` to a copy. Each is safe to run twice. Test on a copy first.
- 001_messages_status_only: drops `messages_no_update`, adds `messages_status_only` (status is the one allowed update).
- 002_no_replace: adds a BEFORE INSERT trigger per unique key on all five tables, so `INSERT OR REPLACE` can't delete and overwrite a row.
