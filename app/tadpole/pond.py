"""The tadpole. Its colour follows how recently you wrote something down; its growth follows how your symptoms have been.

Colour: green while you are keeping up, yellow after a day of silence, red after more than that.
Growth: replayed from the diary, day by day. A day with entries and mild symptoms (3 or under) earns a point, a middling day (4 to 6) costs half a point,
a flare (7 or more) costs two, a day with no entries changes nothing. Points never go below zero. Today only counts if something has already gone wrong,
so a good day is rewarded once it is over."""
from datetime import timedelta

from . import clock, diary

GREEN_HOURS, YELLOW_HOURS = 18, 42
STAGES = [(0, "Tadpole"), (3, "Back leg buds"), (7, "Back legs"), (12, "Four legs"), (18, "Froglet"), (26, "Frog")]
GOOD, FLARE = 3, 7


def mood(db, now):
    """-> (color, hours since the last entry or None)."""
    r = db.one("SELECT ts FROM entries WHERE removed_at IS NULL ORDER BY ts DESC LIMIT 1")
    if not r:
        return "green", None
    h = (now - clock.parse_iso(r["ts"])).total_seconds() / 3600
    return ("green" if h <= GREEN_HOURS else "yellow" if h <= YELLOW_HOURS else "red"), h


def day_severity(rows):
    """Worst symptom of a day's entries (a symptom with no number counts as 5), 0 when there was none."""
    sev = 0
    for r in rows:
        if r["kind"] == "symptom":
            sev = max(sev, 5 if r["severity"] is None else r["severity"])
    return sev


def by_day(db, tz):
    out = {}
    for r in diary.live(db):
        out.setdefault(diary.local_day(r["ts"], tz), []).append(r)
    return out


def growth(db, tz, today):
    """-> {points, stage, name, to_next (points, or None when full grown), thresholds}. Replays every day since the first entry."""
    days = by_day(db, tz)
    pts = 0.0
    if days:
        d = min(days)
        while d <= today:
            rows = days.get(d)
            if rows:
                sev = day_severity(rows)
                if d < today:
                    pts += 1 if sev <= GOOD else (-0.5 if sev < FLARE else -2)
                elif sev >= FLARE:
                    pts -= 2
                elif sev > GOOD:
                    pts -= 0.5
                pts = max(0.0, pts)
            d += timedelta(days=1)
    stage = max(i for i, (t, _) in enumerate(STAGES) if pts >= t)
    nxt = STAGES[stage + 1][0] - pts if stage + 1 < len(STAGES) else None
    return {"points": pts, "stage": stage, "name": STAGES[stage][1], "to_next": nxt, "stages": STAGES}


def control(db, tz, today):
    """How the last week has gone. -> {label, average, logged_days, trend}."""
    days = by_day(db, tz)

    def week(end):
        sev = [day_severity(days[end - timedelta(days=i)]) for i in range(7) if (end - timedelta(days=i)) in days]
        return sev
    this, before = week(today), week(today - timedelta(days=7))
    if len(this) < 3:
        return {"label": "not enough yet", "key": "unknown", "average": None, "logged_days": len(this), "trend": None}
    avg = sum(this) / len(this)
    trend = None
    if len(before) >= 3:
        prev = sum(before) / len(before)
        trend = "better" if avg <= prev - 0.75 else "worse" if avg >= prev + 0.75 else "steady"
    key = "good" if avg <= 2.5 else "mixed" if avg <= 5 else "flaring"
    return {"label": {"good": "under control", "mixed": "up and down", "flaring": "flaring"}[key], "key": key, "average": round(avg, 1), "logged_days": len(this), "trend": trend}


def ago(hours):
    if hours is None:
        return "nothing written yet"
    if hours < 1:
        return f"{max(1, int(hours * 60))} min ago"
    if hours < 48:
        return f"{int(hours)} h ago"
    return f"{int(hours // 24)} days ago"


def state(db, tz, now):
    today = now.astimezone(tz).date()
    color, hours = mood(db, now)
    g, c = growth(db, tz, today), control(db, tz, today)
    start, end = diary.day_bounds(today, tz)
    todays = diary.live(db, start, end)
    line = {"green": "Content. Keep the entries coming.", "yellow": "Getting peckish. Write something down.", "red": "Hungry for entries. It has been too long."}[color]
    return {"color": color, "hours": hours, "ago": ago(hours), "line": line, "growth": g, "control": c,
            "today_count": len(todays), "today_food": sum(1 for r in todays if r["kind"] == "food"), "stage": g["stage"], "stage_name": g["name"]}


STOP = {"and", "with", "the", "some", "a", "an", "of", "for", "my", "had", "ate", "drank", "plus", "little", "bit", "small", "large", "big", "cup", "glass", "bowl", "piece", "slice", "side", "then", "from", "home", "made", "fresh", "cooked", "plain", "meal", "size", "kcal", "fodmap", "triggers"}


def words(text):
    import re
    return {w for w in re.findall(r"[a-z]{3,}", (text or "").lower()) if w not in STOP}


def triggers(db, tz, window_hours=12, min_seen=3):
    """Foods that were often followed by a symptom (4 or worse, 30 minutes to 12 hours later). Only a pattern in your own entries, not a diagnosis.
    -> {baseline, items: [{word, seen, followed, rate}]} """
    rows = diary.live(db)
    foods = [(clock.parse_iso(r["ts"]), words(r["text"])) for r in rows if r["kind"] == "food"]
    bad = [clock.parse_iso(r["ts"]) for r in rows if r["kind"] == "symptom" and (5 if r["severity"] is None else r["severity"]) >= 4]
    if not foods:
        return {"baseline": 0.0, "items": []}

    def followed(t):
        return any(timedelta(minutes=30) <= b - t <= timedelta(hours=window_hours) for b in bad)
    flags = [followed(t) for t, _ in foods]
    seen, hit = {}, {}
    for (t, ws), f in zip(foods, flags):
        for w in ws:
            seen[w] = seen.get(w, 0) + 1
            hit[w] = hit.get(w, 0) + (1 if f else 0)
    base = sum(flags) / len(flags)
    items = [{"word": w, "seen": n, "followed": hit[w], "rate": hit[w] / n} for w, n in seen.items() if n >= min_seen and hit[w] / n >= max(0.5, base + 0.25)]
    items.sort(key=lambda i: (-i["rate"], -i["seen"], i["word"]))
    return {"baseline": base, "items": items[:12]}
