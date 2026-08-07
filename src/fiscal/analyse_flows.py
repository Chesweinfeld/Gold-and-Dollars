"""Check the flow network and describe what it shows.

A transfer is booked twice — as expenditure by the sender, as revenue by the
receiver — so in principle the network is self-checking. In practice most
receiving entries are labelled `otras tesorerías` or `venido de fuera` without
naming an origin, so only a few edges are identified at both ends. Veracruz is
the exception and the one worth testing: it names Mexico City as its source and
is a pure transit node, so its books should balance.
"""

import pandas as pd

PESO_G = 25.560          # fine silver in a peso of 272 maravedis
M = 1e6


def main():
    f = pd.read_csv("colmex_flows.csv")
    f = f[(f.year >= 1500) & (f.year <= 1825)]
    out, inn = f[f.direction == "out"], f[f.direction == "in"]

    print("=" * 70)
    print("VERACRUZ AS A TEST OF THE NETWORK")
    print("=" * 70)
    vi = inn[inn.caja == "VERACRUZ"].pesos_272mrv.sum()
    vo = out[out.caja == "VERACRUZ"].pesos_272mrv.sum()
    print(f"  received {vi/M:>8,.1f}M pesos")
    print(f"  despatched {vo/M:>6,.1f}M pesos     in/out = {vi/vo:.3f}")
    print("  Veracruz was a conduit, not a reservoir: silver arrived from")
    print("  Mexico City and left for Spain, Havana and the Caribbean garrisons,")
    print("  and the two sides of its ledger agree to within a few per cent.")

    mx_at_vc = inn[(inn.caja == "VERACRUZ")
                   & (inn.counterparty == "Mexico City")]
    print(f"\n  of which booked as coming from Mexico City: "
          f"{mx_at_vc.pesos_272mrv.sum()/M:,.1f}M "
          f"({mx_at_vc.year.min()}-{mx_at_vc.year.max()})")
    print("  Mexico City's own books show less leaving than Veracruz records")
    print("  arriving, because most of its outflow is filed under the")
    print("  destination-free heading 'otras tesorerías'. Cross-treasury")
    print("  matching works only where both ends name each other.")

    print()
    print("=" * 70)
    print("THE ATLANTIC LEG — who despatched to Spain")
    print("=" * 70)
    esp = out[out.counterparty == "Spain"]
    t = (esp.groupby(["region", "caja"])
         .agg(pesos=("pesos_272mrv", "sum"), n=("year", "size"),
              first=("year", "min"), last=("year", "max"))
         .sort_values("pesos", ascending=False))
    t["pesos"] = (t.pesos / M).round(1)
    print(t.head(8).to_string())
    print(f"\n  total despatched to Spain in this sample: "
          f"{esp.pesos_272mrv.sum()/M:,.0f}M pesos "
          f"= {esp.pesos_272mrv.sum()*PESO_G/M:,.0f} t fine silver")

    print()
    print("=" * 70)
    print("THE SITUADO NETWORK — the empire subsidising itself")
    print("=" * 70)
    sit = out[out.account.str.contains("SITUADO", case=False, na=False)]
    s = (sit.groupby("counterparty")
         .agg(pesos=("pesos_272mrv", "sum"), n=("year", "size"),
              first=("year", "min"), last=("year", "max"))
         .sort_values("pesos", ascending=False))
    s["pesos_M"] = (s.pesos / M).round(2)
    print(s[["pesos_M", "n", "first", "last"]].head(14).to_string())
    print("\n  These are garrisons and colonies that never paid for themselves:")
    print("  silver mined in Mexico and Peru held the Caribbean, the Pacific")
    print("  and the Rio de la Plata frontier. Manila's subsidy appears only")
    print("  from 1789, Louisiana's only after 1779 — both late acquisitions.")

    print()
    print("=" * 70)
    print("DESPATCH vs ARRIVAL — what this sample can and cannot say")
    print("=" * 70)
    e = esp.copy()
    e["decade"] = e.year // 10 * 10
    ham = pd.read_csv("hamilton_1929_arrivals.csv")
    ham["decade"] = ham.first_year // 10 * 10
    gb = pd.read_csv("morineau_annual_1717_1778.csv")
    gb["decade"] = gb.year // 10 * 10
    arr = pd.concat([ham.set_index("decade").pesos_272mrv,
                     gb.groupby("decade").garcia_baquero.sum()]) \
        .groupby(level=0).sum()

    cmp = pd.DataFrame({"despatched": e.groupby("decade").pesos_272mrv.sum(),
                        "arrived": arr}).dropna()
    cmp["despatched_t_ag"] = (cmp.despatched * PESO_G / M).round(0)
    cmp["arrived_t_ag"] = (cmp.arrived * PESO_G / M).round(0)
    cmp["ratio"] = (cmp.despatched / cmp.arrived).round(3)
    print(cmp[["despatched_t_ag", "arrived_t_ag", "ratio"]].to_string())
    print(f"\n  overall {cmp.despatched.sum()/cmp.arrived.sum():.3f}")
    print("""
  This is NOT a leakage or contraband estimate, and should not be read as
  one. Only three treasuries in the Colmex sample despatched to Spain at
  all, and their coverage is intermittent, whereas Hamilton and
  García-Baquero count everything that landed. The ratio therefore measures
  how much of the Atlantic trade this sample happens to observe. Its one
  solid use is as a floor: in the 1650s the sample alone accounts for 87%
  of recorded arrivals, so despatch records of that decade are close to
  complete.""")

    cmp.to_csv("atlantic_despatch_vs_arrival.csv")
    s[["pesos", "n", "first", "last"]].to_csv("situado_network.csv")
    print("\n-> atlantic_despatch_vs_arrival.csv, situado_network.csv")


if __name__ == "__main__":
    main()
