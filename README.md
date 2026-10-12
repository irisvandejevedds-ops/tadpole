# Tadpole
A frog-themed food and symptom diary. The phone app keeps the diary on the phone; a computer companion is optional.

- `web/` the app itself: plain JS, no build step. One copy of the logic (`core.js`) runs in the Android app, in the browser demo and in the tests.
- `android/` the APK: a full-screen WebView that serves `web/` from its own files, a local SQLite diary, the home-screen widget, and pairing/sync (`Desk.java`). Built without Gradle: `android/build.sh`.
- `app/` the desktop companion (FastAPI + SQLite): keeps a copy of the diary, shows it on a bigger screen, holds documents, and answers the phone's sync on a TLS port the phone pins.
- `desktop/` the one-command launcher that is zipped for download (`python3 start.py`).
- `site/` the download site (static, for Cloudflare Pages): `python site/build.py` writes `site/dist`.

Tests:
- `cd app && ../.venv/bin/python -m pytest` (desktop side, including sync and pairing)
- `cd web && TZ=America/Toronto node --test tests/parity.test.js` (the JS rules agree with the Python rules; regenerate fixtures with `tests/gen_parity.py`)
- `python web/tests/browser_check.py OUT_DIR [WIDTH] [demo|native]` (drives the real app in headless Firefox)
