"""Syncing with a paired phone. The phone is where entries are made, so it is the source of truth; this side keeps a copy, adds what it knows (imported history,
documents) and sends it back. Each entry has a stable id. When both sides changed the same entry, the later edit wins."""
import hashlib
import json
import re

from . import clock, diary

MAX_ENTRIES = 5000
MAX_DETAILS = 20000
MAX_BODY = 6_000_000
ID = re.compile(r"^[A-Za-z0-9-]{8,64}$")


def _iso(v, what):
    try:
        clock.parse_iso(v)
    except (TypeError, ValueError):
        raise ValueError(f"bad {what}")
    return v


def clean(e):
    """One entry from the phone -> the values to store. Raises ValueError for anything malformed."""
    if not isinstance(e, dict):
        raise ValueError("an entry is not an object")
    uid = str(e.get("id") or "")
    if not ID.match(uid):
        raise ValueError("bad id")
    ts = _iso(e.get("ts"), "ts")
    updated = _iso(e.get("updatedAt") or ts, "updatedAt")
    removed = _iso(e["removedAt"], "removedAt") if e.get("removedAt") else None
    text = " ".join(str(e.get("text") or "").split())[:diary.MAX_TEXT]
    kind, sev = e.get("kind"), e.get("severity")
    if kind not in diary.KINDS:
        p = diary.parse(text)
        kind, text, sev = p["kind"], p["text"] or text, p["severity"] if sev is None else sev
    if kind == "clear":
        sev = 0
    elif kind != "symptom":
        sev = None
    elif sev is not None:
        sev = max(0, min(10, int(sev)))
    if not text and kind != "clear":
        raise ValueError("empty entry")
    details = e.get("details")
    if isinstance(details, str):
        try:
            details = json.loads(details)
        except ValueError:
            details = None
    details = json.dumps(details, ensure_ascii=False, sort_keys=True) if isinstance(details, dict) and details else None
    if details and len(details) > MAX_DETAILS:
        details = None
    source = e.get("source") if e.get("source") in diary.SOURCES else "app"
    return {"uuid": uid, "ts": ts, "kind": kind, "text": text or "No symptoms", "severity": sev, "source": source, "details": details, "removed_at": removed, "updated_at": updated}


def apply(db, entries):
    """Merge the phone's changed entries. -> {accepted, stale, rejected: [reasons], ids: set of ids that arrived}."""
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise ValueError("too many entries in one sync")
    out = {"accepted": 0, "stale": 0, "rejected": [], "ids": set()}
    now = clock.iso(clock.now())
    with db.tx():
        for e in entries:
            try:
                v = clean(e)
            except (ValueError, TypeError) as ex:
                out["rejected"].append(str(ex))
                continue
            out["ids"].add(v["uuid"])
            old = db.one("SELECT id, updated_at FROM entries WHERE uuid=?", (v["uuid"],))
            if old and old["updated_at"] >= v["updated_at"]:
                out["stale"] += 1
                continue
            if old:
                db.ex("UPDATE entries SET ts=?, kind=?, text=?, severity=?, source=?, details=COALESCE(?, details), removed_at=?, updated_at=? WHERE id=?",
                      (v["ts"], v["kind"], v["text"], v["severity"], v["source"], v["details"], v["removed_at"], v["updated_at"], old["id"]))
            else:
                db.ex("INSERT INTO entries(uuid,ts,kind,text,severity,source,details,removed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                      (v["uuid"], v["ts"], v["kind"], v["text"], v["severity"], v["source"], v["details"], v["removed_at"], now, v["updated_at"]))
            out["accepted"] += 1
    return out


def export(db, since, skip=(), limit=2000):
    """Entries changed after revision `since`. -> (entries, cursor, more). cursor is where the phone should resume."""
    rows = db.q("SELECT * FROM entries WHERE rev>? ORDER BY rev LIMIT ?", (int(since), limit + 1))
    more = len(rows) > limit
    rows = rows[:limit]
    cursor = rows[-1]["rev"] if rows else int(since)
    out = []
    for r in rows:
        if r["uuid"] in skip:
            continue
        d = None
        if r["details"]:
            try:
                d = json.loads(r["details"])
            except ValueError:
                d = None
        out.append({"id": r["uuid"], "ts": r["ts"], "kind": r["kind"], "text": r["text"], "severity": r["severity"], "source": r["source"], "details": d,
                    "removedAt": r["removed_at"], "updatedAt": r["updated_at"]})
    if not more and not rows:
        cursor = max(int(since), db.val("SELECT COALESCE(MAX(rev),0) FROM entries", default=0))
    return out, cursor, more


def docs_signature(db):
    rows = db.q("SELECT slug, updated_at FROM documents ORDER BY slug")
    return hashlib.sha256(json.dumps([[r["slug"], r["updated_at"]] for r in rows]).encode()).hexdigest()[:16]


def docs(db):
    return [{"slug": r["slug"], "title": r["title"], "kind": r["kind"], "body": r["body"] if r["kind"] == "md" else "", "sort": r["sort"]}
            for r in db.q("SELECT slug,title,kind,body,sort FROM documents ORDER BY sort, id")]


def handle(db, body):
    """The whole sync exchange. body is the phone's request (a dict); returns the reply."""
    since = body.get("since", 0)
    since = since if isinstance(since, int) and since >= 0 else 0
    got = apply(db, body.get("entries") or [])
    entries, cursor, more = export(db, since, skip=got["ids"])
    reply = {"ok": True, "accepted": got["accepted"], "stale": got["stale"], "rejected": got["rejected"][:20], "entries": entries, "cursor": cursor, "more": more,
             "settings": {k: db.get_setting(k) for k in ("pond_start",) if db.get_setting(k)}, "docs_sig": docs_signature(db)}
    if body.get("docs_sig") != reply["docs_sig"]:
        reply["docs"] = docs(db)
    return reply
