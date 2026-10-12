-- Syncing with phones: every entry gets a stable id (uuid), a change counter (rev) that goes up on every insert or edit so a phone can ask
-- "what changed since rev N", and an updated_at used to settle two edits of the same entry (the later one wins).
ALTER TABLE entries ADD COLUMN uuid TEXT;
ALTER TABLE entries ADD COLUMN rev INTEGER NOT NULL DEFAULT 0;
ALTER TABLE entries ADD COLUMN updated_at TEXT;
UPDATE entries SET
  uuid = lower(hex(randomblob(4)))||'-'||lower(hex(randomblob(2)))||'-4'||substr(lower(hex(randomblob(2))),2)||'-'||substr('89ab',abs(random())%4+1,1)||substr(lower(hex(randomblob(2))),2)||'-'||lower(hex(randomblob(6))),
  rev = id, updated_at = COALESCE(removed_at, created_at);
CREATE UNIQUE INDEX ix_entries_uuid ON entries(uuid);
CREATE INDEX ix_entries_rev ON entries(rev);
CREATE TRIGGER entries_ai AFTER INSERT ON entries BEGIN
  UPDATE entries SET
    uuid = COALESCE(NEW.uuid, lower(hex(randomblob(4)))||'-'||lower(hex(randomblob(2)))||'-4'||substr(lower(hex(randomblob(2))),2)||'-'||substr('89ab',abs(random())%4+1,1)||substr(lower(hex(randomblob(2))),2)||'-'||lower(hex(randomblob(6)))),
    rev = (SELECT COALESCE(MAX(rev), 0) + 1 FROM entries),
    updated_at = COALESCE(NEW.updated_at, strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
  WHERE id = NEW.id;
END;
CREATE TRIGGER entries_au AFTER UPDATE ON entries WHEN NEW.rev = OLD.rev BEGIN
  UPDATE entries SET
    rev = (SELECT MAX(rev) + 1 FROM entries),
    updated_at = CASE WHEN NEW.updated_at IS OLD.updated_at THEN strftime('%Y-%m-%dT%H:%M:%SZ', 'now') ELSE NEW.updated_at END
  WHERE id = NEW.id;
END;
-- documents change by slug; remember when, so a phone only downloads them when they changed
-- (importer.py already sets updated_at on each document)
ALTER TABLE api_tokens ADD COLUMN scope TEXT NOT NULL DEFAULT 'widget';
