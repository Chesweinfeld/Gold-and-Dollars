"""The land-value cartogram at the resolution of the data, not of borders.

Parcel-level land value does not exist as a global dataset and nothing here
pretends otherwise.  What does exist is a population grid at 30 arc-seconds,
and that is the floor this map works to: the national land-value figures are
spread across a 5.6 km grid by population, and the map is then cut into tiles
of **equal value** by quadtree.

So a tile is not a place.  It is a fixed quantity of money -- about $4 billion
of land -- and its size on the page is therefore the same everywhere, because
that is what a density-equalising cartogram does to equal-value cells.  What
the tiles show is *how much ground* that money covers: a tile in Tokyo is a few
kilometres across, a tile in the Sahara is several hundred, and the colour says
which is which.  Zoom in and the mesh subdivides where the money is.

Writes docs/figures/land_value_cartogram_grid.html and
data/land/grid_cartogram_check.csv.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
from rasterio.features import rasterize
from rasterio.transform import from_bounds
from shapely.geometry import Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_subnational import coarsen_population  # noqa: E402
from cartogram import DiffusionCartogram  # noqa: E402
from make_cartogram import _bin, _path, _rebuild, densify  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
FIG = ROOT / "docs" / "figures"

EQUAL_EARTH = "EPSG:8857"
NX, NY = 6144, 3072      # 5.6 km cells; the population source is 4.6 km
PAD_CELLS = 384          # blank frame, in grid cells, for the map to expand into
BLOCK = 8                # tile side, in grid cells: about 50 km


def main():
    vals = pd.read_csv(DATA / "land_value_2020.csv").set_index("iso3")

    grid, extent, units = value_surface(vals)
    tiles, tile_value = uniform_tiles(grid)

    verts, tile_rings, borders_g = build_mesh(tiles, extent, units)
    print(f"\nDiffusion grid {NX}x{NY}, {len(verts):,d} vertices "
          f"({len(tiles):,d} tiles + country outlines)")
    moved = relax(grid, extent, verts, tile_rings, tile_value)

    render(tiles, tile_rings, moved, borders_g, tile_value, units, vals)
    return 0


def uniform_tiles(value, block=BLOCK):
    """Every tile is the same patch of ground; what varies is what it is worth.

    An earlier version cut tiles of equal *value* instead, by quadtree.  That
    is a mistake: a cartogram carries its information in area, so making every
    cell worth the same and then equalising density leaves a featureless
    rectangle -- all the signal has been removed by construction.  Equal ground
    keeps the map a map, and the money shows up as the tiles that swell.
    """
    ny, nx = value.shape
    blocks = value[:ny // block * block, :nx // block * block]
    blocks = blocks.reshape(ny // block, block, nx // block, block).sum(axis=(1, 3))
    ys, xs = np.nonzero(blocks > 0)
    tiles = [(int(x) * block, int(y) * block, block) for x, y in zip(xs, ys)]
    vals = blocks[ys, xs]
    km = (2 * 17_243_959.1 / NX) / 1000 * block
    print(f"\n{len(tiles):,d} tiles of {km:.0f} x {km:.0f} km covering "
          f"${vals.sum()/1e12:,.1f}tn")
    print(f"  tile value runs ${vals.min()/1e6:,.1f}m to ${vals.max()/1e9:,.0f}bn, "
          f"a factor of {vals.max()/vals.min():,.0f}")
    return tiles, vals


def relax(grid, extent, verts, rings, tile_value, passes=4):
    """Run the flow, then run it again on what came out.

    One pass cannot do this map.  A single diffusion step handles a density
    range of maybe fifty to one; here it is ten million to one -- an empty
    tile in the Sahara has to shrink by a factor of a thousand in area to
    match a single city cell, and the flow field simply cannot bend that far
    in one go.  Feeding the deformed map back in as the new density converges
    quickly: the spread of tile areas falls by a factor of four over five
    passes, and the check below reports it every time.
    """
    x0, x1, y0, y1 = extent
    tr = from_bounds(x0, y0, x1, y1, NX, NY)
    floor = grid[grid > 0].min()
    field = np.where(grid > 0, grid, grid[grid > 0].mean())
    pts = verts.copy()
    for i in range(passes):
        # north-up array, y0-up solver: flip, or the flow comes out mirrored
        cg = DiffusionCartogram(np.flipud(field), extent, blur=0.8)
        pts = cg.transform(pts, n_steps=220, t_end=6.0 / cg.decay[0, 1])
        areas = np.array([_area(pts[r]) for r in rings])
        good = areas > 0
        share_a = areas / areas[good].sum()
        share_v = tile_value / tile_value.sum()
        err = np.abs(share_a[good] / share_v[good] - 1)
        print(f"  pass {i+1}: median |area error| {np.median(err):.1%}, "
              f"90th percentile {np.percentile(err, 90):.1%}")
        if i == passes - 1:
            break
        shapes = [(Polygon(pts[r]).buffer(0), v / max(a, 1e-9))
                  for r, a, v in zip(rings, areas, tile_value) if a > 0]
        nxt = rasterize(shapes, out_shape=(NY, NX), transform=tr, fill=0.0,
                        dtype="float64", all_touched=True)
        hit = nxt > 0
        field = np.where(hit, nxt, nxt[hit].mean() if hit.any() else floor)
    return pts


# --- the value surface ----------------------------------------------------

def value_surface(vals):
    """Spread each country's land value over a 5.6 km grid.

    Urban value goes by population, farmland value by land area -- the same two
    rules as build_subnational.py, applied to grid cells instead of provinces,
    which is as fine as the population source can carry.
    """
    pop_ll, ll_extent = coarsen_population()

    x0 = -17_243_959.1 - PAD_CELLS * (2 * 17_243_959.1 / NX)
    x1 = -x0
    y1 = 8_392_927.6 + PAD_CELLS * (2 * 8_392_927.6 / NY)
    y0 = -y1
    extent = (x0, x1, y0, y1)
    dx, dy = (x1 - x0) / NX, (y1 - y0) / NY

    pop = np.zeros((NY, NX), dtype=np.float64)
    tf = pyproj.Transformer.from_crs(4326, EQUAL_EARTH, always_xy=True)
    left, bottom, right, top = ll_extent
    nh, nw = pop_ll.shape
    lon = left + (np.arange(nw) + 0.5) * (right - left) / nw
    lat = top - (np.arange(nh) + 0.5) * (top - bottom) / nh
    for a in range(0, nh, 256):
        b = min(a + 256, nh)
        rows = pop_ll[a:b]
        if rows.max() <= 0:
            continue
        LON = np.tile(lon, b - a)
        LAT = np.repeat(lat[a:b], nw)
        X, Y = tf.transform(LON, LAT)
        ix = np.clip(((X - x0) / dx).astype(np.int64), 0, NX - 1)
        iy = np.clip(((y1 - Y) / dy).astype(np.int64), 0, NY - 1)
        np.add.at(pop.reshape(-1), iy * NX + ix, rows.reshape(-1).astype(np.float64))
    print(f"population regridded onto {NX}x{NY} Equal Earth cells "
          f"({dx/1000:.1f} km): {pop.sum()/1e9:.2f}bn")

    g = gpd.read_file(f"zip://{IN / 'ne_10m_admin_1_states_provinces.zip'}")
    g = g[g.admin != "Antarctica"].reset_index(drop=True).to_crs(EQUAL_EARTH)
    ids = rasterize(
        ((geom, i + 1) for i, geom in enumerate(g.geometry)),
        out_shape=(NY, NX), transform=from_bounds(x0, y0, x1, y1, NX, NY),
        fill=0, dtype="int32",
    )
    land = ids > 0
    print(f"  {land.sum():,d} land cells ({land.sum()*dx*dy/1e12:.1f}M km2)")

    iso = g.adm0_a3.values
    unit_iso = np.concatenate([[""], iso])
    codes, uniq = pd.factorize(unit_iso[ids.ravel()])
    codes = codes.reshape(NY, NX)

    pop_by = np.bincount(codes.ravel(), weights=pop.ravel(), minlength=len(uniq))
    cells_by = np.bincount(codes.ravel(), minlength=len(uniq))
    urban = vals.urban_land_usd.reindex(uniq).fillna(0.0).to_numpy(copy=True)
    ag = vals.ag_land_usd.reindex(uniq).fillna(0.0).to_numpy(copy=True)
    urban[uniq == ""] = 0.0
    ag[uniq == ""] = 0.0

    # A country whose people all fall outside the grid still has land: fall
    # back to spreading its urban value by area.
    per_person = np.divide(urban, pop_by, out=np.zeros_like(urban), where=pop_by > 0)
    per_cell_u = np.divide(urban, cells_by, out=np.zeros_like(urban),
                           where=(cells_by > 0) & (pop_by <= 0))
    per_cell_a = np.divide(ag, cells_by, out=np.zeros_like(ag), where=cells_by > 0)

    value = pop * per_person[codes] + (per_cell_u + per_cell_a)[codes]
    value[~land] = 0.0

    tot = value.sum()
    print(f"  value surface totals ${tot/1e12:,.1f}tn against "
          f"${vals.total_land_usd.sum()/1e12:,.1f}tn in the country series "
          f"({100*tot/vals.total_land_usd.sum():.1f}%; the remainder is in "
          "countries with no boundary here)")

    units = pd.DataFrame({
        "name": np.concatenate([["(sea)"], g.name.fillna(g.admin).values]),
        "admin": np.concatenate([["(sea)"], g.admin.values]),
    })
    return value, extent, (units, ids, g)


# --- mesh, transport, drawing --------------------------------------------

def build_mesh(tiles, extent, units):
    """Tile corners on a shared lattice, plus one hanging node per short edge.

    Corners are deduplicated by lattice index, so neighbouring tiles hand the
    same vertex to the flow and the mesh cannot tear.
    """
    x0, x1, y0, y1 = extent
    dx, dy = (x1 - x0) / NX, (y1 - y0) / NY
    owner = np.zeros((NY, NX), dtype=np.int32)
    for x, y, s in tiles:
        owner[y:y + s, x:x + s] = s

    index, verts, rings = {}, [], []

    def vid(ix, iy):
        key = (ix, iy)
        got = index.get(key)
        if got is None:
            got = len(verts)
            index[key] = got
            verts.append((x0 + ix * dx, y1 - iy * dy))
        return got

    for x, y, s in tiles:
        ring = []
        # top edge left->right, right edge, bottom edge, left edge
        for (ax, ay), (bx, by), probe in (
            ((x, y), (x + s, y), (x + s // 2, max(y - 1, 0))),
            ((x + s, y), (x + s, y + s), (min(x + s, NX - 1), y + s // 2)),
            ((x + s, y + s), (x, y + s), (x + s // 2, min(y + s, NY - 1))),
            ((x, y + s), (x, y), (max(x - 1, 0), y + s // 2)),
        ):
            ring.append(vid(ax, ay))
            nsize = owner[probe[1], probe[0]]
            if s > 1 and 0 < nsize < s:
                ring.append(vid((ax + bx) // 2, (ay + by) // 2))
        rings.append(ring)

    # Country outlines ride the same flow so they still line up afterwards.
    _, _, g = units
    countries = g.dissolve("adm0_a3").reset_index()
    countries["geometry"] = countries.geometry.simplify(12_000).buffer(0)
    dense = [densify(q, 25_000) for q in countries.geometry]
    n0 = len(verts)
    cidx = []
    for i, geom in enumerate(dense):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for p in polys:
            for r in [p.exterior] + list(p.interiors):
                c = np.asarray(r.coords)
                cidx.append((i, len(verts), len(c)))
                verts.extend(map(tuple, c))
    return np.asarray(verts, dtype=float), rings, (countries, dense, cidx, n0)


def render(tiles, rings, moved, borders_g, tile_value, units, vals):
    FIG.mkdir(parents=True, exist_ok=True)
    names, ids, _ = units
    countries, dense, cidx, _ = borders_g

    poly = [moved[r] for r in rings]
    areas = np.array([_area(p) for p in poly])
    good = areas > 0
    share_a = areas / areas[good].sum()
    share_v = tile_value / tile_value.sum()
    err = share_a[good] / share_v[good] - 1
    print("\nArea check -- each tile's drawn area against its share of land value")
    print(f"  median |error| {np.median(np.abs(err)):.1%}; "
          f"across the 2,000 most valuable tiles, "
          f"{np.median(np.abs(err[np.argsort(-share_v[good])[:2000]])):.1%}")
    print(f"  correlation of drawn area with value: "
          f"{np.corrcoef(share_a[good], share_v[good])[0,1]:.4f}")

    bx0, by0 = moved.min(0)
    bx1, by1 = moved.max(0)
    m = 0.01 * max(bx1 - bx0, by1 - by0)
    x0, x1, y0, y1 = bx0 - m, bx1 + m, by0 - m, by1 + m
    W = 1600.0
    H = W * (y1 - y0) / (x1 - x0)

    def px(p):
        return ((p[:, 0] - x0) / (x1 - x0) * W,
                H - (p[:, 1] - y0) / (y1 - y0) * H)

    cell_area_km2 = ((2 * 17_243_959.1 / NX) / 1000) ** 2
    paths, meta = [], []
    name_list, name_idx = [], {}
    for k, (tx, ty, s) in enumerate(tiles):
        p = poly[k]
        if len(p) < 3 or areas[k] <= 0:
            continue
        X, Y = px(p)
        d = "M" + "L".join(f"{a:.1f},{b:.1f}" for a, b in zip(X, Y)) + "Z"
        ground = s * s * cell_area_km2
        density = tile_value[k] / ground
        nm = names.name.iloc[int(ids[min(ty + s // 2, NY - 1),
                                     min(tx + s // 2, NX - 1)])]
        ad = names.admin.iloc[int(ids[min(ty + s // 2, NY - 1),
                                      min(tx + s // 2, NX - 1)])]
        label = nm if nm == ad else f"{nm}, {ad}"
        j = name_idx.get(label)
        if j is None:
            j = len(name_list)
            name_idx[label] = j
            name_list.append(label)
        paths.append(f'<path class="t b{_bin(density)}" d="{d}" data-i="{len(meta)}"/>')
        meta.append([j, int(round(density)), round(tile_value[k] / 1e6)])

    border_paths = []
    for i, geom in enumerate(dense):
        rebuilt = _rebuild([geom], moved, [(0, s, n) for (j, s, n) in cidx if j == i])
        d = _path(rebuilt[0], lambda v: (v - x0) / (x1 - x0) * W,
                  lambda v: H - (v - y0) / (y1 - y0) * H)
        if d:
            border_paths.append(f'<path class="cb" d="{d}"/>')

    check = pd.DataFrame({
        "tile_x": [t[0] for t in tiles], "tile_y": [t[1] for t in tiles],
        "cells_per_side": [t[2] for t in tiles],
        "value_usd": tile_value, "drawn_area": areas,
    })
    check.to_csv(DATA / "grid_cartogram_check.csv", index=False)

    svg = (f'<svg id="map" viewBox="0 0 {W:.0f} {H:.0f}" role="img" '
           'aria-label="Zoomable cartogram of the world on a 50 km grid, each '
           'cell sized by the value of its land">'
           f'<g id="scene">\n{chr(10).join(paths)}\n'
           f'<g class="borders">{chr(10).join(border_paths)}</g>\n</g></svg>')

    import json
    (FIG / "land_value_cartogram_grid.html").write_text(
        _HTML.format(svg=svg, tiles=len(meta),
                     side=(2 * 17_243_959.1 / NX) / 1000 * BLOCK,
                     total=vals.total_land_usd.sum() / 1e12,
                     km=(2 * 17_243_959.1 / NX) / 1000,
                     names=json.dumps(name_list, ensure_ascii=False),
                     meta=json.dumps(meta)),
        encoding="utf-8")
    print(f"\n-> docs/figures/land_value_cartogram_grid.html "
          f"({len(meta):,d} tiles drawn)")


def _area(p):
    x, y = p[:, 0], p[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, 1)) - np.dot(y, np.roll(x, 1)))


_HTML = """<title>Global land value, on a 50 km grid</title>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1:#fcfcfb; --surface-2:#f0efec;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#7a7973;
  --b0:#cde2fb; --b1:#9ec5f4; --b2:#6da7ec; --b3:#3987e5;
  --b4:#256abf; --b5:#184f95; --b6:#0d366b;
  --cb:rgba(252,252,251,.85);
  background:var(--surface-1); color:var(--text-primary);
  font:15px/1.55 -apple-system,"Segoe UI",Roboto,sans-serif;
  max-width:1500px; margin:0 auto; padding:28px 20px 60px;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#242423;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
    --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
    --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
    --cb:rgba(255,255,255,.5);
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#242423;
  --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
  --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
  --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
  --cb:rgba(255,255,255,.5);
}}
h1 {{ font-size:25px; margin:0 0 6px; letter-spacing:-.01em; }}
p.sub {{ color:var(--text-secondary); margin:0 0 14px; max-width:78ch; }}
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
.wrap {{ position:relative; overflow:hidden; border-radius:8px; touch-action:none; }}
svg {{ width:100%; height:auto; display:block; cursor:grab; }}
svg.drag {{ cursor:grabbing; }}
.t {{ stroke:none; }}
.t:hover {{ stroke:var(--text-primary); stroke-width:1.4;
            vector-effect:non-scaling-stroke; }}
.b0{{fill:var(--b0)}} .b1{{fill:var(--b1)}} .b2{{fill:var(--b2)}} .b3{{fill:var(--b3)}}
.b4{{fill:var(--b4)}} .b5{{fill:var(--b5)}} .b6{{fill:var(--b6)}}
.cb {{ fill:none; stroke:var(--cb); stroke-width:1; vector-effect:non-scaling-stroke;
       stroke-linejoin:round; pointer-events:none; }}
#tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
        background:var(--surface-1); color:var(--text-primary);
        border:1px solid var(--surface-2); border-radius:7px; padding:7px 10px;
        font-size:12.5px; line-height:1.45; box-shadow:0 4px 16px rgba(0,0,0,.18);
        z-index:9; max-width:250px; }}
</style>
<div class="viz-root">
<h1>The world, drawn by what its land is worth</h1>
<p class="sub">{tiles:,d} tiles, each the same {side:.0f} &times; {side:.0f} km
patch of real ground, each drawn at the value of the land inside it —
${total:,.0f} trillion in all. Cities swell to many times their true size and
empty country collapses to a thread. Colour is land value per square kilometre.
Scroll or pinch to zoom, drag to pan; hover a tile for where it is.</p>

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

<p class="warn">National totals are farmland measured (World Bank, <i>Changing
Wealth of Nations</i> 2024) plus urban land modelled at 1.92 &times; GDP. Inside
a country the value is spread across a {km:.1f} km grid by population (JRC
GHS-POP 2020) for the urban part and by area for the farmland part. That is the
finest the sources go: <b>there is no global parcel-level land-value data</b>,
and this is a population-weighted disaggregation, not a record of prices. It
knows that Tokyo is worth more per hectare than Hokkaido; it does not know that
Ginza is worth more than Adachi.</p>
</div>
<script>
(function () {{
  var NAMES = {names}, META = {meta};
  var svg = document.getElementById('map'), scene = document.getElementById('scene'),
      tip = document.getElementById('tip'), zlab = document.getElementById('zlab'),
      vb = svg.viewBox.baseVal, k = 1, tx = 0, ty = 0;

  function apply() {{
    if (!isFinite(tx) || !isFinite(ty)) {{ tx = 0; ty = 0; }}
    scene.setAttribute('transform',
      'translate(' + tx + ',' + ty + ') scale(' + k + ')');
    zlab.textContent = k.toFixed(1) + '\\u00d7';
  }}
  function zoomAt(px, py, f) {{
    var next = Math.min(120, Math.max(1, k * f));
    f = next / k; tx = px - f * (px - tx); ty = py - f * (py - ty); k = next;
    if (k === 1) {{ tx = 0; ty = 0; }}
    apply();
  }}
  function local(e) {{
    var r = svg.getBoundingClientRect();
    if (!r.width) return [vb.width / 2, vb.height / 2];
    return [(e.clientX - r.left) / r.width * vb.width,
            (e.clientY - r.top) / r.height * vb.height];
  }}
  svg.addEventListener('wheel', function (e) {{
    e.preventDefault(); var p = local(e);
    zoomAt(p[0], p[1], Math.exp(-e.deltaY * 0.0022));
  }}, {{passive: false}});
  var drag = null;
  svg.addEventListener('pointerdown', function (e) {{
    drag = {{x: e.clientX, y: e.clientY, tx: tx, ty: ty}};
    try {{ svg.setPointerCapture(e.pointerId); }} catch (err) {{}}
    svg.classList.add('drag');
  }});
  svg.addEventListener('pointermove', function (e) {{
    if (!drag || e.buttons === 0) {{ drag = null; svg.classList.remove('drag'); return; }}
    var r = svg.getBoundingClientRect(); if (!r.width) return;
    var s = vb.width / r.width;
    tx = drag.tx + (e.clientX - drag.x) * s;
    ty = drag.ty + (e.clientY - drag.y) * s;
    apply();
  }});
  ['pointerup', 'pointercancel'].forEach(function (t) {{
    svg.addEventListener(t, function () {{ drag = null; svg.classList.remove('drag'); }});
  }});
  svg.addEventListener('dblclick', function (e) {{
    var p = local(e); zoomAt(p[0], p[1], 1.9);
  }});
  document.getElementById('zin').onclick = function () {{
    zoomAt(vb.width / 2, vb.height / 2, 1.7); }};
  document.getElementById('zout').onclick = function () {{
    zoomAt(vb.width / 2, vb.height / 2, 1 / 1.7); }};
  document.getElementById('zreset').onclick = function () {{
    k = 1; tx = 0; ty = 0; apply(); }};

  svg.addEventListener('pointerover', function (e) {{
    var el = e.target.closest('.t');
    if (!el) {{ tip.style.opacity = 0; return; }}
    var m = META[+el.dataset.i];
    tip.innerHTML = '<b>' + NAMES[m[0]] + '</b><br>$' +
      (m[2] >= 1000 ? (m[2] / 1000).toFixed(1) + 'bn' : m[2] + 'm') +
      ' of land<br>$' + m[1].toLocaleString() + ' per km&sup2;';
    tip.style.opacity = 1;
  }});
  svg.addEventListener('pointermove', function (e) {{
    tip.style.left = Math.min(e.clientX + 15, window.innerWidth - 265) + 'px';
    tip.style.top = Math.min(e.clientY + 15, window.innerHeight - 100) + 'px';
  }});
  svg.addEventListener('pointerleave', function () {{ tip.style.opacity = 0; }});
  apply();
}})();
</script>
"""


if __name__ == "__main__":
    sys.exit(main())
