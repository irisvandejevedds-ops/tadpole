/* Tadpole, the app. Runs the same in a browser (the demo), and inside the Android app, where storage and syncing go through TadpoleNative.
 * All explanatory text lives in the "i" callouts; the page itself stays quiet. */
(function () {
  'use strict';
  var C = window.TadpoleCore, A = window.TadpoleAssets, store = window.TadpoleStore.create();
  var cfg = window.TADPOLE_CONFIG || {};
  var app = document.getElementById('app');

  var S = store.load();
  var picker = null;           // {mode: 'stool'|'neuro'|'size'|'trig', size, mask}
  var justSaved = null;        // id of the entry just added, for the undo notice
  var diaryDays = 7, notice = '';

  // ---------- helpers ----------
  function el(tag, props) {
    var n = document.createElement(tag);
    if (props) Object.keys(props).forEach(function (k) {
      var v = props[k];
      if (v == null || v === false) return;
      if (k === 'class') n.className = v;
      else if (k === 'text') n.textContent = v;
      else if (k === 'html') n.innerHTML = v;
      else if (k.indexOf('on') === 0) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? '' : v);
    });
    for (var i = 2; i < arguments.length; i++) add(n, arguments[i]);
    return n;
  }
  function add(n, c) { if (c == null || c === false) return; if (Array.isArray(c)) c.forEach(function (x) { add(n, x); }); else n.appendChild(typeof c === 'string' ? document.createTextNode(c) : c); }
  var uidN = 0;
  /** A heading with an "i" button that opens a callout: the only place explanatory text appears. */
  function head(tag, title, info) {
    var id = 'i' + (++uidN), box = document.createDocumentFragment();
    if (!info) { box.appendChild(el(tag, null, title)); return box; }
    box.appendChild(el('input', { type: 'checkbox', id: id, class: 'infotoggle' }));
    box.appendChild(el(tag, null, el('span', null, title), el('label', { for: id, class: 'infobtn', 'aria-label': 'More about this', text: 'i' })));
    box.appendChild(el('div', { class: 'callout', text: info }));
    return box;
  }
  function card(title, info) { var c = el('div', { class: 'card' }); if (title) c.appendChild(head('h3', title, info)); return c; }
  function pixelSvg(rows, colorOf, scale, label) {
    var w = rows[0].length, parts = [];
    rows.forEach(function (row, y) { for (var x = 0; x < row.length; x++) { var c = colorOf(row[x]); if (c) parts.push('<rect x="' + x + '" y="' + y + '" width="1" height="1" fill="' + c + '"/>'); } });
    return '<svg xmlns="http://www.w3.org/2000/svg" width="' + (w * scale) + '" height="' + (rows.length * scale) + '" viewBox="0 0 ' + w + ' ' + rows.length + '" shape-rendering="crispEdges" role="img" aria-label="' + label + '">' + parts.join('') + '</svg>';
  }
  function frogSvg(stage, color, scale) {
    var pal = A.palettes[color] || A.palettes.green;
    return pixelSvg(A.stages[Math.max(0, Math.min(5, stage))], function (ch) { return ch === '.' ? null : pal[ch]; }, scale, 'Tadpole');
  }
  function glyph(name, ink, scale) { return pixelSvg(A.glyphs[name], function (ch) { return ch === 'k' ? ink : null; }, scale, name); }
  function food(i, scale) { return pixelSvg(A.foods[i], function (ch) { return A.foodColors[ch] || null; }, scale, C.FOOD_NAMES[i]); }
  function bowl(level, scale) {
    var rows = []; for (var r = 0; r < 4; r++) rows.push(r >= 4 - level ? '.cccccccc.' : '..........');
    rows.push('kkkkkkkkkk', '.kkkkkkkk.', '..kkkkkk..', '...kkkk...');
    return pixelSvg(rows, function (ch) { return ch === 'c' ? '#C98A3E' : ch === 'k' ? '#1F5E2E' : null; }, scale, 'bowl ' + level);
  }
  function localInput(d) { return C.dayKey(d) + 'T' + (d.getHours() < 10 ? '0' : '') + d.getHours() + ':' + (d.getMinutes() < 10 ? '0' : '') + d.getMinutes(); }
  function chip(e) { return el('span', { class: 'chip ' + e.kind }, C.KIND_WORDS[e.kind] + (e.kind === 'symptom' ? ' ' + (e.severity == null ? '?' : e.severity) : '')); }
  function nowD() { return new Date(); }
  function pondStart() { return S.settings.pond_start || null; }
  function pondState() { return C.state(S.entries, nowD(), pondStart()); }

  // ---------- changing things ----------
  function persist(e) { store.put(e); }
  function afterChange() {
    var st = pondState();
    store.snapshot({ color: st.color, stage: st.stage, stage_name: st.stage_name, control: st.control.label, last_ts: st.last_ts, today_count: st.today_count, to_next: st.growth.to_next });
  }
  function addEntry(e) { S.entries.push(e); persist(e); justSaved = e.id; picker = null; notice = ''; afterChange(); render(); }
  function submitText(text, opts) {
    try { addEntry(C.makeEntry(text, nowD(), opts)); return true; } catch (err) { notice = err.message; render(); return false; }
  }
  function change(id, fn) {
    var e = S.entries.find(function (x) { return x.id === id; });
    if (!e) return;
    fn(e); e.updatedAt = C.iso(nowD()); persist(e); afterChange(); render();
  }
  function setPondStart(v) { S.settings.pond_start = v; store.set('pond_start', v); }

  // ---------- pieces ----------
  function entryRow(e) {
    return el('div', { class: 'entry ' + e.kind }, el('span', { class: 'when', text: C.hhmm(C.parseIso(e.ts)) }), el('span', { class: 'txt', text: e.text }), chip(e));
  }

  var FACTS = [['entry_type', 'Type'], ['phase', 'Phase'], ['fodmap_group', 'FODMAP group'], ['stool_bsfs', 'Bristol'], ['onset_lag_h', 'Onset lag (h)'], ['bloating', 'Bloating'], ['abdo_pain', 'Abdominal pain'],
    ['gas', 'Gas'], ['urgency', 'Urgency'], ['energy', 'Energy'], ['stress', 'Stress'], ['sleep_h', 'Sleep (h)'], ['mood_context', 'Mood context']];
  var NOTES = [['what', 'What'], ['suspected_group', 'Suspected group'], ['symptoms', 'Symptoms'], ['context', 'Context'], ['notes', 'Notes'], ['verbatim', 'Your words']];
  function detailsOf(e) {
    var d = e.details;
    if (typeof d === 'string') { try { d = JSON.parse(d); } catch (x) { d = null; } }
    return d || {};
  }
  function factsList(e) {
    var d = detailsOf(e), dl = el('dl', { class: 'facts' }), any = false;
    FACTS.forEach(function (f) { if (d[f[0]] != null) { any = true; dl.appendChild(el('dt', { text: f[1] })); dl.appendChild(el('dd', { text: String(d[f[0]]) })); } });
    if (d.reconstructed) { any = true; dl.appendChild(el('dt', { text: 'Origin' })); dl.appendChild(el('dd', { text: 'rebuilt from an old spreadsheet; the wording is not your own' })); }
    if (d.time_unknown) { any = true; dl.appendChild(el('dt', { text: 'Time' })); dl.appendChild(el('dd', { text: 'was not recorded; placed just after the previous entry' })); }
    NOTES.forEach(function (f) { if (d[f[0]]) { any = true; dl.appendChild(el('dt', { text: f[1] })); dl.appendChild(el('dd', { class: 'long', text: String(d[f[0]]) })); } });
    return any ? dl : null;
  }

  // ---------- quick pickers (the same ones as the widget) ----------
  function tile(opts) {
    var b = el('button', { type: 'button', class: 'ptile' + (opts.on ? ' on' : ''), style: opts.bg ? 'background:' + opts.bg : null, onclick: opts.click, 'aria-label': opts.label });
    if (opts.icon) b.appendChild(el('span', { class: 'pic', html: opts.icon }));
    if (opts.text) b.appendChild(el('span', { class: 'ptext', text: opts.text }));
    return b;
  }
  function pickerCard() {
    var p = picker, c, grid = el('div', { class: 'pgrid' });
    if (p.mode === 'stool' || p.mode === 'neuro') {
      var isStool = p.mode === 'stool';
      c = card(isStool ? 'Stool quality' : 'Neuroinflammation', isStool ? 'Tap where you are on the Bristol scale. 1 is hard lumps, 3 and 4 are normal, 7 is watery. Green is the healthy middle and both ends are red.' : 'Tap how strong it is, 1 to 7. 1 is barely there, 4 slows you down, 7 means you cannot do your job. It is saved as a symptom.');
      for (var i = 1; i <= 7; i++) (function (n) {
        grid.appendChild(tile({ text: String(n), bg: (isStool ? C.STOOL_COLORS : C.NEURO_COLORS)[n - 1], label: (isStool ? 'Bristol ' : 'Level ') + n, click: function () { addEntry(isStool ? C.stoolEntry(n, nowD()) : C.neuroEntry(n, nowD())); } }));
      })(i);
    } else if (p.mode === 'size') {
      c = card('How big was the meal?', 'Each step is about 500 calories. Next you pick any known FODMAP triggers that were in it.');
      for (var s = 1; s <= 4; s++) (function (n) {
        grid.appendChild(tile({ icon: bowl(n, 5), text: n + '  ~' + C.SIZE_NOTE[n - 1], label: 'Size ' + n, click: function () { picker = { mode: 'trig', size: n, mask: 0 }; render(); } }));
      })(s);
    } else {
      c = card('Known FODMAP triggers in it?', 'Tap each group that was in the meal: wheat, onion or garlic, beans, dairy, apple or honey, mushrooms, stone fruit. Tap Save with none picked if there were none.');
      for (var f = 0; f < 7; f++) (function (k) {
        grid.appendChild(tile({ icon: food(k, 5), text: C.FOOD_NAMES[k], on: !!(p.mask & (1 << k)), label: C.FOOD_NAMES[k], click: function () { p.mask ^= (1 << k); render(); } }));
      })(f);
    }
    c.appendChild(grid);
    var row = el('div', { class: 'row' });
    if (p.mode === 'trig') {
      var n = 0; for (var q = 0; q < 7; q++) if (p.mask & (1 << q)) n++;
      row.appendChild(el('button', { type: 'button', class: 'btn', onclick: function () { addEntry(C.mealEntry(p.size, p.mask, nowD())); } }, n ? 'Save (' + n + ')' : 'Save, none'));
      row.appendChild(el('button', { type: 'button', class: 'btn ghost', onclick: function () { picker = { mode: 'size' }; render(); } }, 'Back'));
    }
    row.appendChild(el('button', { type: 'button', class: 'btn ghost', onclick: function () { picker = null; render(); } }, 'Cancel'));
    c.appendChild(row);
    return c;
  }

  // ---------- pages ----------
  function pondPage() {
    var st = pondState(), g = st.growth, out = el('div');
    out.appendChild(el('section', { class: 'hero' }, el('div', { class: 'stage bob', html: frogSvg(st.stage, st.color, 8) }),
      el('div', { class: 'herotext' }, el('p', { class: 'label', text: st.stage_name }), el('h1', { text: { green: 'Happy', yellow: 'Peckish', red: 'Hungry' }[st.color] }),
        el('p', { text: st.line }), el('p', { class: 'small muted', text: 'Last entry: ' + st.ago }))));

    var form = el('form', { class: 'card', id: 'entry' });
    form.appendChild(head('h3', 'What happened?', 'Type it like a note. Food is the default. Mention a symptom with how bad, like “bloating 6”, and it is kept as one. Words like “pooped a 6” are kept as a stool entry. “No symptoms today” records an all-clear, which also counts as a calm day. The buttons below log common things in two taps.'));
    var input = el('input', { class: 'big-in', type: 'text', name: 'text', maxlength: '400', autocomplete: 'off', autocapitalize: 'sentences', placeholder: 'Oatmeal with banana, coffee', 'aria-label': 'Entry' });
    form.appendChild(input);
    form.appendChild(el('div', { class: 'row' }, el('button', { class: 'btn', type: 'submit' }, 'Add'), el('button', { class: 'btn ghost', type: 'button', onclick: function () { submitText('No symptoms', { kind: 'clear' }); } }, 'No symptoms today')));
    var quick = el('div', { class: 'quick' });
    [['stool', 'Stool', '#E9D5B4', '#4A2E14', 'stool'], ['brain', 'Neuro', '#F8C7B0', '#3A1410', 'neuro'], ['meal', 'Meal', '#F3EFB8', '#3D3510', 'size']].forEach(function (q) {
      quick.appendChild(el('button', { type: 'button', class: 'qbtn', style: 'background:' + q[2], onclick: function () { picker = { mode: q[4] }; render(); } }, el('span', { html: glyph(q[0], q[3], 4) }), el('span', { text: q[1] })));
    });
    form.appendChild(quick);
    form.addEventListener('submit', function (ev) { ev.preventDefault(); submitText(input.value, {}); });
    out.appendChild(form);
    if (notice) out.appendChild(el('div', { class: 'error', text: notice }));
    if (picker) out.appendChild(pickerCard());

    var just = justSaved && S.entries.find(function (e) { return e.id === justSaved && !e.removedAt; });
    if (just) {
      out.appendChild(el('div', { class: 'notice' }, 'Saved as ', el('strong', { text: C.KIND_WORDS[just.kind] + (just.kind === 'symptom' && just.severity != null ? ' ' + just.severity + '/10' : '') }), ': ' + just.text + '. ',
        el('button', { class: 'btn ghost', type: 'button', onclick: function () { justSaved = null; change(just.id, function (e) { e.removedAt = C.iso(nowD()); }); } }, 'Undo'), ' ',
        el('a', { class: 'small', href: '#/diary', onclick: function () { diaryOpen = just.id; } }, 'Change it')));
    }

    var gc = card('Growing up', 'A day with entries and mild symptoms (3 or under) grows it. A middling day (4 to 6) sets it back half a day, a rough day (7 or over) two days. Days with no entries change nothing. Today only counts against it until the day is over. The colour is separate: it goes yellow after about 18 hours without an entry, and red after about 42.');
    gc.appendChild(el('p', { class: 'small', text: g.to_next == null ? 'Fully grown. Keep the symptoms calm and it stays a frog.' : (+g.to_next.toFixed(1)) + ' calm ' + (g.to_next === 1 ? 'day' : 'days') + ' to the next stage, ' + g.stages[g.stage + 1][1] + '.' }));
    gc.appendChild(el('div', { class: 'meter' }, el('i', { style: 'width:' + Math.round(100 * g.stage / (g.stages.length - 1)) + '%' })));
    gc.appendChild(el('p', { class: 'small muted' }, 'Symptoms this week: ', el('strong', { text: st.control.label }),
      st.control.trend ? ', ' + { better: 'better than last week', worse: 'worse than last week', steady: 'about the same as last week' }[st.control.trend] + '.' : '.'));
    out.appendChild(gc);

    var today = C.byDay(S.entries)[C.dayKey(nowD())] || [], tc = card('Today');
    if (today.length) today.slice().reverse().forEach(function (e) { tc.appendChild(entryRow(e)); }); else tc.appendChild(el('p', { class: 'muted', text: 'Nothing written yet today.' }));
    out.appendChild(tc);
    return out;
  }

  var diaryOpen = null;
  function diaryPage() {
    var out = el('div'), days = C.byDay(S.entries), today = C.dayKey(nowD());
    out.appendChild(head('h1', 'The Diary', 'Newest first. Open an entry to fix its words, kind, how bad it was, or when it happened.'));
    for (var i = 0; i < diaryDays; i++) {
      (function (i) {
        var key = C.addDays(today, -i), rows = (days[key] || []).slice().reverse(), sev = rows.length ? C.daySeverity(rows) : null;
        var label = i === 0 ? 'Today' : i === 1 ? 'Yesterday' : C.dayStart(key).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' });
        var c = el('div', { class: 'card' }, el('div', { class: 'cardhead' }, el('h3', { text: label }), sev == null ? null : el('span', { class: 'chip ' + (sev > 3 ? 'symptom' : 'food'), text: sev ? 'worst ' + sev : 'no symptoms' })));
        if (!rows.length) c.appendChild(el('p', { class: 'muted', text: 'Nothing written.' }));
        rows.forEach(function (e) { c.appendChild(editRow(e)); });
        out.appendChild(c);
      })(i);
    }
    out.appendChild(el('p', null, el('button', { class: 'btn ghost', type: 'button', onclick: function () { diaryDays += 14; render(); } }, 'Show earlier days'), ' ',
      el('button', { class: 'btn ghost', type: 'button', onclick: exportCsv }, 'Download everything (CSV)')));
    var removed = S.entries.filter(function (e) { return e.removedAt; }).sort(function (a, b) { return a.removedAt < b.removedAt ? 1 : -1; }).slice(0, 5);
    if (removed.length) {
      var rc = card('Recently removed');
      removed.forEach(function (e) { rc.appendChild(el('div', { class: 'entry' }, el('span', { class: 'txt', text: e.text }), el('button', { class: 'btn ghost', type: 'button', onclick: function () { change(e.id, function (x) { x.removedAt = null; }); } }, 'Put back'))); });
      out.appendChild(rc);
    }
    return out;
  }
  function editRow(e) {
    var d = el('details', { class: 'ed', id: 'e' + e.id });
    if (diaryOpen === e.id) { d.open = true; diaryOpen = null; }
    d.appendChild(el('summary', null, el('span', { class: 'when', text: C.hhmm(C.parseIso(e.ts)) }), ' ', el('span', { class: 'txt', text: e.text }), ' ', chip(e)));
    var f = el('form', { class: 'editform' });
    var words = el('input', { type: 'text', name: 'text', maxlength: '400', value: e.text });
    var kind = el('select', { name: 'kind' }); C.KINDS.forEach(function (k) { kind.appendChild(el('option', { value: k, selected: k === e.kind }, C.KIND_WORDS[k])); });
    var sev = el('select', { name: 'severity' }); sev.appendChild(el('option', { value: '' }, 'not said'));
    for (var n = 0; n <= 10; n++) sev.appendChild(el('option', { value: String(n), selected: e.severity === n }, String(n)));
    var when = el('input', { type: 'datetime-local', name: 'when', value: localInput(C.parseIso(e.ts)) });
    f.appendChild(el('label', { class: 'f' }, 'Words', words));
    f.appendChild(el('div', { class: 'grid2' }, el('label', { class: 'f' }, 'Kind', kind), el('label', { class: 'f' }, 'How bad (symptoms)', sev), el('label', { class: 'f' }, 'When', when)));
    f.appendChild(el('div', { class: 'row' }, el('button', { class: 'btn', type: 'submit' }, 'Save'),
      el('button', { class: 'btn ghost', type: 'button', onclick: function () { change(e.id, function (x) { x.removedAt = C.iso(nowD()); }); } }, 'Remove')));
    f.addEventListener('submit', function (ev) {
      ev.preventDefault();
      var p = C.parse(words.value), k = kind.value;
      change(e.id, function (x) {
        x.text = p.text || words.value.trim().slice(0, 400); x.kind = k;
        x.severity = (k === 'food' || k === 'note' || k === 'stool') ? null : (k === 'clear' ? 0 : (sev.value === '' ? null : Math.max(0, Math.min(10, +sev.value))));
        var t = new Date(when.value); if (!isNaN(t)) x.ts = C.iso(t);
      });
    });
    d.appendChild(f);
    var facts = factsList(e); if (facts) d.appendChild(facts);
    return d;
  }

  function csvCell(v) { v = v == null ? '' : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; }
  function exportCsv() {
    var extra = FACTS.map(function (f) { return f[0]; }).concat(['reconstructed', 'time_unknown'], NOTES.map(function (f) { return f[0]; }));
    var lines = [['date', 'time', 'kind', 'severity', 'text', 'source'].concat(extra).map(csvCell).join(',')];
    C.live(S.entries).forEach(function (e) {
      var t = C.parseIso(e.ts), d = detailsOf(e), p2 = function (n) { return (n < 10 ? '0' : '') + n; };
      lines.push([C.dayKey(t), p2(t.getHours()) + ':' + p2(t.getMinutes()), e.kind, e.severity, e.text, e.source].concat(extra.map(function (k) { return d[k]; })).map(csvCell).join(','));
    });
    var ok = store.saveFile('food-diary.csv', 'text/csv', lines.join('\n') + '\n');
    notice = ok ? '' : 'Could not save the file.'; if (store.native && ok) notice = 'Saved food-diary.csv to your Downloads folder.';
    render();
  }

  function patternsPage() {
    var out = el('div'), days = C.byDay(S.entries), today = C.dayKey(nowD());
    out.appendChild(head('h1', 'Patterns'));
    var c = card('The last 30 days', 'Each bar is that day’s worst symptom out of 10: green is 3 or under, yellow 4 to 6, red 7 or over. A short grey bar means nothing was written that day. Left is a month ago, right is today.');
    var bars = el('div', { class: 'bars' });
    for (var i = 29; i >= 0; i--) {
      var k = C.addDays(today, -i), logged = !!days[k], sev = logged ? C.daySeverity(days[k]) : null;
      bars.appendChild(el('div', { class: 'bar', title: k + ': ' + (logged ? sev : 'nothing written') }, el('i', { class: !logged ? 'none' : sev <= 3 ? 'ok' : sev < 7 ? 'mid' : 'bad', style: 'height:' + (logged ? 8 + sev * 9 : 6) + 'px' })));
    }
    c.appendChild(bars); out.appendChild(c);
    var t = C.triggers(S.entries), tc = card('Foods that came before bad spells', 'Words that showed up in at least three entries, where a symptom of 4 or worse followed within 12 hours more often than usual. This is only a pattern in your own entries, not a diagnosis, and it gets better the more you write. It needs a few weeks of entries, and some bad days, before it can say much. Share it with whoever helps you with this.');
    if (t.items.length) {
      var tb = el('tbody'); t.items.forEach(function (i) { tb.appendChild(el('tr', null, el('td', null, el('strong', { text: i.word })), el('td', { text: String(i.seen) }), el('td', { text: i.followed + ' of ' + i.seen + ' (' + Math.round(100 * i.rate) + '%)' }))); });
      tc.appendChild(el('table', { class: 't' }, el('thead', null, el('tr', null, el('th', null, 'Word'), el('th', null, 'Seen'), el('th', null, 'Followed by symptoms'))), tb));
      tc.appendChild(el('p', { class: 'small muted', text: 'For comparison, ' + Math.round(100 * t.baseline) + '% of all your food entries were followed by a symptom.' }));
    } else tc.appendChild(el('p', { class: 'muted', text: 'Nothing stands out yet.' }));
    out.appendChild(tc);
    out.appendChild(el('p', null, el('button', { class: 'btn ghost', type: 'button', onclick: exportCsv }, 'Download everything (CSV)')));
    return out;
  }

  var openDoc = null;
  function libraryPage() {
    var out = el('div');
    if (openDoc) {
      var d = S.docs.find(function (x) { return x.slug === openDoc; });
      out.appendChild(el('p', null, el('button', { class: 'btn ghost', type: 'button', onclick: function () { openDoc = null; render(); } }, 'Back to the library')));
      var c = el('div', { class: 'card doc' });
      if (d && d.kind === 'md') c.innerHTML = window.TadpoleMd.render(d.body);
      else c.appendChild(el('p', { text: 'This is a PDF. It is kept on your computer; open it from the desktop version.' }));
      out.appendChild(c); return out;
    }
    out.appendChild(head('h1', 'The Library', 'Reference documents kept with the diary, such as a diet protocol or a lab report. They come from your computer when the app is paired with it, and are read-only here.'));
    var lc = el('div', { class: 'card' });
    S.docs.forEach(function (d) { lc.appendChild(el('div', { class: 'entry' }, el('span', { class: 'txt' }, el('a', { href: '#/library', onclick: function (ev) { ev.preventDefault(); openDoc = d.slug; render(); } }, d.title)), el('span', { class: 'chip', text: d.kind === 'pdf' ? 'pdf' : 'note' }))); });
    if (!S.docs.length) lc.appendChild(el('p', { class: 'muted', text: 'Nothing here yet.' }));
    out.appendChild(lc); return out;
  }

  /** Start a sync and watch it: when it finishes, reload what the computer sent. */
  function syncNow() {
    store.sync.now(); notice = 'Syncing…'; render();
    var tries = 0, t = setInterval(function () {
      var st = store.sync.status();
      if (st.running && ++tries < 60) return;
      clearInterval(t); S = store.load(); afterChange();
      notice = st.message ? 'Could not sync: ' + st.message : 'Synced.'; render();
    }, 700);
  }

  function syncWatch() {
    notice = 'Paired. Syncing…'; render();
    var tries = 0, t = setInterval(function () {
      var st = store.sync.status();
      if (st.running && ++tries < 60) return;
      clearInterval(t); S = store.load(); afterChange();
      notice = st.message ? 'Paired, but could not sync yet: ' + st.message : 'Paired and synced.'; render();
    }, 700);
  }

  function settingsPage() {
    var out = el('div');
    out.appendChild(head('h1', 'Settings'));
    var dc = card('Computer', 'Pair this phone with Tadpole on your computer to keep a copy of your diary there, see it on a bigger screen, and bring in documents. On your computer, open Tadpole and scan the pairing code with your phone’s camera app. It works over your home Wi-Fi, and over Tailscale if you use it. Nothing is sent anywhere else, and the app works fine without a computer.');
    if (store.native && store.sync) {
      var s = store.sync.status();
      dc.appendChild(el('p', { text: s.paired ? 'Paired with ' + (s.name || 'your computer') + '.' : 'Not paired.' }));
      if (s.paired) {
        dc.appendChild(el('p', { class: 'small muted', text: (s.last_sync ? 'Last synced ' + s.last_sync + '. ' : 'Not synced yet. ') + (s.message || '') }));
        dc.appendChild(el('div', { class: 'row' }, el('button', { class: 'btn', type: 'button', onclick: syncNow }, s.running ? 'Syncing…' : 'Sync now'),
          el('button', { class: 'btn ghost', type: 'button', onclick: function () { if (confirm('Stop syncing with this computer? Your diary on the phone stays.')) { store.sync.unpair(); render(); } } }, 'Unpair')));
      } else {
        var link = el('input', { type: 'text', placeholder: 'tadpole://pair?…', 'aria-label': 'Pairing link', autocomplete: 'off' });
        dc.appendChild(el('label', { class: 'f' }, 'Or paste the pairing link', link));
        dc.appendChild(el('button', { class: 'btn', type: 'button', onclick: function () { var why = store.sync.pair(link.value); if (why) { notice = why; render(); } else syncWatch(); } }, 'Pair'));
      }
    } else {
      dc.appendChild(el('p', { text: 'This is the browser version. Its diary lives in this browser only and cannot sync.' }));
      dc.appendChild(el('p', { class: 'small muted', text: 'To keep one diary on your phone and your computer, install the Android app and the computer app, then pair them.' }));
      if (cfg.downloadUrl) dc.appendChild(el('a', { class: 'btn', href: cfg.downloadUrl }, 'Get the apps'));
    }
    out.appendChild(dc);
    var data = card('Your data', 'Your diary is stored on this ' + (store.native ? 'phone' : 'browser') + ' only. Download it any time as a spreadsheet file. Deleting removes every entry from here and cannot be undone.');
    data.appendChild(el('div', { class: 'row' }, el('button', { class: 'btn ghost', type: 'button', onclick: exportCsv }, 'Download everything (CSV)'),
      el('button', { class: 'btn warn', type: 'button', onclick: function () { if (confirm('Delete every entry on this ' + (store.native ? 'phone' : 'browser') + '? This cannot be undone.')) { store.deleteAll(); S = store.load(); afterChange(); notice = 'Everything was deleted.'; render(); } } }, 'Delete all')));
    out.appendChild(data);
    if (notice) out.appendChild(el('div', { class: 'notice', text: notice }));
    return out;
  }

  // ---------- shell ----------
  var ROUTES = { '': ['Pond', pondPage], diary: ['Diary', diaryPage], patterns: ['Patterns', patternsPage], library: ['Library', libraryPage], settings: ['Settings', settingsPage] };
  function route() { var r = (location.hash || '#/').replace(/^#\/?/, ''); return ROUTES[r] ? r : ''; }
  function navItems() { return Object.keys(ROUTES).filter(function (k) { return k !== 'library' || S.docs.length; }); }

  function render() {
    var r = route(), page = ROUTES[r][1]();
    var nav = function (cls, label) {
      var n = el('nav', { class: cls, 'aria-label': 'Main' });
      navItems().forEach(function (k) { n.appendChild(el('a', Object.assign({ href: '#/' + k }, k === r ? { 'aria-current': 'page' } : {}), ROUTES[k][0])); });
      return n;
    };
    app.textContent = '';
    if (cfg.demo) app.appendChild(el('div', { class: 'demobar' }, 'Demo: your entries stay in this browser. ', el('a', { href: cfg.downloadUrl || 'index.html' }, 'Get the app')));
    app.appendChild(el('header', { class: 'top' }, el('a', { class: 'brand', href: '#/' }, 'Tadpole'), nav('topnav')));
    app.appendChild(el('main', { class: 'wrap' }, page));
    app.appendChild(nav('tabbar'));
    document.title = 'Tadpole' + (r ? ': ' + ROUTES[r][0].toLowerCase() : '');
    window.scrollTo(0, 0);
  }

  // ---------- start ----------
  function seedDemo() {
    if (!cfg.demo || S.entries.length || store.native) return;
    var now = nowD(), rnd = 7, next = function () { rnd = (rnd * 9301 + 49297) % 233280; return rnd / 233280; };
    var meals = ['Oatmeal with banana, coffee', 'Rice and chicken', 'Toast with eggs', 'Pasta with tomato sauce', 'Yogurt and berries', 'Cheese pizza, 2 slices', 'Salad and soup', 'Banana, handful of almonds'];
    for (var d = 20; d >= 1; d--) {
      var day = new Date(now.getFullYear(), now.getMonth(), now.getDate() - d, 8, 0);
      [8, 13, 19].forEach(function (h) {
        var t = new Date(day.getTime() + (h - 8) * 3600000 + Math.floor(next() * 40) * 60000), e = C.makeEntry(meals[Math.floor(next() * meals.length)], t, { ts: t, source: 'demo' }); S.entries.push(e); store.put(e);
      });
      if (next() < 0.35) { var t2 = new Date(day.getTime() + 15 * 3600000), e2 = C.makeEntry('bloating ' + (2 + Math.floor(next() * 5)), t2, { ts: t2, source: 'demo' }); S.entries.push(e2); store.put(e2); }
    }
  }
  seedDemo();
  // entries the home-screen widget added while the app was closed can arrive as plain text with no kind yet: sort them out now
  S.entries.forEach(function (e) { if (!e.kind) { var p = C.parse(e.text); e.kind = p.kind; e.severity = e.severity == null ? p.severity : e.severity; e.text = p.text || e.text; e.updatedAt = C.iso(nowD()); persist(e); } });
  afterChange();
  window.addEventListener('hashchange', function () { picker = null; notice = ''; render(); });
  document.addEventListener('visibilitychange', function () { if (!document.hidden) { if (store.native) S = store.load(); afterChange(); render(); } });
  setInterval(function () { if (!document.hidden && !picker && document.activeElement && document.activeElement.tagName !== 'INPUT' && document.activeElement.tagName !== 'SELECT') render(); }, 60000);
  window.__tadpole = { S: function () { return S; }, render: render };
  render();
})();
