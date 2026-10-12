import csv
import io
import pathlib
import re
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, Form, HTTPException, Request
import json

from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from markupsafe import Markup
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.gzip import GZipMiddleware

from . import auth, clock, diary, mdrender, pairing, pond, sprites, sync, tokens, widget_routes
from .config import get_config
from .db import DB, open_db

HERE = pathlib.Path(__file__).parent
templates = Jinja2Templates(directory=str(HERE / "templates"))
NAV = [("Pond", "/"), ("Diary", "/diary"), ("Patterns", "/patterns"), ("Library", "/library"), ("Phone", "/settings/phone")]
FACT_LABELS = [("entry_type", "Type"), ("phase", "Phase"), ("fodmap_group", "FODMAP group"), ("stool_bsfs", "Bristol"), ("onset_lag_h", "Onset lag (h)"),
               ("bloating", "Bloating"), ("abdo_pain", "Abdominal pain"), ("gas", "Gas"), ("urgency", "Urgency"), ("energy", "Energy"), ("stress", "Stress"),
               ("sleep_h", "Sleep (h)"), ("mood_context", "Mood context")]
NOTE_LABELS = [("what", "What"), ("suspected_group", "Suspected group"), ("symptoms", "Symptoms"), ("context", "Context"), ("notes", "Notes"), ("verbatim", "Your words")]
CSV_EXTRA = [k for k, _ in FACT_LABELS] + ["reconstructed", "time_unknown"] + [k for k, _ in NOTE_LABELS]


def entry_details(row):
    try:
        return json.loads(row["details"]) if row["details"] else {}
    except ValueError:
        return {}


def entry_facts(row):
    """What an imported entry carried beyond its words: -> {facts: [(label, value)], notes: [(label, text)]}."""
    d = entry_details(row)
    facts = [(label, d[k]) for k, label in FACT_LABELS if d.get(k) is not None]
    if d.get("reconstructed"):
        facts.append(("Origin", "rebuilt from the old spreadsheet; the wording is not your own"))
    if d.get("time_unknown"):
        facts.append(("Time", "was not recorded; placed just after the previous entry"))
    return {"facts": facts, "notes": [(label, d[k]) for k, label in NOTE_LABELS if d.get(k)]}
PUBLIC_PREFIXES = ("/static/", "/healthz", "/login", "/setup", "/manifest.webmanifest")
KIND_WORDS = {"food": "food", "symptom": "symptom", "clear": "all clear", "note": "note", "stool": "stool"}


class NeedLogin(Exception):
    pass


class NeedSetup(Exception):
    pass


def safe_next(n):
    return n if n and n.startswith("/") and not n.startswith("//") else "/"


templates.env.globals["entry_facts"] = entry_facts
templates.env.globals["frog"] =lambda stage, mood, scale=8, cls="": Markup(sprites.svg(stage, mood, scale, cls))


def create_app():
    cfg = get_config()
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    app.mount("/static", StaticFiles(directory=str(HERE / "static")), name="static")
    open_db(cfg.db_path).close()

    def get_db():
        d = DB(cfg.db_path)
        try:
            yield d
        finally:
            d.close()

    def session(request: Request, db: DB = Depends(get_db)):
        if not auth.has_passphrase(db):
            raise NeedSetup()
        s = auth.lookup_session(db, request.cookies.get(auth.COOKIE))
        if not s:
            bearer = request.headers.get("authorization", "")
            if bearer[:7].lower() == "bearer " and request.url.path in tokens.ALLOWED:
                if tokens.too_many_failures():
                    raise HTTPException(429, "too many attempts")
                if tokens.verify(db, bearer[7:].strip(), request.url.path):
                    return {"token": True}
                tokens.note_failure()
            raise NeedLogin()
        return s

    def wants_json(request):
        return request.url.path.startswith("/api/")

    @app.exception_handler(NeedLogin)
    async def _need_login(request, exc):
        if wants_json(request):
            return JSONResponse({"error": "login required"}, status_code=401)
        nxt = request.url.path + (("?" + request.url.query) if request.url.query else "")
        return RedirectResponse("/login?next=" + nxt, status_code=303)

    @app.exception_handler(NeedSetup)
    async def _need_setup(request, exc):
        return JSONResponse({"error": "setup required"}, status_code=401) if wants_json(request) else RedirectResponse("/setup", 303)

    @app.middleware("http")
    async def guard(request: Request, call_next):
        path = request.url.path
        if cfg.sync_only and path not in ("/healthz", "/api/sync"):
            return PlainTextResponse("Not found", status_code=404)
        if path != "/healthz" and cfg.require_ts_header and not cfg.sync_only:
            who = request.headers.get("tailscale-user-login", "").lower()
            if who not in cfg.ts_logins:
                return PlainTextResponse("This app is only available on your tailnet.", status_code=403)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            site = request.headers.get("sec-fetch-site")
            origin = request.headers.get("origin")
            if site and site not in ("same-origin", "none"):
                return PlainTextResponse("Cross-site request blocked.", status_code=403)
            if origin and site not in ("same-origin", "none") and urlparse(origin).netloc != request.headers.get("host", ""):
                return PlainTextResponse("Cross-site request blocked.", status_code=403)
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault("Content-Security-Policy", "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
                                "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if not path.startswith("/static/"):
            resp.headers.setdefault("Cache-Control", "no-store")
        return resp

    def render(request, db, name, **kw):
        now = clock.now()
        st = pond.state(db, cfg.tz, now) if db is not None and auth.has_passphrase(db) and name not in ("login.html", "error.html") else None
        return templates.TemplateResponse(request, name, {"request": request, "nav": NAV, "path": request.url.path, "tz": cfg.tz, "pond": st,
                                                          "mood": st["color"] if st else "green", "kind_words": KIND_WORDS, **kw})

    @app.exception_handler(StarletteHTTPException)
    async def _friendly_errors(request, exc):
        if wants_json(request) or request.url.path.startswith("/static/") or request.method == "HEAD":
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
        msg = exc.detail if isinstance(exc.detail, str) else "Something went wrong."
        return templates.TemplateResponse(request, "error.html", {"request": request, "nav": NAV, "path": "", "mood": "green", "pond": None,
                                                                  "title": {404: "Nothing here"}.get(exc.status_code, "Hold on"), "message": msg,
                                                                  "back": request.headers.get("referer") and urlparse(request.headers["referer"]).path or "/"},
                                          status_code=exc.status_code)

    @app.get("/healthz")
    def healthz():
        return {"ok": True}

    # ---------------- gate ----------------
    @app.get("/setup", response_class=HTMLResponse)
    def setup_page(request: Request, db: DB = Depends(get_db)):
        if auth.has_passphrase(db):
            return RedirectResponse("/login", 303)
        return render(request, db, "login.html", mode="setup", error=None, next="/", bare=True)

    @app.post("/setup")
    def setup_submit(request: Request, passphrase: str = Form(...), confirm: str = Form(...), db: DB = Depends(get_db)):
        if auth.has_passphrase(db):
            return RedirectResponse("/login", 303)
        if len(passphrase) < auth.MIN_PASSPHRASE or passphrase != confirm:
            return render(request, db, "login.html", mode="setup", next="/", bare=True, error=f"Use at least {auth.MIN_PASSPHRASE} characters, typed the same twice.")
        auth.set_passphrase(db, passphrase)
        resp = RedirectResponse("/", 303)
        resp.set_cookie(auth.COOKIE, auth.create_session(db, request.headers.get("user-agent", "")), max_age=auth.SESSION_DAYS * 86400,
                        httponly=True, secure=cfg.cookie_secure, samesite="strict")
        return resp

    @app.get("/login", response_class=HTMLResponse)
    def login_page(request: Request, next: str = "/", db: DB = Depends(get_db)):
        if not auth.has_passphrase(db):
            return RedirectResponse("/setup", 303)
        return render(request, db, "login.html", mode="login", error=None, next=safe_next(next), bare=True)

    @app.post("/login")
    def login_submit(request: Request, passphrase: str = Form(...), next: str = Form("/"), db: DB = Depends(get_db)):
        if auth.locked():
            return render(request, db, "login.html", mode="login", next=safe_next(next), bare=True, error="Too many attempts. Wait ten minutes and try again.")
        if not auth.check_passphrase(db, passphrase):
            auth.record_fail()
            return render(request, db, "login.html", mode="login", next=safe_next(next), bare=True, error="That passphrase is not right.")
        auth.reset_fails()
        resp = RedirectResponse(safe_next(next), 303)
        resp.set_cookie(auth.COOKIE, auth.create_session(db, request.headers.get("user-agent", "")), max_age=auth.SESSION_DAYS * 86400,
                        httponly=True, secure=cfg.cookie_secure, samesite="strict")
        return resp

    @app.post("/logout")
    def logout(request: Request, db: DB = Depends(get_db)):
        auth.destroy_session(db, request.cookies.get(auth.COOKIE))
        resp = RedirectResponse("/login", 303)
        resp.delete_cookie(auth.COOKIE)
        return resp

    # ---------------- the pond ----------------
    def local_input(ts_iso):
        return clock.parse_iso(ts_iso).astimezone(cfg.tz).strftime("%Y-%m-%dT%H:%M")

    def from_local(v):
        try:
            return datetime.strptime(v, "%Y-%m-%dT%H:%M").replace(tzinfo=cfg.tz).astimezone(timezone.utc)
        except (TypeError, ValueError):
            return None

    @app.get("/", response_class=HTMLResponse)
    def home(request: Request, saved: int = 0, db: DB = Depends(get_db), _=Depends(session)):
        now = clock.now()
        start, end = diary.day_bounds(now.astimezone(cfg.tz).date(), cfg.tz)
        todays = list(reversed(diary.live(db, start, end)))
        just = db.one("SELECT * FROM entries WHERE id=? AND removed_at IS NULL", (saved,)) if saved else None
        return render(request, db, "pond.html", todays=todays, just=just, hhmm=lambda ts: clock.parse_iso(ts).astimezone(cfg.tz).strftime("%-I:%M %p").lower())

    @app.post("/entry")
    async def add_entry(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        f = await request.form()
        try:
            eid = diary.add(db, f.get("text") or "", clock.now(), kind=f.get("kind") or None, severity=(int(f["severity"]) if (f.get("severity") or "").isdigit() else None), source="app")
        except ValueError as e:
            raise HTTPException(400, str(e))
        return RedirectResponse(f"/?saved={eid}", 303)

    @app.post("/entry/clear")
    def add_clear(db: DB = Depends(get_db), _=Depends(session)):
        eid = diary.add(db, "No symptoms", clock.now(), kind="clear", source="app")
        return RedirectResponse(f"/?saved={eid}", 303)

    @app.post("/entry/remove")
    async def remove_entry(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        f = await request.form()
        if (f.get("id") or "").isdigit():
            diary.remove(db, int(f["id"]), clock.now(), restore=f.get("restore") == "1")
        back = f.get("back") or "/"
        return RedirectResponse(back if back.startswith("/") and not back.startswith("//") else "/", 303)

    @app.post("/entry/edit")
    async def edit_entry(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        f = await request.form()
        if not (f.get("id") or "").isdigit() or not db.one("SELECT 1 FROM entries WHERE id=?", (int(f["id"]),)):
            raise HTTPException(404, "No such entry")
        when = from_local(f.get("when"))
        diary.update(db, int(f["id"]), f.get("text") or "", f.get("kind"), f.get("severity"), when)
        return RedirectResponse("/diary#e" + f["id"], 303)

    @app.get("/diary", response_class=HTMLResponse)
    def diary_page(request: Request, days: int = 7, db: DB = Depends(get_db), _=Depends(session)):
        days = max(1, min(60, days))
        today = clock.now().astimezone(cfg.tz).date()
        groups = []
        for i in range(days):
            d = today - timedelta(days=i)
            s, e = diary.day_bounds(d, cfg.tz)
            rows = list(reversed(diary.live(db, s, e)))
            groups.append({"day": d, "label": "Today" if i == 0 else "Yesterday" if i == 1 else d.strftime("%a %b %-d"), "rows": rows, "sev": pond.day_severity(rows) if rows else None})
        removed = db.q("SELECT * FROM entries WHERE removed_at IS NOT NULL ORDER BY removed_at DESC LIMIT 5")
        return render(request, db, "diary.html", groups=groups, days=days, removed=removed, local_input=local_input, label=lambda ts: diary.meal_label(ts, cfg.tz),
                      hhmm=lambda ts: clock.parse_iso(ts).astimezone(cfg.tz).strftime("%-I:%M %p").lower())

    @app.get("/patterns", response_class=HTMLResponse)
    def patterns(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        today = clock.now().astimezone(cfg.tz).date()
        days = pond.by_day(db, cfg.tz)
        bars = []
        for i in range(29, -1, -1):
            d = today - timedelta(days=i)
            bars.append({"day": d, "logged": d in days, "sev": pond.day_severity(days[d]) if d in days else None})
        return render(request, db, "patterns.html", bars=bars, trig=pond.triggers(db, cfg.tz))

    @app.get("/export.csv")
    def export(db: DB = Depends(get_db), _=Depends(session)):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["date", "time", "kind", "severity", "text", "source"] + CSV_EXTRA)
        for r in diary.live(db):
            t = clock.parse_iso(r["ts"]).astimezone(cfg.tz)
            d = entry_details(r)
            w.writerow([t.strftime("%Y-%m-%d"), t.strftime("%H:%M"), r["kind"], "" if r["severity"] is None else r["severity"], r["text"], r["source"]]
                       + ["" if d.get(k) is None else d[k] for k in CSV_EXTRA])
        return Response(out.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="food-diary.csv"'})

    # ---------------- the library: reference documents kept with the diary ----------------
    @app.get("/library", response_class=HTMLResponse)
    def library(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        return render(request, db, "library.html", docs=db.q("SELECT slug,title,kind,source,updated_at FROM documents ORDER BY sort, id"))

    def find_doc(db, slug):
        d = db.one("SELECT * FROM documents WHERE slug=?", (slug,))
        if not d:
            raise HTTPException(404, "No such document")
        return d

    @app.get("/library/{slug}", response_class=HTMLResponse)
    def library_doc(slug: str, request: Request, db: DB = Depends(get_db), _=Depends(session)):
        d = find_doc(db, slug)
        return render(request, db, "doc.html", doc=d, html=Markup(mdrender.render(d["body"])) if d["kind"] == "md" else None)

    @app.get("/library/{slug}/file")
    def library_file(slug: str, db: DB = Depends(get_db), _=Depends(session)):
        d = find_doc(db, slug)
        p = cfg.data_dir / "library" / (d["file_name"] or "missing")
        if d["kind"] != "pdf" or not p.is_file():
            raise HTTPException(404, "No file for this document")
        return FileResponse(p, media_type="application/pdf", filename=f"{slug}.pdf", content_disposition_type="inline")

    # ---------------- phones ----------------
    @app.post("/api/sync")
    async def api_sync(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        if int(request.headers.get("content-length") or 0) > sync.MAX_BODY:
            raise HTTPException(413, "too much data in one sync")
        raw = await request.body()
        if len(raw) > sync.MAX_BODY:
            raise HTTPException(413, "too much data in one sync")
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError("body is not an object")
            return sync.handle(db, body)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e) or "bad sync request")

    def phone_page(request, db, new_token=None):
        host = request.headers.get("host", "")
        urls = pairing.endpoints(cfg, host)
        link = pairing.link(cfg, urls, new_token, name=pairing.computer_name()) if new_token else None
        return render(request, db, "phone.html", phones=tokens.listing(db, "sync"), new_token=new_token, link=link, urls=urls,
                      qr=pairing.qr_svg(link) if link else None, tls_ready=pairing.pin(cfg) is not None,
                      apk=(cfg.apk_dir / widget_routes.APK_NAME).exists(), apk_kb=((cfg.apk_dir / widget_routes.APK_NAME).stat().st_size // 1024) if (cfg.apk_dir / widget_routes.APK_NAME).exists() else 0)

    @app.get("/settings/phone", response_class=HTMLResponse)
    def phone_get(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        return phone_page(request, db)

    @app.post("/settings/phone/new", response_class=HTMLResponse)
    async def phone_new(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        f = await request.form()
        return phone_page(request, db, tokens.create(db, (f.get("name") or "My phone").strip(), "sync"))

    @app.post("/settings/phone/revoke")
    async def phone_revoke(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        f = await request.form()
        if (f.get("id") or "").isdigit():
            tokens.revoke(db, int(f["id"]))
        return RedirectResponse("/settings/phone", 303)

    # ---------------- the widget's API ----------------
    def api_state(db):
        now = clock.now()
        st = pond.state(db, cfg.tz, now)
        last = diary.recent(db, 1)
        g = st["growth"]
        return {"color": st["color"], "stage": st["stage"], "stage_name": st["stage_name"], "ago": st["ago"], "line": st["line"], "today_count": st["today_count"],
                "control": st["control"]["label"], "control_key": st["control"]["key"], "to_next": g["to_next"], "points": g["points"],
                "last": ({"id": last[0]["id"], "text": last[0]["text"], "kind": last[0]["kind"]} if last else None)}

    @app.get("/api/state")
    def state(db: DB = Depends(get_db), _=Depends(session)):
        return api_state(db)

    @app.post("/api/entry")
    async def api_entry(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        b = await request.json()
        now = clock.now()
        ts = None
        if b.get("ts"):
            try:
                ts = clock.parse_iso(b["ts"])
            except ValueError:
                raise HTTPException(400, "bad timestamp")
            if ts > now + timedelta(minutes=5) or ts < now - timedelta(days=45):
                raise HTTPException(400, "timestamp out of range")
        sev = b.get("severity")
        try:
            eid = diary.add(db, str(b.get("text") or ""), now, ts=ts, kind=b.get("kind") or None, severity=(int(sev) if sev is not None else None),
                            source="widget", key=str(b.get("key") or "")[:80] or None)
        except (ValueError, TypeError) as e:
            raise HTTPException(400, str(e) or "bad entry")
        row = db.one("SELECT * FROM entries WHERE id=?", (eid,))
        return {"ok": True, "id": eid, "kind": row["kind"], "severity": row["severity"], "state": api_state(db)}

    @app.post("/api/undo")
    async def api_undo(request: Request, db: DB = Depends(get_db), _=Depends(session)):
        b = await request.json()
        if not db.one("SELECT 1 FROM entries WHERE id=?", (int(b.get("id", 0)),)):
            raise HTTPException(404, "unknown entry")
        diary.remove(db, int(b["id"]), clock.now())
        return {"ok": True, "state": api_state(db)}

    @app.get("/manifest.webmanifest")
    def manifest():
        icon = [{"src": "/static/icons/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": "/static/icons/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": "/static/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]
        return JSONResponse({"name": "Tadpole", "short_name": "Tadpole", "description": "A food diary with a frog.", "id": "/", "start_url": "/", "scope": "/",
                             "display": "standalone", "background_color": "#17414A", "theme_color": "#2F8442", "icons": icon})

    widget_routes.register(app, cfg, get_db, session, render)
    return app


def get_app():
    return create_app()
