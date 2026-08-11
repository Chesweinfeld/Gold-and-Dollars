/* Reserve currency flows — vanilla JS, no dependencies.
 *
 * Two arc maps that mean different things. The TIC layer draws real country
 * pairs (holder -> United States). The BIS layer draws currency of
 * denomination, so its arcs start at a central bank and mean "owed in this
 * currency", never "lent by this country". Keeping that distinction visible is
 * most of the design.
 */

/* The projection, the SVG helper, the basemap and arcPath come from
 * projection.js, which both pages share so the two maps stay identical. */

'use strict';

const el = (id) => document.getElementById(id);

/* Net positions are signed, so the sign goes outside the currency symbol —
   "−$200bn", not "$-200bn" — with a real minus rather than a hyphen. */
function money(bn) {
  if (bn == null) return '—';
  const sign = bn < 0 ? '−' : '';
  const a = Math.abs(bn);
  if (a >= 1000) return sign + '$' + (a / 1000).toFixed(2) + 'tn';
  if (a >= 1) return sign + '$' + Math.round(a).toLocaleString() + 'bn';
  return sign + '$' + (a * 1000).toFixed(0) + 'm';
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

function monthLabel(p) {
  const [y, m] = p.split('-');
  return `${MONTHS[+m - 1]} ${y}`;
}

let W = null;
let F = null;

/* One projection state for the page, so switching tabs never lands you on a
 * differently framed map than the one you just left. */
function applyView(name) {
  if (!setView(name)) return;
  for (const s of document.querySelectorAll('.zoom-select')) s.value = name;
  drawBasemap(el('tic-grat'), el('tic-land'), W);
  drawBasemap(el('bis-grat'), el('bis-land'), W);
  ticLegend();
  bisLegend();
  drawTic();
  drawBis();
}

/* ── shared tooltip plumbing ──────────────────────────────────────── */

function showTip(tip, mapEl, x, y, html) {
  tip.innerHTML = html;
  const box = mapEl.getBoundingClientRect();
  const vb = mapEl.viewBox.baseVal;
  const px = box.left + ((x - vb.x) / vb.width) * box.width;
  const py = box.top + ((y - vb.y) / vb.height) * box.height;
  const wrap = tip.parentElement.getBoundingClientRect();
  tip.hidden = false;
  tip.style.left = (px - wrap.left) + 'px';
  tip.style.top = (py - wrap.top - 10) + 'px';
}

function nearest(mapEl, ev, nodes) {
  const box = mapEl.getBoundingClientRect();
  if (!box.width) return null;
  const vb = mapEl.viewBox.baseVal;
  const sx = vb.x + ((ev.clientX - box.left) / box.width) * vb.width;
  const sy = vb.y + ((ev.clientY - box.top) / box.height) * vb.height;
  let best = null;
  let bestD = Infinity;
  for (const n of nodes) {
    const d = Math.hypot(n.x - sx, n.y - sy);
    const score = d <= n.r ? d - n.r : d;
    if (score < bestD) { bestD = score; best = n; }
  }
  return bestD > 6 ? null : best;
}

/* ─────────────────────────────  TIC  ───────────────────────────── */

const tic = { i: 0, top: 20, playing: false, timer: null, nodes: [] };

function ticRows(i) {
  return F.tic.holders
    .map((h) => ({ h, v: h.v[i] }))
    .filter((r) => r.v)
    .sort((a, b) => b.v - a.v);
}

function drawTic() {
  const i = tic.i;
  const rows = ticRows(i);
  const shown = rows.slice(0, tic.top);
  const max = rows.length ? rows[0].v : 1;

  const arcs = el('tic-arcs');
  const nodes = el('tic-nodes');
  arcs.textContent = '';
  nodes.textContent = '';
  tic.nodes = [];

  const target = F.tic.target;
  // Thin arcs on top of thick ones, so a small holder stays hoverable. Each
  // stops on the edge of the target dot rather than under it, so twenty arcs
  // converging on Kansas stay countable.
  for (const { h, v } of [...shown].reverse()) {
    const w = Math.max(0.35, Math.sqrt(v / max) * 3.4);
    svg('path', {
      d: arcPath(h.c, target.c, 1, 4.4),
      class: 'arc', 'stroke-width': w.toFixed(2),
    }, arcs);
  }

  for (const { h, v } of shown) {
    const [x, y] = project(h.c[0], h.c[1]);
    const r = Math.max(0.9, Math.sqrt(v / max) * 5.5);
    svg('circle', { cx: x, cy: y, r, class: 'node' }, nodes);
    tic.nodes.push({ x, y, r: Math.max(r, 2.4), h, v });
  }
  const [tx, ty] = project(target.c[0], target.c[1]);
  svg('circle', { cx: tx, cy: ty, r: 4.2, class: 'node target' }, nodes);

  el('tic-out').textContent = monthLabel(F.tic.periods[i]);
  el('tic-period').value = i;

  const total = F.tic.total[i];
  const placed = F.tic.placed[i];
  const official = F.tic.official[i];
  const top = rows[0];

  el('tic-readout').innerHTML = `
    <dl class="stat"><dt>Held abroad, ${monthLabel(F.tic.periods[i])}</dt>
      <dd>${money(total)}<span class="sub">${official ? (official / total * 100).toFixed(0) + '% foreign official' : 'official split not published'}</span></dd></dl>
    <dl class="stat"><dt>Largest holder</dt>
      <dd>${top ? top.h.name : '—'}<span class="sub">${top ? money(top.v) + ' · ' + (top.v / total * 100).toFixed(1) + '% of the total' : ''}</span></dd></dl>
    <dl class="stat"><dt>Top ${Math.min(tic.top, rows.length)} shown</dt>
      <dd>${money(shown.reduce((a, r) => a + r.v, 0))}<span class="sub">of ${rows.length} named holders</span></dd></dl>`;

  el('tic-coverage').textContent =
    `${(placed / total * 100).toFixed(0)}% of foreign holdings this month are ` +
    `attributable to a named country and drawable as an arc. The rest is ` +
    `"All Other"` +
    (placed / total < 0.9 ? `, plus the grouped Caribbean and oil-exporter lines Treasury published until 2016.` : `.`);

  el('tic-table').innerHTML =
    `<thead><tr><th class="n">#</th><th>Holder</th><th class="n">Held</th>` +
    `<th class="n">Share</th></tr></thead><tbody>` +
    rows.slice(0, 20).map((r, n) =>
      `<tr><td class="n">${n + 1}</td><td>${r.h.name}</td>` +
      `<td class="n">${money(r.v)}</td>` +
      `<td class="n">${(r.v / total * 100).toFixed(1)}%</td></tr>`).join('') +
    `</tbody>`;
}

/* Zoomed in, the far end of every arc is off the map. Say so rather than
 * leaving the lines running out of the frame unexplained. */
function ticLegend() {
  el('tic-legend').innerHTML =
    `<span class="legend-cap">Arc width ∝ value held; scaled to the largest holder each month` +
    (viewName === 'world' ? '' :
      ' · the United States lies outside this frame, and every arc runs to it') +
    `</span>`;
}

/* ─────────────────────────────  BIS  ───────────────────────────── */

const bis = { i: 0, cur: 'ALL', playing: false, timer: null, nodes: [] };
const CUR_ORDER = ['USD', 'EUR', 'JPY'];

/* Radius of a country's mark, needed before the arcs are drawn so each
 * arrowhead knows how far short of the circle to stop. */
function nodeR(v, max) {
  return Math.max(0.8, Math.sqrt(Math.abs(v) / max) * 4.6);
}

function drawBis() {
  const i = bis.i;
  const list = bis.cur === 'ALL' ? CUR_ORDER : [bis.cur];

  // Ranked by the size of the net position, not its sign — the biggest
  // creditors matter as much as the biggest debtors.
  const rows = F.bis.countries
    .map((c) => ({ c, v: list.reduce((a, k) => a + c[k][i], 0) }))
    .filter((r) => Math.abs(r.v) > 0)
    .sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
  // Up to three arcs per country, so the count multiplies fast; 30 is where
  // the web still reads as a web rather than as hatching.
  const shown = rows.slice(0, 30);
  const max = shown.length ? Math.abs(shown[0].v) : 1;

  const arcs = el('bis-arcs');
  const nodes = el('bis-nodes');
  arcs.textContent = '';
  nodes.textContent = '';
  bis.nodes = [];

  for (const { c, v: net } of [...shown].reverse()) {
    for (const k of list) {
      const v = c[k][i];
      if (!v) continue;
      const home = F.bis.currencies[k];
      // Skip the degenerate arc from a currency's home to itself.
      if (Math.hypot(home.c[0] - c.c[0], home.c[1] - c.c[1]) < 1.5) continue;
      // The arrow points at whoever owes. Positive net means the banking
      // system's claims on the country exceed its liabilities to it, so the
      // obligation runs towards the country; negative reverses the arrow.
      // Either way the head stops on the edge of the mark it points at — the
      // whole reading of this layer is which end the arrowhead is on.
      const owes = v > 0;
      const w = Math.max(0.25, Math.sqrt(Math.abs(v) / max) * 2.8);
      svg('path', {
        d: owes ? arcPath(home.c, c.c, 1, nodeR(net, max) + 1.2)
                : arcPath(c.c, home.c, -1, 4.8),
        class: 'arc cur-' + k,
        'stroke-width': w.toFixed(2),
        'marker-end': `url(#ah-${k})`,
      }, arcs);
    }
  }

  for (const { c, v } of shown) {
    const [x, y] = project(c.c[0], c.c[1]);
    const r = nodeR(v, max);
    svg('circle', {
      cx: x, cy: y, r,
      class: 'node ' + (v > 0 ? 'is-debtor' : 'is-creditor'),
    }, nodes);
    bis.nodes.push({ x, y, r: Math.max(r, 2.4), c, v });
  }
  for (const k of list) {
    const home = F.bis.currencies[k];
    const [x, y] = project(home.c[0], home.c[1]);
    svg('rect', {
      x: x - 2.7, y: y - 2.7, width: 5.4, height: 5.4,
      transform: `rotate(45 ${x} ${y})`, class: 'issuer-mark cur-stroke-' + k,
    }, nodes);
    const t = svg('text', {
      x, y: y - 5.2, class: 'issuer-label', 'text-anchor': 'middle',
    }, nodes);
    t.textContent = k;
  }

  el('bis-out').textContent = F.bis.periods[i];
  el('bis-period').value = i;

  const gross = F.bis.countries.reduce((a, c) => a + c.cl[i], 0);
  const debtors = F.bis.countries.filter((c) => c.TO1[i] > 0);
  const owed = debtors.reduce((a, c) => a + c.TO1[i], 0);
  const usdNet = F.bis.countries.reduce((a, c) => a + Math.max(c.USD[i], 0), 0);
  const top = rows[0];

  el('bis-readout').innerHTML = `
    <dl class="stat"><dt>Gross claims outstanding, ${F.bis.periods[i]}</dt>
      <dd>${money(gross)}<span class="sub">the balance sheet the net comes out of</span></dd></dl>
    <dl class="stat"><dt>Owed on net</dt>
      <dd>${money(owed)}<span class="sub">${debtors.length} net debtor countries, ${F.bis.countries.length - debtors.length} net creditors · ${money(usdNet)} of it in dollars</span></dd></dl>
    <dl class="stat"><dt>Largest net position${bis.cur === 'ALL' ? '' : ' in ' + bis.cur}</dt>
      <dd>${top ? top.c.name : '—'}<span class="sub">${top ? (top.v > 0 ? 'owes ' : 'is owed ') + money(Math.abs(top.v)) : ''}</span></dd></dl>`;

  el('bis-table').innerHTML =
    `<thead><tr><th class="n">#</th><th>Counterparty</th><th>Direction</th>` +
    `<th class="n">Net USD</th><th class="n">Net EUR</th><th class="n">Net JPY</th>` +
    `<th class="n">Net all</th><th class="n">Gross claims</th></tr></thead><tbody>` +
    rows.slice(0, 20).map((r, n) =>
      `<tr><td class="n">${n + 1}</td><td>${r.c.name}</td>` +
      `<td>${r.c.TO1[i] > 0 ? 'owes' : 'is owed'}</td>` +
      `<td class="n">${money(r.c.USD[i])}</td>` +
      `<td class="n">${money(r.c.EUR[i])}</td>` +
      `<td class="n">${money(r.c.JPY[i])}</td>` +
      `<td class="n">${money(r.c.TO1[i])}</td>` +
      `<td class="n">${money(r.c.cl[i])}</td></tr>`).join('') +
    `</tbody>`;
}

function bisLegend() {
  el('bis-legend').innerHTML =
    CUR_ORDER.map((k) =>
      `<span class="key"><span class="chip c-${k}"></span>${F.bis.currencies[k].name}` +
      ` <span style="color:var(--ink-muted)">${F.bis.currencies[k].seat}</span></span>`).join('') +
    `<span class="legend-cap">Arrow points at whoever owes on net; ` +
    `width ∝ the size of the net position` +
    (viewName === 'world' ? '' :
      ' · only the euro is seated inside this frame, and arcs crossing it may ' +
      'have both ends elsewhere') +
    `</span>`;
}

/* ── play loops ───────────────────────────────────────────────────── */

function makePlay(state, draw, ids, n, ms) {
  return function play() {
    const btn = el(ids.btn);
    if (state.playing) {
      clearInterval(state.timer);
      state.playing = false;
      btn.dataset.state = '';
      el(ids.label).textContent = 'Play';
      return;
    }
    state.playing = true;
    btn.dataset.state = 'playing';
    el(ids.label).textContent = 'Pause';
    if (state.i >= n() - 1) state.i = 0;
    state.timer = setInterval(() => {
      state.i += 1;
      if (state.i >= n() - 1) { state.i = n() - 1; draw(); play(); return; }
      draw();
    }, ms);
  };
}

/* ── wiring ───────────────────────────────────────────────────────── */

function switchView(which) {
  const onTic = which === 'tic';
  el('panel-tic').hidden = !onTic;
  el('panel-bis').hidden = onTic;
  el('tab-tic').classList.toggle('on', onTic);
  el('tab-bis').classList.toggle('on', !onTic);
  el('tab-tic').setAttribute('aria-selected', String(onTic));
  el('tab-bis').setAttribute('aria-selected', String(!onTic));
  if (tic.playing && !onTic) ticPlay();
  if (bis.playing && onTic) bisPlay();
}

let ticPlay, bisPlay;

async function main() {
  const [world, flows] = await Promise.all([
    fetch('data/world.json').then((r) => r.json()),
    fetch('data/flows.json').then((r) => r.json()),
  ]);
  W = world; F = flows;

  tic.i = F.tic.periods.length - 1;
  bis.i = F.bis.periods.length - 1;

  const ticSlider = el('tic-period');
  ticSlider.max = F.tic.periods.length - 1;
  ticSlider.value = tic.i;
  const bisSlider = el('bis-period');
  bisSlider.max = F.bis.periods.length - 1;
  bisSlider.value = bis.i;

  for (const s of document.querySelectorAll('.zoom-select')) {
    fillZoomSelect(s);
    s.addEventListener('change', (e) => applyView(e.target.value));
  }
  applyView('world');

  ticPlay = makePlay(tic, drawTic,
    { btn: 'tic-play', label: 'tic-play-label' },
    () => F.tic.periods.length, 90);
  bisPlay = makePlay(bis, drawBis,
    { btn: 'bis-play', label: 'bis-play-label' },
    () => F.bis.periods.length, 420);

  ticSlider.addEventListener('input', () => {
    if (tic.playing) ticPlay();
    tic.i = +ticSlider.value;
    drawTic();
  });
  bisSlider.addEventListener('input', () => {
    if (bis.playing) bisPlay();
    bis.i = +bisSlider.value;
    drawBis();
  });
  el('tic-play').addEventListener('click', () => ticPlay());
  el('bis-play').addEventListener('click', () => bisPlay());
  el('tic-top').addEventListener('change', (e) => {
    tic.top = +e.target.value;
    drawTic();
  });
  el('bis-cur').addEventListener('change', (e) => {
    bis.cur = e.target.value;
    drawBis();
  });
  el('tab-tic').addEventListener('click', () => switchView('tic'));
  el('tab-bis').addEventListener('click', () => switchView('bis'));

  const ticMap = el('tic-map');
  const ticTip = el('tic-tip');
  ticMap.addEventListener('pointermove', (ev) => {
    const hit = nearest(ticMap, ev, tic.nodes);
    if (!hit) { ticTip.hidden = true; return; }
    const total = F.tic.total[tic.i];
    showTip(ticTip, ticMap, hit.x, hit.y,
      `<b>${hit.h.name}</b>` +
      `<div class="row"><span>US Treasuries held</span><span>${money(hit.v)}</span></div>` +
      `<div class="row"><span>Share of foreign total</span><span>${(hit.v / total * 100).toFixed(1)}%</span></div>`);
  });
  ticMap.addEventListener('pointerleave', () => { ticTip.hidden = true; });

  const bisMap = el('bis-map');
  const bisTip = el('bis-tip');
  bisMap.addEventListener('pointermove', (ev) => {
    const hit = nearest(bisMap, ev, bis.nodes);
    if (!hit) { bisTip.hidden = true; return; }
    const c = hit.c;
    const i = bis.i;
    const owes = c.TO1[i] > 0;
    showTip(bisTip, bisMap, hit.x, hit.y,
      `<b>${c.name} ${owes ? 'owes on net' : 'is owed on net'}</b>` +
      `<div class="row"><span>Net, all currencies</span><span>${money(Math.abs(c.TO1[i]))}</span></div>` +
      `<div class="row"><span>Net in dollars</span><span>${money(c.USD[i])}</span></div>` +
      `<div class="row"><span>Net in euro</span><span>${money(c.EUR[i])}</span></div>` +
      `<div class="row"><span>Net in yen</span><span>${money(c.JPY[i])}</span></div>` +
      `<div class="row"><span>Gross claims / owed to it</span><span>${money(c.cl[i])} / ${money(c.li[i])}</span></div>`);
  });
  bisMap.addEventListener('pointerleave', () => { bisTip.hidden = true; });

  el('src-tic').textContent =
    `${monthLabel(F.tic.periods[0])} to ${monthLabel(F.tic.periods[F.tic.periods.length - 1])}, ` +
    `${F.tic.holders.length} named countries`;
  el('src-bis').textContent =
    `${F.bis.periods[0]} to ${F.bis.periods[F.bis.periods.length - 1]}, ` +
    `${F.bis.countries.length} counterparties`;
}

main().catch((err) => {
  console.error(err);
  document.querySelector('main').insertAdjacentHTML('afterbegin',
    `<div class="panel"><p><strong>Could not load the data.</strong> This page ` +
    `reads two JSON files and must be served over HTTP.</p></div>`);
});
