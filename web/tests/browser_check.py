"""Loads the real app in headless Firefox, drives it (typing, taps, pickers, pages), and screenshots it with a pass/fail report on top.
    python browser_check.py OUT_DIR [WIDTH] [demo]
Serves ../ over local http only; nothing leaves the machine."""
import http.server
import pathlib
import shutil
import subprocess
import sys
import tempfile
import threading
import time

WEB = pathlib.Path(__file__).resolve().parents[1]
TYPES = {".js": "text/javascript", ".css": "text/css", ".woff2": "font/woff2", ".png": "image/png", ".html": "text/html", ".webmanifest": "application/manifest+json"}

TEST = r"""
(function () {
  var out = [], demo = !!(window.TADPOLE_CONFIG && window.TADPOLE_CONFIG.demo);
  function say(ok, msg) { out.push((ok ? 'PASS ' : 'FAIL ') + msg); var p = document.getElementById('report'); if (p) p.textContent = out.join('\n'); }
  function $(s) { return document.querySelector(s); }
  function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
  function S() { return window.__tadpole.S(); }
  function pk() { return $('.pgrid').closest('.card'); }
  function live() { return S().entries.filter(function (e) { return !e.removedAt; }); }
  function click(el) { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); }
  function typeAndAdd(text) { var i = $('#entry input[name=text]'); i.value = text; $('#entry').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true })); }
  function go() {
    try {
      var n0 = live().length;
      say(!!$('.hero svg') && $('h1').textContent.length > 0, 'pond page shows the frog and a mood word (' + $('h1').textContent + ')');
      say(demo ? n0 > 20 && !!$('.demobar') : n0 === 0, demo ? 'demo is seeded with ' + n0 + ' entries and shows its banner' : 'a fresh app starts empty');
      var callout = $('.callout'), box = $('.infotoggle');
      say(getComputedStyle(callout).display === 'none', 'explainer text is hidden until asked for');
      box.checked = true; box.dispatchEvent(new Event('change', { bubbles: true }));
      say(getComputedStyle(callout).display === 'block', 'the i button opens its callout');
      box.checked = false;
      typeAndAdd('bloating 6');
      var e = live().slice(-1)[0];
      say(e && e.kind === 'symptom' && e.severity === 6 && /Saved as/.test($('.notice').textContent), 'typing "bloating 6" saves a symptom 6 and says so');
      click($('.notice .btn'));
      say(live().length === n0, 'Undo removes it again');
      typeAndAdd('   ');
      say(live().length === n0 && !!$('.error'), 'an empty line is refused with a message');
      typeAndAdd('pooped a 5/6');
      say(live().slice(-1)[0].kind === 'stool', '"pooped a 5/6" is kept as a stool entry');
      click($$('.qbtn')[0]);
      say($$('.pgrid .ptile').length === 7, 'the stool button opens a 1 to 7 scale');
      var tiles = $$('.pgrid .ptile'); say(tiles[2].style.background !== tiles[0].style.background, 'scale tiles are colour coded');
      click(tiles[5]);
      say(live().slice(-1)[0].text === 'Stool, Bristol 6' && live().slice(-1)[0].kind === 'stool' && !$('.pgrid'), 'tapping 6 saves "Stool, Bristol 6" and closes the picker');
      click($$('.qbtn')[1]); click($$('.pgrid .ptile')[6]);
      var nz = live().slice(-1)[0]; say(nz.kind === 'symptom' && nz.severity === 10 && nz.text === 'Neuroinflammation 7/7', 'neuro 7 saves a symptom of severity 10');
      click($$('.qbtn')[2]);
      say($$('.pgrid .ptile').length === 4, 'the meal button first asks for a size 1 to 4');
      click($$('.pgrid .ptile')[1]);
      say($$('.pgrid .ptile').length === 7, 'then offers the seven FODMAP food icons');
      click($$('.pgrid .ptile')[0]); click($$('.pgrid .ptile')[1]);
      say($$('.pgrid .ptile.on').length === 2 && /Save \(2\)/.test(pk().querySelector('.row .btn').textContent), 'picked foods light up and the button counts them');
      click(pk().querySelector('.row .btn'));
      var meal = live().slice(-1)[0]; say(meal.kind === 'food' && meal.text === 'Meal size 2 (~1000 kcal) - FODMAP triggers: 2 (wheat, onion/garlic)', 'the meal is saved with its size and triggers');
      click($$('.qbtn')[2]); click($$('.pgrid .ptile')[0]); click(pk().querySelector('.row .btn.ghost'));
      say($$('.pgrid .ptile').length === 4, 'Back returns to the size step');
      click(pk().querySelector('.row .btn.ghost:last-child'));
      say(!$('.pgrid'), 'Cancel closes the picker without saving');
      click($$('.btn.ghost').filter(function (b) { return /No symptoms today/.test(b.textContent); })[0]);
      say(live().slice(-1)[0].kind === 'clear' && live().slice(-1)[0].severity === 0, '"No symptoms today" saves an all-clear');
      say(JSON.parse(localStorage.getItem('tadpole.v1')).entries.length >= live().length, 'entries are persisted to storage');
      location.hash = '#/diary';
      setTimeout(function () {
        say(!!$('.ed') && $$('.ed').length >= 5, 'diary lists entries by day (' + $$('.ed').length + ' on screen)');
        var d = $('.ed'); d.open = true;
        var f = d.querySelector('form'); f.querySelector('input[name=text]').value = 'edited words'; f.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
        say(live().some(function (x) { return x.text === 'edited words'; }), 'editing an entry in the diary saves the new words');
        location.hash = '#/patterns';
        setTimeout(function () {
          say($$('.bar').length === 30, 'patterns shows 30 day bars');
          location.hash = '#/settings';
          setTimeout(function () {
            say(!!$('h1') && /Settings/.test($('h1').textContent) && $$('.btn.warn').length === 1, 'settings page has the delete-all control');
            var get = $$('a.btn').filter(function (b) { return b.textContent === 'Get the apps'; });
            say(demo ? get.length === 1 && /cannot sync/.test(document.body.textContent) : get.length === 0 && /cannot sync/.test(document.body.textContent), 'the browser version says it cannot sync' + (demo ? ' and links to the apps' : ''));
            say($$('.topnav a').length === 4 && $$('.tabbar a').length === 4, 'navigation has four tabs (no Library without documents)');
            location.hash = '#/';
            setTimeout(function () { say(true, 'done'); }, 100);
          }, 100);
        }, 100);
      }, 100);
    } catch (e) { say(false, 'exception: ' + e + ' ' + ((e.stack || '').split('\n')[0])); }
  }
  setTimeout(go, 300);
})();
"""



FAKE_BRIDGE = r"""
(function () {
  var db = { entries: [{ id: 'aaaaaaaa-0000-4000-8000-000000000001', ts: new Date(Date.now() - 3600000).toISOString().replace(/\.\d{3}Z$/, 'Z'), kind: null, text: 'bloating 7', severity: null, source: 'widget', details: null, removedAt: null, updatedAt: new Date().toISOString().replace(/\.\d{3}Z$/, 'Z') }],
             settings: {}, docs: [{ slug: 'p', title: 'Protocol', kind: 'md', body: '# Plan\n\nEat **well**.' }, { slug: 'l', title: 'Lab report', kind: 'pdf', body: '' }] };
  var paired = false, running = false, log = [];
  window.__bridge = { db: db, log: log, snapshots: [] };
  window.TadpoleNative = {
    loadAll: function () { return JSON.stringify(db); },
    putEntry: function (j) { var e = JSON.parse(j), i = db.entries.findIndex(function (x) { return x.id === e.id; }); if (i >= 0) db.entries[i] = e; else db.entries.push(e); log.push('put ' + e.id.slice(0, 4)); },
    setSetting: function (k, v) { db.settings[k] = v; },
    saveSnapshot: function (j) { window.__bridge.snapshots.push(JSON.parse(j)); },
    deleteAll: function () { db.entries = []; db.docs = []; log.push('deleteAll'); },
    saveFile: function (n, m, t) { log.push('file ' + n + ' ' + t.split('\n')[0].slice(0, 20)); return true; },
    syncStatus: function () { return JSON.stringify({ paired: paired, name: paired ? 'Test PC' : '', message: '', running: running, last_sync: paired ? 'today' : '' }); },
    syncNow: function () { running = true; log.push('syncNow'); setTimeout(function () { running = false; }, 900); },
    unpair: function () { paired = false; log.push('unpair'); },
    pair: function (l) { if (l.indexOf('tadpole://pair?') !== 0) return 'That is not a Tadpole pairing link.'; paired = true; running = true; setTimeout(function () { running = false; }, 900); return ''; }
  };
})();
"""

TEST_NATIVE = r"""
(function () {
  var out = [];
  function say(ok, msg) { out.push((ok ? 'PASS ' : 'FAIL ') + msg); var p = document.getElementById('report'); if (p) p.textContent = out.join('\n'); }
  function $(s) { return document.querySelector(s); } function $$(s) { return Array.prototype.slice.call(document.querySelectorAll(s)); }
  function click(el) { el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); }
  var B = window.__bridge;
  function go() {
    try {
      var e0 = B.db.entries[0];
      say(e0.kind === 'symptom' && e0.severity === 7 && e0.text === 'bloating 7', 'a widget entry that arrived with no kind was sorted out and saved back (' + e0.kind + ' ' + e0.severity + ')');
      var snap = B.snapshots[B.snapshots.length - 1];
      say(!!snap && snap.color === 'green' && typeof snap.stage === 'number' && snap.stage_name && snap.control && snap.last_ts, 'the widget snapshot has colour, stage, name, weekly label and last entry time');
      var i = $('#entry input[name=text]'); i.value = 'toast'; $('#entry').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
      say(B.db.entries.length === 2 && B.db.entries[1].text === 'toast' && B.db.entries[1].id.length === 36, 'a new entry goes to the phone database with an id');
      say(B.snapshots.length >= 2, 'and the widget snapshot is refreshed');
      say($$('.topnav a').length === 5 && /Library/.test($('.topnav').textContent), 'the Library tab appears because documents were synced');
      location.hash = '#/library';
      setTimeout(function () {
        say($$('.card .entry').length === 2, 'the library lists both documents');
        click($$('.card .entry a')[0]);
        say(/Plan/.test($('.doc').innerHTML) && /<strong>well<\/strong>/.test($('.doc').innerHTML), 'a note document is shown as formatted text');
        location.hash = '#/settings';
        setTimeout(function () {
          say(/Not paired/.test(document.body.textContent), 'settings says the phone is not paired');
          var link = $('input[placeholder^="tadpole://"]'); link.value = 'nonsense';
          click($$('button').filter(function (b) { return b.textContent === 'Pair'; })[0]);
          say(/not a Tadpole pairing link/.test(document.body.textContent), 'a bad pairing link is refused with a reason');
          $('input[placeholder^="tadpole://"]').value = 'tadpole://pair?v=1&key=tps_x&e=https%3A%2F%2F1.2.3.4%3A8120';
          click($$('button').filter(function (b) { return b.textContent === 'Pair'; })[0]);
          setTimeout(function () {
            say(/Paired and synced/.test(document.body.textContent) && /Paired with Test PC/.test(document.body.textContent), 'a good link pairs and the page reports the sync finishing');
            click($$('button').filter(function (b) { return /Sync now/.test(b.textContent); })[0]);
            say(B.log.indexOf('syncNow') >= 0 && /Syncing/.test(document.body.textContent), 'Sync now starts a sync and shows that it is running');
            setTimeout(function () {
              say(/Synced\./.test(document.body.textContent), 'and says when it is done');
              click($$('button').filter(function (b) { return b.textContent === 'Download everything (CSV)'; })[0]);
              say(B.log.some(function (l) { return /^file food-diary.csv date,time,kind/.test(l); }), 'the CSV is saved through the phone to Downloads');
              window.confirm = function () { return true; };
              click($$('button').filter(function (b) { return b.textContent === 'Delete all'; })[0]);
              say(B.log.indexOf('deleteAll') >= 0 && /deleted/.test(document.body.textContent), 'Delete all clears the phone database');
              say(true, 'done');
            }, 1700);
          }, 1700);
        }, 100);
      }, 100);
    } catch (e) { say(false, 'exception: ' + e + ' ' + ((e.stack || '').split('\n')[0])); }
  }
  setTimeout(go, 300);
})();
"""


def main():
    out = pathlib.Path(sys.argv[1]).resolve()
    width = int(sys.argv[2]) if len(sys.argv) > 2 else 1100
    demo = "demo" in sys.argv[3:]
    native = "native" in sys.argv[3:]
    out.mkdir(parents=True, exist_ok=True)
    tmp = pathlib.Path(tempfile.mkdtemp())

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/wait":
                time.sleep(9)
                body, ctype = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x01D\x00;", "image/gif"
            elif path == "/config.js":
                body, ctype = ("window.TADPOLE_CONFIG={demo:%s,downloadUrl:'/index.html'};" % ("true" if demo else "false")).encode(), "text/javascript"
            elif path == "/__bridge.js":
                body, ctype = FAKE_BRIDGE.encode(), "text/javascript"
            elif path == "/__test.js":
                body, ctype = (TEST_NATIVE if native else TEST).encode(), "text/javascript"
            elif path in ("/", "/index.html"):
                html = (WEB / "index.html").read_text()
                if native:
                    html = html.replace('<script src="config.js"></script>', '<script src="__bridge.js"></script><script src="config.js"></script>')
                html = html.replace('<div id="app"></div>', '<div id="app"></div><img src="/wait" width="1" height="1" alt="" style="position:absolute"><pre id="report" style="position:fixed;top:0;left:0;right:0;z-index:99;margin:0;padding:8px;background:#000d;color:#fff;font:13px/1.3 monospace;white-space:pre-wrap"></pre>')
                html = html.replace("</body>", '<script src="__test.js"></script></body>')
                body, ctype = html.encode(), "text/html"
            else:
                f = (WEB / path.lstrip("/")).resolve()
                ok = f.is_file() and WEB in f.parents and "tests" not in f.parts
                body, ctype = (f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream")) if ok else (b"", "text/plain")
            self.send_response(200 if body else 404)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    shot = out / f"tadpole_{'demo_' if demo else ''}{'native_' if native else ''}{width}.png"
    prof = tmp / "p"
    prof.mkdir()
    r = subprocess.run(["firefox", "--no-remote", "--profile", str(prof), "--headless", f"--window-size={width},1500", "--screenshot", str(shot), f"http://127.0.0.1:{srv.server_address[1]}/"],
                       capture_output=True, text=True, timeout=150, env={"MOZ_HEADLESS": "1", "PATH": "/usr/bin:/bin", "HOME": str(tmp), "TZ": "America/Toronto"})
    srv.shutdown()
    shutil.rmtree(tmp, ignore_errors=True)
    print(shot if shot.exists() else r.stderr[-600:])


if __name__ == "__main__":
    main()
