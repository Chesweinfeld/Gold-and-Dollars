"""Split each country's land value across its states and provinces.

The country series says nothing about where inside a country the value sits,
and that is where nearly all of it varies -- a national figure is an average
over a range of four orders of magnitude.  There is no sub-national land-value
record to read, so this splits the national figure by two rules, and neither is
a measurement of land price:

    urban land value   ->  by population   (GHS-POP 2020, 30 arc-second grid)
    farmland value     ->  by land area

That gives every state the same land value per resident as its country, and
every hectare of countryside the same farmland value as its country. It gets
Tokyo, the US Northeast and the Chinese coast right for the reason that they
hold the people, and it cannot see rent gradients within a city, or that an
Iowa acre is worth more than a Nevada acre.

Reads the GHS population raster once and sums it inside 4,596 Natural Earth
admin-1 units.  Writes data/land/subnational_land_value.csv.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
from rasterio.features import rasterize
from rasterio.transform import from_bounds

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
OUT = ROOT / "data" / "land"

POP_TIF = IN / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
ADM1_ZIP = IN / "ne_10m_admin_1_states_provinces.zip"
DECIMATE = 5  # 30 arc-second -> 2.5 arc-minute, about 4.6 km at the equator


def coarsen_population():
    """Block-sum the 43202 x 21384 population grid down by DECIMATE.

    Read in strips: the full raster is 3.4 GB in memory and does not need to be.
    """
    src = rasterio.open(POP_TIF)
    h, w = src.shape
    nh, nw = h // DECIMATE, w // DECIMATE
    out = np.zeros((nh, nw), dtype=np.float32)
    rows = DECIMATE * 64
    for y0 in range(0, nh * DECIMATE, rows):
        n = min(rows, nh * DECIMATE - y0)
        band = src.read(1, window=((y0, y0 + n), (0, nw * DECIMATE)))
        band = np.nan_to_num(band, nan=0.0)
        band[band < 0] = 0.0
        out[y0 // DECIMATE: y0 // DECIMATE + n // DECIMATE] = (
            band.reshape(n // DECIMATE, DECIMATE, nw, DECIMATE).sum(axis=(1, 3))
        )
    # The remainder rows and columns are dropped, so the south and east edges
    # move; north and west are the raster's own.
    b = src.bounds
    extent = (b.left,
              b.top - nh * DECIMATE * src.res[1],
              b.left + nw * DECIMATE * src.res[0],
              b.top)
    print(f"GHS-POP {w}x{h} -> {nw}x{nh} at {DECIMATE * 30} arc-seconds; "
          f"world population {out.sum()/1e9:.2f}bn")
    return out, extent


def zonal_population(pop, extent):
    g = gpd.read_file(f"zip://{ADM1_ZIP}")
    g = g[g.admin != "Antarctica"].reset_index(drop=True)
    left, bottom, right, top = extent
    nh, nw = pop.shape
    tr = from_bounds(left, bottom, right, top, nw, nh)

    # Unit 0 is "no unit"; ids are 1-based.
    ids = rasterize(
        ((geom, i + 1) for i, geom in enumerate(g.geometry)),
        out_shape=(nh, nw), transform=tr, fill=0, dtype="int32", all_touched=False,
    )
    counts = np.bincount(ids.ravel(), weights=pop.ravel(), minlength=len(g) + 1)
    cells = np.bincount(ids.ravel(), minlength=len(g) + 1)
    g["pop"] = counts[1:]
    g["cells"] = cells[1:]
    inside = counts[1:].sum()
    print(f"{len(g)} admin-1 units; {inside/1e9:.2f}bn people fall inside one "
          f"({inside/pop.sum()*100:.1f}% of the grid total)")
    print(f"  {(g.cells == 0).sum()} units are smaller than one 2.5' cell "
          "and get their population from area instead")
    return g


def main():
    if not POP_TIF.exists():
        raise SystemExit(f"missing {POP_TIF} -- run src/land/fetch_inputs.py")

    pop, extent = coarsen_population()
    g = zonal_population(pop, extent)

    g = g.to_crs("EPSG:8857")
    g["area_km2"] = g.geometry.area / 1e6
    g["iso3"] = g.adm0_a3

    vals = pd.read_csv(OUT / "land_value_2020.csv").set_index("iso3")
    have = g.iso3.isin(vals.index)
    lost = sorted(set(g.loc[~have, "admin"]))
    print(f"\n{have.sum()} of {len(g)} units are in a country with a land value")
    print("  no country value: " + ", ".join(lost[:14])
          + (f", and {len(lost)-14} more" if len(lost) > 14 else ""))
    g = g[have].copy()

    # A unit with no resolvable population still has land; give it the country's
    # average population density rather than zero, or it would vanish entirely.
    country_pop = g.groupby("iso3")["pop"].transform("sum")
    country_area = g.groupby("iso3")["area_km2"].transform("sum")
    floor = np.where(g["cells"] == 0, country_pop / country_area * g.area_km2, 0.0)
    g["pop"] = np.maximum(g["pop"], floor)
    country_pop = g.groupby("iso3")["pop"].transform("sum")

    urban = g.iso3.map(vals.urban_land_usd)
    ag = g.iso3.map(vals.ag_land_usd).fillna(0.0)
    g["urban_land_usd"] = urban * g["pop"] / country_pop.replace(0, np.nan)
    g["urban_land_usd"] = g.urban_land_usd.fillna(
        urban * g.area_km2 / country_area)  # country with no people on the grid
    g["ag_land_usd"] = ag * g.area_km2 / country_area
    g["total_land_usd"] = g.urban_land_usd + g.ag_land_usd
    g["density"] = g.total_land_usd / g.area_km2

    out = g[["adm1_code", "iso3", "admin", "name", "type_en", "pop", "area_km2",
             "ag_land_usd", "urban_land_usd", "total_land_usd", "density"]]
    out = out.sort_values("total_land_usd", ascending=False)
    out.to_csv(OUT / "subnational_land_value.csv", index=False)

    _report(out, vals)
    return 0


def _report(out, vals):
    tot = out.total_land_usd.sum()
    print(f"\nsubnational_land_value.csv  {len(out):,d} units, "
          f"${tot/1e12:,.0f}tn")

    # The split must not create or destroy value.
    per_country = out.groupby("iso3").total_land_usd.sum()
    ref = vals.total_land_usd.reindex(per_country.index)
    gap = (per_country - ref).abs() / ref
    print(f"  reallocation check: largest country-level discrepancy "
          f"{gap.max():.2e} (should be rounding only)")

    pos = out.density[out.density > 0]
    print(f"\n  {(out.density == 0).sum()} units have no value at all "
          "(no people, and their country has no farmland figure)")
    print(f"  density spread over the rest: {pos.min():,.0f} to "
          f"{out.density.max():,.0f} US$ per km2, a factor of "
          f"{out.density.max()/pos.min():,.0f}\n")

    print("  top 12 units")
    for _, r in out.head(12).iterrows():
        print(f"    {r['name'][:22]:<22} {r.admin[:14]:<14} "
              f"${r.total_land_usd/1e12:5.2f}tn  {100*r.total_land_usd/tot:4.1f}%  "
              f"${r.density/1e6:,.0f}m per km2")

    print("\n  concentration")
    s = out.total_land_usd.sort_values(ascending=False).cumsum() / tot
    for n in (10, 50, 100, 500):
        print(f"    top {n:>3d} units  {s.iloc[n-1]*100:5.1f}% of world land value")


if __name__ == "__main__":
    sys.exit(main())
