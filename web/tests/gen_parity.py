"""Runs the real Python rules over synthetic phrases and diaries and writes parity.json, which parity.test.js replays against core.js.
    cd app && /opt/finapp/venv/bin/python ../web/tests/gen_parity.py
All data here is made up. Timezone is America/Toronto, so run the node test with TZ=America/Toronto."""
import json
import pathlib
import random
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "app"))
from tadpole import clock, diary, pond  # noqa: E402
from tadpole.db import open_db  # noqa: E402

TZ = ZoneInfo("America/Toronto")
rnd = random.Random(20261011)

PHRASES = [
    "Oatmeal with banana, coffee", "bloating 6", "stomach cramps 7/10", "mild headache", "really bad nausea", "terrible reflux", "heartburn", "symptom: tired 4",
    "no symptoms today", "feeling fine", "all good", "note: started new medication", "food: 2 eggs and toast", "2 eggs and toast at 8", "pizza, 3 slices",
    "woke up neuroinflamed", "foggy and groggy 4", "some flatulence right now", "jittery, dehydrated, tense, headachey", "urgency 5", "hungover", "pooped a 6", "bm 5/6",
    "stool: 4", "Bristol 3 this morning", "pooped a 6 and neuroinflamed", "coffee and toast at 7", "  spaced    out   text  ", "S: gas 3", "f: rice", "n: remember to call", "ate noodles",
    "drank a sour beer", "no symptoms but a bit of gas", "symptom-free", "felt great", "bloating 11", "pain 10/10", "cramps 2 out of 10", "10", "7", "headache at 3pm", "BM 4", "poop 7",
    "stool 5-6", "bristol 6 5", "pooped at 9:30", "lunch 12:30 sandwich", "bad day", "very bloated", "slight ache", "moderate pain", "worst migraine", "not any symptoms",
    "Meal size 2 (~1000 kcal) - FODMAP triggers: 2 (onion/garlic, dairy)", "Stool, Bristol 6", "Neuroinflammation 5/7", "no symptoms", "", "   ", "symptom:", "food:",
]
FOODS = ["toast", "rice", "pasta", "oatmeal", "coffee", "cheese pizza", "beans", "apple", "yogurt", "salad", "burger", "noodles", "garlic bread", "banana", "eggs", "sour beer"]
SYMS = ["bloating", "cramps", "headache", "nausea", "gas", "pain", "reflux", "foggy", "tense"]
for _ in range(260):
    k = rnd.random()
    if k < .35:
        PHRASES.append(rnd.choice(FOODS) + rnd.choice(["", " with " + rnd.choice(FOODS), " at " + str(rnd.randint(1, 12)), ", " + rnd.choice(FOODS)]))
    elif k < .7:
        PHRASES.append(rnd.choice(SYMS) + rnd.choice(["", " " + str(rnd.randint(0, 12)), " " + str(rnd.randint(0, 10)) + "/10", " mild", " bad", " really bad", " moderate", " awful"]))
    elif k < .85:
        PHRASES.append(rnd.choice(["pooped", "bm", "stool", "bristol", "poop"]) + " " + rnd.choice(["", "a ", "type "]) + str(rnd.randint(1, 7)) + rnd.choice(["", "/" + str(rnd.randint(1, 7)), "-" + str(rnd.randint(1, 7))]))
    else:
        PHRASES.append(rnd.choice(["no symptoms", "all good", "feeling fine", "symptom free", "felt well"]) + rnd.choice(["", " today", " but " + rnd.choice(SYMS)]))

parse_cases = []
for t in PHRASES:
    p = diary.parse(t)
    parse_cases.append({"text": t, "kind": p["kind"], "severity": p["severity"], "out": p["text"], "bristol": diary.bristol(t)})


def scenario(seed, days, bad_rate):
    r = random.Random(seed)
    tmp = pathlib.Path(tempfile.mkdtemp())
    db = open_db(tmp / "t.db")
    base = datetime(2026, 8, 1, tzinfo=TZ)
    rows = []
    for d in range(days):
        if r.random() < .12:
            continue
        day = base + timedelta(days=d)
        for _ in range(r.randint(1, 6)):
            when = day + timedelta(hours=r.randint(6, 23), minutes=r.randint(0, 59))
            u = r.random()
            if u < .55:
                kind, sev, text = "food", None, " ".join(r.sample(FOODS, r.randint(1, 3)))
            elif u < .8 and r.random() < bad_rate * 3:
                kind, sev, text = "symptom", r.choice([None, 2, 3, 4, 5, 6, 7, 8, 9]), r.choice(SYMS)
            elif u < .9:
                kind, sev, text = "stool", None, "Stool, Bristol %d" % r.randint(1, 7)
            elif u < .95:
                kind, sev, text = "clear", 0, "No symptoms"
            else:
                kind, sev, text = "note", None, "a note"
            removed = r.random() < .05
            ts = clock.iso(when)
            rid = db.ex("INSERT INTO entries(ts,kind,text,severity,source,created_at,removed_at) VALUES(?,?,?,?,?,?,?)", (ts, kind, text, sev, "app", ts, ts if removed else None)).lastrowid
            rows.append({"ts": ts, "kind": kind, "text": text, "severity": sev, "removed": removed})
    out = {"entries": rows, "checks": []}
    for pond_start in (None, "2026-08-20"):
        db.ex("DELETE FROM settings WHERE key='pond_start'")
        if pond_start:
            db.set_setting("pond_start", pond_start)
        for offset_h in (5, 30, 80, days * 24 - 3, days * 24 + 10, days * 24 + 60):
            now = (base + timedelta(hours=offset_h)).astimezone(timezone.utc)
            st = pond.state(db, TZ, now)
            tr = pond.triggers(db, TZ)
            out["checks"].append({"now": clock.iso(now), "pond_start": pond_start, "color": st["color"], "hours": st["hours"], "stage": st["stage"], "points": st["growth"]["points"],
                                  "to_next": st["growth"]["to_next"], "control": st["control"], "today_count": st["today_count"], "today_food": st["today_food"], "ago": st["ago"],
                                  "triggers": tr})
    db.close()
    return out


data = {"parse": parse_cases, "scenarios": [scenario(1, 70, .05), scenario(2, 70, .3), scenario(3, 45, .0), scenario(4, 90, .5), scenario(5, 12, .2)]}
(HERE / "parity.json").write_text(json.dumps(data, indent=0))
print(len(parse_cases), "phrases;", sum(len(s["checks"]) for s in data["scenarios"]), "pond checks;",
      "frogs reached:", sorted({c["stage"] for s in data["scenarios"] for c in s["checks"]}), "colours:", sorted({c["color"] for s in data["scenarios"] for c in s["checks"]}),
      "trigger items seen:", sum(len(c["triggers"]["items"]) for s in data["scenarios"] for c in s["checks"]))
