"""The land-value cartogram at state and province level, zoomable.

Same diffusion transform as make_cartogram.py, but the density field varies
inside countries, so the map bends within them: the US Northeast and the
Chinese coast swell, Siberia and the Sahara collapse.  4,405 admin-1 units.

Writes docs/figures/land_value_cartogram_subnational.html and
data/land/cartogram_area_check_subnational.csv.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from rasterio.features import rasterize

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cartogram import DiffusionCartogram  # noqa: E402
from make_cartogram import _affine, _bin, _esc, _path, _rebuild, densify  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
FIG = ROOT / "docs" / "figures"

EQUAL_EARTH = "EPSG:8857"
NX, NY = 3072, 1536
PAD = 0.18
SIMPLIFY_M = 9_000     # outline detail kept before transport
SEGMENT_M = 22_000     # and the spacing vertices are inserted at
DENSITY_FLOOR_PCT = 1  # percentile of positive density used as the floor

COUNTRY_LABEL_MIN = 0.012   # label a country at 1.2% of world land value
# Unit labels come in two tiers, revealed as the zoom deepens: 120 units at
# 0.15% of world land value, then 377 more at 0.04%.
UNIT_LABEL_MIN = 0.0015
UNIT_LABEL_MIN_2 = 0.0004


def main():
    units = pd.read_csv(DATA / "subnational_land_value.csv")
    g = gpd.read_file(f"zip://{IN / 'ne_10m_admin_1_states_provinces.zip'}")
    g = g[["adm1_code", "geometry"]].merge(units, on="adm1_code")
    g = gpd.GeoDataFrame(g, geometry="geometry", crs=4326).to_crs(EQUAL_EARTH)

    # Simplify the units as a *coverage*, not one at a time: an independent
    # simplify moves each side of a shared border differently and opens a sliver
    # of empty space along every internal boundary.  1.27M vertices -> ~113k.
    simple = shapely.coverage_simplify(
        np.asarray(g.geometry.values), tolerance=SIMPLIFY_M, simplify_boundary=True)
    bad = ~shapely.is_valid(simple)
    if bad.any():
        simple[bad] = shapely.make_valid(simple[bad])
        print(f"  {bad.sum()} units needed repair after simplification")
    g["geometry"] = simple
    g = g[~g.geometry.is_empty & g.geometry.notna()]
    g = g[g.geometry.geom_type.isin(["Polygon", "MultiPolygon"])].reset_index(drop=True)
    g["area_km2"] = g.geometry.area / 1e6
    g["density"] = g.total_land_usd / g.area_km2

    floor = np.percentile(g.density[g.density > 0], DENSITY_FLOOR_PCT)
    n_floored = int((g.density < floor).sum())
    g["draw_density"] = g.density.clip(lower=floor)
    print(f"{len(g):,d} admin-1 units after simplifying to {SIMPLIFY_M/1000:.0f} km")
    print(f"  density floored at the {DENSITY_FLOOR_PCT}st percentile "
          f"(${floor:,.0f}/km2) for {n_floored} units, so that the emptiest "
          "ground\n  still occupies a pixel and the flow stays finite")

    countries = g.dissolve("iso3", aggfunc={"total_land_usd": "sum"}).reset_index()
    countries["name"] = countries.iso3.map(
        pd.read_csv(DATA / "land_value_2020.csv").set_index("iso3").country)

    x0, y0, x1, y1 = g.total_bounds
    px, py = (x1 - x0) * PAD, (y1 - y0) * PAD
    extent = (x0 - px, x1 + px, y0 - py, y1 + py)
    mean_density = g.total_land_usd.sum() / g.area_km2.sum()

    rho = np.flipud(rasterize(
        [(geom, d) for geom, d in zip(g.geometry, g.draw_density)],
        out_shape=(NY, NX), transform=_affine(extent, NX, NY),
        fill=mean_density, dtype="float64",
    ))
    cg = DiffusionCartogram(rho, extent, blur=0.8)
    t_end = 6.0 / cg.decay[0, 1]
    print(f"  density spread (sd/mean) {cg.uniformity(0):.3f} at t=0 -> "
          f"{cg.uniformity(t_end):.4f} at t=T")

    # Units and country outlines ride the same flow, so their borders still meet.
    dense_u = [densify(q, SEGMENT_M) for q in g.geometry]
    dense_c = [densify(q, SEGMENT_M) for q in countries.geometry]
    pts, idx_u = _collect(dense_u)
    pts_c, idx_c = _collect(dense_c)
    n = len(pts)
    idx_c = [(i, s + n, k) for i, s, k in idx_c]
    allpts = np.vstack([pts, pts_c])
    print(f"  transporting {len(allpts):,d} vertices ...")
    moved = cg.transform(allpts, n_steps=300, t_end=t_end)

    g2 = g.copy()
    g2["geometry"] = _rebuild(dense_u, moved, idx_u)
    g2["new_area"] = g2.geometry.area
    c2 = countries.copy()
    c2["geometry"] = _rebuild(dense_c, moved, idx_c)

    check = _area_check(g2)
    check.to_csv(DATA / "cartogram_area_check_subnational.csv", index=False)
    _render(g2, c2, check)
    return 0


def _collect(geoms):
    pts, index = [], []
    for i, geom in enumerate(geoms):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for p in polys:
            for ring in [p.exterior] + list(p.interiors):
                c = np.asarray(ring.coords)
                index.append((i, len(pts), len(c)))
                pts.extend(c)
    return np.asarray(pts), index


def _area_check(g2):
    d = g2.copy()
    d["value_share"] = d.total_land_usd / d.total_land_usd.sum()
    d["area_share"] = d.new_area / d.new_area.sum()
    d["error"] = d.area_share / d.value_share.replace(0, np.nan) - 1
    e = d.error.abs().dropna()
    r = np.corrcoef(d.value_share, d.area_share)[0, 1]
    print("\nArea check -- each unit's drawn area against its share of land value")
    print(f"  correlation {r:.5f}   median |error| {np.median(e):.1%}   "
          f"top-200 median |error| "
          f"{np.median(d.nlargest(200, 'value_share').error.abs()):.1%}")

    by_country = d.groupby("iso3")[["value_share", "area_share"]].sum()
    gap = (by_country.area_share - by_country.value_share).abs()
    print(f"  by country, largest gap {gap.max()*100:.2f} percentage points "
          f"({gap.idxmax()})")
    return d[["adm1_code", "iso3", "admin", "name", "total_land_usd",
              "value_share", "area_share", "error", "area_km2", "density",
              "pop"]].sort_values("value_share", ascending=False)


def _render(g2, c2, check):
    FIG.mkdir(parents=True, exist_ok=True)
    bx0, by0, bx1, by1 = g2.total_bounds
    m = 0.02 * max(bx1 - bx0, by1 - by0)
    x0, x1, y0, y1 = bx0 - m, bx1 + m, by0 - m, by1 + m
    W, H = 1400, 1400 * (y1 - y0) / (x1 - x0)

    def sx(x):
        return (x - x0) / (x1 - x0) * W

    def sy(y):
        return H - (y - y0) / (y1 - y0) * H

    total = g2.total_land_usd.sum()
    units = []
    for _, r in g2.iterrows():
        d = _path(r.geometry, sx, sy)
        if not d:
            continue
        units.append(
            f'<path class="u b{_bin(r.density)}" d="{d}" '
            f'data-n="{_esc(r["name"])}" data-a="{_esc(r.admin)}" '
            f'data-t="{_esc(r.type_en)}" data-v="{r.total_land_usd/1e9:.0f}" '
            f'data-s="{r.total_land_usd/total*100:.3f}" '
            f'data-d="{r.density:,.0f}" data-p="{r["pop"]/1e6:.2f}"/>')

    borders = []
    for _, r in c2.iterrows():
        d = _path(r.geometry, sx, sy)
        if d:
            borders.append(f'<path class="cb" d="{d}"/>')

    clab, ulab = [], []
    for _, r in c2.iterrows():
        if r.total_land_usd / total < COUNTRY_LABEL_MIN:
            continue
        c = _biggest_point(r.geometry)
        clab.append(f'<text class="lab" x="{sx(c.x):.1f}" y="{sy(c.y):.1f}">'
                    f'{_esc(_short(r["name"]))}<tspan class="labv" x="{sx(c.x):.1f}" '
                    f'dy="1.1em">{r.total_land_usd/total*100:.1f}%</tspan></text>')
    for _, r in g2.iterrows():
        share = r.total_land_usd / total
        if share < UNIT_LABEL_MIN_2:
            continue
        tier = "ulab" if share >= UNIT_LABEL_MIN else "ulab ulab2"
        c = _biggest_point(r.geometry)
        ulab.append(f'<text class="{tier}" x="{sx(c.x):.1f}" y="{sy(c.y):.1f}">'
                    f'{_esc(r["name"])}</text>')

    svg = (f'<svg id="map" viewBox="0 0 {W:.0f} {H:.0f}" '
           'role="img" aria-label="Zoomable cartogram of the world with every '
           'state and province sized by the value of its land">'
           f'<g id="scene">\n{chr(10).join(units)}\n'
           f'<g class="borders">{chr(10).join(borders)}</g>\n'
           f'<g id="ulabs">{chr(10).join(ulab)}</g>\n'
           f'<g id="clabs">{chr(10).join(clab)}</g>\n</g></svg>')

    rows = "".join(
        f"<tr><td>{_esc(r['name'])}</td><td>{_esc(r.admin)}</td>"
        f"<td>{r.total_land_usd/1e12:,.2f}</td><td>{r.value_share*100:,.2f}</td>"
        f"<td>{r.density/1e6:,.1f}</td><td>{r['pop']/1e6:,.1f}</td></tr>"
        for _, r in check.head(50).iterrows())

    s = check.total_land_usd.sort_values(ascending=False).cumsum() / total
    conc = " &middot; ".join(
        f"top {n} units <b>{s.iloc[n-1]*100:.0f}%</b>" for n in (10, 100, 500))

    (FIG / "land_value_cartogram_subnational.html").write_text(
        _HTML.format(svg=svg, rows=rows, total=total / 1e12, n=len(g2),
                     conc=conc), encoding="utf-8")
    print(f"\n-> docs/figures/land_value_cartogram_subnational.html "
          f"({len(units):,d} units drawn)")


def _biggest_point(geom):
    p = max((geom.geoms if geom.geom_type == "MultiPolygon" else [geom]),
            key=lambda q: q.area)
    return p.representative_point()


def _short(n):
    return {"Russian Federation": "Russia", "Korea, Rep.": "South Korea",
            "Iran, Islamic Rep.": "Iran", "Egypt, Arab Rep.": "Egypt",
            "Turkiye": "Turkey", "United Kingdom": "UK"}.get(n, n)


_HTML = """<title>Global land value, by state and province</title>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f0efec;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#7a7973;
  --b0:#cde2fb; --b1:#9ec5f4; --b2:#6da7ec; --b3:#3987e5;
  --b4:#256abf; --b5:#184f95; --b6:#0d366b;
  --edge:rgba(252,252,251,.45); --cb:#fcfcfb;
  --lab:#0b0b0b; --labhalo:#fcfcfb;
  background:var(--surface-1); color:var(--text-primary);
  font:15px/1.55 -apple-system,"Segoe UI",Roboto,sans-serif;
  max-width:1400px; margin:0 auto; padding:28px 20px 60px;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#242423;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
    --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
    --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
    --edge:rgba(26,26,25,.5); --cb:#1a1a19;
    --lab:#fff; --labhalo:#1a1a19;
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#242423;
  --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
  --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
  --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
  --edge:rgba(26,26,25,.5); --cb:#1a1a19;
  --lab:#fff; --labhalo:#1a1a19;
}}
h1 {{ font-size:25px; margin:0 0 6px; letter-spacing:-.01em; }}
p.sub {{ color:var(--text-secondary); margin:0 0 14px; max-width:76ch; }}
p.warn {{ color:var(--text-muted); font-size:13.5px; max-width:80ch; }}
.bar {{ display:flex; flex-wrap:wrap; gap:14px; align-items:center;
        margin:10px 0; font-size:12.5px; color:var(--text-secondary); }}
.ramp {{ display:flex; }}
.ramp i {{ width:34px; height:11px; display:block; }}
.ramp span {{ display:inline-block; width:34px; text-align:center;
              font-size:10.5px; color:var(--text-muted); }}
button {{ font:inherit; font-size:12.5px; padding:3px 10px; cursor:pointer;
          border:1px solid var(--surface-2); border-radius:6px;
          background:var(--surface-2); color:var(--text-primary); }}
button:hover {{ border-color:var(--text-muted); }}
.wrap {{ position:relative; overflow:hidden; border-radius:8px;
         background:var(--surface-1); touch-action:none; }}
svg {{ width:100%; height:auto; display:block; cursor:grab; }}
svg.drag {{ cursor:grabbing; }}
.u {{ stroke:var(--edge); stroke-width:.4; vector-effect:non-scaling-stroke; }}
.u:hover {{ stroke:var(--text-primary); stroke-width:1.6;
            vector-effect:non-scaling-stroke; }}
.cb {{ fill:none; stroke:var(--cb); stroke-width:1.1;
       vector-effect:non-scaling-stroke; stroke-linejoin:round;
       pointer-events:none; }}
.b0{{fill:var(--b0)}} .b1{{fill:var(--b1)}} .b2{{fill:var(--b2)}} .b3{{fill:var(--b3)}}
.b4{{fill:var(--b4)}} .b5{{fill:var(--b5)}} .b6{{fill:var(--b6)}}
.lab, .ulab {{ fill:var(--lab); text-anchor:middle; paint-order:stroke;
               stroke:var(--labhalo); stroke-linejoin:round; stroke-linecap:round;
               pointer-events:none; }}
.lab {{ font-weight:600; stroke-width:3.4px; }}
.labv {{ font-weight:400; opacity:.78; }}
.ulab {{ font-weight:500; stroke-width:2.6px; opacity:0; transition:opacity .15s; }}
#ulabs.on .ulab {{ opacity:.92; }}
#ulabs.on .ulab2 {{ opacity:0; }}
#ulabs.on.deep .ulab2 {{ opacity:.9; }}
#tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
        background:var(--surface-1); color:var(--text-primary);
        border:1px solid var(--surface-2); border-radius:7px;
        padding:7px 10px; font-size:12.5px; line-height:1.45;
        box-shadow:0 4px 16px rgba(0,0,0,.18); z-index:9; max-width:230px; }}
table {{ border-collapse:collapse; font-size:13px; margin-top:12px; }}
th, td {{ padding:4px 12px 4px 0; text-align:right;
          border-bottom:1px solid var(--surface-2); }}
th:first-child, td:first-child, th:nth-child(2), td:nth-child(2) {{ text-align:left; }}
details {{ margin-top:22px; }} summary {{ cursor:pointer; color:var(--text-secondary); }}
</style>
<div class="viz-root">
<h1>The world, drawn by what its land is worth</h1>
<p class="sub">Every state and province is drawn at its share of world land
value in 2020 — <b>${total:,.0f} trillion</b> across {n:,d} units. Scroll or
pinch to zoom, drag to pan. Concentration: {conc}.</p>

<div class="bar">
  <span>US$ per km&sup2; of real land</span>
  <span class="ramp">
    <i style="background:var(--b0)"></i><i style="background:var(--b1)"></i>
    <i style="background:var(--b2)"></i><i style="background:var(--b3)"></i>
    <i style="background:var(--b4)"></i><i style="background:var(--b5)"></i>
    <i style="background:var(--b6)"></i>
  </span>
  <button id="zin">Zoom in</button><button id="zout">Zoom out</button>
  <button id="zreset">Reset</button>
  <span id="zlab" style="color:var(--text-muted)">1.0&times;</span>
</div>
<div class="bar" style="margin-top:-6px">
  <span style="visibility:hidden">US$ per km&sup2; of real land</span>
  <span class="ramp"><span>30k</span><span>100k</span><span>300k</span>
    <span>1M</span><span>3M</span><span>10M</span></span>
</div>

<div class="wrap">{svg}</div>
<div id="tip"></div>

<p class="warn">Area is land value; colour is land value per square kilometre of
the unit's real surface. National totals are farmland measured (World Bank,
<i>Changing Wealth of Nations</i> 2024) plus urban land modelled at 1.92 &times;
GDP. The split <b>inside</b> each country is a second model and not a
measurement: urban value by population (GHS-POP 2020), farmland value by area.
So a province's figure says where its country's people are, not what an acre
there sells for — it cannot see that Manhattan outprices upstate New York, only
that New York State outweighs Wyoming.</p>

<details><summary>Table view &mdash; top 50 units by land value</summary>
<table><thead><tr><th>Unit</th><th>Country</th><th>Land value, US$ tn</th>
<th>Share of world, %</th><th>US$ m per km&sup2;</th><th>Population, m</th>
</tr></thead><tbody>{rows}</tbody></table>
</details>
</div>
<script>
(function () {{
  var svg = document.getElementById('map'),
      scene = document.getElementById('scene'),
      ulabs = document.getElementById('ulabs'),
      clabs = document.getElementById('clabs'),
      tip = document.getElementById('tip'),
      zlab = document.getElementById('zlab'),
      vb = svg.viewBox.baseVal,
      k = 1, tx = 0, ty = 0;

  function apply() {{
    if (!isFinite(tx) || !isFinite(ty)) {{ tx = 0; ty = 0; }}
    scene.setAttribute('transform',
      'translate(' + tx + ',' + ty + ') scale(' + k + ')');
    // Text rides the transform, so shrink it by the same factor to hold its
    // size on screen.
    clabs.style.fontSize = (12.5 / k) + 'px';
    ulabs.style.fontSize = (10.5 / k) + 'px';
    clabs.style.strokeWidth = (3.4 / k) + 'px';
    ulabs.style.strokeWidth = (2.6 / k) + 'px';
    ulabs.classList.toggle('on', k >= 2.2);
    ulabs.classList.toggle('deep', k >= 5);
    clabs.style.opacity = k >= 5 ? 0.5 : 1;
    zlab.textContent = k.toFixed(1) + '\\u00d7';
  }}

  function zoomAt(px, py, factor) {{
    var next = Math.min(60, Math.max(1, k * factor));
    factor = next / k;
    tx = px - factor * (px - tx);
    ty = py - factor * (py - ty);
    k = next;
    if (k === 1) {{ tx = 0; ty = 0; }}
    apply();
  }}

  function local(e) {{
    var r = svg.getBoundingClientRect();
    return [(e.clientX - r.left) / r.width * vb.width,
            (e.clientY - r.top) / r.height * vb.height];
  }}

  svg.addEventListener('wheel', function (e) {{
    e.preventDefault();
    var p = local(e);
    zoomAt(p[0], p[1], Math.exp(-e.deltaY * 0.0022));
  }}, {{passive: false}});

  var drag = null;
  svg.addEventListener('pointerdown', function (e) {{
    drag = {{x: e.clientX, y: e.clientY, tx: tx, ty: ty}};
    try {{ svg.setPointerCapture(e.pointerId); }} catch (err) {{ /* synthetic */ }}
    svg.classList.add('drag');
  }});
  svg.addEventListener('pointermove', function (e) {{
    if (!drag || e.buttons === 0) {{ drag = null; svg.classList.remove('drag'); return; }}
    var r = svg.getBoundingClientRect(), s = vb.width / r.width;
    tx = drag.tx + (e.clientX - drag.x) * s;
    ty = drag.ty + (e.clientY - drag.y) * s;
    apply();
  }});
  ['pointerup', 'pointercancel'].forEach(function (t) {{
    svg.addEventListener(t, function (e) {{
      drag = null; svg.classList.remove('drag');
    }});
  }});
  svg.addEventListener('dblclick', function (e) {{
    var p = local(e); zoomAt(p[0], p[1], 1.8);
  }});

  document.getElementById('zin').onclick = function () {{
    zoomAt(vb.width / 2, vb.height / 2, 1.6); }};
  document.getElementById('zout').onclick = function () {{
    zoomAt(vb.width / 2, vb.height / 2, 1 / 1.6); }};
  document.getElementById('zreset').onclick = function () {{
    k = 1; tx = 0; ty = 0; apply(); }};

  svg.addEventListener('pointerover', function (e) {{
    var el = e.target.closest('.u');
    if (!el) {{ tip.style.opacity = 0; return; }}
    var d = el.dataset;
    tip.innerHTML = '<b>' + d.n + '</b><br>' + d.a + ' &middot; ' + d.t +
      '<br>$' + (+d.v).toLocaleString() + 'bn &middot; ' + d.s + '% of world' +
      '<br>$' + d.d + ' per km&sup2;<br>' + d.p + 'm people';
    tip.style.opacity = 1;
  }});
  svg.addEventListener('pointermove', function (e) {{
    tip.style.left = Math.min(e.clientX + 15, window.innerWidth - 245) + 'px';
    tip.style.top = Math.min(e.clientY + 15, window.innerHeight - 110) + 'px';
  }});
  svg.addEventListener('pointerleave', function () {{ tip.style.opacity = 0; }});

  apply();
}})();
</script>
"""


if __name__ == "__main__":
    sys.exit(main())
