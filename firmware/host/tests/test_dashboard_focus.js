// Exercise the real dashboard renderer with a synthetic sensor snapshot.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '../dashboard/index.html'), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)[1];
let clock = 10000;
const elements = new Map();
const context = new Proxy({}, {
  get: (_target, key) => {
    if (key === 'createImageData') return () => ({data: new Uint8ClampedArray(32 * 24 * 4)});
    if (key === 'createLinearGradient' || key === 'createRadialGradient') return () => ({addColorStop() {}});
    if (key === 'measureText') return () => ({width: 0});
    return () => {};
  },
});
function element(id) {
  if (!elements.has(id)) elements.set(id, {
    innerHTML: '', textContent: '', className: '', style: {}, width: 640, height: 420,
    classList: {add() {}, toggle() {}}, getContext: () => context,
    getBoundingClientRect: () => ({width: 640, height: 420}), addEventListener() {},
  });
  return elements.get(id);
}
const intervals = [];
const streams = [];
const sandbox = {
  console, Math, Date: {now: () => clock}, devicePixelRatio: 1,
  document: {getElementById: element, createElement: () => element('offscreen'),
    querySelectorAll: () => [], documentElement: element('root'), body: element('body')},
  getComputedStyle: () => ({getPropertyValue: () => '#000'}),
  setInterval: fn => intervals.push(fn), EventSource: function () {streams.push(this);},
  window: {devicePixelRatio: 1, addEventListener() {}}, requestAnimationFrame() {},
  fetch: () => Promise.resolve({json: () => Promise.resolve({})}),
};
vm.runInNewContext(script, sandbox);

const live = {
  simulated: false, source: '/dev/test',
  health: {thermal: {status: 'ok', hz: 8}, radar: {status: 'ok', hz: 25},
    csi: {status: 'offline', hz: 0}, ambient: {status: 'ok', hz: 2}},
  stats: {frames_ok: 42, crc_errors: 0},
  thermal: {pixels: Array(768).fill(30), min: 20, max: 35, blob: null},
  radar: {presence: true, distance_m: 0.8, heart_rate_bpm: 72, respiration_rpm: 16},
  body: {position: {position: 'upright'}, surface_temp: {estimate_f: 94.2, site: 'neck region', note: 'Neck-region surface; skin unverified; not core temperature'}},
  fusion: {verdict: 'person', distance_m: 0.8, bearing_deg: 0},
  vitals: {heart_rate_bpm: 72, respiration_rpm: 16, heart_source: 'radar', respiration_source: 'radar',
    heart_reason: 'current', respiration_reason: 'current', estimate: {
      heart_rate_bpm: {value: 70, low: 68, high: 72, spread: 4, age_s: 0, stale: false},
      respiration_rpm: {value: 15, low: 14, high: 16, spread: 2, age_s: 0, stale: false},
    }, disagreements: []},
  csi: null, ambient: null,
  posture_events: [{detail: 'old alert', notified: true, limitations: []}],
};
streams[0].onmessage({data: JSON.stringify(live)});
assert.match(element('hudHeart').textContent, /70/);
assert.match(element('hudBreath').textContent, /15/);
assert.match(element('hudTemp').textContent, /94\.2/);
assert.match(element('hudPosition').textContent, /upright/i);
assert.match(element('hudTempNote').textContent, /neck-region surface; skin unverified/i);
assert.match(element('sHead').textContent, /neck-region surface; skin unverified/i);
assert.match(element('vHr').innerHTML, /70/);
assert.match(element('vResp').innerHTML, /15/);
assert.doesNotMatch(html, /id="vAbn"|id="postureEvents"/);
assert.doesNotMatch(html, /id="conflict"|Suspect reading|The two instruments disagree/);

const unconfirmed = JSON.parse(JSON.stringify(live));
unconfirmed.radar.presence = null;
unconfirmed.radar.distance_m = null;
streams[0].onmessage({data: JSON.stringify(unconfirmed)});
assert.match(element('hudTemp').textContent, /not available/i);
assert.match(element('vHead').innerHTML, /not available/i);

const unavailable = JSON.parse(JSON.stringify(live));
unavailable.vitals.estimate = {};
unavailable.body = null;
streams[0].onmessage({data: JSON.stringify(unavailable)});
for (const id of ['hudHeart', 'hudBreath', 'hudTemp', 'hudPosition'])
  assert.match(element(id).textContent, /not available/i, `${id} must not retain an old reading`);

clock += 5000;
for (const tick of intervals) tick();
for (const id of ['hudHeart', 'hudBreath', 'hudTemp', 'hudPosition'])
  assert.match(element(id).textContent, /not available/i, `${id} must clear when the stream stops`);
console.log('PASS: dashboard HUD shows gated estimates and clears unavailable readings');
