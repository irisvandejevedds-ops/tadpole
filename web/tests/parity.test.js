// Replays parity.json (made by the Python rules) through core.js. Run with TZ=America/Toronto.
const test = require('node:test');
const assert = require('node:assert');
const C = require('../core.js');
const data = require('./parity.json');

test('timezone is the one the fixtures were made in', () => {
  assert.equal(new Date('2026-10-11T12:00:00Z').getTimezoneOffset(), 240, 'run with TZ=America/Toronto');
});

test('parse and bristol agree with Python on every phrase', () => {
  let bad = [];
  for (const c of data.parse) {
    const p = C.parse(c.text);
    if (p.kind !== c.kind || p.severity !== c.severity || p.text !== c.out || C.bristol(c.text) !== c.bristol) bad.push({ text: c.text, js: p, py: c });
  }
  assert.deepEqual(bad.slice(0, 5), [], bad.length + ' of ' + data.parse.length + ' differ');
});

const near = (a, b) => (a === null || b === null) ? a === b : Math.abs(a - b) < 1e-6;

data.scenarios.forEach((s, i) => test('pond rules agree with Python in scenario ' + i, () => {
  const entries = s.entries.map((e, k) => ({ id: 'e' + k, ts: e.ts, kind: e.kind, text: e.text, severity: e.severity, removedAt: e.removed ? e.ts : null }));
  for (const c of s.checks) {
    const st = C.state(entries, new Date(c.now), c.pond_start), where = ' at ' + c.now + ' start ' + c.pond_start;
    assert.equal(st.color, c.color, 'color' + where);
    assert.ok(near(st.hours, c.hours), 'hours' + where);
    assert.equal(st.stage, c.stage, 'stage' + where);
    assert.ok(near(st.growth.points, c.points), 'points ' + st.growth.points + ' vs ' + c.points + where);
    assert.ok(near(st.growth.to_next, c.to_next), 'to_next' + where);
    assert.equal(st.control.label, c.control.label, 'control label' + where);
    assert.equal(st.control.logged_days, c.control.logged_days, 'logged days' + where);
    assert.equal(st.control.trend, c.control.trend, 'trend' + where);
    assert.ok(near(st.control.average, c.control.average), 'average' + where);
    assert.equal(st.today_count, c.today_count); assert.equal(st.today_food, c.today_food); assert.equal(st.ago, c.ago, 'ago' + where);
    const tr = C.triggers(entries);
    assert.ok(near(tr.baseline, c.triggers.baseline), 'baseline');
    assert.deepEqual(tr.items.map(x => [x.word, x.seen, x.followed]), c.triggers.items.map(x => [x.word, x.seen, x.followed]), 'trigger items');
  }
}));
