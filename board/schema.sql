-- Shared board for separate jobs. Paper only. The database file lives outside the repo (W/data/board.db).
-- Every table is append-only: updates and deletes are refused. One exception: messages.status (new, read, done) can be updated. One writer per table, see docs/board.md.
-- source_key is the writer's own id for a row, so copying the same thing twice is refused.

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY,
    source_job TEXT NOT NULL,
    source_key TEXT NOT NULL UNIQUE,
    market TEXT,
    symbol TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    score REAL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS proposed_orders (
    id INTEGER PRIMARY KEY,
    source_job TEXT NOT NULL,
    source_key TEXT NOT NULL UNIQUE,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    qty_or_dollars TEXT NOT NULL,
    thesis TEXT,
    against TEXT,
    status TEXT NOT NULL CHECK (status IN ('proposed', 'approved', 'rejected', 'sent', 'filled', 'failed')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Written only by the Executor. A status change is a new row, so a client_order_id appears once per status.
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY,
    proposed_order_id INTEGER REFERENCES proposed_orders(id),
    client_order_id TEXT NOT NULL,
    alpaca_order_id TEXT,
    status TEXT NOT NULL CHECK (status IN ('sent', 'filled', 'partially_filled', 'canceled', 'rejected', 'failed')),
    filled_qty TEXT,
    filled_avg_price TEXT,
    updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (client_order_id, status)
);
-- One client_order_id belongs to one proposed order, or none.
CREATE TRIGGER IF NOT EXISTS orders_one_proposal BEFORE INSERT ON orders
WHEN EXISTS (SELECT 1 FROM orders WHERE client_order_id = NEW.client_order_id
             AND proposed_order_id IS NOT NEW.proposed_order_id)
BEGIN SELECT RAISE(ABORT, 'client_order_id already used by another proposed order'); END;

CREATE TABLE IF NOT EXISTS results (
    id INTEGER PRIMARY KEY,
    job TEXT NOT NULL,
    source_key TEXT NOT NULL UNIQUE,
    metric TEXT NOT NULL,
    value REAL,
    period TEXT,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    from_job TEXT NOT NULL,
    to_job TEXT NOT NULL,
    body TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new', 'read', 'done')),
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);
CREATE TRIGGER IF NOT EXISTS signals_no_update BEFORE UPDATE ON signals
BEGIN SELECT RAISE(ABORT, 'signals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS signals_no_delete BEFORE DELETE ON signals
BEGIN SELECT RAISE(ABORT, 'signals is append-only'); END;
CREATE TRIGGER IF NOT EXISTS proposed_orders_no_update BEFORE UPDATE ON proposed_orders
BEGIN SELECT RAISE(ABORT, 'proposed_orders is append-only'); END;
CREATE TRIGGER IF NOT EXISTS proposed_orders_no_delete BEFORE DELETE ON proposed_orders
BEGIN SELECT RAISE(ABORT, 'proposed_orders is append-only'); END;
CREATE TRIGGER IF NOT EXISTS orders_no_update BEFORE UPDATE ON orders
BEGIN SELECT RAISE(ABORT, 'orders is append-only'); END;
CREATE TRIGGER IF NOT EXISTS orders_no_delete BEFORE DELETE ON orders
BEGIN SELECT RAISE(ABORT, 'orders is append-only'); END;
CREATE TRIGGER IF NOT EXISTS results_no_update BEFORE UPDATE ON results
BEGIN SELECT RAISE(ABORT, 'results is append-only'); END;
CREATE TRIGGER IF NOT EXISTS results_no_delete BEFORE DELETE ON results
BEGIN SELECT RAISE(ABORT, 'results is append-only'); END;
-- messages: status is the one allowed update. Any other column, named in an UPDATE, is refused.
CREATE TRIGGER IF NOT EXISTS messages_status_only BEFORE UPDATE OF id, from_job, to_job, body, created_at ON messages
BEGIN SELECT RAISE(ABORT, 'messages: only status can be updated'); END;
CREATE TRIGGER IF NOT EXISTS messages_no_delete BEFORE DELETE ON messages
BEGIN SELECT RAISE(ABORT, 'messages is append-only'); END;
