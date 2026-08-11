/* The Reserve Currency Map — vanilla JS, no dependencies.
 *
 * Two charts that deliberately do not join: a map of who holds reserves, and a
 * stacked area of what currency the world's reserves are in. See the "cannot be
 * joined" section in index.html for why there is no third chart connecting them.
 */

/* The projection, the SVG helper and the basemap come from projection.js,
 * which both pages share. */

'use strict';

/* ── small helpers ────────────────────────────────────────────────── */

const el = (id) => document.getElementById(id);

function money(bn) {
  if (bn === null || bn === undefined) return '—';
  if (Math.abs(bn) >= 1000) return '$' + (bn / 1000).toFixed(2) + 'tn';
  if (Math.abs(bn) >= 1) return '$' + Math.round(bn).toLocaleString() + 'bn';
  return '$' + (bn * 1000).toFixed(0) + 'm';
}

function coord(lon, lat) {
  const ns = lat >= 0 ? 'N' : 'S';
  const ew = lon >= 0 ? 'E' : 'W';
  return `${Math.abs(lat).toFixed(1)}°${ns}, ${Math.abs(lon).toFixed(1)}°${ew}`;
}

/* Longitude of the reserve centroid, unwrapped so the readout can talk about
 * total movement east without a 360° jump if it ever crosses the antimeridian. */
function eastward(track, from, to) {
  let sum = 0;
  for (let i = from + 1; i <= to; i++) {
    if (!track[i] || !track[i - 1]) continue;
    let d = track[i][0] - track[i - 1][0];
    if (d > 180) d -= 360;
    if (d < -180) d += 360;
    sum += d;
  }
  return sum;
}

/* ── state ────────────────────────────────────────────────────────── */

const state = { year: 2024, measure: 'total', view: 'world', playing: false, timer: null };
let W = null;   // world.json
let H = null;   // holders.json
let C = null;   // cofer.json
let bubbleIndex = [];   // {cx, cy, r, country, value} for nearest-point hover
let sizeScale = 1;

/* ── map ──────────────────────────────────────────────────────────── */

function measureValue(country, yearIndex) {
  const total = country.total[yearIndex];
  const gold = country.gold[yearIndex];
  if (state.measure === 'total') return total;
  if (state.measure === 'gold') return gold;
  if (total === null || total === undefined) return null;
  if (gold === null || gold === undefined) return null;
  return total - gold;
}

/* One radius scale for every year, so the animation shows the tenfold growth in
 * world reserves rather than renormalising it away. Area is proportional to
 * value; radius therefore goes as the square root. */
function computeSizeScale() {
  let max = 0;
  for (const c of H.countries) {
    for (let i = 0; i < H.years.length; i++) {
      const v = measureValue(c, i);
      if (v && v > max) max = v;
    }
  }
  sizeScale = max > 0 ? 15 / Math.sqrt(max) : 1;
  return max;
}

function drawBubbles() {
  const g = el('bubbles');
  g.textContent = '';
  bubbleIndex = [];
  const yi = H.years.indexOf(state.year);

  const rows = [];
  for (const c of H.countries) {
    const v = measureValue(c, yi);
    if (!v || v <= 0) continue;
    rows.push({ c, v });
  }
  // Largest first so small circles land on top and stay clickable.
  rows.sort((a, b) => b.v - a.v);

  for (const { c, v } of rows) {
    const [cx, cy] = project(c.c[0], c.c[1]);
    const r = Math.max(0.6, Math.sqrt(v) * sizeScale);
    const node = svg('circle', { cx, cy, r, class: 'bubble', 'data-id': c.id }, g);
    bubbleIndex.push({ cx, cy, r, country: c, value: v, node });
  }
  return rows;
}

/* Label placement only, and only for the whole-globe view — London, Frankfurt
 * and Bern are within eleven units of each other there, and so are Washington
 * and Ottawa, which the pole aspect stacks along one ray instead of one above
 * the other. Note which side each label sits on: east runs anticlockwise here,
 * so Frankfurt is to the *left* of London. Zoomed in, nothing collides and a
 * plain label above the mark is better. Purely presentational; the positions
 * themselves come from the data file. */
const ISSUER_LABEL = {
  USD: { dx: 4.6, dy: 2.4, anchor: 'start' },
  CAD: { dx: -4.6, dy: -2.6, anchor: 'end' },
  GBP: { dx: 4.6, dy: 1.9, anchor: 'start' },
  EUR: { dx: -4.8, dy: 2.2, anchor: 'end' },
  CHF: { dx: -4.8, dy: -2.2, anchor: 'end' },
  CNY: { dx: 0, dy: 9.2, anchor: 'middle' },
  JPY: { dx: -5.5, dy: 3.4, anchor: 'end' },
  AUD: { dx: 0, dy: 8.4, anchor: 'middle' },
};
const ISSUER_LABEL_PLAIN = { dx: 0, dy: -5.2, anchor: 'middle' };

function drawIssuers() {
  const g = el('issuers');
  g.textContent = '';
  for (const iss of H.issuers) {
    const [x, y] = project(iss.c[0], iss.c[1]);
    svg('rect', {
      x: x - 2.6, y: y - 2.6, width: 5.2, height: 5.2,
      transform: `rotate(45 ${x} ${y})`, class: 'issuer',
    }, g);
    const off = (state.view === 'world' && ISSUER_LABEL[iss.code]) || ISSUER_LABEL_PLAIN;
    const t = svg('text', {
      x: x + off.dx, y: y + off.dy, class: 'issuer-label', 'text-anchor': off.anchor,
    }, g);
    t.textContent = iss.code;
    const title = svg('title', {}, t);
    title.textContent = `${iss.name} — ${iss.authority}`;
  }
}

function drawTrack() {
  const past = [];
  const future = [];
  const yi = H.years.indexOf(state.year);
  H.track.forEach((p, i) => {
    if (!p) return;
    const xy = project(p[0], p[1]);
    if (i <= yi) past.push(xy);
    if (i >= yi) future.push(xy);
  });

  const g = el('track-line');
  g.textContent = '';
  if (future.length > 1) {
    svg('path', { d: 'M' + future.map((p) => p.join(' ')).join('L'), class: 'track future' }, g);
  }
  if (past.length > 1) {
    svg('path', { d: 'M' + past.map((p) => p.join(' ')).join('L'), class: 'track past' }, g);
  }

  const head = el('track-head');
  head.textContent = '';
  const now = H.track[yi];
  if (now) {
    const [x, y] = project(now[0], now[1]);
    svg('circle', { cx: x, cy: y, r: 2.6, class: 'track-dot' }, head);
    const label = svg('text', { x, y: y + 9.5, class: 'track-label', 'text-anchor': 'middle' }, head);
    label.textContent = state.year;
  }
}

/* Nearest-point hover. A world map has circles a fraction of a pixel apart in
 * western Europe; per-mark hit targets cannot meet a 24px minimum there, so the
 * whole plot is one target and the nearest mark wins. */
function initHover() {
  const map = el('map');
  const tip = el('tip');
  let hot = null;

  function clear() {
    if (hot) { hot.node.classList.remove('is-hot'); hot = null; }
    tip.hidden = true;
  }

  map.addEventListener('pointermove', (ev) => {
    const box = map.getBoundingClientRect();
    if (!box.width) return;
    const vb = map.viewBox.baseVal;
    const sx = vb.x + ((ev.clientX - box.left) / box.width) * vb.width;
    const sy = vb.y + ((ev.clientY - box.top) / box.height) * vb.height;

    let best = null;
    let bestD = Infinity;
    for (const b of bubbleIndex) {
      const d = Math.hypot(b.cx - sx, b.cy - sy);
      // inside the circle always wins; otherwise nearest within a small radius
      const score = d <= b.r ? d - b.r : d;
      if (score < bestD) { bestD = score; best = b; }
    }
    if (!best || bestD > 6) { clear(); return; }

    if (hot !== best) {
      if (hot) hot.node.classList.remove('is-hot');
      hot = best;
      hot.node.classList.add('is-hot');
    }

    const yi = H.years.indexOf(state.year);
    const total = best.country.total[yi];
    const gold = best.country.gold[yi];
    tip.innerHTML =
      `<b>${best.country.name}</b>` +
      `<div class="row"><span>All reserves</span><span>${money(total)}</span></div>` +
      (gold !== null && gold !== undefined
        ? `<div class="row"><span>of which gold</span><span>${money(gold)}</span></div>`
        : '') +
      `<div class="row"><span>Share of world</span><span>${sharePct(best.value)}</span></div>`;

    // Position against the figure, not offsetParent: a hidden element has no
    // offsetParent, so reading it here throws before the tooltip is ever shown.
    const px = box.left + ((best.cx - vb.x) / vb.width) * box.width;
    const py = box.top + ((best.cy - vb.y) / vb.height) * box.height;
    const wrapBox = tip.parentElement.getBoundingClientRect();
    tip.hidden = false;
    tip.style.left = (px - wrapBox.left) + 'px';
    tip.style.top = (py - wrapBox.top - best.r * (box.height / vb.height) - 8) + 'px';
  });

  map.addEventListener('pointerleave', clear);
}

function sharePct(v) {
  const yi = H.years.indexOf(state.year);
  let sum = 0;
  for (const c of H.countries) {
    const x = measureValue(c, yi);
    if (x) sum += x;
  }
  return sum > 0 ? (v / sum * 100).toFixed(1) + '%' : '—';
}

/* Nested circles sharing a baseline, each with a leader to its own label. The
 * three marks are far enough apart in radius that their labels never collide;
 * the caption is HTML beside the figure rather than text inside it, which is
 * what made the two overlap. */
function drawSizeLegend() {
  const host = el('size-legend');
  host.textContent = '';

  const cap = document.createElement('span');
  cap.className = 'legend-cap';
  // Zoomed in, say so: the circles are not rescaled to the region, which is
  // what makes a European circle comparable with the Chinese one off-frame.
  cap.textContent = state.view === 'world'
    ? 'Circle area ∝ reserves'
    : 'Circle area ∝ reserves, on the same world scale as the whole globe';
  host.appendChild(cap);

  const marks = [100, 1000, 3000];
  const rs = marks.map((m) => Math.max(1.2, Math.sqrt(m) * sizeScale));
  const maxR = rs[rs.length - 1];
  const pad = 2;
  const labelX = maxR * 2 + 12;
  const width = labelX + 36;
  const height = maxR * 2 + pad * 2;
  // The globe renders 430 viewBox units across an 820px cap — 1.9 pixels per
  // unit at a desktop width — so drawing the legend at that same ratio keeps
  // these circles the size the map would actually draw them.
  const scale = 1.9;

  const s = svg('svg', {
    viewBox: `0 0 ${width} ${height}`,
    width: (width * scale).toFixed(0), height: (height * scale).toFixed(0),
    role: 'img', 'aria-label':
      'Legend: circle area is proportional to reserves held, shown at 100 billion, 1 trillion and 3 trillion dollars',
  }, host);

  marks.forEach((m, i) => {
    const r = rs[i];
    const cy = height - pad - r;
    svg('circle', {
      cx: maxR + pad, cy, r,
      fill: 'none', stroke: 'var(--bubble)', 'stroke-width': 0.6, opacity: 0.8,
    }, s);
    const topY = cy - r;
    svg('line', {
      x1: maxR + pad, y1: topY, x2: labelX - 2, y2: topY,
      stroke: 'var(--axis)', 'stroke-width': 0.3, 'stroke-dasharray': '1 1',
    }, s);
    const t = svg('text', { x: labelX, y: topY + 1.8 }, s);
    t.textContent = money(m);
  });
}

/* ── readout + table ──────────────────────────────────────────────── */

function updateReadout(rows) {
  const yi = H.years.indexOf(state.year);
  const [n] = H.coverage[yi];
  const total = rows.reduce((a, r) => a + r.v, 0);
  const top = rows[0];
  const here = H.track[yi];
  const moved = eastward(H.track, 0, yi);

  const label = { total: 'Reserves held', fx: 'Foreign exchange', gold: 'Gold at market' }[state.measure];

  el('readout').innerHTML = `
    <dl class="stat"><dt>${label}, ${state.year}</dt>
      <dd>${money(total)}<span class="sub">${n} reporting countries</span></dd></dl>
    <dl class="stat"><dt>Largest holder</dt>
      <dd>${top ? top.c.name : '—'}<span class="sub">${top ? money(top.v) + ' · ' + (top.v / total * 100).toFixed(1) + '% of world' : ''}</span></dd></dl>
    <dl class="stat"><dt>Centre of gravity</dt>
      <dd>${here ? coord(here[0], here[1]) : '—'}<span class="sub">${moved >= 0 ? moved.toFixed(0) + '° east' : Math.abs(moved).toFixed(0) + '° west'} of its 1960 position</span></dd></dl>`;

  const rowsHtml = rows.slice(0, 15).map((r, i) => {
    const gold = r.c.gold[yi];
    return `<tr><td class="n">${i + 1}</td><td>${r.c.name}</td>` +
      `<td class="n">${money(r.v)}</td>` +
      `<td class="n">${(r.v / total * 100).toFixed(1)}%</td>` +
      `<td class="n">${gold ? money(gold) : '—'}</td></tr>`;
  }).join('');
  el('holders-table').innerHTML =
    `<thead><tr><th class="n">#</th><th>Country</th><th class="n">${label}</th>` +
    `<th class="n">Share</th><th class="n">Gold</th></tr></thead><tbody>${rowsHtml}</tbody>`;
}

/* ── COFER stacked area ───────────────────────────────────────────── */

const SERIES = [
  { code: 'USD', label: 'US dollar', parts: ['USD'] },
  { code: 'EUR', label: 'Euro', parts: ['EUR', 'DEM', 'FRF', 'NLG', 'ECU'],
    note: 'and its predecessor currencies before 1999' },
  { code: 'JPY', label: 'Japanese yen', parts: ['JPY'] },
  { code: 'GBP', label: 'Pound sterling', parts: ['GBP'] },
  { code: 'CNY', label: 'Renminbi', parts: ['CNY'] },
  { code: 'CAD', label: 'Canadian dollar', parts: ['CAD'] },
  { code: 'AUD', label: 'Australian dollar', parts: ['AUD'] },
  { code: 'OTH', label: 'Swiss franc and other', parts: ['CHF', 'OTH'] },
];

function coferSeries() {
  const byCode = {};
  for (const c of C.currencies) byCode[c.code] = c;
  return SERIES.map((s) => ({
    ...s,
    values: C.periods.map((_, i) => {
      let sum = 0;
      let any = false;
      for (const p of s.parts) {
        const v = byCode[p] && byCode[p].share[i];
        if (v !== null && v !== undefined) { sum += v; any = true; }
      }
      return any ? sum : 0;
    }),
  }));
}

function periodYear(p) { return parseInt(p.slice(0, 4), 10); }

function drawCofer() {
  const s = el('cofer');
  s.textContent = '';
  const w = 900, h = 440;
  // The top margin is deep enough to hold the two annotation labels outside the
  // stack — there is no white space inside a chart that always sums to 100%.
  const m = { top: 46, right: 100, bottom: 46, left: 58 };
  const pw = w - m.left - m.right;
  const ph = h - m.top - m.bottom;

  const series = coferSeries();
  const n = C.periods.length;
  const x = (i) => m.left + (n === 1 ? 0 : (i / (n - 1)) * pw);
  const y = (v) => m.top + ph - (v / 100) * ph;

  // gridlines + y axis
  for (let v = 0; v <= 100; v += 20) {
    svg('line', { x1: m.left, x2: m.left + pw, y1: y(v), y2: y(v), class: v === 0 ? 'ax-line' : 'ax-grid' }, s);
    const t = svg('text', { x: m.left - 8, y: y(v) + 4, class: 'ax-text', 'text-anchor': 'end' }, s);
    t.textContent = v + '%';
  }

  const yt = svg('text', {
    x: 6, y: m.top + ph / 2, class: 'ax-title',
    'text-anchor': 'middle', transform: `rotate(-90 6 ${m.top + ph / 2})`,
  }, s);
  yt.textContent = 'Share of world allocated reserves';

  // x axis: a tick every five years
  const seen = new Set();
  C.periods.forEach((p, i) => {
    const yr = periodYear(p);
    if (yr % 5 !== 0 || seen.has(yr)) return;
    seen.add(yr);
    svg('line', { x1: x(i), x2: x(i), y1: m.top + ph, y2: m.top + ph + 5, class: 'ax-line' }, s);
    const t = svg('text', { x: x(i), y: m.top + ph + 19, class: 'ax-text', 'text-anchor': 'middle' }, s);
    t.textContent = yr;
  });

  // stacked bands, drawn top-down so the 2px surface stroke separates them
  const cum = new Array(n).fill(0);
  const tops = [];
  for (const ser of series) {
    const lower = cum.slice();
    for (let i = 0; i < n; i++) cum[i] += ser.values[i];
    tops.push(cum.slice());
    let d = 'M' + x(0) + ' ' + y(cum[0]);
    for (let i = 1; i < n; i++) d += 'L' + x(i) + ' ' + y(cum[i]);
    for (let i = n - 1; i >= 0; i--) d += 'L' + x(i) + ' ' + y(lower[i]);
    svg('path', { d: d + 'Z', class: 'band f-' + ser.code }, s);
    ser._top = tops[tops.length - 1];
    ser._bottom = lower;
  }

  // selective direct labels: the two bands big enough to hold one
  for (const ser of series) {
    const last = n - 1;
    const height = ser._top[last] - ser._bottom[last];
    if (height < 12) continue;
    const t = svg('text', {
      x: m.left + pw + 8,
      y: y((ser._top[last] + ser._bottom[last]) / 2) + 4,
      class: 'band-label',
    }, s);
    t.textContent = `${ser.label} ${ser.values[last].toFixed(0)}%`;
  }

  // Annotations for the two dataset changes a reader would otherwise misread as
  // events in the world rather than in the measurement. They sit over the busiest
  // part of the stack, so each carries a surface halo (see .annot-text).
  const annot = [
    { period: C.first_quarterly, text: 'euro replaces DEM, FRF, NLG, ECU', row: 0 },
    { period: firstPeriodWith('CNY'), text: 'renminbi identified separately', row: 1 },
  ];
  for (const a of annot) {
    const i = C.periods.indexOf(a.period);
    if (i < 0) continue;
    const ty = 14 + a.row * 15;
    svg('line', { x1: x(i), x2: x(i), y1: ty + 4, y2: m.top + ph, class: 'annot' }, s);
    // Flip the label to the left of its rule if it would run past the plot.
    const right = (m.left + pw - x(i)) > a.text.length * 5.4 + 12;
    const t = svg('text', {
      x: x(i) + (right ? 6 : -6),
      y: ty,
      class: 'annot-text',
      'text-anchor': right ? 'start' : 'end',
    }, s);
    t.textContent = a.text;
  }

  buildCoferLegend(series);
  buildCoferTable(series);
  initCoferHover(s, series, x, y, m, pw, ph);
}

function firstPeriodWith(code) {
  const c = C.currencies.find((x) => x.code === code);
  if (!c) return null;
  const i = c.share.findIndex((v) => v !== null && v !== undefined);
  return i < 0 ? null : C.periods[i];
}

function buildCoferLegend(series) {
  el('cofer-legend').innerHTML = series.map((s) =>
    `<span class="key"><span class="chip c-${s.code}"></span>${s.label}` +
    (s.note ? ` <span style="color:var(--ink-muted)">${s.note}</span>` : '') +
    `</span>`).join('');
}

function buildCoferTable(series) {
  // One row per year — the Q4 reading, or the last quarter available.
  const rowsByYear = new Map();
  C.periods.forEach((p, i) => rowsByYear.set(periodYear(p), i));
  const years = [...rowsByYear.keys()].sort((a, b) => a - b);
  const head = `<thead><tr><th>Year</th>${series.map((s) =>
    `<th class="n">${s.code}</th>`).join('')}</tr></thead>`;
  const body = years.map((yr) => {
    const i = rowsByYear.get(yr);
    return `<tr><td>${C.periods[i]}</td>${series.map((s) =>
      `<td class="n">${s.values[i] ? s.values[i].toFixed(1) : '—'}</td>`).join('')}</tr>`;
  }).join('');
  el('cofer-table').innerHTML = head + `<tbody>${body}</tbody>`;
}

function initCoferHover(s, series, x, y, m, pw, ph) {
  const tip = el('cofer-tip');
  const cross = svg('line', { class: 'crosshair', y1: m.top, y2: m.top + ph, opacity: 0 }, s);
  const hit = svg('rect', {
    x: m.left, y: m.top, width: pw, height: ph, fill: 'transparent',
  }, s);

  hit.addEventListener('pointermove', (ev) => {
    const box = s.getBoundingClientRect();
    const vb = s.viewBox.baseVal;
    const sx = vb.x + ((ev.clientX - box.left) / box.width) * vb.width;
    const i = Math.max(0, Math.min(C.periods.length - 1,
      Math.round(((sx - m.left) / pw) * (C.periods.length - 1))));

    cross.setAttribute('x1', x(i));
    cross.setAttribute('x2', x(i));
    cross.setAttribute('opacity', 1);

    tip.innerHTML = `<b>${C.periods[i]}</b>` + series
      .filter((ser) => ser.values[i] > 0)
      .sort((a, b) => b.values[i] - a.values[i])
      .map((ser) => `<div class="row"><span>${ser.label}</span><span>${ser.values[i].toFixed(1)}%</span></div>`)
      .join('');

    const wrapBox = tip.parentElement.getBoundingClientRect();
    const px = box.left + ((x(i) - vb.x) / vb.width) * box.width;
    tip.hidden = false;
    tip.style.left = Math.max(90, px - wrapBox.left) + 'px';
    tip.style.top = (box.top - wrapBox.top + 12) + 'px';
    tip.style.transform = 'translate(-50%, 0)';
  });

  hit.addEventListener('pointerleave', () => {
    cross.setAttribute('opacity', 0);
    tip.hidden = true;
  });
}

/* ── wiring ───────────────────────────────────────────────────────── */

/* Everything that moves when the view changes. The legend circles do not
 * resize — they carry values, and a zoom is a camera move — but their caption
 * changes to say so. */
function redrawMap() {
  drawBasemap(el('graticule'), el('land'), W);
  drawIssuers();
  drawSizeLegend();
  render();
}

function render() {
  el('year-out').textContent = state.year;
  el('year').value = state.year;

  const yi = H.years.indexOf(state.year);
  const [n] = H.coverage[yi];
  const partial = state.year > H.complete_through;
  el('provisional').hidden = !partial;
  if (partial) el('prov-count').textContent = n;

  const rows = drawBubbles();
  drawTrack();
  updateReadout(rows);
}

function play() {
  const btn = el('play');
  if (state.playing) {
    clearInterval(state.timer);
    state.playing = false;
    btn.dataset.state = '';
    el('play-label').textContent = 'Play';
    return;
  }
  state.playing = true;
  btn.dataset.state = 'playing';
  el('play-label').textContent = 'Pause';
  if (state.year >= H.complete_through) state.year = H.years[0];
  state.timer = setInterval(() => {
    state.year += 1;
    if (state.year > H.complete_through) { state.year = H.complete_through; play(); }
    render();
  }, 190);
}

function fillSourceCells() {
  el('src-cofer').textContent =
    `${C.periods[0]} to ${C.periods[C.periods.length - 1]}, world aggregate only`;
  el('src-wb').textContent =
    `${H.years[0]}–${H.years[H.years.length - 1]}, ${H.countries.length} countries`;
}

async function main() {
  const [world, holders, cofer] = await Promise.all([
    fetch('data/world.json').then((r) => r.json()),
    fetch('data/holders.json').then((r) => r.json()),
    fetch('data/cofer.json').then((r) => r.json()),
  ]);
  W = world; H = holders; C = cofer;

  const slider = el('year');
  slider.min = H.years[0];
  slider.max = H.years[H.years.length - 1];
  state.year = H.complete_through;

  computeSizeScale();
  initHover();
  fillZoomSelect(el('zoom'));
  redrawMap();

  drawCofer();
  fillSourceCells();

  slider.addEventListener('input', () => {
    if (state.playing) play();
    state.year = +slider.value;
    render();
  });
  el('measure').addEventListener('change', (ev) => {
    state.measure = ev.target.value;
    computeSizeScale();
    drawSizeLegend();
    render();
  });
  el('zoom').addEventListener('change', (ev) => {
    if (!setView(ev.target.value)) return;
    state.view = ev.target.value;
    redrawMap();
  });
  el('play').addEventListener('click', play);
}

main().catch((err) => {
  console.error(err);
  document.querySelector('main').insertAdjacentHTML('afterbegin',
    `<div class="panel"><p><strong>Could not load the data.</strong> ` +
    `This page reads three JSON files and needs to be served over HTTP — ` +
    `opening it straight from the filesystem will not work.</p></div>`);
});
