-- messages: status (new, read, done) is the one allowed update. Every other column stays locked; DELETE stays refused.
-- Safe to run more than once. Other tables are not touched.
BEGIN;
DROP TRIGGER IF EXISTS messages_no_update;
CREATE TRIGGER IF NOT EXISTS messages_status_only BEFORE UPDATE OF id, from_job, to_job, body, created_at ON messages
BEGIN SELECT RAISE(ABORT, 'messages: only status can be updated'); END;
COMMIT;
