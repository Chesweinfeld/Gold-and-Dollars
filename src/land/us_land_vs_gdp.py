"""Land value against output, tile by tile, on the same 3.84 km lattice.

Both American surfaces in this directory are cut from the same grid, so they
can be divided by each other.  The ratio -- dollars of land value per dollar of
annual GDP -- is the interesting quantity: it is high where ground is dear
relative to what is done on it, and low where a lot of output stands on cheap
ground.

Two things to keep in mind about the ratio:

  * The numerator is a stock and the denominator is a flow, so the ratio has
    units of years.  A tile at 1.0 is ground worth one year of its own output.
  * The two surfaces are different vintages -- land is Nolte's 2020-dollar
    estimate, GDP is BEA 2023 -- and they are allocated by different rules.
    The ratio is a comparison of two maps, not a measured statistic.

Writes data/land/us_land_vs_gdp.csv.gz.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_us_cartogram import IN, _geo, _gdp_tiles, _land_tiles  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "land"
BLOCK = 8


def main():
    geo = _geo(BLOCK, None)
    # private=True: the ratio divides a price by an output, so ground with no
    # market -- the parks and the bases -- has no business in the numerator.
    # The land-value figures do not do this; see make_us_cartogram.tile_values.
    land = _land_tiles(geo, BLOCK, None, private=True)
    gdp = _gdp_tiles(geo)
    area = (geo["side"] / 1000.0) ** 2

    print(f"\n{np.count_nonzero(land):,d} tiles carry land value, "
          f"{np.count_nonzero(gdp):,d} carry output, "
          f"{np.count_nonzero((land > 0) & (gdp > 0)):,d} carry both")
    print(f"land ${land.sum()/1e12:,.2f}tn against GDP ${gdp.sum()/1e12:,.2f}tn "
          f"-- {land.sum()/gdp.sum():.2f} years of output")

    both = (land > 0) & (gdp > 0)
    iy, ix = np.nonzero(both)
    d = pd.DataFrame({
        "tile_row": iy, "tile_col": ix,
        "land_usd": np.round(land[both]).astype("int64"),
        "gdp_usd": np.round(gdp[both]).astype("int64"),
    })
    d["years"] = d.land_usd / d.gdp_usd

    print("\nConcentration, over the tiles that have both")
    for name, col in (("land value", "land_usd"), ("GDP", "gdp_usd")):
        s = np.sort(d[col].to_numpy())[::-1]
        c = np.cumsum(s) / s.sum()
        n10 = int(np.searchsorted(c, 0.10) + 1)
        n50 = int(np.searchsorted(c, 0.50) + 1)
        print(f"  half of {name:10s} sits on {n50:>7,d} tiles "
              f"({n50*area:>9,.0f} km2); a tenth on {n10:>6,d} "
              f"({n10*area:,.0f} km2)")

    w = d.gdp_usd.to_numpy().astype(float)
    q = _wpct(d.years.to_numpy(), w, [10, 25, 50, 75, 90])
    print("\nYears of output the ground under it is worth, weighted by output")
    print("  10th %5.2f | 25th %5.2f | median %5.2f | 75th %5.2f | 90th %5.2f"
          % tuple(q))

    top = d.nlargest(12, "gdp_usd")
    print("\nThe twelve highest-output tiles")
    print(f"  {'row':>5s} {'col':>5s} {'GDP':>12s} {'land':>12s} {'years':>7s}")
    for r in top.itertuples():
        print(f"  {r.tile_row:5d} {r.tile_col:5d} "
              f"${r.gdp_usd/1e9:10,.2f}bn ${r.land_usd/1e9:10,.2f}bn "
              f"{r.years:7.2f}")

    county_check(geo, land, gdp)

    d.to_csv(DATA / "us_land_vs_gdp.csv.gz", index=False, float_format="%.4f")
    print(f"\n-> data/land/us_land_vs_gdp.csv.gz ({len(d):,d} tiles)")
    return 0


def county_check(geo, land, gdp):
    """How much of the ratio is the county allocation showing through.

    Every rate in the allocation -- output per job, per resident, per farmed
    hectare -- is constant inside a county by construction, so a smooth patch
    in the ratio could be a county rather than a place.  Two readings of that,
    printed on every build so it cannot quietly get worse:

      the variance split   what share of the variance of log(land / output)
                           lies between counties rather than within them, taken
                           separately over the ground that has workplaces on it
                           and the ground that does not.
      the seam test        the typical step in log ratio between two squares
                           either side of a county line, against the typical
                           step inside one -- measured against a placebo where
                           the county map is rolled sideways, and against the
                           land surface, which has no county rule in it at all.
                           County lines follow rivers, so a raw seam ratio
                           above 1 proves nothing on its own.
    """
    import geopandas as gpd
    import rasterio.features
    import rasterio.transform

    src = IN / "cb_2023_us_county_500k.zip"
    if not src.exists():
        print("\n(no county file; skipping the allocation check)")
        return
    g = gpd.read_file(f"zip://{src}")
    g = g[~g.STATEFP.isin(["02", "15", "60", "66", "69", "72", "78"])]
    tr = rasterio.transform.from_origin(geo["x0"], geo["y1"], geo["side"],
                                        geo["side"])
    idx = rasterio.features.rasterize(
        ((q, i + 1) for i, q in enumerate(g.to_crs(5070).geometry)),
        out_shape=land.shape, transform=tr, fill=0, dtype="int32")

    jobs = _gdp_tiles(geo, kinds=(0,))
    ok = (land > 0) & (gdp > 0) & (idx > 0)
    lr = np.where(ok, np.log(np.where(ok, land / np.maximum(gdp, 1.0), 1.0)),
                  np.nan)

    print("\nHow much of the ratio is the county rule, not the place")
    print(f"  {'':32s}{'between':>9s}{'within':>8s}{'of land value':>15s}")
    for label, m in (("ground with workplace output", ok & (jobs > 0)),
                     ("ground with none", ok & (jobs <= 0)),
                     ("all of it", ok)):
        y = lr[m]
        mu = pd.Series(y).groupby(idx[m]).transform("mean").to_numpy()
        print(f"  {label:32s}{np.var(mu)/np.var(y):>8.1%}"
              f"{np.var(y - mu)/np.var(y):>8.1%}"
              f"{land[m].sum()/land.sum():>15.1%}")

    def seam(a, ix):
        """Median step across a boundary over the median step inside one."""
        f = np.where(ok, np.log(np.where(ok, a, 1.0)), np.nan)
        ins, out = [], []
        for axis in (0, 1):
            step = np.abs(np.diff(f, axis=axis))
            same = np.diff(ix, axis=axis) == 0
            good = np.isfinite(step)
            ins.append(step[good & same])
            out.append(step[good & ~same])
        ins, out = np.concatenate(ins), np.concatenate(out)
        return np.median(ins), np.median(out), np.median(out) / np.median(ins)

    # A raw seam ratio cannot be read on its own: county lines follow rivers
    # and ridges, so a field that has never heard of counties still steps at
    # them.  The placebo is the same county map rolled a county's width east,
    # which keeps the shape of the boundaries and destroys their placement.
    # What matters is the excess of the real over the placebo, and whether the
    # ratio's excess is bigger than that of the land surface it is built from.
    print("\n  step in log across a boundary over the step inside one:")
    print(f"  {'':26s}{'real':>7s}{'placebo':>9s}{'excess':>8s}")
    for label, a in (("the land surface alone", land),
                     ("the ratio", np.where(ok, land / np.maximum(gdp, 1.0),
                                            1.0))):
        _, _, real = seam(a, idx)
        fake = np.median([seam(a, np.roll(idx, k, axis=1))[2]
                          for k in (9, 17, 25)])
        print(f"  {label:26s}{real:>7.2f}{fake:>9.2f}{real/fake:>8.2f}")
    print("  The land surface knows nothing of counties, so its excess is the "
          "floor.\n  If the ratio's excess is near it, the allocation is not "
          "adding county edges.")


def _wpct(x, w, qs):
    o = np.argsort(x)
    c = np.cumsum(w[o])
    c = (c - 0.5 * w[o]) / c[-1] * 100
    return np.interp(qs, c, x[o])


if __name__ == "__main__":
    sys.exit(main())
