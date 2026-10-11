"""Reads the old Obsidian health folder (Daily Entries/*.md and a few reference documents) into plain data Tadpole can store. Read-only: it never writes to the vault."""
import json
import pathlib
import re
from datetime import datetime, timedelta, timezone

from . import clock

SCORES = ("bloating", "abdo_pain", "gas", "urgency", "energy", "stress", "sleep_h")
FOOD_TYPES = {"Meal", "Snack", "Drink", "Challenge"}
SECTION_KEYS = {"What": "what", "Suspected FODMAP group": "suspected_group", "Symptoms": "symptoms", "Context": "context", "Notes": "notes", "Verbatim": "verbatim"}


def _value(raw):
    v = raw.strip()
    if v == "":
        return None
    if v[0] == '"':
        try:
            return json.loads(v)
        except ValueError:
            return v.strip('"')
    if v[0] == "'":
        return v.strip("'").replace("''", "'")
    if v in ("true", "false"):
        return v == "true"
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return v


def split_note(text):
    """-> (frontmatter dict, body text)."""
    m = re.match(r"---\n(.*?)\n---\n?(.*)", text, re.S)
    if not m:
        return {}, text
    fm = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith((" ", "#")):
            k, _, v = line.partition(":")
            fm[k.strip()] = _value(v)
    return fm, m.group(2)


def sections(body):
    out = {}
    for part in re.split(r"^## ", body, flags=re.M)[1:]:
        head, _, rest = part.partition("\n")
        key = SECTION_KEYS.get(head.strip())
        rest = rest.strip()
        if key and rest and rest != "—":
            out[key] = rest
    return out


def _first_para(s):
    return re.split(r"\n\s*\n", s.strip())[0].replace("\n", " ").strip() if s else ""


def _verbatim_line(s):
    if not s or s.lstrip().startswith("_Not preserved"):
        return ""
    line = s.strip().splitlines()[0].strip()
    return line.strip('"“” ').strip()


def _num(v):
    return v if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def convert(stem, fm, body):
    """One entry file -> {external_id, date, time (or None), kind, severity, text, details}. None when it has nothing to keep."""
    sec = sections(body)
    etype = fm.get("entry_type") or "Other"
    bsfs = None if fm.get("stool_bsfs") in (None, "") else str(fm["stool_bsfs"]).strip()
    scores = {k: _num(fm.get(k)) for k in SCORES}
    gi = [scores[k] for k in ("bloating", "abdo_pain", "gas", "urgency") if scores[k] is not None]
    mood = (fm.get("mood_context") or "").strip() or None
    what = _first_para(sec.get("what", ""))
    if what.startswith("Not recorded"):
        what = ""
    if etype in FOOD_TYPES:
        kind, severity, text = "food", None, (fm.get("food") or what or "").strip()
    elif etype == "Stool":
        kind, severity = "stool", None
        text = f"Stool, Bristol {bsfs}" if bsfs else (what or "Stool")
    elif etype == "Symptom":
        quote = _verbatim_line(sec.get("verbatim", ""))
        text = ("" if '" / "' in quote else quote) or what or _first_para(sec.get("notes", ""))
        if gi and max(gi) == 0:
            kind, severity = "clear", 0
        elif gi:
            kind, severity = "symptom", int(max(gi))
        elif mood:
            kind, severity = "note", None
        else:
            kind, severity = "symptom", None
    else:
        kind, severity, text = "note", None, (fm.get("food") or what or "").strip()
    if not text:
        text = what or _first_para(sec.get("notes", "")) or etype
    d = {"entry_type": etype, "phase": fm.get("phase"), "fodmap_group": fm.get("fodmap_group"), "stool_bsfs": bsfs, "onset_lag_h": _num(fm.get("onset_lag_h")),
         "mood_context": mood, "reconstructed": bool(fm.get("reconstructed"))}
    d.update({k: v for k, v in scores.items() if v is not None})
    d.update(sec)
    d = {k: v for k, v in d.items() if v is not None and v != "" and v is not False}
    return {"external_id": stem, "date": str(fm.get("date") or stem[:10]), "time": fm.get("time"), "kind": kind, "severity": severity, "text": text[:400], "details": d}


def read_entries(health, tz):
    """-> (entries, problems). Entries get a UTC timestamp; one with no time is placed just after the previous entry that day (or at noon)."""
    out, problems = [], []
    last_by_day = {}
    for f in sorted((pathlib.Path(health) / "Daily Entries").glob("*.md")):
        try:
            fm, body = split_note(f.read_text(encoding="utf-8"))
            e = convert(f.stem, fm, body)
        except Exception as ex:  # one bad file must not hide the rest
            problems.append(f"{f.name}: {ex}")
            continue
        day = datetime.strptime(e["date"], "%Y-%m-%d").date()
        if e["time"]:
            h, m = (int(x) for x in str(e["time"]).split(":")[:2])
            local = datetime(day.year, day.month, day.day, h, m, tzinfo=tz)
        else:
            prev = last_by_day.get(day)
            local = prev + timedelta(minutes=1) if prev else datetime(day.year, day.month, day.day, 12, 0, tzinfo=tz)
            e["details"]["time_unknown"] = True
        last_by_day[day] = local
        e["ts"] = clock.iso(local.astimezone(timezone.utc))
        out.append(e)
    return out, problems


# the reference documents worth keeping, as (slug, title, file relative to the health folder, kind)
DOCUMENTS = [
    ("fodmap-protocol", "FODMAP protocol", "FODMAP Protocol (from Health).md", "md"),
    ("weekly-review-2026-09-13", "Weekly review, 13 Sep 2026", "Weekly Reviews/Weekly Review 2026-09-13.md", "md"),
    ("lab-report-2026-08", "Lab report (LifeLabs, collected 27 Aug 2026)", "GutScreening.pdf", "pdf"),
    ("logging-rules", "Logging rules (scales and guardrails from the old gut-health-log skill)", "_skill/SKILL.md", "md"),
]


def read_documents(health):
    health = pathlib.Path(health)
    docs = []
    for n, (slug, title, rel, kind) in enumerate(DOCUMENTS):
        p = health / rel
        if not p.exists():
            continue
        item = {"slug": slug, "title": title, "kind": kind, "source": rel, "sort": n}
        if kind == "md":
            text = p.read_text(encoding="utf-8")
            item["body"] = split_note(text)[1] if text.startswith("---\n") else text
        else:
            item["file"] = str(p)
        docs.append(item)
    return docs
