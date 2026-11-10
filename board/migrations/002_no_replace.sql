-- Board: no REPLACE overwrites. Safe to run more than once.
-- INSERT OR REPLACE (and REPLACE conflict handling) deletes the clashing row without firing the delete triggers.
-- These refuse an insert whose id or other unique key already exists, before any conflict handling runs,
-- so a row can't be overwritten on any connection. The message keeps SQLite's own wording, so a plain
-- duplicate still fails as an IntegrityError naming the column.
BEGIN;
CREATE TRIGGER IF NOT EXISTS signals_no_replace_id BEFORE INSERT ON signals
WHEN EXISTS (SELECT 1 FROM signals WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: signals.id (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS signals_no_replace_key BEFORE INSERT ON signals
WHEN EXISTS (SELECT 1 FROM signals WHERE source_key = NEW.source_key)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: signals.source_key (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS proposed_orders_no_replace_id BEFORE INSERT ON proposed_orders
WHEN EXISTS (SELECT 1 FROM proposed_orders WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: proposed_orders.id (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS proposed_orders_no_replace_key BEFORE INSERT ON proposed_orders
WHEN EXISTS (SELECT 1 FROM proposed_orders WHERE source_key = NEW.source_key)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: proposed_orders.source_key (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS orders_no_replace_id BEFORE INSERT ON orders
WHEN EXISTS (SELECT 1 FROM orders WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: orders.id (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS orders_no_replace_key BEFORE INSERT ON orders
WHEN EXISTS (SELECT 1 FROM orders WHERE client_order_id = NEW.client_order_id AND status = NEW.status)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: orders.client_order_id, orders.status (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS results_no_replace_id BEFORE INSERT ON results
WHEN EXISTS (SELECT 1 FROM results WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: results.id (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS results_no_replace_key BEFORE INSERT ON results
WHEN EXISTS (SELECT 1 FROM results WHERE source_key = NEW.source_key)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: results.source_key (replace refused)'); END;
CREATE TRIGGER IF NOT EXISTS messages_no_replace_id BEFORE INSERT ON messages
WHEN EXISTS (SELECT 1 FROM messages WHERE id = NEW.id)
BEGIN SELECT RAISE(ABORT, 'UNIQUE constraint failed: messages.id (replace refused)'); END;
COMMIT;
