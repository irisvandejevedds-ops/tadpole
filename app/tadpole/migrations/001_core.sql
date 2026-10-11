CREATE TABLE settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE sessions(token_hash TEXT PRIMARY KEY, created_at TEXT NOT NULL, last_seen TEXT NOT NULL, expires_at TEXT NOT NULL, user_agent TEXT NOT NULL DEFAULT '');
CREATE TABLE api_tokens(
  id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, token_sha256 TEXT NOT NULL UNIQUE,
  created_at TEXT NOT NULL, last_used_at TEXT, revoked_at TEXT);
-- the diary: what was eaten or drunk, how the body felt, and notes. ts is when it happened (UTC).
CREATE TABLE entries(
  id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT NOT NULL,
  kind TEXT NOT NULL,                              -- food | symptom | clear (an explicit "no symptoms") | note
  text TEXT NOT NULL DEFAULT '',
  severity INTEGER,                                -- 0 to 10, symptoms only (null = not said)
  source TEXT NOT NULL DEFAULT 'app',              -- app | widget
  idempotency_key TEXT UNIQUE, created_at TEXT NOT NULL, removed_at TEXT);
CREATE INDEX ix_entries_ts ON entries(ts);
