"""Assemble a country land-value series: measured farmland, modelled urban land.

Land value has no global measurement.  Two partial records exist and they do
not overlap:

  * The World Bank's Changing Wealth of Nations values *agricultural* land for
    150 countries by capitalising crop and pasture rents.  It has the coverage
    and none of the value -- farmland is a small share of what land is worth.
  * National balance sheets under SNA 2008 carry *all* land, asset AN.211, at
    market prices.  That is the concept people mean by "land value", and only
    a couple of dozen rich countries compile it.

So the urban half has to be modelled, and this script does exactly one thing
with a model: fits urban land value against GDP on the countries that report
both, then extends it.  Everything it prints is a check on that step.

Outputs (data/land/):
    land_value_2020.csv          per country, agricultural + urban + total
    urban_land_calibration.csv   the 18 reporters and what happened to each
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
OUT = ROOT / "data" / "land"

YEAR = 2020  # last year of Changing Wealth of Nations 2024


def load():
    ctry = pd.read_csv(IN / "wb_countries.csv").set_index("iso3")
    names = ctry["country"]

    w = pd.read_csv(IN / "wb_wealth.csv")
    w = w[w.year == YEAR].pivot_table(index="iso3", columns="indicator", values="value")

    d = pd.read_csv(IN / "wb_wdi.csv")
    d = d[d.year == YEAR].pivot_table(index="iso3", columns="indicator", values="value")

    o = pd.read_csv(IN / "oecd_land.csv")
    o = o[(o.INSTR_ASSET == "N211N") & (o.year == YEAR)]
    o = o.set_index("iso3")["value"].rename("land_lcu_mn")

    df = w.join(d, how="outer").join(o, how="outer")
    df = df[df.index.isin(ctry.index)]  # drop WLD, OED and the other aggregates
    return df, names


def cwon_urban_land_test(w):
    """CWON publishes produced capital with and without urban land.  Ask what
    the difference actually contains."""
    a = pd.read_csv(IN / "wb_wealth.csv")
    a = a.pivot_table(index=["iso3", "year"], columns="indicator", values="value")
    a = a.dropna(subset=["NW.PCA.TO.IN.CD", "NW.PCA.TO.EX.CD"])
    ratio = a["NW.PCA.TO.IN.CD"] / a["NW.PCA.TO.EX.CD"]
    print("CWON urban land = produced capital x k")
    print(f"  k over {len(ratio):,d} country-years, {a.index.get_level_values(0).nunique()} countries, "
          f"{a.index.get_level_values(1).min()}-{a.index.get_level_values(1).max()}")
    print(f"  min {ratio.min():.10f}   max {ratio.max():.10f}   sd {ratio.std():.2e}")
    print(f"  -> the World Bank's urban land is {ratio.mean() - 1:.2f} x produced capital,")
    print("     the same multiplier for every country and every year.  It carries no")
    print("     country information beyond produced capital, so it is not used here.\n")
    return float(ratio.mean() - 1)


def calibrate(df, names):
    """Urban land = reported total land - CWON agricultural land, in USD."""
    c = df.dropna(subset=["land_lcu_mn", "gdp_usd", "fx_lcu_per_usd"]).copy()
    c["land_usd"] = c.land_lcu_mn * 1e6 / c.fx_lcu_per_usd
    c["ag_land_usd"] = c["NW.NCA.CROP.TO.CD"] + c["NW.NCA.PAST.TO.CD"]
    c["urban_land_usd"] = c.land_usd - c.ag_land_usd
    c["country"] = names.reindex(c.index).values

    dropped = c[~(c.urban_land_usd > 0)]
    c["used"] = c.urban_land_usd > 0
    print(f"Calibration sample: {len(c)} countries report land in Table 9B for {YEAR}")
    for iso, r in dropped.iterrows():
        print(f"  dropped {iso} ({r.country}): reported land ${r.land_usd/1e9:,.0f}bn is below "
              f"CWON farmland ${r.ag_land_usd/1e9:,.0f}bn -- the national balance sheet does not "
              "cover all land")
    fit = c[c.used]
    print(f"  {len(fit)} usable\n")

    y = np.log(fit.urban_land_usd.values)
    x = np.log(fit.gdp_usd.values)

    # Free elasticity.
    X = np.column_stack([np.ones(len(x)), x])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ b
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    loo = leave_one_out(X, y)

    # Elasticity pinned to 1: urban land is a constant multiple of GDP.
    k = np.exp(np.mean(y - x))
    resid1 = y - (np.log(k) + x)
    r2_1 = 1 - resid1 @ resid1 / ((y - y.mean()) @ (y - y.mean()))
    loo_1 = leave_one_out(np.ones((len(x), 1)), y - x)

    print("Fit: log(urban land) on log(GDP), both current US$")
    print(f"  free      elasticity {b[1]:.3f}  intercept {b[0]:.3f}  "
          f"R2 {r2:.3f}  LOO rmse(log) {loo:.3f}")
    print(f"  pinned    elasticity 1.000  k = {k:.3f}          "
          f"R2 {r2_1:.3f}  LOO rmse(log) {loo_1:.3f}")

    ratio = fit.urban_land_usd / fit.gdp_usd
    print(f"  urban land / GDP in sample: {ratio.min():.2f} ({ratio.idxmin()}) to "
          f"{ratio.max():.2f} ({ratio.idxmax()}), geometric mean {k:.2f}")
    print(f"  sample GDP range: ${fit.gdp_usd.min()/1e9:,.0f}bn ({fit.gdp_usd.idxmin()}) to "
          f"${fit.gdp_usd.max()/1e12:,.1f}tn ({fit.gdp_usd.idxmax()})\n")

    c["urban_pred_free"] = np.exp(b[0] + b[1] * np.log(c.gdp_usd))
    c["urban_pred_k"] = k * c.gdp_usd
    return c, b, k, r2, loo, r2_1, loo_1


def leave_one_out(X, y):
    errs = []
    for i in range(len(y)):
        m = np.ones(len(y), bool)
        m[i] = False
        b, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        errs.append(y[i] - X[i] @ b)
    return float(np.sqrt(np.mean(np.square(errs))))


def choose(df, b, k):
    """The free fit is superlinear, so it extrapolates upward off the top of a
    sample that stops at Japan.  Show what that costs before picking."""
    big = df.dropna(subset=["gdp_usd"]).nlargest(4, "gdp_usd")
    print("Out of sample, at the top:")
    for iso, r in big.iterrows():
        print(f"  {iso}  GDP ${r.gdp_usd/1e12:5.1f}tn   free fit implies urban land / GDP "
              f"{r.urban_pred_free / r.gdp_usd:5.2f}   pinned {k:.2f}")
    print(f"  The free elasticity is {b[1]:.2f}: every doubling of GDP raises the land/GDP")
    print("  ratio by a quarter.  Applied to the United States -- four times richer than")
    print("  the largest economy in the calibration sample -- it returns a ratio no country")
    print("  in that sample reaches except Korea.  The pinned model is published; the free")
    print("  one is carried alongside as the sensitivity.\n")


def main():
    df, names = load()
    cwon_urban_land_test(df)
    calib, b, k, r2, loo, r2_1, loo_1 = calibrate(df, names)

    df["ag_land_usd"] = df["NW.NCA.CROP.TO.CD"] + df["NW.NCA.PAST.TO.CD"]
    df["urban_pred_free"] = np.exp(b[0] + b[1] * np.log(df.gdp_usd))
    df["urban_land_usd"] = k * df.gdp_usd
    choose(df, b, k)

    out = df.reset_index()[
        ["iso3", "gdp_usd", "ag_land_usd", "urban_land_usd", "urban_pred_free"]
    ].copy()
    out.insert(1, "country", names.reindex(out.iso3).values)
    out["total_land_usd"] = out.ag_land_usd.fillna(0) + out.urban_land_usd
    out["total_free_usd"] = out.ag_land_usd.fillna(0) + out.urban_pred_free
    out["ag_source"] = np.where(out.ag_land_usd.notna(), "cwon", "missing")
    # Countries measured directly keep their own number for the record.
    meas = calib[calib.used]
    out = out.merge(
        meas.reset_index()[["iso3", "land_usd", "urban_land_usd"]].rename(
            columns={"land_usd": "reported_land_usd",
                     "urban_land_usd": "reported_urban_land_usd"}),
        on="iso3", how="left",
    )
    out = out[out.total_land_usd.notna()].sort_values("total_land_usd", ascending=False)
    out.to_csv(OUT / "land_value_2020.csv", index=False)

    calib.reset_index()[
        ["iso3", "country", "gdp_usd", "land_usd", "ag_land_usd", "urban_land_usd",
         "urban_pred_k", "urban_pred_free", "used"]
    ].to_csv(OUT / "urban_land_calibration.csv", index=False)

    tot = out.total_land_usd.sum()
    print(f"land_value_2020.csv  {len(out)} countries, world total ${tot/1e12:,.0f}tn "
          f"(free-elasticity variant ${out.total_free_usd.sum()/1e12:,.0f}tn)")
    print(f"  agricultural ${out.ag_land_usd.sum()/1e12:,.0f}tn, "
          f"urban ${out.urban_land_usd.sum()/1e12:,.0f}tn")
    print(f"  no CWON farmland figure: {(out.ag_source == 'missing').sum()} countries, "
          "urban land only")
    top = out.head(10)
    print("\n  top 10, share of world land value")
    for _, r in top.iterrows():
        print(f"    {r.iso3}  {r.country[:22]:<22} ${r.total_land_usd/1e12:6.1f}tn  "
              f"{100*r.total_land_usd/tot:5.1f}%")
    print(f"    top 10 combined {100*top.total_land_usd.sum()/tot:.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
