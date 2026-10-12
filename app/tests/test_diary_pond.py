from datetime import datetime, timedelta, timezone

import pytest
from conftest import env  # noqa: F401
from tadpole import clock, diary, pond

UTC = timezone.utc


def at(s):
    return clock.parse_iso(s)


@pytest.mark.parametrize("text,kind,sev", [
    ("Oatmeal with banana, coffee", "food", None),
    ("bloating 6", "symptom", 6), ("stomach cramps 7/10", "symptom", 7), ("mild headache", "symptom", 3), ("really bad nausea", "symptom", 7),
    ("terrible reflux", "symptom", 9), ("heartburn", "symptom", None), ("symptom: tired 4", "symptom", 4),
    ("no symptoms today", "clear", 0), ("feeling fine", "clear", 0), ("all good", "clear", 0),
    ("note: started new medication", "note", None), ("food: 2 eggs and toast", "food", None),
    ("2 eggs and toast at 8", "food", None), ("pizza, 3 slices", "food", None),
    ("woke up neuroinflamed", "symptom", None), ("foggy and groggy 4", "symptom", 4), ("some flatulence right now", "symptom", None),
    ("jittery, dehydrated, tense, headachey", "symptom", None), ("urgency 5", "symptom", 5), ("hungover", "symptom", None),
    ("pooped a 6", "stool", None), ("bm 5/6", "stool", None), ("stool: 4", "stool", None), ("Bristol 3 this morning", "stool", None),
    ("pooped a 6 and neuroinflamed", "symptom", None), ("coffee and toast at 7", "food", None),
])
def test_a_typed_line_becomes_the_right_kind_of_entry(text, kind, sev):
    p = diary.parse(text)
    assert (p["kind"], p["severity"]) == (kind, sev)


@pytest.mark.parametrize("text,bsfs", [("pooped a 6", "6"), ("bm 5/6", "5-6"), ("Bristol 5-6", "5-6"), ("stool: 4", "4"), ("pooped", None), ("pooped at 9:30", None), ("bm 6-5", "5-6")])
def test_the_bristol_number_is_read_from_a_stool_line(text, bsfs):
    assert diary.bristol(text) == bsfs


def test_prefixes_are_not_kept_in_the_text_and_numbers_in_food_are_not_severities():
    assert diary.parse("food: 2 eggs")["text"] == "2 eggs" and diary.parse("food: 2 eggs")["severity"] is None
    assert diary.parse("a 5 oz steak")["kind"] == "food"


def test_entries_are_stored_replays_are_ignored_and_range_is_checked(db):
    now = at("2026-10-10T15:00:00Z")
    a = diary.add(db, "toast", now, key="k1", source="widget")
    assert diary.add(db, "toast", now, key="k1") == a and db.val("SELECT COUNT(*) FROM entries") == 1
    with pytest.raises(ValueError):
        diary.add(db, "   ", now)
    b = diary.add(db, "bloating", now, severity=8)
    assert db.val("SELECT severity FROM entries WHERE id=?", (b,)) == 8
    c = diary.add(db, "fine", now, kind="clear")
    assert db.val("SELECT text FROM entries WHERE id=?", (c,)) == "fine" and db.val("SELECT severity FROM entries WHERE id=?", (c,)) == 0
    diary.remove(db, a, now)
    assert a not in [r["id"] for r in diary.live(db)]
    diary.remove(db, a, now, restore=True)
    assert a in [r["id"] for r in diary.live(db)]


def test_colour_follows_how_long_since_the_last_entry(db):
    assert pond.mood(db, at("2026-10-10T12:00:00Z")) == ("green", None)
    diary.add(db, "toast", at("2026-10-10T12:00:00Z"))
    assert pond.mood(db, at("2026-10-10T20:00:00Z"))[0] == "green"          # 8 hours: overnight and workday gaps are fine
    assert pond.mood(db, at("2026-10-11T12:00:00Z"))[0] == "yellow"         # 24 hours
    assert pond.mood(db, at("2026-10-12T12:00:00Z"))[0] == "red"            # 48 hours
    diary.add(db, "soup", at("2026-10-12T12:30:00Z"))
    assert pond.mood(db, at("2026-10-12T13:00:00Z"))[0] == "green"           # writing again turns it green at once


def log_day(db, day, text="toast", sev=None, hour=12):
    ts = datetime(2026, 9, day, hour, 0, tzinfo=UTC)
    diary.add(db, text, ts)
    if sev is not None:
        diary.add(db, "bloating", ts + timedelta(hours=1), severity=sev)


def test_legs_grow_with_calm_days_and_regress_with_flares_and_missed_days_change_nothing(db, cfg):
    today = datetime(2026, 9, 30, 15, tzinfo=cfg.tz).date()
    for d in range(1, 4):                                   # three mild days
        log_day(db, d, sev=2)
    g = pond.growth(db, cfg.tz, today)
    assert g["points"] == 3 and g["stage"] == 1 and g["name"] == "Back leg buds"
    assert pond.growth(db, cfg.tz, datetime(2026, 9, 3, tzinfo=cfg.tz).date())["points"] == 2     # the last day only counts once it is over
    for d in range(10, 14):                                 # a gap of missed days, then four good ones
        log_day(db, d)
    assert pond.growth(db, cfg.tz, today)["points"] == 7 and pond.growth(db, cfg.tz, today)["stage"] == 2
    log_day(db, 14, sev=8)                                  # a flare
    assert pond.growth(db, cfg.tz, today)["points"] == 5
    log_day(db, 15, sev=5)                                  # a middling day
    assert pond.growth(db, cfg.tz, today)["points"] == 4.5
    for d in range(16, 30):
        log_day(db, d)
    g = pond.growth(db, cfg.tz, today)
    assert g["points"] == 18.5 and g["name"] == "Froglet" and g["to_next"] == 7.5


def test_points_never_go_below_zero_and_a_bad_day_today_costs_at_once(db, cfg):
    day = datetime(2026, 9, 5, 12, tzinfo=UTC)
    diary.add(db, "bloating", day, severity=9)
    today = datetime(2026, 9, 5, tzinfo=cfg.tz).date()
    assert pond.growth(db, cfg.tz, today)["points"] == 0
    assert pond.growth(db, cfg.tz, today + timedelta(days=3))["points"] == 0


def test_a_full_frog_after_enough_calm_days_and_symptom_week_label(db, cfg):
    for d in range(1, 29):
        log_day(db, d, sev=1 if d % 2 else None)
    today = datetime(2026, 9, 29, tzinfo=cfg.tz).date()
    g = pond.growth(db, cfg.tz, today)
    assert g["stage"] == 5 and g["name"] == "Frog" and g["to_next"] is None
    c = pond.control(db, cfg.tz, today)
    assert c["key"] == "good" and c["label"] == "under control" and c["logged_days"] == 6
    assert pond.control(db, cfg.tz, datetime(2026, 8, 20, tzinfo=cfg.tz).date())["key"] == "unknown"


def test_the_week_can_be_flaring_and_a_trend_is_reported(db, cfg):
    for d in range(1, 8):
        log_day(db, d, sev=2)
    for d in range(8, 15):
        log_day(db, d, sev=7)
    c = pond.control(db, cfg.tz, datetime(2026, 9, 14, tzinfo=cfg.tz).date())
    assert c["key"] == "flaring" and c["trend"] == "worse"


def test_foods_often_followed_by_symptoms_surface_and_others_do_not(db, cfg):
    for d in range(1, 9):
        base = datetime(2026, 9, d, 12, tzinfo=UTC)
        diary.add(db, "cheese pizza", base)
        diary.add(db, "bloating", base + timedelta(hours=3), severity=6) if d <= 6 else None
        diary.add(db, "plain rice", base + timedelta(hours=8))
    t = pond.triggers(db, cfg.tz)
    words = [i["word"] for i in t["items"]]
    assert "pizza" in words and "cheese" in words and "rice" not in words
    assert next(i for i in t["items"] if i["word"] == "pizza")["followed"] == 6 and 0 < t["baseline"] < 1
    assert pond.triggers(db, cfg.tz, min_seen=50)["items"] == []


def test_history_before_the_pond_start_does_not_grow_the_frog(db):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Toronto")
    for d in range(1, 11):
        diary.add(db, "toast", at(f"2026-09-{d:02d}T15:00:00Z"), ts=at(f"2026-09-{d:02d}T15:00:00Z"))
    today = at("2026-10-05T15:00:00Z").astimezone(tz).date()
    assert pond.growth(db, tz, today)["points"] == 10
    db.set_setting("pond_start", "2026-10-01")
    assert pond.growth(db, tz, today)["points"] == 0
    diary.add(db, "toast", at("2026-10-02T15:00:00Z"), ts=at("2026-10-02T15:00:00Z"))
    assert pond.growth(db, tz, today)["points"] == 1
