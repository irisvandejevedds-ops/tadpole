import json
import pathlib
import shutil
import sqlite3
import subprocess
from urllib.parse import parse_qs, unquote, urlparse

import pytest
from fastapi.testclient import TestClient
from conftest import env
from tadpole import auth, clock, diary, pairing, sync, tokens
from tadpole.config import Config, set_config
from tadpole.db import DB, MIGRATIONS, open_db
from tadpole.main import create_app

@pytest.fixture(autouse=True)
def no_real_network_lookups(monkeypatch):
    monkeypatch.setattr(pairing, "tailscale_ip", lambda: None)


PASS = "correct horse battery"
U1, U2, U3 = "11111111-1111-4111-8111-111111111111", "22222222-2222-4222-8222-222222222222", "33333333-3333-4333-8333-333333333333"


def e(uid, text="toast", ts="2026-10-10T12:00:00Z", **kw):
    d = {"id": uid, "ts": ts, "kind": "food", "text": text, "severity": None, "source": "app", "details": None, "removedAt": None, "updatedAt": ts}
    d.update(kw)
    return d


def test_every_entry_gets_an_id_and_a_rising_revision(db):
    a = diary.add(db, "toast", clock.parse_iso("2026-10-10T12:00:00Z"))
    b = diary.add(db, "soup", clock.parse_iso("2026-10-10T13:00:00Z"))
    ra, rb = (db.one("SELECT * FROM entries WHERE id=?", (i,)) for i in (a, b))
    assert len(ra["uuid"]) == 36 and ra["uuid"] != rb["uuid"] and rb["rev"] == ra["rev"] + 1 and ra["updated_at"]
    diary.remove(db, a, clock.parse_iso("2026-10-10T14:00:00Z"))
    after = db.one("SELECT * FROM entries WHERE id=?", (a,))
    assert after["rev"] > rb["rev"] and after["uuid"] == ra["uuid"]


def test_the_migration_backfills_ids_for_entries_that_already_exist(tmp_path):
    conn = sqlite3.connect(tmp_path / "old.db")
    for name in ("001_core.sql", "002_import.sql"):
        conn.executescript((MIGRATIONS / name).read_text())
    for i in range(3):
        conn.execute("INSERT INTO entries(ts,kind,text,created_at) VALUES(?,?,?,?)", (f"2026-09-0{i + 1}T12:00:00Z", "food", f"meal {i}", "2026-09-10T00:00:00Z"))
    conn.commit()
    conn.executescript((MIGRATIONS / "003_sync.sql").read_text())
    rows = conn.execute("SELECT uuid, rev, updated_at FROM entries ORDER BY id").fetchall()
    assert len({r[0] for r in rows}) == 3 and all(len(r[0]) == 36 for r in rows) and [r[1] for r in rows] == [1, 2, 3] and all(r[2] for r in rows)


def test_new_entries_merge_in_and_replays_change_nothing(db):
    r = sync.handle(db, {"entries": [e(U1, details={"energy": 4}), e(U2, "bloating 6", kind="symptom", severity=6)], "since": 0})
    assert r["accepted"] == 2 and r["rejected"] == [] and db.val("SELECT COUNT(*) FROM entries") == 2
    assert json.loads(db.val("SELECT details FROM entries WHERE uuid=?", (U1,)))["energy"] == 4
    again = sync.handle(db, {"entries": [e(U1), e(U2, "bloating 6", kind="symptom", severity=6)], "since": 0})
    assert again["accepted"] == 0 and again["stale"] == 2 and db.val("SELECT COUNT(*) FROM entries") == 2


def test_the_later_edit_wins_both_ways(db):
    sync.handle(db, {"entries": [e(U1, "toast", updatedAt="2026-10-10T12:00:00Z")]})
    sync.handle(db, {"entries": [e(U1, "toast and jam", updatedAt="2026-10-10T13:00:00Z")]})
    assert db.val("SELECT text FROM entries WHERE uuid=?", (U1,)) == "toast and jam"
    r = sync.handle(db, {"entries": [e(U1, "older edit", updatedAt="2026-10-10T12:30:00Z")]})
    assert r["stale"] == 1 and db.val("SELECT text FROM entries WHERE uuid=?", (U1,)) == "toast and jam"
    sync.handle(db, {"entries": [e(U1, "toast and jam", removedAt="2026-10-10T14:00:00Z", updatedAt="2026-10-10T14:00:00Z")]})
    assert db.val("SELECT removed_at FROM entries WHERE uuid=?", (U1,)) == "2026-10-10T14:00:00Z"
    sync.handle(db, {"entries": [e(U1, "toast and jam", updatedAt="2026-10-10T15:00:00Z")]})
    assert db.val("SELECT removed_at FROM entries WHERE uuid=?", (U1,)) is None, "putting it back is a newer edit"


def test_bad_entries_are_reported_and_the_good_ones_still_land(db):
    r = sync.handle(db, {"entries": [e(U1), {"id": "x"}, e("../../etc", "evil"), e(U2, ts="not a time"), "junk", e(U3, "  ")]})
    assert r["accepted"] == 1 and len(r["rejected"]) == 5 and db.val("SELECT COUNT(*) FROM entries") == 1
    with pytest.raises(ValueError):
        sync.handle(db, {"entries": [e(U1)] * (sync.MAX_ENTRIES + 1)})


def test_an_entry_with_no_kind_is_sorted_out_by_the_server(db):
    sync.handle(db, {"entries": [e(U1, "bloating 7", kind=None), e(U2, "pooped a 6", kind=None), e(U3, "Oatmeal", kind="nonsense")]})
    kinds = {r["uuid"]: (r["kind"], r["severity"]) for r in db.q("SELECT * FROM entries")}
    assert kinds == {U1: ("symptom", 7), U2: ("stool", None), U3: ("food", None)}


def test_what_the_phone_does_not_have_comes_back_and_what_it_just_sent_does_not(db):
    diary.add(db, "imported lunch", clock.parse_iso("2026-09-05T16:00:00Z"), source="vault")
    first = sync.handle(db, {"entries": [e(U1)], "since": 0})
    assert [x["text"] for x in first["entries"]] == ["imported lunch"] and first["entries"][0]["source"] == "vault"
    cur = first["cursor"]
    assert sync.handle(db, {"entries": [], "since": cur})["entries"] == []
    diary.add(db, "added on the desktop", clock.parse_iso("2026-10-11T12:00:00Z"))
    nxt = sync.handle(db, {"entries": [], "since": cur})
    assert [x["text"] for x in nxt["entries"]] == ["added on the desktop"] and nxt["cursor"] > cur


def test_documents_and_settings_come_down_only_when_they_changed(db):
    db.set_setting("pond_start", "2026-10-10")
    db.ex("INSERT INTO documents(slug,title,kind,body,source,sort,created_at,updated_at) VALUES('p','Protocol','md','# Hi','',0,'2026-10-10T00:00:00Z','2026-10-10T00:00:00Z')")
    db.ex("INSERT INTO documents(slug,title,kind,body,file_name,source,sort,created_at,updated_at) VALUES('l','Lab','pdf','secret text','l.pdf','',1,'2026-10-10T00:00:00Z','2026-10-10T00:00:00Z')")
    r = sync.handle(db, {"entries": []})
    assert r["settings"] == {"pond_start": "2026-10-10"} and [d["slug"] for d in r["docs"]] == ["p", "l"]
    assert next(d for d in r["docs"] if d["slug"] == "l")["body"] == "", "a pdf's text is not sent"
    assert "docs" not in sync.handle(db, {"entries": [], "docs_sig": r["docs_sig"]})


@pytest.fixture
def c(tmp_path):
    auth.reset_fails()
    set_config(Config(env(tmp_path)))
    cl = TestClient(create_app(), follow_redirects=False)
    cl.post("/setup", data={"passphrase": PASS, "confirm": PASS})
    cl.dbpath = tmp_path / "tadpole.db"
    cl.cookies.clear()
    return cl


def key(c, scope="sync", name="My phone"):
    d = DB(c.dbpath)
    k = tokens.create(d, name, scope)
    d.close()
    return k


def post(c, k, body, **kw):
    return c.post("/api/sync", content=json.dumps(body) if not isinstance(body, (bytes, str)) else body, headers={"Authorization": "Bearer " + k, "Content-Type": "application/json"}, **kw)


def test_a_phone_key_syncs_and_nothing_else_can(c):
    k = key(c)
    r = post(c, k, {"entries": [e(U1)], "since": 0})
    assert r.status_code == 200 and r.json()["accepted"] == 1
    assert c.post("/api/sync", content="{}").status_code == 401
    assert post(c, "tps_wrong", {}).status_code == 401
    assert post(c, key(c, "widget"), {}).status_code == 401, "the old widget key cannot sync"
    for path in ("/api/state", "/export.csv", "/diary", "/api/entry"):
        assert c.get(path, headers={"Authorization": "Bearer " + k}).status_code in (401, 303, 405), path
    assert c.post("/api/entry", content=json.dumps({"text": "x"}), headers={"Authorization": "Bearer " + k}).status_code == 401
    d = DB(c.dbpath)
    assert d.val("SELECT last_used_at FROM api_tokens WHERE scope='sync' ORDER BY id LIMIT 1") is not None
    d.close()


def test_a_cancelled_phone_is_cut_off_and_bad_requests_are_refused(c):
    k = key(c)
    d = DB(c.dbpath); tokens.revoke(d, d.val("SELECT id FROM api_tokens")); d.close()
    assert post(c, k, {}).status_code == 401
    k2 = key(c)
    assert post(c, k2, "{not json").status_code == 400
    assert post(c, k2, "[1,2]").status_code == 400
    assert post(c, k2, b"x" * (sync.MAX_BODY + 10)).status_code == 413


def test_the_companion_listener_answers_only_the_sync_route(tmp_path):
    auth.reset_fails()
    set_config(Config(env(tmp_path)))
    admin = TestClient(create_app(), follow_redirects=False)
    admin.post("/setup", data={"passphrase": PASS, "confirm": PASS})
    d = DB(tmp_path / "tadpole.db"); k = tokens.create(d, "p", "sync"); d.close()
    set_config(Config(env(tmp_path, TADPOLE_SYNC_ONLY="1", TADPOLE_REQUIRE_TS_HEADER="1", TADPOLE_TS_LOGINS="me@example.com")))
    cl = TestClient(create_app(), follow_redirects=False)
    assert cl.get("/healthz").status_code == 200
    for path in ("/", "/diary", "/login", "/settings/phone", "/static/app.css", "/export.csv"):
        assert cl.get(path).status_code == 404, path
    assert post(cl, k, {"entries": [e(U1)]}).status_code == 200, "no Tailscale header is needed: the key is the credential"
    assert post(cl, "tps_wrong", {}).status_code == 401


def make_cert(d):
    d.mkdir(parents=True, exist_ok=True)
    subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "30", "-subj", "/CN=tadpole", "-keyout", str(d / "key.pem"), "-out", str(d / "cert.pem")], check=True, capture_output=True)


@pytest.mark.skipif(shutil.which("openssl") is None, reason="openssl is not installed")
def test_the_pairing_page_makes_a_code_with_every_address_and_the_certificate_pin(c, tmp_path, monkeypatch):
    make_cert(tmp_path / "tls")
    monkeypatch.setattr(pairing, "lan_ip", lambda: "192.168.1.20")
    admin = TestClient(create_app(), follow_redirects=False)
    admin.post("/login", data={"passphrase": PASS})
    assert "Pair a phone" in admin.get("/settings/phone").text
    page = admin.post("/settings/phone/new", data={"name": "Pixel"}, headers={"host": "box.tail1234.ts.net:8444"}).text
    assert "<svg" in page and "tadpole://pair?" in page and 'class="qr"' in page
    link = next(x for x in page.split('"') if x.startswith("tadpole://pair?")).replace("&amp;", "&")
    q = parse_qs(urlparse(link).query)
    assert q["v"] == ["1"] and q["key"][0].startswith("tps_") and len(q["e"]) == 2
    home, tail = (unquote(x) for x in q["e"])
    assert home == "https://192.168.1.20:8120#" + pairing.pin(Config(env(tmp_path))) and len(home.split("#")[1]) == 64
    assert tail == "https://box.tail1234.ts.net:8444", "Tailscale already has a real certificate, so it carries no pin"
    assert post(c, q["key"][0], {"entries": []}).status_code == 200, "the key in the code works"
    assert "Pixel" in admin.get("/settings/phone").text and "tps_" not in admin.get("/settings/phone").text
    admin.post("/settings/phone/revoke", data={"id": "1"})
    assert post(c, q["key"][0], {}).status_code == 401


def test_without_a_certificate_only_tailscale_addresses_are_offered(c, monkeypatch):
    monkeypatch.setattr(pairing, "lan_ip", lambda: "192.168.1.20")
    cfg = Config(env(pathlib.Path("/nonexistent")))
    assert pairing.endpoints(cfg, "box.tail1234.ts.net") == [{"url": "https://box.tail1234.ts.net", "pin": None, "label": "Tailscale"}]
    assert pairing.endpoints(cfg, "127.0.0.1:8101") == []


def test_a_tailscale_address_is_offered_automatically_when_this_computer_is_on_tailscale(tmp_path, monkeypatch):
    make_cert(tmp_path / "tls")
    cfg = Config(env(tmp_path))
    monkeypatch.setattr(pairing, "lan_ip", lambda: "192.168.1.20")
    monkeypatch.setattr(pairing, "tailscale_ip", lambda: "100.101.102.103")
    eps = pairing.endpoints(cfg, "127.0.0.1:8101")
    assert [(e["url"], bool(e["pin"]), e["label"]) for e in eps] == [("https://192.168.1.20:8120", True, "home Wi-Fi"), ("https://100.101.102.103:8120", True, "Tailscale")]
    monkeypatch.setattr(pairing, "tailscale_ip", lambda: None)
    assert [e["label"] for e in pairing.endpoints(cfg, "127.0.0.1:8101")] == ["home Wi-Fi"]
    monkeypatch.setattr(pairing.shutil, "which", lambda n: None)
    assert pairing.tailscale_ip() is None
