"""Download the land-value inputs.

Five sources, all public:

  World Bank, Changing Wealth of Nations (API source 59) -- cropland and
      pastureland value, and produced capital with and without urban land,
      150 countries, 1995-2020, current US$.
  World Bank, WDI -- GDP, population, exchange rates.
  OECD, Table 9B "Balance sheets for non-financial assets" (SDMX) -- land
      (asset N211N) at current prices, national currency, for the countries
      whose national accounts actually measure it.
  Natural Earth -- country boundaries (110m), the 4,596 admin-1 units (10m),
      and populated places (10m), used to label the deformed maps.
  Nolte (2020) PLACES -- fair market value of land for every 480 m cell of the
      conterminous US, from six million sales.  299 MB; only
      make_us_cartogram.py needs it, and it is not committed.
  JRC GHS-POP R2023A -- population on a 30 arc-second grid, 2020.  480 MB;
      only build_subnational.py needs it, and it is not committed.

Writes data/land/inputs/.  Nothing here is derived; that is build_land_value.py.
"""

import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data" / "land" / "inputs"

WEALTH = [
    "NW.NCA.CROP.TO.CD",  # cropland
    "NW.NCA.PAST.TO.CD",  # pastureland
    "NW.NCA.AGRI.TO.CD",  # agricultural land, total
    "NW.PCA.TO.EX.CD",  # produced capital, excluding urban land
    "NW.PCA.TO.IN.CD",  # produced capital, including urban land
]

WDI = {
    "NY.GDP.MKTP.CD": "gdp_usd",
    "PA.NUS.FCRF": "fx_lcu_per_usd",
    "SP.POP.TOTL": "pop",
    "SP.URB.TOTL": "urban_pop",
    "AG.LND.TOTL.K2": "land_km2",
}

GHS_POP_URL = (
    "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/GHSL/"
    "GHS_POP_GLOBE_R2023A/GHS_POP_E2020_GLOBE_R2023A_4326_30ss/V1-0/"
    "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.zip"
)

PLACES_URL = (
    "https://zenodo.org/api/records/4073355/files/"
    "places_fmv_pnas_dryad.zip/content"
)

OECD_URL = (
    "https://sdmx.oecd.org/public/rest/data/"
    "OECD.SDD.NAD,DSD_NASEC10@DF_TABLE9B,1.0/A............."
    "?startPeriod=2014&endPeriod=2021"
)


def worldbank(indicator):
    rows, page = [], 1
    while True:
        url = (
            f"https://api.worldbank.org/v2/country/all/indicator/{indicator}"
            f"?format=json&per_page=20000&page={page}"
        )
        payload = requests.get(url, timeout=120).json()
        if len(payload) < 2 or payload[1] is None:
            raise SystemExit(f"{indicator}: {payload}")
        for r in payload[1]:
            if r["value"] is not None and r["countryiso3code"]:
                rows.append(
                    (
                        indicator,
                        r["countryiso3code"],
                        r["country"]["value"],
                        int(r["date"]),
                        r["value"],
                    )
                )
        if page >= payload[0]["pages"]:
            return pd.DataFrame(
                rows, columns=["indicator", "iso3", "country", "year", "value"]
            )
        page += 1


def curl(url, path, label):
    """Some of these hosts serve certificate chains that Python's bundled roots
    reject but the system's accept, so downloads go through curl."""
    proc = subprocess.run(
        ["curl", "-sSL", "--fail", "--max-time", "900", "-o", str(path), url],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"{label} download failed: {proc.stderr.strip()}")


def countries():
    """The World Bank country list, so the aggregates (WLD, OED, high income
    ...) can be dropped -- they come back from the indicator API alongside
    real countries and would otherwise be double-counted."""
    payload = requests.get(
        "https://api.worldbank.org/v2/country?format=json&per_page=400", timeout=120
    ).json()
    rows = [
        (c["id"], c["name"], c["region"]["value"], c["incomeLevel"]["value"])
        for c in payload[1]
    ]
    d = pd.DataFrame(rows, columns=["iso3", "country", "region", "income"])
    return d[d.region != "Aggregates"]


def oecd_land():
    # sdmx.oecd.org serves a chain that Python's certifi bundle rejects
    # ("Missing Authority Key Identifier") while the system trust store
    # accepts it, so this one request goes through curl.
    proc = subprocess.run(
        [
            "curl", "-sS", "--fail", "--max-time", "300",
            "-H", "Accept: application/vnd.sdmx.data+csv;version=1.0",
            OECD_URL,
        ],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise SystemExit(f"OECD download failed: {proc.stderr.strip()}")
    d = pd.read_csv(io.StringIO(proc.stdout))
    # S1 is the total economy; N211N is land, net, at current prices.  The
    # observations arrive in millions of national currency (UNIT_MULT 6).
    d = d[(d.SECTOR == "S1") & (d.INSTR_ASSET.isin(["N211N", "N2111N"]))]
    keep = ["REF_AREA", "INSTR_ASSET", "TIME_PERIOD", "OBS_VALUE", "UNIT_MULT", "CURRENCY"]
    return d[keep].rename(
        columns={"REF_AREA": "iso3", "TIME_PERIOD": "year", "OBS_VALUE": "value"}
    )


def main():
    OUT.mkdir(parents=True, exist_ok=True)

    wealth = pd.concat([worldbank(i) for i in WEALTH], ignore_index=True)
    wealth.to_csv(OUT / "wb_wealth.csv", index=False)
    print(f"wb_wealth.csv        {len(wealth):6,d} rows  "
          f"{wealth.iso3.nunique()} areas  {wealth.year.min()}-{wealth.year.max()}")

    wdi = pd.concat([worldbank(i) for i in WDI], ignore_index=True)
    wdi["indicator"] = wdi.indicator.map(WDI)
    wdi.to_csv(OUT / "wb_wdi.csv", index=False)
    print(f"wb_wdi.csv           {len(wdi):6,d} rows")

    # naciscdn.org has the same certificate-chain problem as the OECD host.
    for name, url in (
        ("ne_110m_admin_0_countries.zip",
         "https://naciscdn.org/naturalearth/110m/cultural/"
         "ne_110m_admin_0_countries.zip"),
        ("ne_10m_admin_1_states_provinces.zip",
         "https://naciscdn.org/naturalearth/10m/cultural/"
         "ne_10m_admin_1_states_provinces.zip"),
        ("ne_10m_populated_places.zip",
         "https://naciscdn.org/naturalearth/10m/cultural/"
         "ne_10m_populated_places.zip"),
    ):
        path = OUT / name
        if not path.exists():
            curl(url, path, "Natural Earth")
        print(f"{name[:20]:<20} {path.stat().st_size/1024:6,.0f} KB  "
              "Natural Earth boundaries")

    # Natural Earth at 1:10m is too coarse for the US maps once they are
    # zoomed: a bay a few kilometres across is a straight line in it.  The
    # Census cartographic boundaries at 1:500k carry five times the detail and
    # are clipped to the shoreline, which is what makes the coasts read.
    for name, what in (("state", "state outlines, 1:500,000"),
                       ("county", "county outlines, for allocation")):
        tiger = OUT / f"cb_2023_us_{name}_500k.zip"
        if not tiger.exists():
            curl(f"https://www2.census.gov/geo/tiger/GENZ2023/shp/{tiger.name}",
                 tiger, "Census TIGER")
        print(f"{tiger.name[:20]:<20} {tiger.stat().st_size/1024:6,.0f} KB  "
              f"{what}")

    # The Cropland Data Layer: 2 GB zipped, 3.3 GB of 30 m raster, in the same
    # Albers grid everything else here is cut on.  Only src/land/
    # build_us_farmland.py needs it, and only once.
    cdl_zip = OUT / "2023_30m_cdls.zip"
    if not (OUT / "cdl" / "2023_30m_cdls.tif").exists():
        if not cdl_zip.exists():
            curl("https://www.nass.usda.gov/Research_and_Science/Cropland/"
                 "Release/datasets/2023_30m_cdls.zip", cdl_zip, "USDA CDL")
        print("unzipping the Cropland Data Layer ...")
        subprocess.run(["unzip", "-o", "-q", str(cdl_zip), "-d",
                        str(OUT / "cdl")], check=True)
    print(f"{'2023_30m_cdls':<20} "
          f"{(OUT / 'cdl' / '2023_30m_cdls.tif').stat().st_size/1e9:6,.1f} GB  "
          "USDA Cropland Data Layer, 30 m")

    # The Census of Agriculture, 2022: 295 MB of every figure NASS publishes,
    # of which src/land/build_us_ag_sales.py wants two per county.  It is the
    # only measure fine enough to tell an acre of almonds from an acre of
    # wheat, which is what the farmland rates are fitted on.
    nass = OUT / "nass" / "qs.census2022.txt.gz"
    if not nass.exists():
        nass.parent.mkdir(parents=True, exist_ok=True)
        curl("https://www.nass.usda.gov/datasets/qs.census2022.txt.gz",
             nass, "Census of Agriculture")
    print(f"{'Census of Ag 2022':<20} {nass.stat().st_size/1e6:6,.0f} MB  "
          "county sales, crops and animals")

    # MSHA's register of mines and EIA-860's of power plants, for
    # src/land/build_us_facilities.py.  Both put the work at the worksite,
    # which is the thing LODES does not do for these two industries.
    msha = OUT / "msha_mines.zip"
    if not msha.exists():
        curl("https://arlweb.msha.gov/OpenGovernmentData/DataSets/Mines.zip",
             msha, "MSHA mines")
    print(f"{'MSHA mines':<20} {msha.stat().st_size/1e6:6,.0f} MB  "
          "every mine, with a coordinate and a headcount")

    eia = OUT / "eia860.zip"
    if not eia.exists():
        curl("https://www.eia.gov/electricity/data/eia860/archive/xls/"
             "eia8602023.zip", eia, "EIA-860")
    print(f"{'EIA-860 2023':<20} {eia.stat().st_size/1e6:6,.0f} MB  "
          "generating plants, coordinates and nameplate capacity")

    # FracFocus, for src/land/build_us_facilities.py: every hydraulic
    # fracturing job in the country since 2011, with a coordinate.  It is the
    # only free national source fine enough to say where inside a county the
    # oil is, and EIA itself buys Enverus for the county figures.
    frac = OUT / "fracfocus" / "fracfocuscsv.zip"
    if not frac.exists():
        frac.parent.mkdir(parents=True, exist_ok=True)
        curl("https://www.fracfocusdata.org/digitaldownload/fracfocuscsv.zip",
             frac, "FracFocus")
    print(f"{'FracFocus':<20} {frac.stat().st_size/1e6:6,.0f} MB  "
          "fracked wells, coordinates and water volume")

    # CalGEM's WellSTAR register, for the California wells FracFocus cannot
    # see.  It comes off an ArcGIS endpoint 2,000 rows at a time rather than as
    # one file, so it is paged here.
    cal = OUT / "calgem" / "calgem_producing_wells.csv"
    if not cal.exists():
        cal.parent.mkdir(parents=True, exist_ok=True)
        base = ("https://gis.conservation.ca.gov/server/rest/services/WellSTAR"
                "/Wells/MapServer/0/query")
        where = "WellStatus='Active' AND WellType IN ('OG','DG','SC')"
        rows, off = [], 0
        print("fetching CalGEM producing wells ...")
        while True:
            out = OUT / "calgem" / f"_page{off}.json"
            curl(f"{base}?where={requests.utils.quote(where)}"
                 "&outFields=API,Latitude,Longitude,CountyName,WellType"
                 f"&returnGeometry=false&resultOffset={off}"
                 "&resultRecordCount=2000&f=json", out, "CalGEM")
            page = json.loads(out.read_text()).get("features", [])
            out.unlink()
            rows += [r["attributes"] for r in page]
            if len(page) < 2000:
                break
            off += 2000
        cols = ["API", "Latitude", "Longitude", "CountyName", "WellType"]
        with cal.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({k: r.get(k) for k in cols})
    print(f"{'CalGEM wells':<20} {cal.stat().st_size/1e6:6,.1f} MB  "
          "California's producing wells, which FracFocus cannot see")

    # QCEW, for src/land/check_lodes_coverage.py.  Nothing on the map is built
    # from it; it exists so that how well LODES counts the country is a
    # measured number rather than a hope.
    qcew = OUT / "qcew" / "2023_annual_singlefile.zip"
    if not qcew.exists():
        qcew.parent.mkdir(parents=True, exist_ok=True)
        curl("https://data.bls.gov/cew/data/files/2023/csv/"
             "2023_annual_singlefile.zip", qcew, "BLS QCEW")
    print(f"{'BLS QCEW 2023':<20} {qcew.stat().st_size/1e6:6,.0f} MB  "
          "county employment by industry, as a check on LODES")

    # GHS-POP: 480 MB, only needed by build_subnational.py.  The archive is
    # kept so a rerun does not fetch it again; both it and the raster are
    # gitignored.
    pop_zip = OUT / "ghs_pop_30ss.zip"
    pop_tif = OUT / "GHS_POP_E2020_GLOBE_R2023A_4326_30ss_V1_0.tif"
    if not pop_tif.exists():
        if not pop_zip.exists():
            curl(GHS_POP_URL, pop_zip, "GHS-POP")
        subprocess.run(["unzip", "-o", "-q", str(pop_zip), pop_tif.name,
                        "-d", str(OUT)], check=True)
    print(f"GHS-POP raster       {pop_tif.stat().st_size/1e6:6,.0f} MB  "
          "population, 30 arc-second")

    # PLACES: 299 MB, only needed by make_us_cartogram.py.  Zenodo rather than
    # Dryad, because Dryad now sits behind a proof-of-work bot check.
    fmv_zip = OUT / "places_fmv_pnas.zip"
    fmv_dir = OUT / "places_fmv"
    if not (fmv_dir / "places_fmv_vacant.tif").exists():
        if not fmv_zip.exists():
            curl(PLACES_URL, fmv_zip, "PLACES")
        subprocess.run(["unzip", "-o", "-q", "-j", str(fmv_zip),
                        "1 estimates/places_fmv_all.tif",
                        "1 estimates/places_fmv_vacant.tif",
                        "-d", str(fmv_dir)], check=True)
    print(f"places_fmv/          {sum(f.stat().st_size for f in fmv_dir.iterdir())/1e6:6,.0f} MB  "
          "US land value, 480 m")

    ctry = countries()
    ctry.to_csv(OUT / "wb_countries.csv", index=False)
    print(f"wb_countries.csv     {len(ctry):6,d} countries (aggregates dropped)")

    land = oecd_land()
    land.to_csv(OUT / "oecd_land.csv", index=False)
    mult = sorted(land.UNIT_MULT.unique())
    print(f"oecd_land.csv        {len(land):6,d} rows  "
          f"{land.iso3.nunique()} countries  unit_mult {mult}")
    if mult != [6]:
        print("  WARNING: mixed unit multipliers; build_land_value.py assumes millions")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
