# Board status

Shared database, copy only. No job reads from it yet. Paper only.

- Last mirror: 2026-11-10T21:08:26Z (0.0s)
- Tables: signals 630, proposed_orders 53, orders 0, results 1450, messages 0
- Added this run: signals 0, proposed_orders 0, results 0
- Last export: 2026-11-10 (data/board-export.csv)
- Messages: status (new, read, done) is the one allowed update; other columns and deletes refused
- Errors: 0

## Migration 002_no_replace (2026-11-10)

- Applied to board.db after backup (board.db.bak-20261110-pre002, outside the repo).
- Triggers: 20 total, 9 no-replace. Integrity check: ok.
- INSERT OR REPLACE / REPLACE / upsert onto an existing id or unique key: refused on all five tables.
- Tests on a throwaway copy and a fresh database: 73 of 73 passed. Errors: 0.
- This section is replaced by the next mirror run; the record stays in git history.
