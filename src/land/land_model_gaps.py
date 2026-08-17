"""Where the land surface has no urban peak, and what that does to the ratio.

A deep teal blob over north-east Indiana on the land-versus-output map sent me
looking, and it turned out to be a defect in the land surface rather than a
fact about Indiana.  This script is the evidence, so the claim can be rechecked
rather than taken on trust.  Three tests:

  1. How peaked is each state's land surface -- the 99.9th percentile of tile
     density over the median.  A state with cities should be strongly peaked.
     Indiana is the flattest state in the country that has a metropolitan
     hierarchy.

  2. A rural transect across the Indiana/Ohio line.  If the model applied some
     state-level offset the line would show as a step.  It does not: rural
     Indiana is priced like rural Ohio.  So the flatness is not a discount on
     Indiana, it is a missing premium on Indiana's *cities*.

  3. Heavy-industry districts in seven states, matched by land use, against
     Gary.  Gary's ground prices about eight times below the median of its
     peers, which is what makes its land-to-output ratio the extreme it is.

The conclusion is narrow and worth stating carefully.  Nothing here shows the
Nolte surface is wrong in general -- its rural values line up across the border
test, and the paper reports its own out-of-sample accuracy.  What it shows is
that in Indiana the urban premium is largely absent, and that any tile in an
Indiana city therefore reads as cheaper ground, and so as more teal, than it
should.

Writes data/land/land_model_gaps.csv.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import rasterio.windows
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
FMV = IN / "places_fmv" / "places_fmv_vacant.tif"

SIDE = 3840.0
X0, Y1 = -2357205.0, 3173925.0
AREA = (SIDE / 1000.0) ** 2

# Heavy industry in seven states, matched by land use: steel and auto plants on
# river or lake ground.  If Gary's dirt were merely cheap Midwestern dirt it
# would sit inside this spread rather than an order of magnitude below it.
MILLS = [
    ("Gary, Indiana (US Steel)", -87.34, 41.62, "IN"),
    ("Burns Harbor, Indiana", -87.15, 41.63, "IN"),
    ("East Chicago, Indiana", -87.45, 41.65, "IN"),
    ("Cleveland, Ohio (the Flats)", -81.68, 41.47, "OH"),
    ("Middletown, Ohio (AK Steel)", -84.39, 39.51, "OH"),
    ("Granite City, Illinois", -90.13, 38.70, "IL"),
    ("South Works, Chicago", -87.53, 41.66, "IL"),
    ("Dearborn, Michigan (the Rouge)", -83.15, 42.30, "MI"),
    ("Weirton, West Virginia", -80.58, 40.41, "WV"),
    ("Sparrows Point, Maryland", -76.47, 39.22, "MD"),
]

# Midwestern metros of broadly comparable size, for the urban premium test.
METROS = [
    ("Fort Wayne, Indiana", -85.139, 41.079, "IN"),
    ("South Bend, Indiana", -86.250, 41.676, "IN"),
    ("Toledo, Ohio", -83.545, 41.654, "OH"),
    ("Dayton, Ohio", -84.192, 39.759, "OH"),
    ("Akron, Ohio", -81.519, 41.081, "OH"),
    ("Grand Rapids, Michigan", -85.668, 42.963, "MI"),
    ("Lansing, Michigan", -84.556, 42.733, "MI"),
    ("Rockford, Illinois", -89.094, 42.271, "IL"),
    ("Peoria, Illinois", -89.589, 40.694, "IL"),
    ("Madison, Wisconsin", -89.384, 43.073, "WI"),
    ("Des Moines, Iowa", -93.625, 41.587, "IA"),
]


def main():
    if not FMV.exists():
        sys.exit(f"missing {FMV}; run src/land/fetch_inputs.py first")
    src = rasterio.open(FMV)
    fwd = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)

    def dollars_per_km2(lon, lat, half_cells=2):
        """Median $/km2 of land over a small box of 480 m cells."""
        x, y = fwd.transform(lon, lat)
        r, c = src.index(x, y)
        n = half_cells
        w = rasterio.windows.Window(c - n, r - n, 2 * n + 1, 2 * n + 1)
        a = src.read(1, window=w).astype("float64")
        v = np.exp(a[np.isfinite(a)]) / 1e4      # the raster is ln($/ha)
        return float(np.median(v)) if v.size else float("nan")

    rows = []

    # --- 1. how peaked is each state ------------------------------------
    land = pd.read_csv(DATA / "us_cartogram_check_usratioflat.csv.gz")
    R, C = land.tile_row.max() + 1, land.tile_col.max() + 1
    val = np.zeros((R, C))
    val[land.tile_row, land.tile_col] = land.value_usd
    rr, cc = np.mgrid[0:R, 0:C]
    inv = gpd.GeoDataFrame(
        geometry=gpd.points_from_xy((X0 + (cc + 0.5) * SIDE).ravel(),
                                    (Y1 - (rr + 0.5) * SIDE).ravel()),
        crs="EPSG:5070")
    st = gpd.read_file(f"zip://{IN / 'ne_10m_admin_1_states_provinces.zip'}")
    st = st[st.iso_a2 == "US"][["postal", "geometry"]].to_crs("EPSG:5070")
    code = gpd.sjoin(inv, st, how="left",
                     predicate="within").postal.to_numpy().reshape(R, C)

    print("1. PEAKEDNESS OF THE LAND SURFACE, BY STATE")
    print("   99.9th percentile of tile density over the median.  A state with "
          "cities\n   in it should be strongly peaked.\n")
    peaks = []
    for s in sorted({x for x in code.ravel() if isinstance(x, str)}):
        m = (code == s) & (val > 0)
        if m.sum() < 200:
            continue
        v = val[m] / AREA / 1e6
        med, hi = float(np.median(v)), float(np.percentile(v, 99.9))
        peaks.append((s, med, hi, hi / med))
        rows.append(dict(test="state_peakedness", name=s, state=s,
                         median_usd_m_per_km2=round(med, 4),
                         p999_usd_m_per_km2=round(hi, 3),
                         peak_over_median=round(hi / med, 2)))
    peaks.sort(key=lambda t: t[3])
    rank = {s: i + 1 for i, (s, *_) in enumerate(peaks)}
    for s, med, hi, r in peaks[:6]:
        print(f"     {rank[s]:2d}. {s}  median ${med:.3f}m  p99.9 ${hi:7.2f}m  "
              f"peak/median {r:6.1f}")
    print("        ...")
    for s in ("OH", "MI", "IL", "KY"):
        med, hi, r = next((m, h, q) for c, m, h, q in peaks if c == s)
        print(f"     {rank[s]:2d}. {s}  median ${med:.3f}m  p99.9 ${hi:7.2f}m  "
              f"peak/median {r:6.1f}")

    # --- 2. is it a state-level offset? ---------------------------------
    print("\n2. RURAL TRANSECT ACROSS THE INDIANA/OHIO LINE (lat 41.00)")
    print("   The line is at lon -84.80.  A state-level offset would show as a "
          "step.\n")
    for lon in np.arange(-85.6, -84.0, 0.10):
        v = dollars_per_km2(float(lon), 41.00)
        side = "IN" if lon < -84.80 else "OH"
        rows.append(dict(test="border_transect", name=f"{lon:.2f},41.00",
                         state=side, median_usd_m_per_km2=round(v, 4)))
        print(f"     {lon:7.2f}  {side}  ${v:6.3f}m per km2  "
              + "#" * int(min(v, 3) * 18))
    inn = [r["median_usd_m_per_km2"] for r in rows
           if r["test"] == "border_transect" and r["state"] == "IN"]
    oh = [r["median_usd_m_per_km2"] for r in rows
          if r["test"] == "border_transect" and r["state"] == "OH"]
    print(f"\n     Indiana side ${np.mean(inn):.3f}m, Ohio side ${np.mean(oh):.3f}m "
          f"-- a ratio of {np.mean(inn)/np.mean(oh):.2f}.")
    print("     No step at the line: rural Indiana is priced like rural Ohio.")

    # --- 3. what is missing is the urban premium ------------------------
    for label, group, half in (("3. HEAVY INDUSTRY, MATCHED BY LAND USE", MILLS, 2),
                               ("4. MIDWEST METRO CENTRES", METROS, 2)):
        print(f"\n{label}\n")
        vals = []
        for name, lon, lat, state in group:
            v = dollars_per_km2(lon, lat, half)
            vals.append((name, state, v))
            rows.append(dict(test=label.split(".")[1].strip().lower().replace(" ", "_"),
                             name=name, state=state,
                             median_usd_m_per_km2=round(v, 4)))
        peer = float(np.median([v for _, s, v in vals if s != "IN"]))
        for name, state, v in sorted(vals, key=lambda t: t[2]):
            mark = f"   <-- {peer/v:.1f}x below the non-Indiana median" \
                if state == "IN" and v < peer else ""
            print(f"     {name:32s} {state}  ${v:7.3f}m per km2{mark}")
        print(f"     non-Indiana median ${peer:.3f}m per km2")

    out = pd.DataFrame(rows)
    out.to_csv(DATA / "land_model_gaps.csv", index=False)
    print(f"\n-> data/land/land_model_gaps.csv ({len(out)} rows)")
    print("\nCONCLUSION.  Rural Indiana prices like its neighbours; Indiana's "
          "cities and\nindustrial districts do not carry the premium their "
          "peers elsewhere do. Any\nIndiana tile therefore reads as cheaper "
          "ground, and so as more teal on the\nland-versus-output map, than it "
          "should. This is a property of the land\nsurface, not of Indiana's "
          "economy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
