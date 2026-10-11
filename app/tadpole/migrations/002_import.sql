-- entries imported from the old Obsidian diary keep their file name (so an import can be re-run safely) and every extra field they carried
ALTER TABLE entries ADD COLUMN external_id TEXT;
ALTER TABLE entries ADD COLUMN details TEXT;
CREATE UNIQUE INDEX ix_entries_external ON entries(external_id) WHERE external_id IS NOT NULL;
-- reference documents kept alongside the diary: the protocol, reviews, lab reports. kind is md (body holds the text) or pdf (file_name is in the library folder)
CREATE TABLE documents(
  id INTEGER PRIMARY KEY AUTOINCREMENT, slug TEXT NOT NULL UNIQUE, title TEXT NOT NULL, kind TEXT NOT NULL,
  body TEXT NOT NULL DEFAULT '', file_name TEXT, source TEXT NOT NULL DEFAULT '', sort INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
