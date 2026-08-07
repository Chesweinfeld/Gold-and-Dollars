"""Join New World production (our TePaske extraction) to Atlantic arrivals and
the Spanish money stock (Chen/Palma/Ward, via the Vagaries replication file).

Everything is expressed in kilograms of fine silver equivalent. Gold is
converted at the contemporary bimetallic ratio implied by TePaske's own paired
peso/kg columns (silver factor / gold factor), so the conversion is internal to
the sources rather than imposed.
"""

import pandas as pd

SILVER_F = [(1728, 0.025560), (1772, 0.024810), (1786, 0.024430), (9999, 0.024245)]
GOLD_F = [(1771, 0.001551), (1785, 0.001525), (9999, 0.001480)]


def factor(table, y):
    for cut, f in table:
        if y <= cut:
            return f


def ag_equivalent(y):
    """Silver-equivalent kg per kg of gold, from the two era-stepped factors."""
    return factor(SILVER_F, y) / factor(GOLD_F, y)


def main():
    w = pd.read_csv("../tepaske_annual.csv")
    out = w[w.measure == "output"]

    ag = (out[out.metal == "silver"].groupby("year").kilograms.sum()
          .rename("prod_silver_kg"))
    # TePaske reports gold OUTPUT only by decade (ch.2), so the annual gold
    # series comes from Palma's compilation, which interpolates those decade
    # totals and adds Brazil from Costa et al. (2013).
    au = (pd.read_stata("ReproductionFiles/data/datadescriptive.dta",
                        columns=["year", "tnsgoldnew"])
            .dropna(subset=["tnsgoldnew"])
            .assign(year=lambda x: x.year.astype(int))
            .set_index("year").tnsgoldnew.mul(1000).rename("prod_gold_kg"))

    m = pd.read_stata("vagaries_money.tab",
                      columns=["year", "in_esp", "sisto_esp", "loss",
                               "pesograms", "gdp_nom_reales"])
    m["year"] = pd.to_datetime(m.year).dt.year
    m = m.set_index("year").rename(columns={
        "in_esp": "arrivals_ag_kg", "sisto_esp": "money_stock_ag_kg",
        "loss": "shipwreck_loss_ag_kg", "gdp_nom_reales": "gdp_nominal_reales"})

    d = pd.concat([ag, au], axis=1).join(m, how="outer").sort_index()
    d = d.loc[1500:1810]
    d.index.name = "year"

    # Palma's gold series is already expressed in silver-equivalent tonnes
    # (its silver and gold columns sum exactly to his printed total), so it is
    # carried straight through rather than converted again.
    d["prod_gold_ag_equiv_kg"] = d.prod_gold_kg
    d["prod_total_ag_kg"] = (d.prod_silver_kg.fillna(0)
                             + d.prod_gold_ag_equiv_kg.fillna(0))
    d.loc[d.prod_total_ag_kg == 0, "prod_total_ag_kg"] = pd.NA

    d["arrival_share"] = d.arrivals_ag_kg / d.prod_total_ag_kg

    cols = ["prod_silver_kg", "prod_gold_kg", "prod_gold_ag_equiv_kg",
            "prod_total_ag_kg", "arrivals_ag_kg", "arrival_share",
            "money_stock_ag_kg", "shipwreck_loss_ag_kg",
            "gdp_nominal_reales", "pesograms"]
    d[cols].round(2).to_csv("production_to_arrivals.csv")

    print(f"rows {len(d)}   {d.index.min()}-{d.index.max()}")
    both = d.dropna(subset=["prod_total_ag_kg", "arrivals_ag_kg"])
    print(f"years with both production and arrivals: {len(both)}")
    print(f"\ntotals over 1531-1810 (tonnes Ag-equivalent):")
    t = d.loc[1531:1810]
    print(f"  New World production (our TePaske) : {t.prod_total_ag_kg.sum()/1000:>9,.0f}")
    print(f"    of which gold, as silver         : {t.prod_gold_ag_equiv_kg.sum()/1000:>9,.0f}")
    print(f"  Arrivals in Spain (Chen/Palma/Ward): {t.arrivals_ag_kg.sum()/1000:>9,.0f}")
    print(f"  Lost at sea                        : {t.shipwreck_loss_ag_kg.sum()/1000:>9,.0f}")
    print(f"  Spanish money stock, 1810          : {d.money_stock_ag_kg.loc[1810]/1000:>9,.0f}")

    print("\narrivals as share of production, by half-century:")
    b = both.copy()
    b["era"] = (b.index // 50 * 50)
    g = b.groupby("era").agg(prod_t=("prod_total_ag_kg", "sum"),
                             arrivals_t=("arrivals_ag_kg", "sum"))
    g["share"] = (g["arrivals_t"] / g["prod_t"]).round(3)
    g[["prod_t", "arrivals_t"]] = (g[["prod_t", "arrivals_t"]] / 1000).round(0)
    print(g.to_string())

    print("\ncorrelation of annual production and arrivals (logs), 1580-1810:",
          round(both.loc[1580:1810].prod_total_ag_kg.apply("log")
                .corr(both.loc[1580:1810].arrivals_ag_kg.apply("log")), 3))


if __name__ == "__main__":
    main()
