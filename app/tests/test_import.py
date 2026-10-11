import os
import pathlib
import textwrap

import pytest
from fastapi.testclient import TestClient
from conftest import env
from tadpole import auth, clock, importer, mdrender, vaultimport
from tadpole.config import Config, set_config
from tadpole.main import create_app

PASS = "correct horse battery"
REAL = pathlib.Path(os.environ.get("TADPOLE_REAL_VAULT_HEALTH", "/nonexistent"))


def note(front, body="# t\n"):
    return "---\n" + textwrap.dedent(front).strip() + "\n---\n" + body


def conv(front, body="## What\nSomething happened.\n\n## Verbatim\n\"in my words\"\n"):
    fm, b = vaultimport.split_note(note(front, body))
    return vaultimport.convert("2026-09-14-02", fm, b)


def test_a_meal_becomes_food_and_keeps_every_extra_field():
    e = conv('date: 2026-09-14\ntime: "16:40"\nentry_type: "Meal"\nfood: "Leftover pad thai, roughly 1.5 cups"\nfodmap_group: "Unknown"\nbloating: 6\ngas: 0\nonset_lag_h: 3\nphase: "Baseline"\nreconstructed: false')
    assert (e["kind"], e["severity"], e["text"]) == ("food", None, "Leftover pad thai, roughly 1.5 cups")
    d = e["details"]
    assert d["fodmap_group"] == "Unknown" and d["bloating"] == 6 and d["gas"] == 0 and d["onset_lag_h"] == 3 and d["what"] == "Something happened." and d["verbatim"] == '"in my words"'
    assert "reconstructed" not in d


def test_stool_symptom_clear_and_mood_entries_map_to_the_right_kinds():
    assert conv('date: 2026-09-14\nentry_type: "Stool"\nstool_bsfs: "5-6"')["text"] == "Stool, Bristol 5-6"
    s = conv('date: 2026-09-14\nentry_type: "Symptom"\nbloating: 2\nurgency: 3')
    assert (s["kind"], s["severity"], s["text"]) == ("symptom", 3, "in my words")
    c = conv('date: 2026-09-14\nentry_type: "Symptom"\nbloating: 0\ngas: 0')
    assert (c["kind"], c["severity"]) == ("clear", 0)
    m = conv('date: 2026-09-14\nentry_type: "Symptom"\nmood_context: "bad mood (self-reported)"')
    assert (m["kind"], m["severity"]) == ("note", None) and m["details"]["mood_context"] == "bad mood (self-reported)"
    u = conv('date: 2026-09-14\nentry_type: "Symptom"')
    assert (u["kind"], u["severity"]) == ("symptom", None)


def test_unpreserved_verbatim_and_two_quote_lines_fall_back_to_the_summary():
    e = conv('date: 2026-09-14\nentry_type: "Symptom"\nbloating: 1', "## What\nWoke up groggy.\n\n## Verbatim\n_Not preserved. Rebuilt._\n")
    assert e["text"] == "Woke up groggy."
    e = conv('date: 2026-09-14\nentry_type: "Symptom"\nbloating: 1', '## What\nGroggy and a 7.\n\n## Verbatim\n"groggy" / "that was a 7"\n')
    assert e["text"] == "Groggy and a 7."


def test_entries_without_a_time_are_placed_after_the_previous_one(tmp_path):
    d = tmp_path / "Daily Entries"
    d.mkdir()
    (d / "2026-09-10-01.md").write_text(note('date: 2026-09-10\ntime: "09:00"\nentry_type: "Meal"\nfood: "toast"'))
    (d / "2026-09-10-02.md").write_text(note('date: 2026-09-10\ntime:\nentry_type: "Meal"\nfood: "tea"'))
    (d / "2026-09-11-01.md").write_text(note('date: 2026-09-11\ntime:\nentry_type: "Meal"\nfood: "eggs"'))
    from zoneinfo import ZoneInfo
    es, problems = vaultimport.read_entries(tmp_path, ZoneInfo("America/Toronto"))
    assert not problems
    assert [e["ts"] for e in es] == ["2026-09-10T13:00:00Z", "2026-09-10T13:01:00Z", "2026-09-11T16:00:00Z"]
    assert es[1]["details"]["time_unknown"] is True


def test_import_is_repeatable_starts_the_pond_today_and_keeps_documents(tmp_path, db):
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Toronto")
    src = tmp_path / "vault"
    (src / "Daily Entries").mkdir(parents=True)
    (src / "Daily Entries" / "2026-09-10-01.md").write_text(note('date: 2026-09-10\ntime: "09:00"\nentry_type: "Meal"\nfood: "toast"\nenergy: 4'))
    (src / "FODMAP Protocol (from Health).md").write_text("# Protocol\n\n| a | b |\n|---|---|\n| 1 | 2 |\n")
    (src / "GutScreening.pdf").write_bytes(b"%PDF-1.4 fake")
    es, _ = vaultimport.read_entries(src, tz)
    docs = vaultimport.read_documents(src)
    now = clock.parse_iso("2026-10-10T20:00:00Z")
    first = importer.apply(db, es, docs, tmp_path / "lib", now, tz)
    again = importer.apply(db, es, docs, tmp_path / "lib", now, tz)
    assert first == {"entries_added": 1, "entries_updated": 0, "documents": 2} and again["entries_added"] == 0 and again["entries_updated"] == 1
    assert db.val("SELECT COUNT(*) FROM entries") == 1 and db.val("SELECT source FROM entries") == "vault"
    assert db.get_setting("pond_start") == "2026-10-10"
    assert (tmp_path / "lib" / "lab-report-2026-08.pdf").read_bytes() == b"%PDF-1.4 fake"


def test_the_markdown_renderer_handles_the_documents_and_never_lets_markup_through():
    h = mdrender.render("# Title\n\n**bold** and *it* and `code` <script>alert(1)</script>\n\n| a | b |\n|---|---|\n| 1 | **2** |\n\n1. one\n2. two\n\n> quoted\n\n[x](https://e.com) [[Wiki]] [bad](javascript:alert(1))")
    assert "<h2>Title</h2>" in h and "<strong>bold</strong>" in h and "<code>code</code>" in h and "<table" in h and "<ol>" in h and "<blockquote>" in h
    assert "<script>" not in h and "&lt;script&gt;" in h and 'href="https://e.com"' in h and "Wiki" in h and 'href="javascript' not in h


@pytest.fixture
def c(tmp_path):
    auth.reset_fails()
    set_config(Config(env(tmp_path)))
    cl = TestClient(create_app(), follow_redirects=False)
    cl.post("/setup", data={"passphrase": PASS, "confirm": PASS})
    yield cl
    clock.set_now(None)


def test_imported_entries_show_their_details_and_the_library_and_csv_carry_everything(c, tmp_path):
    from zoneinfo import ZoneInfo
    from tadpole.db import DB
    tz = ZoneInfo("America/Toronto")
    src = tmp_path / "vault"
    (src / "Daily Entries").mkdir(parents=True)
    (src / "Daily Entries" / "2026-10-09-01.md").write_text(note('date: 2026-10-09\ntime: "09:00"\nentry_type: "Meal"\nfood: "toast"\nenergy: 4\nmood_context: "low stretch"', "## Notes\nRestaurant.\n"))
    (src / "FODMAP Protocol (from Health).md").write_text("# Protocol\n\nPhase 0.")
    (src / "GutScreening.pdf").write_bytes(b"%PDF-1.4 fake")
    es, _ = vaultimport.read_entries(src, tz)
    db = DB(tmp_path / "tadpole.db")
    importer.apply(db, es, vaultimport.read_documents(src), tmp_path / "library", clock.parse_iso("2026-10-10T12:00:00Z"), tz)
    db.close()
    clock.set_now(clock.parse_iso("2026-10-10T12:00:00Z"))
    page = c.get("/diary").text
    assert "toast" in page and "Mood context" in page and "low stretch" in page and "Energy" in page and "Restaurant." in page
    assert "Library" in c.get("/").text and "FODMAP protocol" in c.get("/library").text
    assert "Phase 0." in c.get("/library/fodmap-protocol").text
    pdf = c.get("/library/lab-report-2026-08/file")
    assert pdf.status_code == 200 and pdf.content == b"%PDF-1.4 fake" and pdf.headers["content-type"] == "application/pdf"
    assert c.get("/library/nope").status_code == 404
    csv_text = c.get("/export.csv").text
    assert "mood_context" in csv_text.splitlines()[0] and "low stretch" in csv_text and ",vault," in csv_text


@pytest.mark.skipif(not (REAL / "Daily Entries").exists(), reason="the real vault is not on this machine")
def test_every_real_vault_entry_converts_and_keeps_its_scores():
    from zoneinfo import ZoneInfo
    es, problems = vaultimport.read_entries(REAL, ZoneInfo("America/Toronto"))
    files = list((REAL / "Daily Entries").glob("*.md"))
    assert not problems and len(es) == len(files) == 128
    assert all(e["text"] and e["ts"] for e in es)
    assert len({e["external_id"] for e in es}) == 128
    scored = sum(1 for f in files for line in f.read_text().split("---")[1].splitlines() if line.split(":")[0] in ("bloating", "abdo_pain", "gas", "urgency", "energy", "stress", "sleep_h") and line.split(":", 1)[1].strip())
    assert scored == sum(1 for e in es for k in ("bloating", "abdo_pain", "gas", "urgency", "energy", "stress", "sleep_h") if k in e["details"])
