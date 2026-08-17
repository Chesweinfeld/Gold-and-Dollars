"""Does LODES count the jobs the country actually has?

The whole sub-county allocation rests on LODES: eighteen of BEA's twenty
industry lines are spread across census blocks in proportion to the jobs LODES
puts there.  If LODES is missing jobs, it is missing them somewhere, and the
output those jobs produce goes to whichever blocks are left.

LODES is built from unemployment-insurance records, which do not cover
everyone.  Farm proprietors and most farm labour are outside it, which this
project already knew and works around by putting agriculture on the fields.
What it did not know was how large the gap is anywhere else.

QCEW is the obvious check.  It comes from the same unemployment-insurance
system, is published by BLS rather than Census, and reports average annual
employment by county and industry -- including the federal workers LODES
handles differently and the government ownerships LODES folds together.  It is
not a carrier and nothing here feeds the map: this script only reports, so
that the size of the gap is a measured number in the build log rather than an
assumption in a docstring.

Two things make an exact match impossible, and neither is a fault:
  - QCEW counts by establishment's reported county, LODES by block, and the
    two disagree wherever an employer reports centrally.
  - QCEW suppresses a county-industry cell that would disclose an employer,
    and those cells are simply absent rather than zero.

So what matters is the shape of the disagreement, not that it is nonzero.

Prints a comparison by NAICS sector and names the worst counties.
"""

import sys
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
QCEW = IN / "qcew" / "2023_annual_singlefile.zip"
LODES = IN / "lodes"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_us_gdp import CNS, SECTORS, STATES, _st        # noqa: E402

# QCEW's two-digit industry codes, against the LODES sector that means the
# same thing.  The ranges are NAICS supersectors that QCEW reports as one.
NAICS = {
    "CNS01": ["11"], "CNS02": ["21"], "CNS03": ["22"], "CNS04": ["23"],
    "CNS05": ["31-33"], "CNS06": ["42"], "CNS07": ["44-45"],
    "CNS08": ["48-49"], "CNS09": ["51"], "CNS10": ["52"], "CNS11": ["53"],
    "CNS12": ["54"], "CNS13": ["55"], "CNS14": ["56"], "CNS15": ["61"],
    "CNS16": ["62"], "CNS17": ["71"], "CNS18": ["72"], "CNS19": ["81"],
    "CNS20": ["92"],
}


def qcew():
    """Average annual employment by county and sector, all ownerships."""
    if not QCEW.exists():
        sys.exit(f"missing {QCEW} -- run src/land/fetch_inputs.py first")
    want = {c for codes in NAICS.values() for c in codes}
    keep = sorted({_st(s) for s in STATES})
    out = []
    with zipfile.ZipFile(QCEW) as z:
        name = z.namelist()[0]
        with z.open(name) as fh:
            for chunk in pd.read_csv(fh, chunksize=500_000, dtype=str,
                                     usecols=["area_fips", "own_code",
                                              "industry_code", "agglvl_code",
                                              "annual_avg_emplvl"]):
                # agglvl 74 is county by NAICS sector, broken out by
                # ownership; the ownerships are summed so that public and
                # private schools land together, exactly as LODES has them.
                # (75 and below are three-digit industries and finer.)
                c = chunk[chunk.industry_code.isin(want)
                          & (chunk.agglvl_code == "74")
                          & chunk.area_fips.str[:2].isin(keep)]
                if len(c):
                    out.append(c)
    d = pd.concat(out, ignore_index=True)
    d = d[d.own_code != "0"]
    d["emp"] = pd.to_numeric(d.annual_avg_emplvl, errors="coerce").fillna(0)
    g = d.groupby(["area_fips", "industry_code"]).emp.sum().reset_index()
    print(f"QCEW 2023: {g.emp.sum()/1e6:,.1f}M jobs in "
          f"{g.area_fips.nunique():,d} counties")
    return g


def lodes():
    """The same thing from the file the map actually uses."""
    frames = []
    for st in STATES:
        wac = pd.read_csv(LODES / f"{st}_wac.csv.gz",
                          usecols=["w_geocode"] + CNS,
                          dtype={"w_geocode": str})
        xw = pd.read_csv(LODES / f"{st}_xwalk.csv.gz",
                         usecols=["tabblk2020", "cty"],
                         dtype={"tabblk2020": str, "cty": str})
        m = wac.merge(xw, left_on="w_geocode", right_on="tabblk2020")
        frames.append(m.groupby(m.cty.str.zfill(5))[CNS].sum())
    d = pd.concat(frames).groupby(level=0).sum()
    print(f"LODES 8: {d.to_numpy().sum()/1e6:,.1f}M jobs in {len(d):,d} "
          "counties, in the eighteen sectors the map carries")
    return d


def main():
    q, l = qcew(), lodes()
    q = q.pivot(index="area_fips", columns="industry_code", values="emp")

    print("\nby sector -- LODES against QCEW, both in millions of jobs")
    print(f"  {'sector':28s} {'LODES':>8s} {'QCEW':>8s} {'ratio':>7s}")
    rows = []
    for cns in CNS:
        codes = [c for c in NAICS[cns] if c in q.columns]
        if not codes:
            continue
        a, b = l[cns].sum(), q[codes].sum(axis=1).sum()
        name = next(v[1] for v in SECTORS.values() if v[0] == cns)
        rows.append((name, cns, a, b))
        print(f"  {name:28s} {a/1e6:8.2f} {b/1e6:8.2f} "
              f"{(a/b if b else float('nan')):7.2f}")
    ta = sum(r[2] for r in rows)
    tb = sum(r[3] for r in rows)
    print(f"  {'all eighteen':28s} {ta/1e6:8.2f} {tb/1e6:8.2f} {ta/tb:7.2f}")

    # Where the two disagree most, by county, weighted by how many jobs are at
    # stake -- a 40% gap in a county with 200 jobs matters to nobody.
    per = []
    for cns in CNS:
        codes = [c for c in NAICS[cns] if c in q.columns]
        if not codes:
            continue
        j = pd.DataFrame({"lodes": l[cns], "qcew": q[codes].sum(axis=1)})
        j = j.dropna()
        j = j[(j.qcew > 500)]
        j["gap"] = j.lodes - j.qcew
        j["sector"] = cns
        per.append(j)
    p = pd.concat(per)
    p["absgap"] = p.gap.abs()
    print(f"\nof {len(p):,d} county-sectors with more than 500 QCEW jobs, "
          f"LODES is within 20% on {(p.lodes.div(p.qcew).between(0.8, 1.2)).mean():.0%}")
    print("the ten largest single disagreements:")
    for _, r in p.nlargest(10, "absgap").iterrows():
        name = next(v[1] for v in SECTORS.values() if v[0] == r.sector)
        print(f"  {r.name} {name:26s} LODES {r.lodes:>9,.0f}  "
              f"QCEW {r.qcew:>9,.0f}  {r.gap:>+10,.0f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
