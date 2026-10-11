import pytest
from fastapi.testclient import TestClient
from conftest import env
from tadpole import auth, clock, tokens
from tadpole.config import Config, set_config
from tadpole.db import DB
from tadpole.main import create_app

PASS = "correct horse battery"
H = {"X-Finapp": "1"}


@pytest.fixture
def c(tmp_path):
    auth.reset_fails()
    cfg = Config(env(tmp_path))
    set_config(cfg)
    cl = TestClient(create_app(), follow_redirects=False)
    assert cl.post("/setup", data={"passphrase": PASS, "confirm": PASS}).status_code == 303
    yield cl
    clock.set_now(None)


def test_everything_needs_the_passphrase_and_only_the_tailnet_gets_in(tmp_path):
    auth.reset_fails()
    set_config(Config(env(tmp_path, TADPOLE_REQUIRE_TS_HEADER="1", TADPOLE_TS_LOGINS="me@example.com")))
    cl = TestClient(create_app(), follow_redirects=False)
    assert cl.get("/").status_code == 403 and cl.get("/healthz").status_code == 200
    me = {"Tailscale-User-Login": "me@example.com"}
    assert cl.get("/", headers=me).status_code == 303 and cl.get("/", headers=me).headers["location"] == "/setup"
    assert cl.get("/api/state", headers=me).status_code == 401
    cl.post("/setup", data={"passphrase": PASS, "confirm": PASS}, headers=me)
    cl.cookies.clear()
    assert cl.post("/login", data={"passphrase": "wrong wrong wrong"}, headers=me).status_code == 200
    assert cl.post("/login", data={"passphrase": PASS}, headers=me).status_code == 303


def test_typing_an_entry_saves_it_shows_it_and_can_be_undone_or_fixed(c):
    r = c.post("/entry", data={"text": "bloating 6"})
    assert r.status_code == 303 and r.headers["location"].startswith("/?saved=")
    page = c.get(r.headers["location"]).text
    assert "Saved as" in page and "symptom 6/10" in page and "bloating 6" in page and "Tadpole" in page and "<svg" in page
    eid = int(r.headers["location"].split("=")[1])
    assert c.post("/entry/edit", data={"id": str(eid), "text": "bloating", "kind": "symptom", "severity": "8", "when": "2026-10-10T08:30"}).status_code == 303
    assert "worst 8" in c.get("/diary").text or "bloating" in c.get("/diary?days=60").text
    assert c.post("/entry/remove", data={"id": str(eid), "back": "/diary"}).status_code == 303
    assert "Put back" in c.get("/diary").text
    assert c.post("/entry", data={"text": "   "}).status_code == 400
    assert c.post("/entry/clear").status_code == 303 and "all clear" in c.get("/").text
    assert c.post("/entry/edit", data={"id": "999", "text": "x"}).status_code == 404


def test_the_pond_changes_colour_and_stage_and_the_theme_follows(c):
    clock.set_now(clock.parse_iso("2026-10-10T15:00:00Z"))
    c.post("/entry", data={"text": "toast"})
    assert 'data-mood="green"' in c.get("/").text
    clock.set_now(clock.parse_iso("2026-10-11T18:00:00Z"))
    assert 'data-mood="yellow"' in c.get("/").text and "Peckish" in c.get("/").text
    clock.set_now(clock.parse_iso("2026-10-13T18:00:00Z"))
    page = c.get("/").text
    assert 'data-mood="red"' in page and "Hungry" in page and "#D5503A" in page


def test_patterns_and_the_csv_export_work(c):
    c.post("/entry", data={"text": "cheese pizza"})
    c.post("/entry", data={"text": "bloating 6"})
    assert "The last 30 days" in c.get("/patterns").text
    csv_text = c.get("/export.csv").text
    assert csv_text.splitlines()[0].startswith("date,time,kind,severity,text,source,") and "cheese pizza" in csv_text and ",symptom,6,bloating 6,app," in csv_text


def test_the_widget_key_can_add_entries_and_read_state_but_nothing_else(c):
    r = c.post("/settings/widget/new", data={"name": "My phone"})
    import re
    key = re.search(r"tpw_[A-Za-z0-9_-]+", r.text).group(0)
    cl = TestClient(create_app(), follow_redirects=False)
    bearer = {"Authorization": f"Bearer {key}"}
    s = cl.get("/api/state", headers=bearer)
    assert s.status_code == 200 and s.json()["color"] == "green" and s.json()["stage_name"] == "Tadpole" and s.json()["last"] is None
    e = cl.post("/api/entry", json={"text": "Oatmeal and coffee", "key": "w1"}, headers=bearer).json()
    assert e["ok"] and e["kind"] == "food" and e["state"]["today_count"] == 1 and e["state"]["last"]["text"] == "Oatmeal and coffee"
    again = cl.post("/api/entry", json={"text": "Oatmeal and coffee", "key": "w1"}, headers=bearer).json()
    assert again["id"] == e["id"] and again["state"]["today_count"] == 1
    sym = cl.post("/api/entry", json={"text": "bloating", "severity": 4, "key": "w2"}, headers=bearer).json()
    assert sym["kind"] == "symptom" and sym["severity"] == 4
    assert cl.post("/api/entry", json={"text": "x", "ts": "2030-01-01T00:00:00Z"}, headers=bearer).status_code == 400
    assert cl.post("/api/entry", json={"text": ""}, headers=bearer).status_code == 400
    assert cl.get("/diary", headers=bearer).status_code == 303 and cl.get("/export.csv", headers=bearer).status_code == 303          # no way to read the diary
    assert cl.post("/entry", data={"text": "x"}, headers=bearer).status_code == 303
    assert cl.post("/api/undo", json={"id": e["id"]}, headers=bearer).json()["state"]["today_count"] == 1
    assert cl.get("/api/state", headers={"Authorization": "Bearer tpw_nonsense"}).status_code == 401


def test_patterns_says_nothing_stands_out_until_there_is_a_pattern(c):
    c.post("/entry", data={"text": "toast"})
    page = c.get("/patterns").text
    assert "Nothing stands out yet" in page and "<table" not in page


def test_explanations_live_in_info_callouts_not_in_the_page(c):
    import re
    c.post("/entry", data={"text": "toast"})
    for path, snippets in (("/", ["Type it like a note", "A day with entries and mild symptoms"]), ("/diary", ["Open an entry to fix its words"]),
                           ("/patterns", ["Each bar is that day's worst symptom", "not a diagnosis"]), ("/settings/widget", ["It is signed with this machine's own key", "cannot read your diary"])):
        page = c.get(path).text
        assert 'class="infobtn"' in page and 'class="callout"' in page, path
        for s in snippets:
            assert s in page, (path, s)
            inside = [m for m in re.finditer(r'<div class="callout">(.*?)</div>', page, re.S) if s in m.group(1)]
            assert inside, f"{s!r} on {path} is not inside a callout"
            outside = re.sub(r'<div class="callout">.*?</div>', "", page, flags=re.S)
            assert s not in outside, f"{s!r} on {path} also appears outside a callout"
