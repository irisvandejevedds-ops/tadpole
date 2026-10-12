/* Tadpole core: parsing a typed line, the pond rules, and the patterns. One copy of the logic, used by the phone app, the browser demo and
 * the tests. A port of the Python in app/tadpole (diary.py, pond.py); tests/parity.test.js checks the two agree. No DOM, no storage. */
(function (root) {
  'use strict';

  // ---------------- entries ----------------
  var SYMPTOM_WORDS = /bloat|\bgas\b|gassy|cramp|\bpain|ache\b|aches\b|achy|nause|vomit|threw up|reflux|heartburn|indigestion|diarrh|constipat|stomach|tummy|headache|migraine|dizz|fatigue|exhaust|rash|hives|itch|swell|swollen|flare|brain fog|\bsick\b|feel(ing)? (off|bad|awful|terrible|rough|unwell)|\bsymptom|neuro-?inflam\w*|\bfog(gy)?\b|grogg\w*|jitter\w*|\btense\b|hung-?over|hangover|flatulen\w*|\bfart\w*|\burgen(cy|t)\b/i;
  var STOOL_WORDS = /\b(poop(ed|ing|s)?|stools?|bm|bms|bowel movements?|bristol|bsfs)\b/i;
  var STOOL_NUMBER = /\b(poop(ed|ing|s)?|stools?|bm|bms|bowel movements?|bristol|bsfs)\b\W*(\w+\W+){0,2}?[1-7](\s*(-|\/|to)\s*[1-7])?(?![\d:])/ig;
  var BRISTOL = /(?<![\d.:])([1-7])(?:\s*(?:-|\/|to)\s*([1-7]))?(?![\d:])/;
  var CLEAR_WORDS = /\b(no|zero|none|without|not any)\b.{0,12}\bsymptoms?\b|\bsymptom[- ]?free\b|\b(feel(ing)?|felt)\s+(fine|great|good|well|normal)\b|\ball\s+good\b/ig;
  var CLEAR_TEST = /\b(no|zero|none|without|not any)\b.{0,12}\bsymptoms?\b|\bsymptom[- ]?free\b|\b(feel(ing)?|felt)\s+(fine|great|good|well|normal)\b|\ball\s+good\b/i;
  var SEVERITY_WORDS = [[/\b(mild|slight|little|minor|bit of)\b/i, 3], [/\bmoderate\b/i, 5], [/\b(awful|terrible|horrible|worst|excruciating|unbearable)\b/i, 9], [/\b(bad|strong|severe|intense|really|very)\b/i, 7]];
  var OUT_OF_TEN = /(\d{1,2})\s*(?:\/|out of)\s*10/;
  var LONE_NUMBER = /(?<![\d.:\/$])\b(10|\d)\b(?![\d.:%\/])/;
  var PREFIX = /^\s*(food|ate|drank|symptoms?|note|stool|poop|bm|s|f|n)\s*[:\-]\s*/i;
  var KINDS = ['food', 'symptom', 'clear', 'note', 'stool'];
  var KIND_WORDS = { food: 'food', symptom: 'symptom', clear: 'all clear', note: 'note', stool: 'stool' };
  var MAX_TEXT = 400;
  var FORCED = { food: 'food', ate: 'food', drank: 'food', f: 'food', symptom: 'symptom', symptoms: 'symptom', s: 'symptom', note: 'note', n: 'note', stool: 'stool', poop: 'stool', bm: 'stool' };

  function squash(s) { return String(s == null ? '' : s).split(/\s+/).filter(Boolean).join(' ').slice(0, MAX_TEXT); }

  /** -> {kind, severity, text}. A line naming a symptom is a symptom (a number up to 10, or a word like "mild", says how bad); a line saying nothing is wrong is an
   *  all-clear; stool words make a stool entry; anything else is food. "note:", "food:", "symptom:", "stool:" force the kind. */
  function parse(text) {
    var raw = squash(text), forced = null, m = PREFIX.exec(raw);
    if (m) {
      var key = m[1].toLowerCase();
      forced = FORCED[key];
      if (key !== 'ate' && key !== 'drank') raw = raw.slice(m[0].length).trim();
    }
    var kind = forced;
    if (kind === null) {
      var rest = raw.replace(CLEAR_WORDS, '');
      if (CLEAR_TEST.test(raw) && !SYMPTOM_WORDS.test(rest)) kind = 'clear';
      else if (SYMPTOM_WORDS.test(raw)) kind = 'symptom';
      else if (STOOL_WORDS.test(raw)) kind = 'stool';
      else kind = 'food';
    }
    var sev = null;
    if (kind === 'symptom') {
      var scored = raw.replace(STOOL_NUMBER, '');
      var n = OUT_OF_TEN.exec(scored) || ((SYMPTOM_WORDS.test(scored) || forced === 'symptom') ? LONE_NUMBER.exec(scored) : null);
      if (n) sev = Math.max(0, Math.min(10, parseInt(n[1], 10)));
      else for (var i = 0; i < SEVERITY_WORDS.length; i++) if (SEVERITY_WORDS[i][0].test(scored)) { sev = SEVERITY_WORDS[i][1]; break; }
    } else if (kind === 'clear') sev = 0;
    return { kind: kind, severity: sev, text: raw };
  }

  /** The Bristol number in a line ("pooped a 6", "bm 5/6") as "6" or "5-6"; null when there is none. */
  function bristol(text) {
    var m = BRISTOL.exec(text || '');
    if (!m) return null;
    if (!m[2] || m[2] === m[1]) return m[1];
    return [m[1], m[2]].sort().join('-');
  }

  // ---------------- time ----------------
  function iso(d) { return d.toISOString().replace(/\.\d{3}Z$/, 'Z'); }
  function parseIso(s) { return new Date(s); }
  var pad2 = function (n) { return (n < 10 ? '0' : '') + n; };
  /** The calendar day (YYYY-MM-DD) an instant falls on in this device's own timezone. */
  function dayKey(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
  function addDays(key, n) { var p = key.split('-'), d = new Date(Date.UTC(+p[0], +p[1] - 1, +p[2] + n)); return d.getUTCFullYear() + '-' + pad2(d.getUTCMonth() + 1) + '-' + pad2(d.getUTCDate()); }
  function dayStart(key) { var p = key.split('-'); return new Date(+p[0], +p[1] - 1, +p[2], 0, 0, 0, 0); }
  function hhmm(d) { var h = d.getHours(), ap = h >= 12 ? 'pm' : 'am'; h = h % 12 || 12; return h + ':' + pad2(d.getMinutes()) + ' ' + ap; }
  function mealLabel(d) { var h = d.getHours(); return h >= 4 && h < 11 ? 'breakfast' : h >= 11 && h < 15 ? 'lunch' : h >= 15 && h < 17 ? 'snack' : h >= 17 && h < 21 ? 'dinner' : 'late'; }

  function live(entries) { return entries.filter(function (e) { return !e.removedAt; }).sort(function (a, b) { return a.ts < b.ts ? -1 : a.ts > b.ts ? 1 : 0; }); }

  // ---------------- the pond ----------------
  var GREEN_HOURS = 18, YELLOW_HOURS = 42, GOOD = 3, FLARE = 7;
  var STAGES = [[0, 'Tadpole'], [3, 'Back leg buds'], [7, 'Back legs'], [12, 'Four legs'], [18, 'Froglet'], [26, 'Frog']];

  function mood(entries, now) {
    var l = live(entries);
    if (!l.length) return { color: 'green', hours: null };
    var h = (now - parseIso(l[l.length - 1].ts)) / 3600000;
    return { color: h <= GREEN_HOURS ? 'green' : h <= YELLOW_HOURS ? 'yellow' : 'red', hours: h };
  }

  function daySeverity(rows) {
    var sev = 0;
    rows.forEach(function (r) { if (r.kind === 'symptom') sev = Math.max(sev, r.severity == null ? 5 : r.severity); });
    return sev;
  }

  function byDay(entries) {
    var out = {};
    live(entries).forEach(function (e) { var k = dayKey(parseIso(e.ts)); (out[k] = out[k] || []).push(e); });
    return out;
  }

  function growth(entries, todayKey, pondStart) {
    var days = byDay(entries), pts = 0, keys = Object.keys(days).sort();
    if (keys.length) {
      var d = keys[0];
      if (pondStart && pondStart > d) d = pondStart;
      while (d <= todayKey) {
        var rows = days[d];
        if (rows) {
          var sev = daySeverity(rows);
          if (d < todayKey) pts += sev <= GOOD ? 1 : (sev < FLARE ? -0.5 : -2);
          else if (sev >= FLARE) pts -= 2;
          else if (sev > GOOD) pts -= 0.5;
          pts = Math.max(0, pts);
        }
        d = addDays(d, 1);
      }
    }
    var stage = 0;
    STAGES.forEach(function (s, i) { if (pts >= s[0]) stage = i; });
    return { points: pts, stage: stage, name: STAGES[stage][1], to_next: stage + 1 < STAGES.length ? STAGES[stage + 1][0] - pts : null, stages: STAGES };
  }

  function control(entries, todayKey) {
    var days = byDay(entries);
    function week(end) { var out = []; for (var i = 0; i < 7; i++) { var k = addDays(end, -i); if (days[k]) out.push(daySeverity(days[k])); } return out; }
    var avgOf = function (a) { return a.reduce(function (x, y) { return x + y; }, 0) / a.length; };
    var cur = week(todayKey), before = week(addDays(todayKey, -7));
    if (cur.length < 3) return { label: 'not enough yet', key: 'unknown', average: null, logged_days: cur.length, trend: null };
    var avg = avgOf(cur), trend = null;
    if (before.length >= 3) { var prev = avgOf(before); trend = avg <= prev - 0.75 ? 'better' : avg >= prev + 0.75 ? 'worse' : 'steady'; }
    var key = avg <= 2.5 ? 'good' : avg <= 5 ? 'mixed' : 'flaring';
    return { label: { good: 'under control', mixed: 'up and down', flaring: 'flaring' }[key], key: key, average: roundHalfEven(avg, 1), logged_days: cur.length, trend: trend };
  }

  /** Python's round(): ties go to the even digit, so 2.25 -> 2.2 (display only, but it keeps the two apps showing the same number). */
  function roundHalfEven(x, digits) {
    var f = Math.pow(10, digits), r = x * f, fl = Math.floor(r);
    if (Math.abs(r - fl - 0.5) < 1e-9) return (fl % 2 === 0 ? fl : fl + 1) / f;
    return Math.round(r) / f;
  }

  function ago(hours) {
    if (hours == null) return 'nothing written yet';
    if (hours < 1) return Math.max(1, Math.floor(hours * 60)) + ' min ago';
    if (hours < 48) return Math.floor(hours) + ' h ago';
    return Math.floor(hours / 24) + ' days ago';
  }

  /** Everything the pond page and the widget show. now is a Date; pondStart is a YYYY-MM-DD string or null. */
  function state(entries, now, pondStart) {
    var today = dayKey(now), m = mood(entries, now), g = growth(entries, today, pondStart), c = control(entries, today);
    var todays = (byDay(entries)[today] || []);
    var line = { green: 'Content. Keep the entries coming.', yellow: 'Getting peckish. Write something down.', red: 'Hungry for entries. It has been too long.' }[m.color];
    return { color: m.color, hours: m.hours, ago: ago(m.hours), line: line, growth: g, control: c, today_count: todays.length,
             today_food: todays.filter(function (r) { return r.kind === 'food'; }).length, stage: g.stage, stage_name: g.name,
             last_ts: (function () { var l = live(entries); return l.length ? l[l.length - 1].ts : null; })() };
  }

  var STOP = ['and', 'with', 'the', 'some', 'a', 'an', 'of', 'for', 'my', 'had', 'ate', 'drank', 'plus', 'little', 'bit', 'small', 'large', 'big', 'cup', 'glass', 'bowl', 'piece', 'slice', 'side', 'then', 'from', 'home', 'made', 'fresh', 'cooked', 'plain', 'meal', 'size', 'kcal', 'fodmap', 'triggers'];
  function words(text) {
    var out = [], seen = {};
    (String(text || '').toLowerCase().match(/[a-z]{3,}/g) || []).forEach(function (w) { if (STOP.indexOf(w) < 0 && !seen[w]) { seen[w] = 1; out.push(w); } });
    return out;
  }

  /** Foods often followed by a symptom (4 or worse, 30 minutes to 12 hours later). A pattern in your own entries, not a diagnosis. */
  function triggers(entries, windowHours, minSeen) {
    windowHours = windowHours || 12; minSeen = minSeen || 3;
    var rows = live(entries);
    var foods = rows.filter(function (r) { return r.kind === 'food'; }).map(function (r) { return { t: parseIso(r.ts), ws: words(r.text) }; });
    var bad = rows.filter(function (r) { return r.kind === 'symptom' && (r.severity == null ? 5 : r.severity) >= 4; }).map(function (r) { return parseIso(r.ts); });
    if (!foods.length) return { baseline: 0, items: [] };
    var flags = foods.map(function (f) { return bad.some(function (b) { var dh = (b - f.t) / 60000; return dh >= 30 && dh <= windowHours * 60; }); });
    var seen = {}, hit = {};
    foods.forEach(function (f, i) { f.ws.forEach(function (w) { seen[w] = (seen[w] || 0) + 1; hit[w] = (hit[w] || 0) + (flags[i] ? 1 : 0); }); });
    var base = flags.filter(Boolean).length / flags.length, items = [];
    Object.keys(seen).forEach(function (w) { var rate = hit[w] / seen[w]; if (seen[w] >= minSeen && rate >= Math.max(0.5, base + 0.25)) items.push({ word: w, seen: seen[w], followed: hit[w], rate: rate }); });
    items.sort(function (a, b) { return b.rate - a.rate || b.seen - a.seen || (a.word < b.word ? -1 : a.word > b.word ? 1 : 0); });
    return { baseline: base, items: items.slice(0, 12) };
  }

  // ---------------- making entries ----------------
  function uuid() {
    if (root.crypto && root.crypto.randomUUID) return root.crypto.randomUUID();
    var b = new Uint8Array(16); (root.crypto || require('crypto').webcrypto).getRandomValues(b);
    b[6] = (b[6] & 15) | 64; b[8] = (b[8] & 63) | 128;
    var h = Array.prototype.map.call(b, function (x) { return (x < 16 ? '0' : '') + x.toString(16); }).join('');
    return h.slice(0, 8) + '-' + h.slice(8, 12) + '-' + h.slice(12, 16) + '-' + h.slice(16, 20) + '-' + h.slice(20);
  }

  /** Build a new entry from typed text. opts: {ts (Date), kind, severity, source}. Throws "Type something first." on an empty line. */
  function makeEntry(text, now, opts) {
    opts = opts || {};
    var p = parse(text);
    if (opts.kind && KINDS.indexOf(opts.kind) >= 0) { p.kind = opts.kind; if (p.kind === 'clear') p.severity = 0; else if (p.kind !== 'symptom') p.severity = null; }
    if (opts.severity != null && p.kind === 'symptom') p.severity = Math.max(0, Math.min(10, Math.round(opts.severity)));
    if (!p.text && p.kind !== 'clear') throw new Error('Type something first.');
    if (p.kind === 'clear' && !p.text) p.text = 'No symptoms';
    return { id: uuid(), ts: iso(opts.ts || now), kind: p.kind, text: p.text, severity: p.severity, source: opts.source || 'app', details: null, removedAt: null, updatedAt: iso(now) };
  }

  /** The quick pickers: the same wording the widget writes. */
  var STOOL_COLORS = ['#C2452D', '#E9953B', '#8FCB5A', '#4FB85A', '#E3C93F', '#E9953B', '#C2452D'];
  var NEURO_COLORS = ['#4FB85A', '#8FCB5A', '#C9D24A', '#E3C93F', '#E9953B', '#D8663A', '#B33A28'];
  var NEURO_SEVERITY = [1, 3, 4, 6, 7, 9, 10];
  var SIZE_NOTE = ['500', '1000', '1500', '2000'];
  var FOOD_NAMES = ['wheat', 'onion/garlic', 'beans', 'dairy', 'apple/honey', 'mushroom', 'stone fruit'];
  function stoolEntry(n, now) { return makeEntry('Stool, Bristol ' + n, now, { kind: 'stool' }); }
  function neuroEntry(n, now) { return makeEntry('Neuroinflammation ' + n + '/7', now, { kind: 'symptom', severity: NEURO_SEVERITY[n - 1] }); }
  function mealText(size, mask) {
    var names = FOOD_NAMES.filter(function (_, i) { return mask & (1 << i); });
    return 'Meal size ' + size + ' (~' + SIZE_NOTE[size - 1] + ' kcal) - FODMAP triggers: ' + names.length + (names.length ? ' (' + names.join(', ') + ')' : '');
  }
  function mealEntry(size, mask, now) { return makeEntry(mealText(size, mask), now, { kind: 'food' }); }

  var api = { parse: parse, bristol: bristol, iso: iso, parseIso: parseIso, dayKey: dayKey, addDays: addDays, dayStart: dayStart, hhmm: hhmm, mealLabel: mealLabel, live: live,
    mood: mood, daySeverity: daySeverity, byDay: byDay, growth: growth, control: control, ago: ago, state: state, words: words, triggers: triggers, uuid: uuid, makeEntry: makeEntry,
    stoolEntry: stoolEntry, neuroEntry: neuroEntry, mealEntry: mealEntry, mealText: mealText, KINDS: KINDS, KIND_WORDS: KIND_WORDS, STAGES: STAGES,
    STOOL_COLORS: STOOL_COLORS, NEURO_COLORS: NEURO_COLORS, NEURO_SEVERITY: NEURO_SEVERITY, SIZE_NOTE: SIZE_NOTE, FOOD_NAMES: FOOD_NAMES, GREEN_HOURS: GREEN_HOURS, YELLOW_HOURS: YELLOW_HOURS };
  if (typeof module !== 'undefined' && module.exports) module.exports = api; else root.TadpoleCore = api;
})(typeof window !== 'undefined' ? window : globalThis);
