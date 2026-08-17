"""What the housing stock earns, tract by tract.

The largest single line under the national total is the output of dwellings --
rent paid, plus the rent the BEA imputes to owner-occupiers -- and BEA measures
it by county and no finer.  Spread over a county's residents at one rate, it
gives every square in the county the same output per head, which is why so much
inhabited countryside had to be left grey: the denominator had no structure
inside the county line to distinguish one square from the next.

Rent is measured much more finely than that.  The American Community Survey
publishes median gross rent, median owner-occupied value and the split between
the two tenures for all 85,381 census tracts, which in a city are a few blocks
and in the country are a township.  This script turns those into a housing
services figure per tract:

    services  =  renters x median gross rent x 12
              +  owners  x median value x r

where r is the gross rent-to-value ratio, fitted from the survey itself as the
median of rent x 12 over value across the tracts that report both, rather than
assumed.  What consumes this, src/land/build_us_gdp.py, splits each county's
BEA figure across its tracts in proportion to that and then across the tract by
where the people are.  The county total is untouched, so the reconciliation to
BEA is exactly as it was; what changes is that the rate now varies within the
county instead of being flat across it.

Three things it cannot do.  Median rent times count is not aggregate rent, and
the error grows with how skewed a tract's rents are.  Tracts with no reported
rent or value -- small, rural, or heavily vacant -- fall back to their county's
average, which puts them back where they started.  And the imputed side rests
on a single national rent-to-value ratio, when in truth that ratio is lower in
expensive metros than in cheap ones, so this understates how much of the
national housing output belongs to the coasts.

Writes data/land/us_tract_housing.csv.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs" / "acs"
DATA = ROOT / "data" / "land"

# ACS 2023 five-year tables: median gross rent, tenure, median owner value.
TABLES = {"b25064": "rent", "b25003": "tenure", "b25077": "value"}
MISSING = -600000000            # the survey's several jam values are all below


def _read(table):
    f = IN / f"acsdt5y2023-{table}.dat"
    if not f.exists():
        sys.exit(f"missing {f} -- run src/land/fetch_inputs.py first")
    d = pd.read_csv(f, sep="|", dtype={"GEO_ID": str}, low_memory=False)
    d = d[d.GEO_ID.str.startswith("1400000US")].copy()
    d["tract"] = d.GEO_ID.str[9:]
    keep = [c for c in d.columns if c.startswith(table.upper() + "_E")]
    for c in keep:
        d[c] = pd.to_numeric(d[c], errors="coerce").where(lambda s: s > MISSING)
    return d.set_index("tract")[keep]


def main():
    rent = _read("b25064").iloc[:, 0].rename("rent")
    value = _read("b25077").iloc[:, 0].rename("value")
    ten = _read("b25003")
    ten.columns = ["occupied", "owner", "renter"][:ten.shape[1]]
    d = pd.concat([ten[["occupied", "owner", "renter"]], rent, value], axis=1)
    d = d[d.index.str[:2].isin([f"{i:02d}" for i in range(1, 57)])]
    d = d[~d.index.str[:2].isin(["02", "15"])]
    print(f"{len(d):,d} census tracts in the conterminous states")

    both = d.rent.notna() & d.value.notna() & (d.value > 0)
    r = float(np.median(d.rent[both] * 12 / d.value[both]))
    print(f"  gross rent-to-value fitted at {r:.3%} a year across "
          f"{int(both.sum()):,d} tracts reporting both")

    # A county mean stands in wherever the survey withheld a figure.
    d["county"] = d.index.str[:5]
    for col in ("rent", "value"):
        m = d.groupby("county")[col].transform("mean")
        d[col] = d[col].fillna(m).fillna(d[col].mean())
    d["services"] = (d.renter.fillna(0) * d.rent * 12
                     + d.owner.fillna(0) * d.value * r)
    filled = int((rent.reindex(d.index).isna()
                  | value.reindex(d.index).isna()).sum())
    print(f"  {filled:,d} tracts had a rent or a value withheld and took their "
          "county's mean")

    per = d.services / d.occupied.replace(0, np.nan)
    live = per.dropna()
    print(f"  housing services per occupied home: ${live.quantile(.1):,.0f} to "
          f"${live.quantile(.9):,.0f}, median ${live.median():,.0f}")
    inside = d.groupby("county").services.apply(
        lambda s: s.max() / max(s.min(), 1.0) if len(s) > 2 else np.nan)
    print(f"  within a county the tracts differ by a median factor of "
          f"{inside.median():.1f} -- structure the county figure alone has none of")

    out = d[["county", "services", "occupied"]].reset_index()
    out.to_csv(DATA / "us_tract_housing.csv", index=False,
               float_format="%.0f")
    print(f"\n-> data/land/us_tract_housing.csv ({len(out):,d} tracts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
