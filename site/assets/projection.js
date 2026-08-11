/* The projection and the basemap, shared by both pages.
 *
 * North-polar Lambert azimuthal equal-area.
 *
 * Reserve money is a northern-hemisphere object. Every issuer except the
 * Australian dollar sits north of the tropics, as does every one of the twenty
 * largest holders, and a rectangular world map splits that one neighbourhood
 * across two edges: Tokyo and New York are the full width of the page apart on
 * a Robinson map and near neighbours on the globe. Centring on the pole puts
 * the subject in the middle and closes the Pacific.
 *
 * Equal-area rather than equidistant because area is the property this map
 * must not lie about — a country covers its true share of the canvas, so no
 * landmass can masquerade as importance, which is the same reason the holdings
 * map draws circles instead of colouring countries in. The price is shape: it
 * smears progressively outwards, and the rim is the South Pole, one point
 * stretched into a whole circle. Everything the data actually contains falls
 * inside 91% of that radius.
 */

'use strict';

const SVG_NS = 'http://www.w3.org/2000/svg';

function svg(tag, attrs, parent) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const k in attrs) if (attrs[k] != null) n.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(n);
  return n;
}

const D2R = Math.PI / 180;
const R2D = 180 / Math.PI;

/* Radius of the entire globe, in viewBox units. 430 across at the 820px cap in
 * the stylesheet works out at 1.9 pixels per unit — the same as the rectangular
 * map it replaces, so every stroke width and font size below is still the size
 * it was drawn to be. */
const DISC = 210;
const VIEWBOX = '-215 -215 430 430';

/* Which meridian points up the page. Greenwich up puts the Americas on the
 * left, Europe at the top and Asia on the right, which is the west-to-east
 * reading order a reader already has from rectangular maps. */
const LON_UP = 0;

/* Distance from the pole. ρ = 2R·sin(colatitude / 2) is what makes it
 * equal-area; the equator lands at 71% of the radius and therefore takes half
 * the disc, as it should. */
function rho(lat) {
  return DISC * Math.sin((90 - lat) * D2R / 2);
}

function project(lon, lat) {
  const r = rho(lat);
  const t = (lon - LON_UP) * D2R;
  return [r * Math.sin(t), -r * Math.cos(t)];
}

function fmt(pts) {
  return 'M' + pts.map((p) => p[0].toFixed(2) + ' ' + p[1].toFixed(2)).join('L');
}

/* ── basemap ──────────────────────────────────────────────────────── */

const PARALLELS = [60, 30, 0, -30, -60];
const LAT_LABELS = [
  { lat: 60, text: '60°N' },
  { lat: 0, text: 'Equator' },
  { lat: -30, text: '30°S' },
];
/* The line the latitude labels run down. 170°W crosses the Bering Sea and then
 * nothing but open Pacific, so none of the three ever lands on a country. */
const LABEL_LON = -170;

/* A straight segment in longitude and latitude is a curve on this map: two
 * coastline points twenty degrees apart in longitude lie on an arc of a
 * parallel, and joining them with a chord cuts the corner off — visibly, out
 * near the rim. Subdivide the long ones before projecting. Segments running
 * north–south need no help, because meridians really are straight lines here. */
const MAX_STEP = 4;   // degrees of longitude

function projectRing(ring) {
  const out = [];
  for (let i = 0; i < ring.length; i++) {
    const a = ring[i];
    const b = ring[(i + 1) % ring.length];
    out.push(project(a[0], a[1]));
    let dlon = b[0] - a[0];
    if (dlon > 180) dlon -= 360;
    if (dlon < -180) dlon += 360;
    const n = Math.ceil(Math.abs(dlon) / MAX_STEP);
    for (let k = 1; k < n; k++) {
      const t = k / n;
      out.push(project(a[0] + dlon * t, a[1] + (b[1] - a[1]) * t));
    }
  }
  return out;
}

/* Draws the graticule and the land into two existing groups, and sizes the
 * <svg> that holds them, so the viewBox has one definition rather than one per
 * page. */
function drawBasemap(gratEl, landEl, world) {
  const owner = gratEl.ownerSVGElement || gratEl.closest('svg');
  if (owner) owner.setAttribute('viewBox', VIEWBOX);
  gratEl.textContent = '';
  landEl.textContent = '';

  for (const lat of PARALLELS) {
    svg('circle', {
      cx: 0, cy: 0, r: rho(lat).toFixed(2), class: lat === 0 ? 'eq' : null,
    }, gratEl);
  }
  // Meridians stop short of the centre; twelve lines meeting at a point would
  // read as a blot exactly where the centre-of-gravity track lives.
  for (let lon = -180; lon < 180; lon += 30) {
    const [x1, y1] = project(lon, 84);
    const [x2, y2] = project(lon, -90);
    svg('line', { x1: x1.toFixed(2), y1: y1.toFixed(2), x2: x2.toFixed(2), y2: y2.toFixed(2) }, gratEl);
  }
  svg('circle', { cx: 0, cy: 0, r: DISC, class: 'rim' }, gratEl);

  // Latitude is the thing a reader loses first on a polar map, so three rings
  // are named out over the empty Pacific.
  for (const l of LAT_LABELS) {
    const [x, y] = project(LABEL_LON, l.lat);
    const t = svg('text', {
      x: x.toFixed(2), y: (y + 1.7).toFixed(2),
      class: 'grat-label', 'text-anchor': 'middle',
    }, gratEl);
    t.textContent = l.text;
  }

  for (const c of world.countries) {
    // Antarctica is skipped, as it was before, but for a new reason: its ring
    // closes along the line of 90°S, and this projection stretches that line
    // into the entire rim. The continent would be drawn as a disc.
    if (c.id === 'ATA') continue;
    let d = '';
    for (const ring of c.r) d += fmt(projectRing(ring)) + 'Z';
    svg('path', { d, 'data-id': c.id }, landEl);
  }
}

/* ── arcs ─────────────────────────────────────────────────────────── */

function unitVec(lon, lat) {
  const a = lon * D2R;
  const b = lat * D2R;
  const c = Math.cos(b);
  return [c * Math.cos(a), c * Math.sin(a), Math.sin(b)];
}

/* Points along the great circle from `from` to `to`, pushed off it by `bow` so
 * that arcs sharing an endpoint stay separable.
 *
 * Sampling the sphere and projecting each point — rather than curving between
 * the two projected ends, which is what the rectangular version did — is what
 * keeps these honest here. A straight line drawn across this map from
 * Washington to Canberra runs over Siberia. A great circle goes over the
 * Pacific, because that is where the route goes.
 *
 * Swapping the endpoints flips both the plane's normal and the sign of `bow`,
 * so arcPath(a, b, 1) and arcPath(b, a, −1) trace the same curve in opposite
 * directions — which is how the net-direction arrows put the arrowhead on the
 * right end without moving the line. */
function geoLine(from, to, bow) {
  const A = unitVec(from[0], from[1]);
  const B = unitVec(to[0], to[1]);
  const dot = Math.max(-1, Math.min(1, A[0] * B[0] + A[1] * B[1] + A[2] * B[2]));
  const om = Math.acos(dot);
  if (om < 1e-4) return [from, to];
  const so = Math.sin(om);

  let N = [A[1] * B[2] - A[2] * B[1],
           A[2] * B[0] - A[0] * B[2],
           A[0] * B[1] - A[1] * B[0]];
  const nl = Math.hypot(N[0], N[1], N[2]) || 1;
  N = [N[0] / nl, N[1] / nl, N[2] / nl];

  const amp = bow * Math.min(0.26, om * 0.20);
  const n = Math.max(8, Math.min(64, Math.round(om * R2D / 3)));
  const out = [];
  for (let i = 0; i <= n; i++) {
    const t = i / n;
    const s1 = Math.sin((1 - t) * om) / so;
    const s2 = Math.sin(t * om) / so;
    const k = amp * Math.sin(Math.PI * t);
    const v = [s1 * A[0] + s2 * B[0] + k * N[0],
               s1 * A[1] + s2 * B[1] + k * N[1],
               s1 * A[2] + s2 * B[2] + k * N[2]];
    const L = Math.hypot(v[0], v[1], v[2]) || 1;
    out.push([Math.atan2(v[1], v[0]) * R2D,
              Math.asin(Math.max(-1, Math.min(1, v[2] / L))) * R2D]);
  }
  return out;
}

/* `trim` pulls the far end back by that many viewBox units, so an arrowhead
 * lands against the edge of the circle it points at instead of inside it. */
function arcPath(from, to, bow, trim) {
  const pts = geoLine(from, to, bow).map((p) => project(p[0], p[1]));
  if (trim > 0 && pts.length > 2) {
    const end = pts[pts.length - 1];
    let i = pts.length - 1;
    while (i > 1 && Math.hypot(pts[i][0] - end[0], pts[i][1] - end[1]) < trim) i--;
    const d = Math.hypot(pts[i][0] - end[0], pts[i][1] - end[1]) || 1;
    const t = Math.max(0, Math.min(1, (d - trim) / d));
    const back = [pts[i][0] + (end[0] - pts[i][0]) * t,
                  pts[i][1] + (end[1] - pts[i][1]) * t];
    pts.length = i + 1;
    pts[i] = back;
  }
  return fmt(pts);
}
