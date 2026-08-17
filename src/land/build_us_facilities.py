"""Mines and power plants, so that their output can be put where they are.

LODES places a job at the worksite the employer reports, which for a mining
company or a utility is very often the head office.  A Wyoming coal county's
whole mining line therefore landed on the few squares of town that hold the
company's address, and a county with a two-gigawatt station put its utilities
line wherever the operator files its payroll.  The map showed a bright square
in the town and nothing at the pit.

Three registers say where the work actually happens:

  MSHA      every mine in the country, with a coordinate and a headcount.  The
            headcount is measured at the mine, which is the whole point.
  EIA-860   every generating plant of a megawatt or more, with a coordinate
            and a nameplate capacity.
  FracFocus every hydraulically fractured well since 2011, with a coordinate
            and the volume of water the job used.

Both are turned into the same unit the rest of the allocation runs on -- jobs
in a NAICS sector -- and written out as extra carrier points.  Mine employment
is already a headcount and is used as it stands.  Plant capacity is not, and
is converted at the national ratio of utility jobs to installed megawatts,
which is stated on every build rather than assumed here.

These points are *added* to the LODES blocks rather than replacing them.  A
mine's employees may well also appear in the LODES count for the block the
mine sits in, so this double counts them -- and that is harmless, because the
allocation is within-county: every county still receives exactly its BEA
figure, and all the double count does is shift weight from the office to the
pit, which is the direction it should move.  What it deliberately does not do
is take the whole line away from the jobs, because a county can hold both a
quarry and an oilfield and only one of them is in MSHA.

What the wells fixed, measured rather than asserted.  Loving County, Texas
carries $10.7bn of output and had **no census block with a single mining job
in it**, so its oil was stranded and fell through to the county's other 432
jobs -- its output was being drawn on its gas stations.  Martin County carried
$14.7bn on seven blocks holding 103 mining jobs.  They now have 1,736 and
2,982 wells to sit on.

The gap that remains: FracFocus is a disclosure registry for hydraulic
fracturing, so it holds the Permian, the Bakken, the Eagle Ford, the Marcellus
and the Anadarko, and largely misses California's steam-flooded heavy oil and
Appalachia's legacy gas.  Because these points are added to the LODES jobs
rather than replacing them, a county with no fracked wells is left exactly as
it was: the gap costs coverage, not correctness.

Writes data/land/us_facility_points.csv.
"""

import csv
import io
import sys
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
MSHA = IN / "msha_mines.zip"
FRAC = IN / "fracfocus" / "fracfocuscsv.zip"
EIA = IN / "eia860.zip"
COUNTIES = IN / "cb_2023_us_county_500k.zip"

# The states this map covers: the conterminous forty-eight and DC.
DROP_STATES = {"02", "15", "60", "66", "69", "72", "78"}
# A mine that is not producing carries no output.  "Intermittent" and "New
# Mine" do produce, and are kept.
LIVE = {"Active", "Intermittent", "New Mine"}
# Wells fracked in this window stand in for what is producing now.  A shale
# well loses most of its rate in its first two years, so a 2012 well and a
# 2023 well are not the same thing at all, and counting the whole registry
# back to 2011 would put weight on ground that has largely stopped paying.
WELL_YEARS = (2019, 2023)
# A generous CONUS box, to catch a coordinate that is plainly wrong.
BOX = (-125.6, -66.4, 24.0, 49.6)


def mines():
    """Active mines, with the headcount MSHA records at the mine itself."""
    if not MSHA.exists():
        sys.exit(f"missing {MSHA} -- run src/land/fetch_inputs.py first")
    with zipfile.ZipFile(MSHA) as z:
        raw = z.read("Mines.txt").decode("latin-1", "replace")
    rows, no_coord, idle = [], 0, 0
    for r in csv.DictReader(io.StringIO(raw.replace("\0", "")), delimiter="|"):
        if r.get("CURRENT_MINE_STATUS") not in LIVE:
            idle += 1
            continue
        try:
            lat = float(r.get("LATITUDE") or "nan")
            lon = float(r.get("LONGITUDE") or "nan")
            emp = float(r.get("NO_EMPLOYEES") or 0)
        except ValueError:
            no_coord += 1
            continue
        # MSHA writes western longitudes both ways round; take the sign the
        # country is actually on.
        if lon > 0:
            lon = -lon
        if not (np.isfinite(lat) and np.isfinite(lon)):
            no_coord += 1
            continue
        if not (BOX[0] <= lon <= BOX[1] and BOX[2] <= lat <= BOX[3]):
            no_coord += 1
            continue
        st = (r.get("FIPS_CNTY_CD") or "").strip()
        state = (r.get("BOM_STATE_CD") or "").strip()
        if emp <= 0:
            continue
        rows.append((lat, lon, emp, state, st))
    d = pd.DataFrame(rows, columns=["lat", "lon", "weight", "st", "cty"])
    print(f"MSHA: {len(d):,d} producing mines with a coordinate and a "
          f"headcount, {d.weight.sum():,.0f} employees")
    print(f"  {idle:,d} rows abandoned or idle, {no_coord:,d} with no usable "
          "coordinate")
    d["kind"] = "mine"
    return d[["lat", "lon", "weight", "kind"]]


def plants():
    """Generating plants, with nameplate capacity as the weight."""
    if not EIA.exists():
        sys.exit(f"missing {EIA} -- run src/land/fetch_inputs.py first")
    with zipfile.ZipFile(EIA) as z:
        pn = [n for n in z.namelist() if n.startswith("2___Plant")]
        gn = [n for n in z.namelist() if n.startswith("3_1_Generator")]
        if not pn or not gn:
            sys.exit("eia860.zip does not hold the plant and generator files")
        # Both sheets carry two header rows of notes above the real ones.
        p = pd.read_excel(io.BytesIO(z.read(pn[0])), skiprows=1)
        g = pd.read_excel(io.BytesIO(z.read(gn[0])), skiprows=1,
                          sheet_name="Operable")
    p.columns = [str(c).strip() for c in p.columns]
    g.columns = [str(c).strip() for c in g.columns]
    cap = g.groupby("Plant Code")["Nameplate Capacity (MW)"].sum()
    p = p[["Plant Code", "Latitude", "Longitude", "State"]].copy()
    p["weight"] = p["Plant Code"].map(cap)
    p = p[p.weight.notna() & (p.weight > 0)]
    p = p[~p.State.isin({"AK", "HI", "PR", "VI", "GU", "AS", "MP"})]
    p = p[p.Latitude.between(BOX[2], BOX[3])
          & p.Longitude.between(BOX[0], BOX[1])]
    print(f"EIA-860: {len(p):,d} plants in the lower 48, "
          f"{p.weight.sum()/1000:,.0f} GW of nameplate capacity")
    out = p.rename(columns={"Latitude": "lat", "Longitude": "lon"})
    out["kind"] = "plant"
    return out[["lat", "lon", "weight", "kind"]]


def wells():
    """Hydraulically fractured wells, from the FracFocus registry.

    This is the piece that was missing.  BEA reports mining, quarrying and oil
    and gas as one county line; MSHA covers mines and not wells; so a Permian
    county's oil -- most of that line's money -- had nowhere to go but the
    jobs, and the jobs are at the operator's office.  Loving County, Texas
    carries $10.7bn of output on 432 LODES jobs, which is $24.8m a job, all of
    it landing on the handful of squares that hold a worksite.

    FracFocus is a disclosure registry rather than a production database: it
    records every hydraulic fracturing job in the country since 2011, with a
    coordinate, and the volume of water used.  Two things follow from that.

    It sees the wells that matter here and not every well.  Everything drilled
    in the Permian, the Bakken, the Eagle Ford, the Marcellus and the
    Anadarko is fracked and is in it; California's steam-flooded heavy oil and
    Appalachia's legacy gas largely are not.  Because these points are added to
    the LODES jobs rather than replacing them, a county with no fracked wells
    is left exactly as it was, so the gap costs coverage and not correctness.

    And water volume is a proxy, not a measurement.  It scales with lateral
    length and stage count, so it tracks how big a well is and therefore what
    it initially produces; it is not barrels.  Weighting the wells equally
    instead moves almost nothing, because what is being decided is *where in
    the county* the output sits and the wells of a given field are much alike.
    """
    if not FRAC.exists():
        sys.exit(f"missing {FRAC} -- run src/land/fetch_inputs.py first")
    with zipfile.ZipFile(FRAC) as z:
        name = "DisclosureList_1.csv"
        if name not in z.namelist():
            sys.exit(f"{FRAC} does not hold {name}")
        d = pd.read_csv(z.open(name), dtype=str, low_memory=False)
    n0 = len(d)
    for c in ("Latitude", "Longitude", "TotalBaseWaterVolume"):
        d[c] = pd.to_numeric(d[c], errors="coerce")
    # The job date is written as a US timestamp; only the year is wanted.
    year = pd.to_datetime(d.JobEndDate, errors="coerce", format="mixed").dt.year
    d["year"] = year
    d = d[d.year.between(*WELL_YEARS)]
    n1 = len(d)
    d = d[d.Latitude.between(BOX[2], BOX[3])
          & d.Longitude.between(BOX[0], BOX[1])]
    # A well can be disclosed more than once -- a refrac, or a correction --
    # and counting it twice would weight that ground twice.  The most recent
    # disclosure per API number wins.
    d = d.sort_values("year").drop_duplicates("APINumber", keep="last")
    vol = d.TotalBaseWaterVolume
    med = vol[vol > 0].median()
    # A disclosure with no volume is still a well; it takes the median rather
    # than dropping out, which would silently thin the map where operators
    # report badly.
    d["weight"] = np.where(vol.notna() & (vol > 0), vol, med)
    blank = int((~(vol.notna() & (vol > 0))).sum())
    print(f"FracFocus: {len(d):,d} wells fracked {WELL_YEARS[0]}-"
          f"{WELL_YEARS[1]} with a usable coordinate, "
          f"{d.weight.sum()/1e9:,.1f}bn gallons of base water")
    print(f"  {n0 - n1:,d} of {n0:,d} disclosures fall outside that window; "
          f"{blank:,d} kept wells had no volume and take the median "
          f"({med/1e6:,.1f}m gallons)")
    out = d.rename(columns={"Latitude": "lat", "Longitude": "lon"})
    out["kind"] = "well"
    return out[["lat", "lon", "weight", "kind"]]


def counties(d):
    """Which county each point falls in, by the shape rather than the record.

    MSHA and EIA both carry a state and county of their own, in different
    codings and with their own errors.  The coordinate is the thing being used
    to place the point on the map, so the county is taken from the same
    coordinate: if the two ever disagree, what the map draws and what the map
    reconciles against stay the same thing.
    """
    g = gpd.read_file(f"zip://{COUNTIES}")
    g = g[~g.STATEFP.isin(DROP_STATES)].to_crs(4326).reset_index(drop=True)
    pts = gpd.GeoDataFrame(
        d, geometry=gpd.points_from_xy(d.lon, d.lat), crs=4326)
    hit = gpd.sjoin(pts, g[["GEOID", "geometry"]], how="left",
                    predicate="within")
    hit = hit[~hit.index.duplicated()]
    d = d.copy()
    d["county"] = hit.GEOID.to_numpy()
    lost = d.county.isna()
    if lost.any():
        print(f"  {int(lost.sum()):,d} points fell outside every county "
              "(offshore or a bad coordinate) and were dropped")
    return d[~lost]


def main():
    m, p, w = mines(), plants(), wells()
    out = counties(pd.concat([m, p, w], ignore_index=True))
    out.to_csv(DATA / "us_facility_points.csv", index=False)
    n = out.kind.value_counts()
    both = (set(out[out.kind == "mine"].county)
            & set(out[out.kind == "well"].county))
    print(f"  {len(both):,d} counties hold both mines and wells, and only "
          "there does the arithmetic converting the two units decide anything")
    print(f"-> data/land/us_facility_points.csv ({len(out):,d} points: "
          + ", ".join(
              f"{n.get(k, 0):,d} {k}s in "
              f"{out[out.kind == k].county.nunique():,d} counties"
              for k in ("mine", "plant", "well")) + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
