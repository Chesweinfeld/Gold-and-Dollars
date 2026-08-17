"""Density-equalising cartogram of land value, and the check that it worked.

Country outlines are projected to Equal Earth (an equal-area projection, so
the input areas mean something), rasterised to a value-density grid, and run
through the diffusion cartogram in cartogram.py.  Every country's *final* area
should be proportional to its land value; the script measures whether it is.

Colour is a second, independent variable: land value per square kilometre of
real land -- how far each country had to move to get here.

Writes docs/figures/land_value_cartogram.{svg,html} and
data/land/cartogram_area_check.csv.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from rasterio.features import rasterize
from shapely.geometry import MultiPolygon, Polygon

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cartogram import DiffusionCartogram  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
FIG = ROOT / "docs" / "figures"

EQUAL_EARTH = "EPSG:8857"
NX, NY = 3072, 1536        # diffusion grid; the error floor is resolution
PAD = 0.18                  # empty frame around the map, as a share of extent
SEGMENT_M = 20_000          # densify outlines to this spacing before bending
LABEL_MIN_SHARE = 0.012     # label a country at 1.2% of world land value or more


def load_geometry():
    g = gpd.read_file(f"zip://{IN / 'ne_110m_admin_0_countries.zip'}")
    g = g[g.NAME != "Antarctica"].copy()
    g["iso3"] = g.ISO_A3_EH.where(g.ISO_A3_EH != "-99", g.ADM0_A3)
    return g.to_crs(EQUAL_EARTH)


def densify(geom, step):
    """Insert vertices along every edge: a straight border cannot bend."""
    def dens_ring(coords):
        out = []
        for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
            d = np.hypot(x1 - x0, y1 - y0)
            n = max(1, int(np.ceil(d / step)))
            for i in range(n):
                t = i / n
                out.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
        out.append(coords[-1])
        return out

    def dens_poly(p):
        return Polygon(
            dens_ring(list(p.exterior.coords)),
            [dens_ring(list(r.coords)) for r in p.interiors],
        )

    if geom.geom_type == "Polygon":
        return dens_poly(geom)
    return MultiPolygon([dens_poly(p) for p in geom.geoms])


def main():
    vals = pd.read_csv(DATA / "land_value_2020.csv").set_index("iso3")
    g = load_geometry()
    g["value"] = g.iso3.map(vals.total_land_usd)
    g["name"] = g.iso3.map(vals.country).fillna(g.NAME)
    g["area_km2"] = g.geometry.area / 1e6

    missing = g[g.value.isna()]
    print(f"{len(g)} mapped territories, {g.value.notna().sum()} with a land value")
    print("  no value, drawn at the neutral density: "
          + ", ".join(sorted(missing.NAME)) + "\n")

    # Density is value per unit area; the frame and the unmatched territories
    # take the world mean, so they neither swell nor collapse.
    mean_density = g.value.sum() / g.loc[g.value.notna(), "area_km2"].sum()
    g["density"] = (g.value / g.area_km2).fillna(mean_density)

    x0, y0, x1, y1 = g.total_bounds
    px, py = (x1 - x0) * PAD, (y1 - y0) * PAD
    extent = (x0 - px, x1 + px, y0 - py, y1 + py)
    transform = _affine(extent, NX, NY)

    rho = rasterize(
        [(geom, d) for geom, d in zip(g.geometry, g.density)],
        out_shape=(NY, NX),
        transform=transform,
        fill=mean_density,
        dtype="float64",
        all_touched=False,
    )
    rho = np.flipud(rho)  # rasterio writes north-up; the solver works in y-up

    cg = DiffusionCartogram(rho, extent, blur=0.8)
    t_end = 6.0 / cg.decay[0, 1]
    print(f"Diffusion grid {NX}x{NY}, density spread (sd/mean) "
          f"{cg.uniformity(0):.3f} at t=0 -> {cg.uniformity(t_end):.4f} at t=T")

    dense = [densify(geom, SEGMENT_M) for geom in g.geometry]
    pts, index = [], []
    for i, geom in enumerate(dense):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        for p in polys:
            for ring in [p.exterior] + list(p.interiors):
                c = np.asarray(ring.coords)
                index.append((i, len(pts), len(c)))
                pts.extend(c)
    pts = np.asarray(pts)
    print(f"transporting {len(pts):,d} vertices along the flow ...")
    moved = cg.transform(pts, n_steps=300, t_end=t_end)

    out_geoms = _rebuild(dense, moved, index)
    g2 = g.copy()
    g2["geometry"] = out_geoms
    g2["new_area"] = g2.geometry.area

    check = _area_check(g2)
    check.to_csv(DATA / "cartogram_area_check.csv", index=False)

    _render(g2, check)
    return 0


def _affine(extent, nx, ny):
    from rasterio.transform import from_bounds

    x0, x1, y0, y1 = extent
    return from_bounds(x0, y0, x1, y1, nx, ny)


def _rebuild(dense, moved, index):
    out = [None] * len(dense)
    rings = {}
    for i, start, n in index:
        rings.setdefault(i, []).append(moved[start:start + n])
    for i, geom in enumerate(dense):
        polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
        rs = rings[i]
        built, k = [], 0
        for p in polys:
            nrings = 1 + len(p.interiors)
            shell, holes = rs[k], rs[k + 1:k + nrings]
            k += nrings
            built.append(Polygon(shell, holes).buffer(0))
        out[i] = built[0] if len(built) == 1 else MultiPolygon(
            [q for b in built for q in (b.geoms if b.geom_type == "MultiPolygon" else [b])]
        )
    return out


def _area_check(g2):
    """The cartogram's own validation: area share against value share."""
    d = g2[g2.value.notna()].copy()
    d["value_share"] = d.value / d.value.sum()
    d["area_share"] = d.new_area / g2.loc[g2.value.notna(), "new_area"].sum()
    d["error"] = d.area_share / d.value_share - 1
    r = np.corrcoef(d.value_share, d.area_share)[0, 1]
    big = d.nlargest(40, "value_share")
    print("\nArea check -- every country's area should match its share of land value")
    print(f"  correlation of area share with value share: {r:.5f}")
    print(f"  median |error| {np.median(np.abs(d.error)):.1%}, "
          f"top-40 median |error| {np.median(np.abs(big.error)):.1%}")
    worst = d.reindex(d.error.abs().sort_values(ascending=False).index).head(5)
    for _, r_ in worst.iterrows():
        print(f"    worst: {r_['name'][:24]:<24} value {r_.value_share:6.3%}  "
              f"area {r_.area_share:6.3%}  ({r_.error:+.0%})")
    print("  (small countries sit below one grid cell and cannot be resolved; the"
          "\n   frame absorbs the difference)")

    # The individual errors are mostly small countries pulling in both
    # directions; by region they cancel, which is the level the map is read at.
    reg = pd.read_csv(IN / "wb_countries.csv")[["iso3", "region"]]
    r = d.merge(reg, on="iso3").groupby("region")[["value_share", "area_share"]].sum()
    print("\n  by region, share of world land value vs share of the drawing:")
    for name, row in r.sort_values("value_share", ascending=False).iterrows():
        print(f"    {name[:44]:<46} {row.value_share*100:5.2f}%   "
              f"{row.area_share*100:5.2f}%")
    print(f"    largest regional gap {(r.area_share - r.value_share).abs().max()*100:.2f} "
          "percentage points")
    return d[["iso3", "name", "value", "value_share", "area_share", "error",
              "area_km2", "density"]].sort_values("value_share", ascending=False)


# --- rendering ------------------------------------------------------------

BREAKS = [3e4, 1e5, 3e5, 1e6, 3e6, 1e7]  # US$ per km2 of real land


def _bin(density):
    return int(np.searchsorted(BREAKS, density))


def _render(g2, check):
    FIG.mkdir(parents=True, exist_ok=True)
    # Crop to what the transform actually produced, not to the diffusion frame.
    bx0, by0, bx1, by1 = g2.total_bounds
    m = 0.02 * max(bx1 - bx0, by1 - by0)
    x0, x1, y0, y1 = bx0 - m, bx1 + m, by0 - m, by1 + m
    W, H = 1180, 1180 * (y1 - y0) / (x1 - x0)

    def sx(x):
        return (x - x0) / (x1 - x0) * W

    def sy(y):
        return H - (y - y0) / (y1 - y0) * H

    total = g2.value.sum()
    paths = []
    for _, r in g2.sort_values("value", ascending=False, na_position="last").iterrows():
        d = _path(r.geometry, sx, sy)
        if not d:
            continue
        if pd.isna(r.value):
            paths.append(f'<path class="c nodata" d="{d}"><title>{_esc(r["name"])} '
                         '&#183; no land value in the series</title></path>')
            continue
        share = r.value / total
        paths.append(
            f'<path class="c b{_bin(r.density)}" d="{d}" data-n="{_esc(r["name"])}" '
            f'data-v="{r.value/1e12:.2f}" data-s="{share*100:.2f}" '
            f'data-d="{r.density:,.0f}"><title>{_esc(r["name"])} &#183; '
            f'${r.value/1e12:,.2f}tn &#183; {share*100:.2f}% of world land value'
            f'</title></path>')

    labels = []
    for _, r in g2[g2.value.notna()].iterrows():
        if r.value / total < LABEL_MIN_SHARE:
            continue
        p = max(
            (r.geometry.geoms if r.geometry.geom_type == "MultiPolygon" else [r.geometry]),
            key=lambda q: q.area,
        )
        c = p.representative_point()
        labels.append(
            f'<text class="lab" x="{sx(c.x):.1f}" y="{sy(c.y):.1f}">{_esc(_short(r["name"]))}'
            f'<tspan class="labv" x="{sx(c.x):.1f}" dy="13">'
            f'{r.value/total*100:.1f}%</tspan></text>')

    svg = (f'<svg viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" '
           'role="img" aria-label="Cartogram of the world with each country sized by '
           'the value of its land">\n'
           + "\n".join(paths) + "\n" + "\n".join(labels) + "\n</svg>")

    # The standalone SVG carries its own styles: it has to stand up outside
    # the HTML page it was cut from.
    standalone = svg.replace(
        "<svg ", '<svg xmlns="http://www.w3.org/2000/svg" ', 1
    ).replace(">\n", ">\n" + _SVG_STYLE, 1)
    (FIG / "land_value_cartogram.svg").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n' + standalone, encoding="utf-8")

    rows = "".join(
        f"<tr><td>{_esc(r['name'])}</td><td>{r.value/1e12:,.2f}</td>"
        f"<td>{r.value_share*100:,.2f}</td><td>{r.density:,.0f}</td>"
        f"<td>{r.area_km2:,.0f}</td></tr>"
        for _, r in check.head(40).iterrows())
    (FIG / "land_value_cartogram.html").write_text(
        _HTML.format(svg=svg, rows=rows, total=total / 1e12,
                     n=int(check.shape[0])), encoding="utf-8")
    print("\n-> docs/figures/land_value_cartogram.svg and .html")


def _short(n):
    return {"United States": "United States", "Russian Federation": "Russia",
            "Korea, Rep.": "South Korea", "Iran, Islamic Rep.": "Iran",
            "Egypt, Arab Rep.": "Egypt", "Turkiye": "Turkey",
            "United Kingdom": "UK"}.get(n, n)


def _esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _path(geom, sx, sy):
    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    out = []
    for p in polys:
        if p.is_empty or p.area <= 0:
            continue
        for ring in [p.exterior] + list(p.interiors):
            c = np.asarray(ring.coords)
            if len(c) < 4:
                continue
            pts = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in c[:-1])
            out.append("M" + pts.replace(" ", "L", 1).replace(" ", " L") + "Z")
    return "".join(out)


_SVG_STYLE = """<style>
svg { background: #fcfcfb; }
.c { stroke: #fcfcfb; stroke-width: .6; stroke-linejoin: round; }
.b0{fill:#cde2fb} .b1{fill:#9ec5f4} .b2{fill:#6da7ec} .b3{fill:#3987e5}
.b4{fill:#256abf} .b5{fill:#184f95} .b6{fill:#0d366b}
.nodata{fill:#dedcd6}
.lab { font: 600 12.5px -apple-system, "Segoe UI", Roboto, sans-serif; fill:#0b0b0b;
       text-anchor: middle; paint-order: stroke; stroke:#fcfcfb; stroke-width:3.2px; }
.labv { font-weight: 400; font-size: 11px; opacity: .78; }
@media (prefers-color-scheme: dark) {
  svg { background:#1a1a19; }
  .c { stroke:#1a1a19; }
  .b0{fill:#0d366b} .b1{fill:#184f95} .b2{fill:#256abf} .b3{fill:#3987e5}
  .b4{fill:#6da7ec} .b5{fill:#9ec5f4} .b6{fill:#cde2fb}
  .nodata{fill:#3a3a37}
  .lab { fill:#fff; stroke:#1a1a19; }
}
</style>
"""

_HTML = """<!doctype html>
<meta charset="utf-8">
<title>Global land value, as area</title>
<style>
.viz-root {{
  color-scheme: light;
  --surface-1: #fcfcfb; --surface-2: #f0efec;
  --text-primary: #0b0b0b; --text-secondary: #52514e; --text-muted: #7a7973;
  --b0:#cde2fb; --b1:#9ec5f4; --b2:#6da7ec; --b3:#3987e5;
  --b4:#256abf; --b5:#184f95; --b6:#0d366b;
  --nodata:#dedcd6; --edge:#fcfcfb; --lab:#0b0b0b; --labhalo:#fcfcfb;
  background: var(--surface-1); color: var(--text-primary);
  font: 15px/1.55 -apple-system, "Segoe UI", Roboto, sans-serif;
  max-width: 1180px; margin: 0 auto; padding: 28px 20px 60px;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1:#1a1a19; --surface-2:#242423;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
    --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
    --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
    --nodata:#3a3a37; --edge:#1a1a19; --lab:#fff; --labhalo:#1a1a19;
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1:#1a1a19; --surface-2:#242423;
  --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8e85;
  --b0:#0d366b; --b1:#184f95; --b2:#256abf; --b3:#3987e5;
  --b4:#6da7ec; --b5:#9ec5f4; --b6:#cde2fb;
  --nodata:#3a3a37; --edge:#1a1a19; --lab:#fff; --labhalo:#1a1a19;
}}
h1 {{ font-size: 25px; margin: 0 0 6px; letter-spacing: -0.01em; }}
p.sub {{ color: var(--text-secondary); margin: 0 0 18px; max-width: 74ch; }}
p.warn {{ color: var(--text-muted); font-size: 13.5px; max-width: 78ch; }}
svg {{ width: 100%; height: auto; display: block; }}
.c {{ stroke: var(--edge); stroke-width: 0.6; stroke-linejoin: round; }}
.c:hover {{ stroke: var(--text-primary); stroke-width: 1.4; }}
.b0{{fill:var(--b0)}} .b1{{fill:var(--b1)}} .b2{{fill:var(--b2)}} .b3{{fill:var(--b3)}}
.b4{{fill:var(--b4)}} .b5{{fill:var(--b5)}} .b6{{fill:var(--b6)}}
.nodata {{ fill: var(--nodata); }}
.lab {{ font: 600 12.5px -apple-system, sans-serif; fill: var(--lab);
        text-anchor: middle; paint-order: stroke; stroke: var(--labhalo);
        stroke-width: 3.2px; pointer-events: none; }}
.labv {{ font-weight: 400; font-size: 11px; opacity: .78; }}
.legend {{ display: flex; flex-wrap: wrap; gap: 14px; align-items: center;
           margin: 14px 0 4px; font-size: 12.5px; color: var(--text-secondary); }}
.ramp {{ display: flex; }}
.ramp i {{ width: 34px; height: 11px; display: block; }}
.ramp span {{ display: inline-block; width: 34px; text-align: center;
              font-size: 10.5px; color: var(--text-muted); }}
table {{ border-collapse: collapse; font-size: 13px; margin-top: 12px; }}
th, td {{ padding: 4px 12px 4px 0; text-align: right;
          border-bottom: 1px solid var(--surface-2); }}
th:first-child, td:first-child {{ text-align: left; }}
details {{ margin-top: 22px; }} summary {{ cursor: pointer; color: var(--text-secondary); }}
</style>
<div class="viz-root">
<h1>The world, drawn by what its land is worth</h1>
<p class="sub">Every country's <b>area</b> is proportional to the value of its
land in 2020 &mdash; farmland measured, urban land modelled &mdash; about
${total:,.0f} trillion across {n} countries. <b>Colour</b> is a separate
quantity: land value per square kilometre of the country's real surface, so the
top of the scale marks the countries that had to swell the most to get here.</p>

<div class="legend">
  <span>US$ per km&sup2; of real land</span>
  <span class="ramp">
    <i style="background:var(--b0)"></i><i style="background:var(--b1)"></i>
    <i style="background:var(--b2)"></i><i style="background:var(--b3)"></i>
    <i style="background:var(--b4)"></i><i style="background:var(--b5)"></i>
    <i style="background:var(--b6)"></i>
  </span>
  <span><i style="background:var(--nodata);width:14px;height:11px;
     display:inline-block;vertical-align:-1px"></i> no figure</span>
</div>
<div class="legend" style="margin-top:0">
  <span style="visibility:hidden">US$ per km&sup2; of real land</span>
  <span class="ramp"><span>30k</span><span>100k</span><span>300k</span>
    <span>1M</span><span>3M</span><span>10M</span></span>
</div>

{svg}

<p class="warn">Agricultural land is measured (World Bank, <i>Changing Wealth of
Nations</i> 2024: capitalised crop and pasture rents). Urban land is
<b>modelled</b> at 1.92 &times; GDP, the geometric mean ratio in the fourteen
countries whose national accounts report total land under SNA asset AN.211 &mdash;
all of them high-income. Poorer countries almost certainly capitalise land at a
lower multiple, so their share here is overstated. Country shapes are bent by a
diffusion cartogram (Gastner &amp; Newman 2004); countries smaller than one grid
cell cannot reach their exact target area.</p>

<details><summary>Table view &mdash; top 40 by land value</summary>
<table><thead><tr><th>Country</th><th>Land value, US$ tn</th>
<th>Share of world, %</th><th>US$ per km&sup2;</th><th>Real area, km&sup2;</th>
</tr></thead><tbody>{rows}</tbody></table>
</details>
</div>
"""


if __name__ == "__main__":
    sys.exit(main())
