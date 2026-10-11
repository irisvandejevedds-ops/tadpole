"""Copies the old Obsidian health folder into Tadpole. Safe to run again: entries are matched by their file name and documents by slug.

    python -m tadpole.importer HEALTH_DIR [--dry-run]

Reads TADPOLE_DATA_DIR / TADPOLE_TZ like the web app. Never writes to HEALTH_DIR."""
import json
import pathlib
import shutil
import sys
from collections import Counter

from . import clock, vaultimport
from .config import get_config
from .db import open_db


def apply(db, entries, documents, library_dir, now, tz):
    added = updated = 0
    with db.tx():
        for e in entries:
            row = (e["ts"], e["kind"], e["text"], e["severity"], json.dumps(e["details"], ensure_ascii=False, sort_keys=True))
            old = db.one("SELECT id FROM entries WHERE external_id=?", (e["external_id"],))
            if old:
                db.ex("UPDATE entries SET ts=?, kind=?, text=?, severity=?, details=? WHERE id=?", row + (old["id"],))
                updated += 1
            else:
                db.ex("INSERT INTO entries(ts,kind,text,severity,details,source,external_id,created_at) VALUES(?,?,?,?,?,'vault',?,?)",
                      row + (e["external_id"], clock.iso(now)))
                added += 1
        docs = 0
        for d in documents:
            file_name = None
            if d["kind"] == "pdf":
                library_dir.mkdir(parents=True, exist_ok=True)
                file_name = d["slug"] + ".pdf"
                shutil.copyfile(d["file"], library_dir / file_name)
            db.ex("INSERT INTO documents(slug,title,kind,body,file_name,source,sort,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?) "
                  "ON CONFLICT(slug) DO UPDATE SET title=excluded.title, kind=excluded.kind, body=excluded.body, file_name=excluded.file_name, "
                  "source=excluded.source, sort=excluded.sort, updated_at=excluded.updated_at",
                  (d["slug"], d["title"], d["kind"], d.get("body", ""), file_name, d["source"], d["sort"], clock.iso(now), clock.iso(now)))
            docs += 1
        if entries and not db.get_setting("pond_start"):
            db.set_setting("pond_start", now.astimezone(tz).date().isoformat())
    return {"entries_added": added, "entries_updated": updated, "documents": docs}


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__)
        return 2
    cfg = get_config()
    entries, problems = vaultimport.read_entries(args[0], cfg.tz)
    documents = vaultimport.read_documents(args[0])
    kinds = Counter(e["kind"] for e in entries)
    print(f"read {len(entries)} entries {dict(kinds)} and {len(documents)} documents; {len(problems)} problems")
    for p in problems:
        print("  PROBLEM", p)
    if problems:
        return 1
    if "--dry-run" in argv:
        print("dry run: nothing written")
        return 0
    db = open_db(cfg.db_path)
    print(apply(db, entries, documents, cfg.data_dir / "library", clock.now(), cfg.tz))
    db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
