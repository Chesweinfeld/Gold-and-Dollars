"""Set Hamilton's registered arrivals (1503-1660) beside the modern series.

Three quantities, three different measurement points in the same chain:
  production  - TePaske's registered output at the colonial treasuries (ours)
  arrivals    - Hamilton's Seville registrations, and Chen/Palma/Ward's
                composite inflow used in the modern literature
  crown share - Hamilton's public/private split, which no modern series carries
"""

import pandas as pd


def main():
    h = pd.read_csv("hamilton_1929_arrivals.csv")
    chain = pd.read_csv("modern/production_to_arrivals.csv").set_index("year")

    rows = []
    for _, r in h.iterrows():
        y0, y1 = int(r.first_year), int(r.last_year)
        w = chain.loc[y0:y1]
        rows.append(dict(
            period=r.period,
            hamilton_silver_t=round(r.silver_kg / 1000, 1),
            hamilton_gold_t=round(r.gold_kg / 1000, 1),
            hamilton_value_t_ag=round(r.value_ag_equiv_kg / 1000, 1),
            crown_share=r.public_share,
            modern_arrivals_t_ag=round(w.arrivals_ag_kg.sum() / 1000, 1),
            production_t_ag=round(w.prod_total_ag_kg.sum() / 1000, 1)))

    d = pd.DataFrame(rows)
    d["hamilton_vs_modern"] = (d.hamilton_value_t_ag
                               / d.modern_arrivals_t_ag).round(3)
    d["arrivals_over_production"] = (d.modern_arrivals_t_ag
                                     / d.production_t_ag).round(3)
    d.to_csv("arrivals_comparison.csv", index=False)
    print(d.to_string(index=False))

    ov = d[d.period >= "1531"]
    print(f"\n1531-1660, tonnes of silver equivalent:")
    print(f"  Hamilton registered arrivals   {ov.hamilton_value_t_ag.sum():>9,.0f}")
    print(f"  modern composite arrivals      {ov.modern_arrivals_t_ag.sum():>9,.0f}")
    print(f"  TePaske production (ours)      {ov.production_t_ag.sum():>9,.0f}")
    print(f"\n  Hamilton as share of modern    "
          f"{ov.hamilton_value_t_ag.sum()/ov.modern_arrivals_t_ag.sum():.1%}")
    print(f"  crown share of arrivals        "
          f"{(h.public_kg_ag_equiv.sum()/h.value_ag_equiv_kg.sum()):.1%}"
          f"   (Hamilton states 26.2% for 1536-1660)")

    print("\ncrown share by decade — the fiscal story:")
    for _, r in h.iterrows():
        bar = "#" * int(r.public_share * 100)
        print(f"  {r.period}  {r.public_share:5.1%}  {bar}")


if __name__ == "__main__":
    main()
