"""The diary: turning a typed line into an entry, and reading entries back."""
import re
from datetime import datetime, time as dtime, timedelta, timezone

from . import clock

SYMPTOM_WORDS = re.compile(
    r"bloat|\bgas\b|gassy|cramp|\bpain|ache\b|aches\b|achy|nause|vomit|threw up|reflux|heartburn|indigestion|diarrh|constipat|stomach|tummy|headache|migraine|"
    r"dizz|fatigue|exhaust|rash|hives|itch|swell|swollen|flare|brain fog|\bsick\b|feel(ing)? (off|bad|awful|terrible|rough|unwell)|\bsymptom|"
    r"neuro-?inflam\w*|\bfog(gy)?\b|grogg\w*|jitter\w*|\btense\b|hung-?over|hangover|flatulen\w*|\bfart\w*|\burgen(cy|t)\b", re.I)
STOOL_WORDS = re.compile(r"\b(poop(ed|ing|s)?|stools?|bm|bms|bowel movements?|bristol|bsfs)\b", re.I)
STOOL_NUMBER = re.compile(r"\b(poop(ed|ing|s)?|stools?|bm|bms|bowel movements?|bristol|bsfs)\b\W*(\w+\W+){0,2}?[1-7](\s*(-|/|to)\s*[1-7])?(?![\d:])", re.I)
BRISTOL = re.compile(r"(?<![\d.:])([1-7])(?:\s*(?:-|/|to)\s*([1-7]))?(?![\d:])")
CLEAR_WORDS = re.compile(r"\b(no|zero|none|without|not any)\b.{0,12}\bsymptoms?\b|\bsymptom[- ]?free\b|\b(feel(ing)?|felt)\s+(fine|great|good|well|normal)\b|\ball\s+good\b", re.I)
SEVERITY_WORDS = [(re.compile(r"\b(mild|slight|little|minor|bit of)\b", re.I), 3), (re.compile(r"\bmoderate\b", re.I), 5),
                  (re.compile(r"\b(awful|terrible|horrible|worst|excruciating|unbearable)\b", re.I), 9), (re.compile(r"\b(bad|strong|severe|intense|really|very)\b", re.I), 7)]
OUT_OF_TEN = re.compile(r"(\d{1,2})\s*(?:/|out of)\s*10")
LONE_NUMBER = re.compile(r"(?<![\d.:/$])\b(10|\d)\b(?![\d.:%/])")
PREFIX = re.compile(r"^\s*(food|ate|drank|symptoms?|note|stool|poop|bm|s|f|n)\s*[:\-]\s*", re.I)
KINDS = ("food", "symptom", "clear", "note", "stool")
SOURCES = ("app", "widget", "vault", "phone")
MAX_TEXT = 400


def parse(text):
    """-> {kind, severity, text}. A line that names a symptom is a symptom (a number up to 10, or a word like 'mild', gives how bad), a line that says
    nothing is wrong is an explicit all-clear, anything else is food. 'note:' and 'food:' (and 'symptom:') force the kind."""
    raw = " ".join((text or "").split())[:MAX_TEXT]
    forced = None
    m = PREFIX.match(raw)
    if m:
        key = m.group(1).lower()
        forced = {"food": "food", "ate": "food", "drank": "food", "f": "food", "symptom": "symptom", "symptoms": "symptom", "s": "symptom", "note": "note", "n": "note",
                  "stool": "stool", "poop": "stool", "bm": "stool"}[key]
        raw = raw[m.end():].strip() if key not in ("ate", "drank") else raw
    kind = forced
    if kind is None:
        if CLEAR_WORDS.search(raw) and not SYMPTOM_WORDS.search(re.sub(CLEAR_WORDS, "", raw)):
            kind = "clear"
        elif SYMPTOM_WORDS.search(raw):
            kind = "symptom"
        elif STOOL_WORDS.search(raw):
            kind = "stool"
        else:
            kind = "food"
    sev = None
    if kind == "symptom":
        scored = STOOL_NUMBER.sub("", raw)
        m = OUT_OF_TEN.search(scored) or (LONE_NUMBER.search(scored) if SYMPTOM_WORDS.search(scored) or forced == "symptom" else None)
        if m:
            sev = max(0, min(10, int(m.group(1))))
        else:
            for rx, val in SEVERITY_WORDS:
                if rx.search(scored):
                    sev = val
                    break
    elif kind == "clear":
        sev = 0
    return {"kind": kind, "severity": sev, "text": raw}


def bristol(text):
    """The Bristol stool number in a line ('pooped a 6', 'bm 5/6'), as '6' or '5-6'. None when there isn't one."""
    m = BRISTOL.search(text or "")
    if not m:
        return None
    return m.group(1) if not m.group(2) or m.group(2) == m.group(1) else "-".join(sorted((m.group(1), m.group(2))))


def add(db, text, now, ts=None, kind=None, severity=None, source="app", key=None):
    """Store an entry. A replayed key returns the entry already stored. -> entry id."""
    if key:
        old = db.one("SELECT id FROM entries WHERE idempotency_key=?", (key,))
        if old:
            return old["id"]
    p = parse(text)
    if kind in KINDS:
        p["kind"] = kind
        if kind == "clear":
            p["severity"] = 0
        elif kind != "symptom":
            p["severity"] = None
    if severity is not None and p["kind"] == "symptom":
        p["severity"] = max(0, min(10, int(severity)))
    if not p["text"] and p["kind"] != "clear":
        raise ValueError("Type something first.")
    if p["kind"] == "clear" and not p["text"]:
        p["text"] = "No symptoms"
    when = ts or now
    return db.ex("INSERT INTO entries(ts,kind,text,severity,source,idempotency_key,created_at) VALUES(?,?,?,?,?,?,?)",
                 (clock.iso(when), p["kind"], p["text"], p["severity"], source if source in SOURCES else "app", key or None, clock.iso(now))).lastrowid


def live(db, since=None, until=None):
    return db.q("SELECT * FROM entries WHERE removed_at IS NULL AND ts>=? AND ts<? ORDER BY ts, id", (since or "0000", until or "9999"))


def recent(db, n=8):
    return db.q("SELECT * FROM entries WHERE removed_at IS NULL ORDER BY ts DESC, id DESC LIMIT ?", (n,))


def remove(db, entry_id, now, restore=False):
    db.ex("UPDATE entries SET removed_at=? WHERE id=?", (None if restore else clock.iso(now), entry_id))


def update(db, entry_id, text, kind, severity, ts=None):
    p = parse(text)
    kind = kind if kind in KINDS else p["kind"]
    sev = None if kind in ("food", "note", "stool") else (0 if kind == "clear" else (None if severity in (None, "") else max(0, min(10, int(severity)))))
    if ts:
        db.ex("UPDATE entries SET ts=? WHERE id=?", (clock.iso(ts), entry_id))
    db.ex("UPDATE entries SET text=?, kind=?, severity=? WHERE id=?", (p["text"] or text.strip()[:MAX_TEXT], kind, sev, entry_id))


def local_day(ts_iso, tz):
    return clock.parse_iso(ts_iso).astimezone(tz).date()


def day_bounds(day, tz):
    start = datetime.combine(day, dtime(0), tzinfo=tz)
    return clock.iso(start), clock.iso(start + timedelta(days=1))


def meal_label(ts_iso, tz):
    h = clock.parse_iso(ts_iso).astimezone(tz).hour
    return "breakfast" if 4 <= h < 11 else "lunch" if 11 <= h < 15 else "snack" if 15 <= h < 17 else "dinner" if 17 <= h < 21 else "late"
