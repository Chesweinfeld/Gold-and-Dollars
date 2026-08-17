"""Where American GDP is produced, as finely as it is knowable.

There is no gridded measurement of GDP anywhere in the world.  The finest
official American figure is **county** GDP, published by the BEA for about
3,100 counties.  Everything below that is allocation, and this script is
explicit about which is which:

  measured    BEA county GDP, table CAGDP2, on twenty industry lines.
  allocated   within each county, by where the thing that produces it is:
              the jobs of that same industry for most of it, tract housing
              services for the output of dwellings, farmed hectares for the
              output of agriculture.

Jobs are the right allocator for most GDP in a way that population is not.
Output is produced where people work, so a downtown block with forty thousand
jobs and nobody living in it gets the output, and the subdivision that houses
them does not.  For 85.8% of GDP that is what happens here.

Crucially it is not *all* jobs at one rate.  LODES counts jobs in the same
twenty two-digit NAICS sectors that BEA reports GDP on, in every census block,
so each line rides the jobs of its own industry.  Nationally those rates run
from $66,580 a job in accommodation and food to $432,406 in information -- a
spread of six to one that a single county-wide rate flattened away.  Before
this, a refinery block and a school block in the same county received
identical output.

There are two large exceptions, and ignoring them left most of the country
blank -- 62% of the tiles that carry land value had no output at all.

CAGDP2 line 56, "Real estate and rental and leasing" -- $3.78tn, 13.8% of the
national total -- is mostly the output of dwellings: the rent tenants pay plus
the rent BEA imputes to owner-occupiers for living in their own houses.  That
output is produced by the house, on the ground the house stands on, and has
nothing to do with where the occupant goes to work.  Allocating it by jobs put
the whole housing stock's output in the office districts and left every suburb
and small town with a denominator of zero.  It goes by tract housing services
instead, from build_us_housing.py, spread inside the tract by the GHS-POP grid.

CAGDP2 line 3, agriculture, forestry, fishing and hunting, is produced on the
fields, and LODES cannot see it: the workplace file counts jobs covered by
unemployment insurance, which excludes farm proprietors and most farm labour.
What jobs the industry does record sit at the co-op in town.  It goes by
farmed hectares instead, from the USDA Cropland Data Layer by way of
src/land/build_us_farmland.py.

One place where BEA's lines and LODES's sectors do not mean the same thing,
and are pooled rather than matched: lines 69 and 70 are *private* education
and health, while the output of a state university or a county hospital sits
in line 83, government.  LODES draws no such line -- a public school's
teachers are in CNS15 with the private ones.  Matched one to one the error was
gross in both directions, government at $446,032 a job and education at
$6,019 in the median county.  The three lines are pooled and carried by the
three sectors together, which gives up telling a school from a hospital and
buys back not putting a public university's output in the county courthouse.

Four honest caveats.  Line 56 also holds commercial leasing and equipment
rental, which are not produced at homes; that part is misplaced by this
change, and it is the smaller part.  Line 3 holds fishing and hunting, which
are not produced on fields; the counties where that dominates are detected by
their absurd output per hectare and left with their jobs.  BEA suppresses at
least one line in most counties -- 1,122 for management of companies alone --
and each state residual is put back over that line's own carrier, which is
exact by state and approximate inside it.  And where a sector's work is not
at the worksite LODES reports -- mines, power plants, oil and gas wells --
three registers are added as carrier points by build_us_facilities.py, which
puts 57% of the mining line's weight on the ground rather than at the office.

What the allocation still cannot do is vary productivity within a county
*inside* one sector: two blocks of manufacturing jobs in the same county get
the same output per job, whether one is a chip fab and the other a sawmill.
That limit is stated on the figure.

Writes data/land/us_gdp_points.npz -- job blocks, population cells and
farmland cells, each carrying Albers coordinates and allocated GDP -- and
data/land/us_gdp_county_check.csv, which reconciles the allocation back to BEA
county by county.
"""

import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyproj
import rasterio
import rasterio.features
import rasterio.windows
from scipy.optimize import nnls

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
LODES = IN / "lodes"
POP_TIF = IN / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
COUNTIES = IN / "cb_2023_us_county_500k.zip"
TRACTS = IN / "cb_2023_us_tract_500k.zip"
TRACT_HOUSING = DATA / "us_tract_housing.csv"

YEAR = "2023"
ALBERS = "EPSG:5070"
BASE = "https://lehd.ces.census.gov/data/lodes/LODES8"

# CAGDP2 line codes.  Line 1 is the total everything must add back up to.
ALL, HOUSING, FARM = "1", "56", "3"

# BEA publishes county GDP on twenty industry lines, and LODES counts jobs in
# the same twenty two-digit NAICS sectors in every census block.  They match
# one for one, which is what lets output vary inside a county: a line is
# carried by the jobs of its own industry rather than by all jobs at one rate.
#
# The rates are wildly unequal -- as built, a job in accommodation and food
# carries $66,566 of output a year and one in mining, oil and gas $685,529,
# ten to one -- so the flat rate this replaced was putting a refinery's output
# on a school.  Every one of these figures is printed on each build, from the
# same arrays that do the allocating, so none of them can drift from the code.
#
# Two lines are not carried by their own jobs, for reasons set out at the top
# of this file, and their CNS column is recorded here only so the mapping can
# be read as complete:
#   line 3, agriculture -- LODES cannot see farm labour, so it goes on fields.
#   line 56, real estate -- the output is produced by dwellings, not by estate
#   agents.  Line 56 over CNS11 comes to $1,581,377 a job, which is not what an
#   estate agent produces; it is what the housing stock does.
#
# CNS02 carries mining, quarrying and oil and gas together, because that is how
# BEA reports it: there is no county split between the mine and the well.
SECTORS = {
    "3":  ("CNS01", "agriculture"),        "6":  ("CNS02", "mining, oil and gas"),
    "10": ("CNS03", "utilities"),          "11": ("CNS04", "construction"),
    "12": ("CNS05", "manufacturing"),      "34": ("CNS06", "wholesale trade"),
    "35": ("CNS07", "retail trade"),       "36": ("CNS08", "transport, warehousing"),
    "45": ("CNS09", "information"),        "51": ("CNS10", "finance, insurance"),
    "56": ("CNS11", "real estate, rental"), "60": ("CNS12", "professional, scientific"),
    "64": ("CNS13", "management of companies"),
    "65": ("CNS14", "administrative, waste"),
    "69": ("CNS15", "educational services"), "70": ("CNS16", "health, social assistance"),
    "76": ("CNS17", "arts, entertainment"), "79": ("CNS18", "accommodation, food"),
    "82": ("CNS19", "other services"),      "83": ("CNS20", "public administration"),
}
# The lines that ride their own sector's jobs: everything except the two above.
JOB_LINES = [k for k in SECTORS if k not in (FARM, HOUSING)]
CNS = [SECTORS[k][0] for k in JOB_LINES]

# One place where the one-to-one mapping is a lie, and has to be undone.
#
# BEA's lines 69 and 70 are *private* education and health.  The output of a
# state university or a county hospital is not there; it is in line 83,
# government.  LODES makes no such distinction: a public school's teachers are
# counted in CNS15 with the private ones, and CNS20 holds only NAICS 92,
# public administration proper.
#
# Mapped one to one, the error is large and visible in both directions --
# government came out at $446,032 a job against a $122,800 blended rate, and
# education at $23,443 nationally and $6,019 in the median county, which is
# not a wage bill let alone an output.  The three lines are therefore pooled
# and carried by the three sectors together.  That gives up telling a school
# from a hospital, and buys back not putting a public university's output in
# the county courthouse.
GROUPS = [(["69", "70", "83"], ["CNS15", "CNS16", "CNS20"],
           "education, health, government")]
GROUPS += [([k], [SECTORS[k][0]], SECTORS[k][1]) for k in JOB_LINES
           if k not in ("69", "70", "83")]
# Agriculture is read as an average of these years rather than of YEAR alone.
# County farm value added is net of costs and swings by an order of magnitude
# from year to year -- Jackson County, Kansas runs $2m, $16m, $17m, $2m over
# four consecutive years -- while land price capitalises the long run.  Only
# the *share* of a county's output attributed to farming is averaged; the
# county still receives exactly its BEA total for YEAR.
FARM_YEARS = [str(y) for y in range(2019, 2024)]
FARMLAND = DATA / "us_farmland_cells.npz"
# The land-cover classes build_us_farmland.py counts, in its own order.
# The land-cover classes come from build_us_farmland.py itself, so the two
# files cannot drift apart: adding a class there adds it here.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_us_farmland import KINDS          # noqa: E402
# The eight that grow a crop, and the three that feed an animal.  Which sales
# figure explains which ground is the whole point of splitting the fit.
CROP_KINDS = ("row", "smallgrain", "veg", "orchard", "nuts", "vine", "fallow")
GRAZE_KINDS = ("hay", "pasture", "range", "forest")
# Every class has to be in exactly one of the two fits, or ground would either
# be counted twice or silently produce nothing.
assert sorted(CROP_KINDS + GRAZE_KINDS) == sorted(KINDS), "class split is wrong"
AG_SALES = DATA / "us_ag_sales.csv"
FACILITIES = DATA / "us_facility_points.csv"
# How far above the national median output per farmed hectare a county may sit
# before its line 3 is treated as something other than farming.
FARM_CAP = 20

# A generous CONUS box in degrees, for the window taken out of the world
# population raster.  West, north, east, south.
CONUS_BOX = (-125.6, 49.6, -66.4, 24.0)

# The conterminous states plus DC.  Alaska and Hawaii are left out because the
# grid these blocks are binned onto is a CONUS Albers grid; they are 0.9% of
# US GDP between them and the figure says so.
STATES = """al ar az ca co ct dc de fl ga ia id il in ks ky la ma md me mi mn
mo ms mt nc nd ne nh nj nm nv ny oh ok or pa ri sc sd tn tx ut va vt wa wi wv
wy""".split()


def main():
    fetch()
    blocks = read_blocks()
    people, farms = pop_cells(), farm_cells()
    blocks = add_facilities(blocks)
    weights = {HOUSING: people.groupby("county").home.sum(),
               FARM: farms.groupby("county").ha.sum()}
    # Each job line is refilled, where BEA suppressed it, over the jobs of its
    # own sector in that county -- the same carrier it will be allocated on.
    for c in CNS:
        weights[c] = blocks.groupby("county")[c].sum()
    gdp = read_bea(weights)
    rate = farm_weight(farms, gdp)
    farms["ha"] = sum(r * farms[k] for r, k in zip(rate, KINDS))
    out, check = allocate(blocks, people, farms, gdp)

    x, y = pyproj.Transformer.from_crs(4326, ALBERS, always_xy=True).transform(
        out.lon.to_numpy(), out.lat.to_numpy())
    np.savez_compressed(
        DATA / "us_gdp_points.npz",
        x=x.astype("float32"), y=y.astype("float32"),
        gdp=out.gdp_usd.to_numpy().astype("float32"),
        weight=out.weight.to_numpy().astype("float32"),
        # 0 = a census block weighted by jobs, 1 = a population cell weighted
        # by people, 2 = a farmland cell weighted by hectares.  Kept so the
        # three can be told apart downstream.
        kind=out.kind.to_numpy().astype("uint8"),
    )
    check.to_csv(DATA / "us_gdp_county_check.csv", index=False)
    n = out.kind.value_counts()
    print(f"\n-> data/land/us_gdp_points.npz ({len(out):,d} points: "
          f"{n.get(0, 0):,d} job blocks, {n.get(1, 0):,d} population cells, "
          f"{n.get(2, 0):,d} farmland cells)")
    print(f"-> data/land/us_gdp_county_check.csv ({len(check):,d} BEA areas)")
    return 0


def fetch():
    """Two gzipped files per state: the jobs, and the block coordinates.

    Not every state publishes to the same year -- Michigan's latest LODES is
    2021 -- so each state gets its own most recent year at or before YEAR.
    That only shifts *where inside a county* the jobs sit; the county totals
    are still BEA's for YEAR, and the vintages are printed and written out.
    """
    LODES.mkdir(parents=True, exist_ok=True)
    years = {st: _latest(st) for st in STATES}
    stale = {st: y for st, y in years.items() if y != YEAR}
    if stale:
        print("LODES vintage below " + YEAR + ": " +
              ", ".join(f"{st.upper()} {y}" for st, y in sorted(stale.items())))
    (DATA / "us_gdp_lodes_vintage.csv").write_text(
        "state,lodes_year\n" + "".join(f"{st},{y}\n"
                                       for st, y in sorted(years.items())))
    want = []
    for st in STATES:
        want.append((f"{BASE}/{st}/wac/{st}_wac_S000_JT00_{years[st]}.csv.gz",
                     LODES / f"{st}_wac.csv.gz"))
        want.append((f"{BASE}/{st}/{st}_xwalk.csv.gz",
                     LODES / f"{st}_xwalk.csv.gz"))
    todo = [(u, p) for u, p in want if not p.exists()]
    if not todo:
        return
    print(f"fetching {len(todo)} LODES files ...")

    def one(job):
        url, path = job
        r = subprocess.run(["curl", "-sS", "--fail", "--max-time", "600",
                            "-o", str(path), url], capture_output=True, text=True)
        if r.returncode != 0:
            path.unlink(missing_ok=True)
            raise SystemExit(f"{url} failed: {r.stderr.strip()}")
    with ThreadPoolExecutor(8) as pool:
        list(pool.map(one, todo))


def _latest(st):
    """The newest workplace file a state has published, at or before YEAR."""
    r = subprocess.run(["curl", "-sS", "--fail", "--max-time", "60",
                        f"{BASE}/{st}/wac/"], capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"cannot list {st}: {r.stderr.strip()}")
    ys = sorted(re.findall(rf"{st}_wac_S000_JT00_(\d{{4}})\.csv\.gz", r.stdout))
    ys = [y for y in ys if y <= YEAR]
    if not ys:
        raise SystemExit(f"{st}: no workplace file at or before {YEAR}")
    return ys[-1]


def read_blocks():
    """Jobs and coordinates, joined block by block, state by state.

    Every one of the twenty NAICS sector counts is kept, not just the C000
    total.  They are the whole reason output can vary inside a county, and
    they cost nothing to read: they were already in the file.
    """
    frames = []
    for st in STATES:
        wac = pd.read_csv(LODES / f"{st}_wac.csv.gz",
                          usecols=["w_geocode", "C000"] + CNS,
                          dtype=dict({"w_geocode": str},
                                     **{c: "int32" for c in ["C000"] + CNS}))
        xw = pd.read_csv(LODES / f"{st}_xwalk.csv.gz",
                         usecols=["tabblk2020", "cty", "blklatdd", "blklondd"],
                         dtype={"tabblk2020": str, "cty": str})
        m = wac.merge(xw, left_on="w_geocode", right_on="tabblk2020", how="inner")
        m = m[(m.C000 > 0) & m.blklatdd.notna()]
        f = pd.DataFrame({
            "county": m.cty.str.zfill(5).to_numpy(),
            "lat": m.blklatdd.to_numpy(),
            "lon": m.blklondd.to_numpy(),
            "jobs": m.C000.to_numpy(),
        })
        for c in CNS:
            f[c] = m[c].to_numpy()
        frames.append(f)
        lost = len(wac) - len(m)
        if lost > 0.01 * len(wac):
            print(f"  {st}: {lost:,d} of {len(wac):,d} job blocks had no "
                  "coordinate and were dropped")
    b = pd.concat(frames, ignore_index=True)
    # The twenty sectors should account for the total.  Where they do not --
    # LODES suppresses a little at block level -- the shortfall rides the
    # unsectored remainder, which is allocated with everything else that has
    # no sector of its own.
    b["other"] = np.maximum(
        b.jobs.to_numpy() - b[CNS].to_numpy().sum(axis=1), 0)
    print(f"{len(b):,d} census blocks with jobs, {b.jobs.sum()/1e6:,.1f}M jobs "
          f"in {b.county.nunique():,d} counties")
    print(f"  {b[CNS].to_numpy().sum()/1e6:,.1f}M of them fall in the "
          f"{len(CNS)} sectors carried by their own industry; "
          f"{b.other.sum()/1e6:,.1f}M are unsectored or agricultural")
    return b


def add_facilities(blocks):
    """Mines and power plants, as extra carrier points for their own sector.

    LODES puts a job at the worksite the employer reports, which for a mining
    company or a utility is routinely the head office.  MSHA counts a mine's
    employees at the mine and EIA-860 puts every generator at its plant, so
    those two registers are appended here as further points carrying CNS02 and
    CNS03 -- and nothing else.

    Their `jobs` is left at zero deliberately.  That column carries the
    unsectored remainder and the state spill, neither of which has anything to
    do with a coal seam, and inflating it would quietly move money that
    belongs to the rest of the county.

    Capacity is converted to jobs at the national ratio of utility jobs to
    installed megawatts, so that a plant and a LODES block are weighed in one
    unit.  The ratio is printed, because it is the one number here that is a
    choice rather than a measurement.
    """
    if not FACILITIES.exists():
        sys.exit(f"missing {FACILITIES} -- run src/land/build_us_facilities.py")
    f = pd.read_csv(FACILITIES, dtype={"county": str})
    mw = f.loc[f.kind == "plant", "weight"].sum()
    gal = f.loc[f.kind == "well", "weight"].sum()
    # Capacity and frac water are not headcounts, so each is put on the job
    # scale by the national ratio of its sector's jobs to its own total.  Mine
    # employment needs no conversion: MSHA counts people.
    per_mw = blocks.CNS03.sum() / mw if mw > 0 else 0.0
    per_gal = blocks.CNS02.sum() / gal if gal > 0 else 0.0
    f["w"] = np.select(
        [f.kind == "plant", f.kind == "well"],
        [f.weight * per_mw, f.weight * per_gal],
        default=f.weight)

    add = pd.DataFrame({"county": f.county.to_numpy(),
                        "lat": f.lat.to_numpy(), "lon": f.lon.to_numpy(),
                        "jobs": 0.0})
    for c in CNS:
        add[c] = 0.0
    # Wells ride CNS02 with the mines: BEA reports mining, quarrying and oil
    # and gas as one line and does not break it out, so one carrier serves it.
    add["CNS02"] = np.where(f.kind.isin(["mine", "well"]), f.w, 0.0)
    add["CNS03"] = np.where(f.kind == "plant", f.w, 0.0)
    add["other"] = 0.0

    print(f"facilities: {int((f.kind == 'mine').sum()):,d} mines carrying "
          f"{f.loc[f.kind == 'mine', 'w'].sum():,.0f} employees, "
          f"{int((f.kind == 'plant').sum()):,d} plants carrying "
          f"{mw/1000:,.0f} GW, and {int((f.kind == 'well').sum()):,d} wells "
          f"carrying {gal/1e9:,.0f}bn gallons")
    print(f"  a megawatt of nameplate capacity is weighed as {per_mw:.2f} "
          f"utility jobs ({blocks.CNS03.sum():,.0f} CNS03 jobs over {mw/1000:,.0f} GW)")
    print(f"  a million gallons of frac water is weighed as {per_gal*1e6:.2f} "
          f"mining jobs ({blocks.CNS02.sum():,.0f} CNS02 jobs over "
          f"{gal/1e9:,.0f}bn gallons)")
    for c, name in (("CNS02", "mining"), ("CNS03", "utilities")):
        was = blocks[c].sum()
        print(f"  {name}: {was:,.0f} LODES jobs plus {add[c].sum():,.0f} at the "
              f"sites, so {add[c].sum()/(was + add[c].sum()):.0%} of that "
              "sector's weight now sits where the work is")
    return pd.concat([blocks, add], ignore_index=True)


def read_bea(weights):
    """County GDP in total, and the two lines that are allocated differently.

    BEA publishes the all-industry total for every county but withholds an
    industry line wherever disclosing it would identify a firm -- 730 counties
    for real estate, all small.  They are not droppable: they are exactly the
    rural ground this split exists to give a denominator to.  The state total
    less its reported counties is the amount withheld, and it is put back
    across that state's suppressed counties in proportion to the same carrier
    the line will be allocated over -- people for housing, farmed hectares for
    agriculture.  Exact by state, approximate inside it, and printed.

    Filling by all-industry GDP instead, which was the obvious first guess, is
    wrong in a way worth naming: Storey County, Nevada has a car factory, 1,100
    residents and a suppressed real-estate line, and a GDP-weighted fill handed
    its housing $264,000 of output per resident.
    """
    f = IN / "bea" / "CAGDP2__ALL_AREAS_2001_2024.csv"
    d = pd.read_csv(f, dtype=str, encoding="latin-1", on_bad_lines="skip")
    d["fips"] = d.GeoFIPS.str.strip().str.strip('"')
    d["v"] = pd.to_numeric(d[YEAR], errors="coerce") * 1000.0
    keep = sorted({_st(s) for s in STATES})
    d = d[d.fips.str[:2].isin(keep) & (d.fips.str.len() == 5)]

    cty = d[d.fips.str[2:] != "000"]
    tot = cty[cty.LineCode == ALL]
    out = tot[["fips", "GeoName", "v"]].rename(
        columns={"GeoName": "name", "v": "gdp_usd"})
    out = out[out.gdp_usd.notna()].copy()
    out["st"] = out.fips.str[:2]

    print(f"BEA {YEAR}: {len(out):,d} areas, ${out.gdp_usd.sum()/1e12:,.2f}tn")
    for line, col, what in ((HOUSING, "housing_usd", "real estate"),
                            (FARM, "farm_usd", "agriculture")):
        out[col] = _line(d, cty, out, col, line, what, weights[line])
    # The two named lines are read on different terms from the total -- one is
    # filled from a state residual, the other is an average of five years -- so
    # nothing guarantees they fit inside it.  In the handful of counties where
    # they do not, both are scaled back to leave the rest of the economy at
    # zero rather than negative.
    over = (out.housing_usd + out.farm_usd) / out.gdp_usd
    if (over > 1).any():
        k = np.where(over > 1, 1.0 / over, 1.0)
        print(f"  {int((over > 1).sum())} counties where the two named lines "
              f"exceed the county total; both scaled back to fit")
        out["housing_usd"] *= k
        out["farm_usd"] *= k

    # The other eighteen lines, each filled over its own sector's jobs where
    # BEA has suppressed it.  Suppression is much commoner here than for the
    # two big lines -- a county with one sawmill has its manufacturing line
    # withheld -- so the state residual does a lot of work, and how much is
    # printed line by line.
    print(f"  and the {len(JOB_LINES)} lines carried by their own sector, "
          f"in {len(GROUPS)} groups:")
    for lines, cols, what in GROUPS:
        # A line suppressed by BEA is refilled over the same jobs that will
        # carry it, which for a pooled group means the group's jobs together.
        w = sum(weights[c] for c in cols)
        for line in lines:
            label = what if len(lines) == 1 else f"{what} [{line}]"
            out[f"L{line}"] = _line(d, cty, out, f"L{line}", line,
                                    f"  {label}", w, quiet=True)
    named = out[[f"L{line}" for line in JOB_LINES]].sum(axis=1) \
        + out.housing_usd + out.farm_usd
    # Nothing forces twenty separately-filled lines to add to the county total.
    # Where they overshoot they are scaled back; where they fall short the
    # remainder is carried by all of the county's jobs, as it was before any
    # of this.  Either way the county still receives exactly its BEA figure.
    k = np.where(named > out.gdp_usd, out.gdp_usd / named.replace(0.0, np.nan), 1.0)
    k = np.nan_to_num(k, nan=1.0)
    for c in [f"L{line}" for line in JOB_LINES] + ["housing_usd", "farm_usd"]:
        out[c] *= k
    named = named * k
    out["rest_usd"] = (out.gdp_usd - named).clip(lower=0.0)
    print(f"  {int((k < 1).sum()):,d} counties where the twenty lines "
          f"overshot the total and were scaled back "
          f"({1 - float(k.mean()):.2%} on average)")
    print(f"  ${out.rest_usd.sum()/1e12:,.3f}tn "
          f"({out.rest_usd.sum()/out.gdp_usd.sum():.1%}) is left unsectored "
          "and rides all of a county's jobs")
    return out.drop(columns="st")


def _line(d, cty, out, col, line, what, weight, quiet=False):
    """One CAGDP2 industry line per county, with suppression filled in."""
    out = out.copy()
    src = cty[cty.LineCode == line].set_index("fips")
    years = FARM_YEARS if line == FARM else [YEAR]
    v = src[years].apply(pd.to_numeric, errors="coerce").mean(axis=1) * 1000.0
    out[col] = out.fips.map(v)
    missing = out[col].isna()

    states = d[(d.fips.str[2:] == "000") & (d.LineCode == line)]
    sv = states[years].apply(pd.to_numeric, errors="coerce").mean(axis=1) * 1000.0
    held = (sv.groupby(states.fips.str[:2]).first()
            .reindex(out.st.unique()).fillna(0.0)
            - out.groupby("st")[col].sum()).clip(lower=0.0)
    share = out.fips.map(weight).fillna(0.0).where(missing, 0.0)
    denom = share.groupby(out.st).transform("sum").replace(0.0, np.nan)
    out.loc[missing, col] = (out.st.map(held) * share / denom)[missing]
    v = out[col].fillna(0.0).clip(lower=0.0)

    if quiet:
        print(f"  {what:34s} ${v.sum()/1e12:6,.3f}tn  "
              f"{int(missing.sum()):>5,d} counties suppressed, "
              f"${held.sum()/1e9:>6,.0f}bn refilled")
    else:
        print(f"  {what} (line {line}) ${v.sum()/1e12:,.3f}tn, "
              f"{v.sum()/out.gdp_usd.sum():.1%} of it; {int(missing.sum()):,d} "
              f"counties suppressed, filled from the state residual "
              f"(${held.sum()/1e9:,.0f}bn)")
    return v


def pop_cells():
    """Resident population on the GHS-POP grid, tagged by census tract.

    30 arc-seconds is about 800 m at these latitudes, so roughly twenty cells
    fall in each 3.84 km tile of the national cut -- fine enough that the
    housing allocation varies within a town, coarse enough that it should not
    be cut at 480 m without saying so.

    Tracts rather than counties, because the county is the thing that had to be
    got away from: a county's output of housing used to be spread over its
    residents at one rate, and inside a county the tracts differ in housing
    services by a median factor of four.  The county is still recovered, from
    the first five digits of the tract, so nothing downstream changes.
    """
    for p in (POP_TIF, TRACTS, TRACT_HOUSING):
        if not p.exists():
            raise SystemExit(f"missing {p} -- run src/land/fetch_inputs.py "
                             "and src/land/build_us_housing.py")
    src = rasterio.open(POP_TIF)
    w, n, e, s = CONUS_BOX
    r0, c0 = src.index(w, n)
    r1, c1 = src.index(e, s)
    win = rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0)
    pop = src.read(1, window=win).astype("float64")
    pop = np.where(np.isfinite(pop) & (pop > 0), pop, 0.0)
    tr = src.window_transform(win)

    g = gpd.read_file(f"zip://{TRACTS}")
    g = g[g.STATEFP.isin(sorted({_st(s) for s in STATES}))].reset_index(drop=True)
    idx = rasterio.features.rasterize(
        ((geom, i + 1) for i, geom in enumerate(g.to_crs(4326).geometry)),
        out_shape=pop.shape, transform=tr, fill=0, dtype="int32")

    iy, ix = np.nonzero((idx > 0) & (pop > 0))
    lon, lat = rasterio.transform.xy(tr, iy, ix)
    d = pd.DataFrame({
        "tract": g.GEOID.to_numpy()[idx[iy, ix] - 1],
        "lat": np.asarray(lat), "lon": np.asarray(lon),
        "pop": pop[iy, ix],
    })
    d["county"] = d.tract.str[:5]

    # Each tract's housing services, spread over the people in it.  Summed to
    # a county this is still the county's figure; inside one it now varies.
    h = pd.read_csv(TRACT_HOUSING, dtype={"tract": str}).set_index("tract")
    serv = d.tract.map(h.services)
    share = d["pop"] / d.groupby("tract")["pop"].transform("sum")
    d["home"] = (serv * share).fillna(0.0)
    # A tract the survey said nothing about falls back to headcount, which is
    # what every tract used to get.
    blank = d.home <= 0
    if blank.any():
        d.loc[blank, "home"] = d["pop"][blank]
    print(f"{len(d):,d} population cells, {d['pop'].sum()/1e6:,.1f}M people "
          f"in {d.tract.nunique():,d} tracts and {d.county.nunique():,d} "
          f"counties; {int(blank.sum()):,d} cells had no tract housing figure "
          "and fall back to headcount")
    return d


def farm_cells():
    """Farmed hectares per 1.92 km cell, built by src/land/build_us_farmland.py.

    Kept in its own file because it comes out of a 3.3 GB raster and takes
    minutes; this script only reads the result.
    """
    if not FARMLAND.exists():
        raise SystemExit(f"missing {FARMLAND} -- run "
                         "src/land/build_us_farmland.py first")
    z = np.load(FARMLAND)
    lon, lat = pyproj.Transformer.from_crs(ALBERS, 4326, always_xy=True
                                           ).transform(z["x"], z["y"])
    d = pd.DataFrame({"county": z["county"], "lat": lat, "lon": lon})
    for k in KINDS:
        d[k] = z[f"{k}_ha"]
    d["ha"] = d[list(KINDS)].sum(axis=1)
    print(f"{len(d):,d} land-cover cells, {d.ha.sum()/1e6:,.1f}M hectares ("
          + ", ".join(f"{d[k].sum()/1e6:,.0f}M {k}" for k in KINDS)
          + f") in {d.county.nunique():,d} counties")
    return d


# When the fit cannot identify a class, it collapses into its sibling rather
# than into whatever happens to cover the most ground.  Almonds fall back to
# orchards, not to the corn belt; sagebrush falls back to pasture, not to the
# vineyards.  The three roots -- row, orchard, pasture -- have nowhere to fall.
# Grazing runs hay -> pasture -> range -> forest, so a class the fit cannot
# identify falls back on rougher ground rather than on the cropland it happens
# to sit beside.  row, orchard and forest are the roots and have nowhere left
# to fall; if one of those is zeroed the build says so loudly instead.
SIBLING = {"smallgrain": "row", "fallow": "row", "veg": "row",
           "nuts": "orchard", "vine": "orchard",
           "hay": "pasture", "pasture": "range", "range": "forest"}


def _fit(a, b, kinds):
    """Non-negative least squares that refuses to leave a class at zero.

    Least squares with a non-negativity constraint answers an ill-posed
    question by putting a coefficient on the boundary.  Where two classes
    almost always occur together -- almonds beside orchards and vines in the
    same Central Valley counties, sagebrush beside pasture across the same
    western ranges -- the fit cannot separate them, and says so by handing one
    of them nothing at all.

    Zero is not a neutral answer here.  A class at zero carries none of its
    county's farm output, which is the artefact this carrier exists to remove:
    rangeland drawn as producing nothing while identical ground next door,
    which the classifier happened to call pasture, takes the county's whole
    allocation.

    So a class the fit zeroes is folded into its sibling in SIBLING and the
    two are refitted as one column, repeatedly until nothing is left at zero.
    That gives up telling an almond from an apple, which the data cannot
    support, rather than asserting that almonds grow for free.  Every fold is
    returned and printed.
    """
    pos = {k: i for i, k in enumerate(kinds)}
    # Each class starts in its own bucket; folding merges buckets.
    bucket = {k: k for k in kinds}
    folds = []
    for _ in range(len(kinds)):
        names = sorted(set(bucket.values()))
        cols = np.column_stack(
            [a[:, [pos[k] for k in kinds if bucket[k] == n]].sum(axis=1)
             for n in names])
        r, _ = nnls(cols, b)
        dead = [n for n, v in zip(names, r) if v <= 0]
        # A bucket can only fold if something in it still has somewhere to go.
        movable = [n for n in dead
                   if any(bucket[k] == n and k in SIBLING for k in kinds)]
        if not movable:
            rate = {n: v for n, v in zip(names, r)}
            return np.array([rate[bucket[k]] for k in kinds]), folds
        for n in movable:
            members = [k for k in kinds if bucket[k] == n]
            # Follow the sibling chain out of this bucket.
            target = None
            for k in members:
                t = SIBLING.get(k)
                while t is not None and bucket[t] == n:
                    t = SIBLING.get(t)
                if t is not None:
                    target = bucket[t]
                    break
            if target is None:
                continue
            folds.append((sorted(members), target))
            for k in members:
                bucket[k] = target
    rate = {n: v for n, v in zip(sorted(set(bucket.values())), r)}
    return np.array([rate[bucket[k]] for k in kinds]), folds


def farm_weight(farms, gdp):
    """What a hectare of each kind of ground earns, fitted rather than asserted.

    Spreading a county's farm output evenly over its acres treats an almond
    orchard the same as sagebrush, which draws the county as one flat colour
    and leaves the boundary visible against its neighbour.  So a rate is
    fitted per class of ground, by non-negative least squares of county output
    on the hectares of each class, weighted by 1/sqrt(hectares) so that a
    handful of enormous western counties do not decide the whole country.

    Two fits, against two different measures, because one measure cannot do
    both jobs.

    The crop classes are fitted against the Census of Agriculture.  It counts
    gross sales at every farm in the country and separates them by commodity,
    which is what makes an almond distinguishable from an acre of wheat; BEA
    line 3 is value added net of costs and swings by an order of magnitude
    year to year in one county.

    The grazing classes cannot be fitted that way, and it took three attempts
    to accept it.  Regressed on census sales -- animal sales alone, or total
    sales -- pasture, range and forest all come out at exactly zero, and the
    animal-only fit scores R2 -0.278, worse than predicting the mean.  The
    reason is real rather than numerical: the animals that earn the most are
    raised in confinement, in poultry houses and hog barns that the crop map
    sees as a building, so hectares of grass genuinely do not predict what a
    county sells.  Zero is nonetheless the one answer that cannot be shipped,
    because it hands a Wyoming ranching county's whole allocation to whatever
    scrap of cropland it has.

    So the grazing classes are fitted against BEA line 3 itself -- the thing
    actually being spread, which counts grazing and forestry value added -- with
    the crop classes collapsed into a single column carrying their fitted
    shape.  That column's coefficient converts the census's gross-sales units
    into line 3's value-added units, so the two halves end up on one scale.
    Five columns instead of eleven, and no collinearity left to speak of.

    Fitting is still what makes it safe to count range and forest at all.  Any
    class the crop fit cannot identify is folded into its sibling and told to
    share the rate, and every fold is printed.
    """
    if not AG_SALES.exists():
        sys.exit(f"missing {AG_SALES} -- run src/land/build_us_ag_sales.py")
    sales = pd.read_csv(AG_SALES, dtype={"fips": str}).set_index("fips")
    by = farms.groupby("county")[list(KINDS)].sum()

    # 1. The crop classes, against what the census says crops sold for.
    j = by.join(sales["crop_usd"], how="inner")
    tot = j[list(CROP_KINDS)].sum(axis=1)
    m = ((j.crop_usd > 0) & (tot > 0)).to_numpy()
    w = np.sqrt(1.0 / tot.to_numpy()[m])
    crop_rate, folds = _fit(j[list(CROP_KINDS)].to_numpy()[m] * w.reshape(-1, 1),
                            j.crop_usd.to_numpy()[m] * w, list(CROP_KINDS))
    obs = j.crop_usd.to_numpy()[m]
    pred = j[list(CROP_KINDS)].to_numpy()[m] @ crop_rate
    r2c = 1.0 - ((obs - pred) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()
    print(f"  crop rates fitted across {int(m.sum()):,d} counties against "
          f"${obs.sum()/1e9:,.0f}bn of census crop sales, R2 {r2c:.3f}")

    # 2. The grazing classes, against BEA line 3, with the crop shape carried
    #    as one column whose coefficient rescales it into value-added dollars.
    k = by.join(gdp.set_index("fips").farm_usd, how="inner")
    cropcol = k[list(CROP_KINDS)].to_numpy() @ crop_rate
    graze = k[list(GRAZE_KINDS)].to_numpy()
    tot = k[list(KINDS)].sum(axis=1).to_numpy()
    m = (k.farm_usd.to_numpy() > 0) & (tot > 0)
    w = np.sqrt(1.0 / tot[m])
    a = np.column_stack([cropcol[m]] + [graze[m, i]
                                        for i in range(len(GRAZE_KINDS))])
    r, _ = nnls(a * w.reshape(-1, 1), k.farm_usd.to_numpy()[m] * w)
    scale = r[0]
    # Refit the grazing classes alone on what the crop column does not
    # explain, so that they get the same fold-on-zero protection the crop fit
    # has.  Without it pasture came out at zero -- 134M hectares of grass
    # carrying none of their counties' farming.
    resid = np.clip(k.farm_usd.to_numpy()[m] - scale * cropcol[m], 0.0, None)
    graze_rate, gfolds = _fit(graze[m] * w.reshape(-1, 1), resid * w,
                              list(GRAZE_KINDS))
    folds = folds + gfolds
    obs = k.farm_usd.to_numpy()[m]
    pred = scale * cropcol[m] + graze[m] @ graze_rate
    r2g = 1.0 - ((obs - pred) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()
    print(f"  grazing rates fitted across {int(m.sum()):,d} counties against "
          f"${obs.sum()/1e9:,.0f}bn of BEA line {FARM}, R2 {r2g:.3f}")
    print(f"    a dollar of census crop sales carries ${scale:,.3f} of line "
          f"{FARM} value added")

    rate = pd.Series(0.0, index=list(KINDS))
    rate[list(CROP_KINDS)] = crop_rate * scale
    rate[list(GRAZE_KINDS)] = graze_rate
    for kind in KINDS:
        print(f"    {kind:11s} ${rate[kind]:>8,.0f} a hectare a year")
    for members, target in folds:
        print("    the fit could not separate " + ", ".join(members)
              + f" from {target}; they share its rate")
    if (rate <= 0).any():
        print("    !! " + ", ".join(k for k in KINDS if rate[k] <= 0)
              + " carry no weight at all -- their ground will take none of "
              "its county's farm output")
    return rate.reindex(list(KINDS)).to_numpy()


def allocate(blocks, people, farms, gdp):
    """County GDP over its carriers: each industry line on what produces it.

    Eighteen lines ride the jobs of their own NAICS sector, so a block of
    refinery jobs and a block of classroom jobs in the same county no longer
    receive the same output.  Agriculture goes on the farmland and the output
    of dwellings goes on the people, for the reasons at the top of this file.
    Whatever the twenty lines do not account for rides all of a county's jobs.

    Nothing is allowed to go missing.  A county with money in a sector but no
    jobs in it -- which happens wherever BEA's suppression fill put money
    somewhere LODES sees no worksite -- hands that money down a chain: to all
    of its jobs, then to its people, then to its fields.  Each county still
    adds back to its BEA figure exactly, and the check file proves it county
    by county.

    A dozen BEA areas are combinations -- Virginia's independent cities are
    reported with the county that surrounds them -- so their FIPS matches no
    census block.  Rather than hard-code the membership list, whatever GDP does
    not match a county is pooled at the state level and spread over that
    state's remaining jobs.  That is exact in state aggregate, approximate
    inside it, and the check file reports how much went that way.
    """
    gdp = gdp.copy()
    gdp["jobs"] = gdp.fips.map(blocks.groupby("county").jobs.sum()).fillna(0.0)
    gdp["pop"] = gdp.fips.map(people.groupby("county").home.sum()).fillna(0.0)
    gdp["farm_ha"] = gdp.fips.map(farms.groupby("county").ha.sum()).fillna(0.0)

    has_job = gdp.jobs.to_numpy() > 0
    has_pop = gdp["pop"].to_numpy() > 0
    has_ha = gdp.farm_ha.to_numpy() > 0

    # Line 3 is agriculture, forestry, fishing *and hunting*, and in a few
    # counties it is mostly the ones that are not farming: the Florida Keys
    # land their catch in Monroe County, which the Cropland Data Layer sees as
    # 42 hectares of field.  Where the implied output per hectare comes out
    # more than FARM_CAP times the national median, the fields plainly are not
    # producing it, and that county's line 3 is left with its jobs.
    rate = np.divide(gdp.farm_usd.to_numpy(), gdp.farm_ha.to_numpy(),
                     out=np.zeros(len(gdp)), where=has_ha)
    wild = has_ha & (rate > FARM_CAP * np.median(rate[has_ha]))
    has_ha = has_ha & ~wild
    if wild.any():
        print(f"  {int(wild.sum())} counties produce more than {FARM_CAP}x the "
              f"median per farmed hectare (${gdp.farm_usd[wild].sum()/1e9:,.1f}bn, "
              f"{gdp.farm_usd[wild].sum()/gdp.farm_usd.sum():.1%} of line {FARM}"
              "); their agriculture stayed with their jobs")

    house = np.where(has_pop, gdp.housing_usd, 0.0)
    farm = np.where(has_ha, gdp.farm_usd, 0.0)
    # Everything the two carriers above did not take becomes general work
    # money, on top of the unsectored remainder BEA never assigned.
    loose = (gdp.housing_usd.to_numpy() - house) + (gdp.farm_usd.to_numpy() - farm)
    pool = gdp.rest_usd.to_numpy() + loose

    # Each sector on its own jobs.  Where a county has money in a sector but
    # no jobs in it, that money falls into the general pool instead.
    blocks = blocks.copy()
    blocks["gdp_usd"] = 0.0
    idx = pd.Index(gdp.fips.values)
    per_job = {}
    for lines, cols, what in GROUPS:
        money = gdp[[f"L{line}" for line in lines]].sum(axis=1).to_numpy()
        who = blocks[cols].sum(axis=1) if len(cols) > 1 else blocks[cols[0]]
        jobs = gdp.fips.map(who.groupby(blocks.county).sum()
                            ).fillna(0.0).to_numpy()
        stranded = jobs <= 0
        pool += np.where(stranded, money, 0.0)
        money = np.where(stranded, 0.0, money)
        r = pd.Series(np.divide(money, jobs, out=np.zeros_like(money),
                                where=jobs > 0), index=idx)
        blocks["gdp_usd"] += who * blocks.county.map(r).fillna(0.0)
        live = r[r > 0]
        per_job[what] = (money.sum(), jobs.sum(),
                         live.median() if len(live) else 0.0)

    # The pool, down the chain: all jobs, then people, then fields.
    work = np.where(has_job, pool, 0.0)
    left = pool - work
    move = np.where(~has_job & has_pop, left, 0.0)
    house, left = house + move, left - move
    move = np.where(~has_job & has_ha, left, 0.0)
    farm = farm + move
    matched = has_job | has_pop | has_ha

    # Both operands stay numpy: handing np.divide a pandas Series as `where`
    # makes it return a Series indexed 0..n, and pd.Series(series, index=idx)
    # then *reindexes* by FIPS rather than assigning positionally, which
    # silently yields all-NaN and loses the whole remainder.
    njobs = gdp.jobs.to_numpy()
    r = pd.Series(np.divide(work, njobs, out=np.zeros_like(work),
                            where=njobs > 0), index=idx)
    blocks["gdp_usd"] += blocks.jobs * blocks.county.map(r).fillna(0.0)

    rates, out = {"job": r}, [blocks]
    for name, frame, w, money in (("head", people, "home", house),
                                  ("hectare", farms, "ha", farm)):
        weight = gdp[{"home": "pop", "ha": "farm_ha"}[w]].to_numpy()
        rate = pd.Series(np.divide(money, weight, out=np.zeros_like(money),
                                   where=weight > 0), index=idx)
        frame = frame.copy()
        frame["gdp_usd"] = frame[w] * frame.county.map(rate).fillna(0.0)
        rates[name] = rate
        out.append(frame)
    blocks, people, farms = out

    # Whatever is left over in each state, spread across that state's jobs.
    blocks["st"] = blocks.county.str[:2]
    spill = gdp[~matched].groupby(gdp.fips.str[:2]).gdp_usd.sum()
    if len(spill):
        st_jobs = blocks.groupby("st").jobs.sum()
        rr = (spill / st_jobs.reindex(spill.index)).fillna(0.0)
        blocks["gdp_usd"] += blocks.jobs * blocks.st.map(rr).fillna(0.0)
        print(f"  {int((~matched).sum())} BEA areas matched no county "
              f"(${spill.sum()/1e9:,.0f}bn, {spill.sum()/gdp.gdp_usd.sum():.2%} "
              "of the total); spread over their state's jobs instead")

    # Every dollar BEA reported has to be sitting on one of the three
    # carriers.  A NaN rate would silently become a zero at the .fillna()
    # above and quietly lose a county, so the books are cast here and any
    # discrepancy is named rather than rounded past.
    for label, arr in (("sector money", pool), ("housing", house),
                       ("farm", farm), ("work", work)):
        n = int(np.isnan(arr).sum())
        if n:
            print(f"  !! {n:,d} counties have a NaN {label} figure")
    tot = sum(f.gdp_usd.sum() for f in (blocks, people, farms))
    gap = gdp.gdp_usd.sum() - tot
    print(f"allocated ${tot/1e12:,.2f}tn against ${gdp.gdp_usd.sum()/1e12:,.2f}tn "
          f"of BEA GDP ({tot/gdp.gdp_usd.sum():.4%})")
    if abs(gap) > 0.001 * gdp.gdp_usd.sum():
        print(f"  !! ${gap/1e9:,.1f}bn unaccounted for -- this should be zero")
    for label, frame in (("jobs", blocks), ("people", people),
                         ("farmland", farms)):
        print(f"  ${frame.gdp_usd.sum()/1e12:6,.2f}tn over {label:9s} "
              f"({frame.gdp_usd.sum()/tot:5.1%}) on {len(frame):>9,d} points")

    # What each sector pays a job, nationally and in the median county.  This
    # is the table that justifies the whole split: if these were all alike,
    # one flat rate would have been right.
    print("  output per job, by sector -- national, and the median county:")
    for what, (money, jobs, med) in sorted(
            per_job.items(), key=lambda kv: -(kv[1][0] / max(kv[1][1], 1))):
        nat = money / jobs if jobs else 0.0
        print(f"    {what:28s} ${nat:>9,.0f}   ${med:>9,.0f}")
    live = rates["job"][rates["job"] > 0]
    print(f"  the unsectored remainder pays ${live.min():,.0f} to "
          f"${live.max():,.0f} a job, median ${live.median():,.0f}")
    # Housing and farming are both weighted in dollars of a fitted prediction,
    # so their rates are multipliers on it rather than prices: 1.0 means the
    # county earns exactly what the survey and the crop map say it should.
    live = rates["head"][rates["head"] > 0]
    print(f"  a county's housing earns {live.min():.2f} to {live.max():.1f} "
          f"times what its tracts' rents predict, median {live.median():.2f}")
    # The farm weight is already in dollars of fitted output, so this rate is
    # a multiplier on the national fit rather than a price: 1.0 means the
    # county earns exactly what its mix of land cover predicts.
    live = rates["hectare"][rates["hectare"] > 0]
    print(f"  a county earns {live.min():.2f} to {live.max():.1f} times what "
          f"its land cover predicts, median {live.median():.2f}")

    got = pd.concat([f.groupby("county").gdp_usd.sum()
                     for f in (blocks, people, farms)]).groupby(level=0).sum()
    check = gdp[["fips", "name", "gdp_usd", "housing_usd", "farm_usd",
                 "rest_usd", "jobs", "pop", "farm_ha"]].copy()
    check["allocated_usd"] = check.fips.map(got).fillna(0.0)
    check["matched"] = matched

    cols = ["lat", "lon", "weight", "kind", "gdp_usd"]
    for k, (frame, w) in enumerate(((blocks, "jobs"), (people, "home"),
                                    (farms, "ha"))):
        frame["kind"] = np.uint8(k)
        frame["weight"] = frame[w].astype(float)
    return pd.concat([blocks[cols], people[cols], farms[cols]],
                     ignore_index=True), check


def _state_fips():
    return STATES


def _st(abbr):
    return {
        "al": "01", "ar": "05", "az": "04", "ca": "06", "co": "08", "ct": "09",
        "dc": "11", "de": "10", "fl": "12", "ga": "13", "ia": "19", "id": "16",
        "il": "17", "in": "18", "ks": "20", "ky": "21", "la": "22", "ma": "25",
        "md": "24", "me": "23", "mi": "26", "mn": "27", "mo": "29", "ms": "28",
        "mt": "30", "nc": "37", "nd": "38", "ne": "31", "nh": "33", "nj": "34",
        "nm": "35", "nv": "32", "ny": "36", "oh": "39", "ok": "40", "or": "41",
        "pa": "42", "ri": "44", "sc": "45", "sd": "46", "tn": "47", "tx": "48",
        "ut": "49", "va": "51", "vt": "50", "wa": "53", "wi": "55", "wv": "54",
        "wy": "56",
    }[abbr]


if __name__ == "__main__":
    sys.exit(main())
