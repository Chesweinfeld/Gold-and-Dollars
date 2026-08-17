"""What each county's farms actually sold, from the Census of Agriculture.

The farmland carrier in build_us_gdp.py needs to know what an acre of each
kind of ground is worth relative to the others.  Fitting that against BEA's
line 3 alone is possible but poor: line 3 is farm *value added*, net of costs,
which swings by an order of magnitude from year to year in a single county and
is suppressed or noisy in many.  The Census of Agriculture measures the gross
thing directly -- every farm in the country, every five years -- and reports
it by county, split into what came off the fields and what came off the
animals.

This script pulls two figures per county out of the 2022 census:

  crop_usd    CROP TOTALS - SALES
  animal_usd  ANIMAL TOTALS, INCL PRODUCTS - SALES

They are used only to fit the *shape* -- the ratio of one class of ground to
another.  The level still comes from BEA: each county receives exactly its own
line 3, as it did before.  So a county's total is unaffected by this file, and
what changes is how that total is spread across the ground inside it.

Two things this cannot do.  The census withholds a county's figure where it
would identify a farm, marked (D); those counties are dropped from the fit
rather than guessed at, and there are enough left that it hardly matters.  And
livestock raised in confinement -- the poultry houses of Delmarva, the hog
barns of Iowa -- is sold by counties whose pasture had little to do with
producing it, which pushes the fitted grazing rates up.  That is a real
limitation of using land to explain animal sales, and it is why the crop and
animal fits are kept apart rather than run as one regression.

Writes data/land/us_ag_sales.csv.
"""

import gzip
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
SRC = IN / "nass" / "qs.census2022.txt.gz"

WANT = {
    "CROP TOTALS - SALES, MEASURED IN $": "crop_usd",
    "ANIMAL TOTALS, INCL PRODUCTS - SALES, MEASURED IN $": "animal_usd",
}
# The states this map covers: the conterminous forty-eight and DC.
DROP_STATES = {"02", "15", "60", "66", "69", "72", "78"}


def main():
    if not SRC.exists():
        sys.exit(f"missing {SRC} -- run src/land/fetch_inputs.py first")

    rows, held = [], 0
    with gzip.open(SRC, "rt", encoding="latin-1", errors="replace") as fh:
        head = fh.readline().rstrip("\n").split("\t")
        col = {n: i for i, n in enumerate(head)}
        for line in fh:
            f = line.rstrip("\n").split("\t")
            if len(f) <= col["VALUE"]:
                continue
            if f[col["AGG_LEVEL_DESC"]] != "COUNTY":
                continue
            what = WANT.get(f[col["SHORT_DESC"]])
            if what is None or f[col["DOMAIN_DESC"]] != "TOTAL":
                continue
            st, cty = f[col["STATE_FIPS_CODE"]], f[col["COUNTY_CODE"]]
            if st in DROP_STATES or not cty.strip():
                continue
            v = f[col["VALUE"]].strip().replace(",", "")
            # (D) withheld to avoid disclosing a farm, (Z) less than half a
            # unit, (NA)/(X) not applicable.  None of them are a number.
            if not v or v.startswith("("):
                held += 1
                continue
            rows.append((st + cty.zfill(3), what, float(v)))

    if not rows:
        sys.exit("no county sales rows found -- has the census layout changed?")
    d = pd.DataFrame(rows, columns=["fips", "what", "usd"])
    out = d.pivot_table(index="fips", columns="what", values="usd",
                        aggfunc="sum").reset_index()
    for c in ("crop_usd", "animal_usd"):
        if c not in out:
            sys.exit(f"the census gave no {c} at county level")
        out[c] = out[c].fillna(0.0)
    out["total_usd"] = out.crop_usd + out.animal_usd

    print(f"2022 Census of Agriculture, {len(out):,d} counties")
    print(f"  crops   ${out.crop_usd.sum()/1e9:,.1f}bn")
    print(f"  animals ${out.animal_usd.sum()/1e9:,.1f}bn")
    print(f"  total   ${out.total_usd.sum()/1e9:,.1f}bn")
    print(f"  {held:,d} county figures withheld or non-numeric, left out of "
          "the fit")
    out.to_csv(DATA / "us_ag_sales.csv", index=False)
    print(f"-> data/land/us_ag_sales.csv ({len(out):,d} counties)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
