"""Trace silver: mining caja -> hub -> port -> Spain, every hop measured.

Silver is the case gold could not be. For gold, the middle of the chain was
missing: New Granada has no caja in the fiscal record at all, so district -> port
had to be inferred. For silver the treasury transfers exist, so each hop is an
observed quantity rather than an assumption, and the chain can be checked at
every joint instead of only at its ends.

  hop 1   mining caja -> hub        colmex_flows, e.g. ZACATECAS -> Mexico City
  hop 2   hub -> port               MEXICO0x -> VERACRUZ
  hop 3   port -> Spain / Havana    VERACRUZ -> Spain (Havana is the rendezvous)
  hop 4   port -> Cadiz             Garcia-Baquero's vessels, arrival side

What hop 1 carries is the crown's *revenue* from a district, not the district's
metal: the mines' output stayed with the miners net of tax. So the ratio of
remittance to output should land near the royal share, and that is a real test
of whether the edges carry what they claim to.

CIRCULARITY. Where TePaske had no independent output figure he derived one from
tax receipts at an assumed rate, so on those caja-years remittance/output just
returns the assumption. `joined_output_vs_fiscal.csv` flags them. The hop-1 test
below runs on unflagged caja-years ONLY, and prints the flagged ratio beside it
so the difference is visible.

Outputs -> data/routes/
"""

import pandas as pd

# TePaske's table entity -> the caja label used in the Colmex flow file. The
# Mexico City caja is split across four numbered account books; CHIHUAHA is a
# misspelling present in the source and both spellings occur.
CAJA_MAP = {
    "Zacatecas": ["ZACATECAS"], "Guanajuato": ["GUANAJUATO"],
    "Durango": ["DURANGO"], "Guadalajara": ["GUADALAJARA"],
    "Pachua": ["PACHUCA"], "San Luis Potosi": ["SANLUISPOTOSI"],
    "Bolanos": ["BOLAÑOS"], "Rosario/Los Alamos/Cosala": ["ROSARIO"],
    "Sombrerete": ["SOMBRERETE"], "Zimapan": ["ZIMAPAN"],
    "Chihuahua": ["CHIHUAHUA", "CHIHUAHA"],
    "Mexico": ["MEXICO01", "MEXICO02", "MEXICO03", "MEXICO04"],
    "Potosí": ["Potosí"], "Oruro": ["ORURO"], "Lima": ["LIMA"],
    "Carangas": ["CARANGAS"], "Chucuito": ["CHUCUITO"],
    "Cailloma": ["CAILLOMA"], "Arequipa": ["AREQUIPA"], "Arica": ["ARICA"],
    "Trujillo": ["TRUJILLO"], "Huancavelica": ["HUANCAVELICA"],
    "Castrovirreyna": ["CASTROVIRREYNA"], "Huamanga": ["HUAMANGA"],
    "Pasco": ["VICO Y PASCO"],
    "San Juan De Matucana-Jauja": ["SAN JUAN DE MATUCANA", "JAUJA"],
}

HUBS = {"Mexico City", "Lima"}
PORTS = {"VERACRUZ", "BUENOS AIRES", "ACAPULCO", "GUAYAQUIL"}

# The four legs of the chain, as (edge predicate, label). Havana is kept
# separate from Spain: it is the fleet rendezvous, not a destination, and
# lumping it into "to Spain" would double-count the same metal.
LEGS = [
    ("district_to_hub", "mining caja -> hub"),
    ("hub_to_port", "hub -> Atlantic port"),
    ("port_to_spain", "port -> Spain"),
    ("port_to_havana", "port -> Havana (rendezvous)"),
]


MEXICO_HUB = ("MEXICO01", "MEXICO02", "MEXICO03", "MEXICO04")

# Caja labels are raw account-book names ('MEXICO01', 'VERACRUZ'); counterparty
# labels were normalized when the flows were built ('Mexico City', 'Veracruz').
# The same node therefore arrives under two spellings depending on which side of
# the transfer recorded it, and both have to be folded together before the legs
# can be classified at all.
def node(x):
    if x in MEXICO_HUB:
        return "Mexico City"
    return {"LIMA": "Lima", "VERACRUZ": "Veracruz", "ACAPULCO": "Acapulco",
            "BUENOS AIRES": "Buenos Aires", "GUAYAQUIL": "Guayaquil",
            "Potosí": "Potosi", "PANAMA": "Panama"}.get(x, x)


def classify(origin, dest):
    o, d = node(origin), node(dest)
    if d in HUBS and o not in HUBS:
        return "district_to_hub"
    if o == "Mexico City" and d in ("Veracruz", "Acapulco"):
        return "hub_to_port"
    if o == "Lima" and d in ("Panama", "Buenos Aires", "Guayaquil"):
        return "hub_to_port"
    if d == "Spain":
        return "port_to_spain"
    if d == "Havana":
        return "port_to_havana"
    return None


ENSAYADO_TO_OCHO = 450 / 272


def hop1_test(a, m, j, min_output=1_000_000):
    """Silver TAX collected in a district, against that district's silver output.

    The comparator is the mining-tax line from `colmex_mining_annual.csv`, not
    the district's total remittance to the hub. Total remittance also carries
    tribute, alcabala and everything else the caja collected, which is why it
    ran to 0.7 at Arequipa and Castrovirreyna -- small cajas where mining was a
    minor part of the books. Against the mining tax alone the ratio means what
    it should: the crown's effective take on registered silver.

    Districts below `min_output` in matched clean years are dropped. Trujillo
    otherwise reports a share of 91 on a denominator of 2,190 pesos.
    """
    out = (a[(a.metal == "silver") & (a.measure == "output")]
           [["entity", "year", "pesos"]].dropna())
    tax = m[m.tax_class.isin(["silver_tax", "silver_other"])].copy()
    tax["pesos8"] = tax.amount * tax.currency.map(
        {"ENSAYADOS": ENSAYADO_TO_OCHO}).fillna(1.0)
    tax = tax[tax.currency != "ORO"]
    tx = tax.groupby(["caja", "year"]).pesos8.sum().reset_index()
    flags = j.set_index(["caja", "year"]).likely_derived

    rows = []
    for ent, cajas in CAJA_MAP.items():
        o = out[out.entity == ent].set_index("year").pesos
        r = tx[tx.caja.isin(cajas)].groupby("year").pesos8.sum()
        both = sorted(set(o.index) & set(r.index))
        if len(both) < 10:
            continue
        clean = [y for y in both if not bool(flags.get((ent, y), False))]
        derived = [y for y in both if bool(flags.get((ent, y), False))]
        if not clean or o.loc[clean].sum() < min_output:
            continue
        rec = {"district": ent, "years_matched": len(both),
               "years_clean": len(clean),
               "output_pesos": int(o.loc[clean].sum()),
               "silver_tax_pesos": int(r.loc[clean].sum())}
        rec["tax_share_clean"] = round(
            rec["silver_tax_pesos"] / rec["output_pesos"], 4)
        rec["tax_share_derived"] = (
            round(r.loc[derived].sum() / o.loc[derived].sum(), 4)
            if derived and o.loc[derived].sum() else None)
        rows.append(rec)
    return pd.DataFrame(rows).sort_values("output_pesos", ascending=False)


def build_edges(f):
    """One row per directed edge, using whichever side recorded it more fully.

    A transfer is booked twice: the sender writes it as expenditure, the
    receiver as revenue. The two sides are not equally well kept. Mexico City's
    books record only 20.8M pesos of remittances to Veracruz; Veracruz's books
    record 292.5M received from Mexico City. Taking the sender side alone loses
    93% of the largest silver artery in the empire.
    """
    o = f[f.direction == "out"].rename(
        columns={"caja": "origin", "counterparty": "dest"})
    i = f[f.direction == "in"].rename(
        columns={"caja": "dest", "counterparty": "origin"})
    o, i = o.assign(side="sender"), i.assign(side="receiver")
    both = pd.concat([o, i], ignore_index=True)
    both["origin"] = both.origin.map(node)
    both["dest"] = both.dest.map(node)
    g = (both.groupby(["origin", "dest", "side"])
         .agg(n=("year", "size"), pesos=("pesos_272mrv", "sum"),
              year_from=("year", "min"), year_to=("year", "max"))
         .reset_index())
    # keep the better-attested side of each edge, and record the other
    g = g.sort_values("pesos", ascending=False)
    best = g.drop_duplicates(subset=["origin", "dest"], keep="first").copy()
    sides = g.groupby(["origin", "dest"]).side.nunique().rename("sides")
    other = g.groupby(["origin", "dest"]).pesos.min().rename("pesos_low_side")
    best = best.merge(other, on=["origin", "dest"], how="left")
    best = best.merge(sides, on=["origin", "dest"], how="left")
    # Only an edge booked by BOTH parties can be checked; where one side never
    # recorded it there is no second number, not a second number of zero.
    best.loc[best.sides < 2, "pesos_low_side"] = None
    best["agreement"] = (best.pesos_low_side / best.pesos).round(3)
    return best.drop(columns="sides")


def main():
    a = pd.read_csv("data/production/tepaske_annual.csv")
    f = pd.read_csv("data/fiscal/colmex_flows.csv")
    j = pd.read_csv("data/fiscal/joined_output_vs_fiscal.csv")
    s = pd.read_csv("data/arrivals/gb_ships_1717_1778.csv")

    m = pd.read_csv("data/fiscal/colmex_mining_annual.csv")

    edges = build_edges(f)
    edges["leg"] = [classify(a_, b_) for a_, b_ in zip(edges.origin, edges.dest)]
    edges = edges.dropna(subset=["leg"]).sort_values(
        ["leg", "pesos"], ascending=[True, False])
    # 'unspecified' is an origin the flow parser could not name, not a place.
    # It is over a third of the hub inflow and would dominate any leg total, so
    # it is kept in the file and excluded from the arithmetic.
    named = edges[edges.origin != "unspecified"]
    edges.to_csv("data/routes/silver_chain_edges.csv", index=False)

    h1 = hop1_test(a, m, j)
    h1.to_csv("data/routes/silver_hop1_remittance_test.csv", index=False)

    # Veracruz: fiscal despatch to Spain against vessels arriving from Veracruz.
    vs = (f[(f.caja == "VERACRUZ") & (f.direction == "out") &
            (f.counterparty == "Spain")].groupby("year").pesos_272mrv.sum())
    vships = s[s.port == "VRC"].groupby("year").total.sum()
    cmp = pd.DataFrame({"veracruz_despatched": vs, "vessels_at_cadiz": vships})
    cmp = cmp.loc[1717:1778].fillna(0)
    cmp["decade"] = (cmp.index // 10) * 10
    dec = cmp.groupby("decade").sum()
    dec.to_csv("data/routes/veracruz_despatch_vs_ships.csv")

    print("chain volume by leg (named origins only):")
    for leg, label in LEGS:
        sub = named[named.leg == leg]
        print(f"  {label:26s} {len(sub):3d} edges  "
              f"{sub.pesos.sum()/1e6:9,.1f}M pesos  "
              f"{int(sub.year_from.min())}-{int(sub.year_to.max())}")
    unspec = edges[edges.origin == "unspecified"].pesos.sum()
    print(f"  {'(unnamed origin, excluded)':26s}      "
          f"{unspec/1e6:9,.1f}M pesos")

    # Where both parties booked the same transfer, the two figures should match.
    ck = named.dropna(subset=["agreement"]).sort_values("agreement")
    print(f"\ndouble-entry check — {len(ck)} edges booked by both parties, "
          f"median agreement {ck.agreement.median():.3f}")
    print("worst-agreeing edges:")
    print(ck.head(4)[["origin", "dest", "pesos", "pesos_low_side",
                      "agreement"]].to_string(index=False))

    print("\nhop 1 — silver tax collected as a share of silver output")
    print("(clean = caja-years TePaske did NOT derive from receipts)\n")
    print(h1.to_string(index=False))

    cl = h1[h1.years_clean >= 20]
    print(f"\nmedian clean share, {len(cl)} districts with 20+ clean years: "
          f"{cl.tax_share_clean.median():.4f}")
    d = h1.dropna(subset=["tax_share_derived"])
    print(f"median on TePaske-derived years, {len(d)} districts: "
          f"{d.tax_share_derived.median():.4f}")

    # The circularity signature, seen across districts rather than within one.
    # A real effective tax rate varies by district and century -- different ores,
    # different exemptions, different smuggling. A rate that was assumed does
    # not vary at all. Compare the spread of the two columns.
    q = h1.dropna(subset=["tax_share_derived"])
    iqr_c = q.tax_share_clean.quantile(.75) - q.tax_share_clean.quantile(.25)
    iqr_d = q.tax_share_derived.quantile(.75) - q.tax_share_derived.quantile(.25)
    near = ((q.tax_share_derived - 0.1135).abs() < 0.01).sum()
    print(f"\ncross-district spread of the tax share (IQR over {len(q)} districts)")
    print(f"  independently recorded years : {iqr_c:.4f}")
    print(f"  TePaske-derived years        : {iqr_d:.4f}"
          f"   ({iqr_c / iqr_d:.1f}x tighter)")
    print(f"  derived districts within 1pt of 0.1135: {near}/{len(q)}")

    print("\nVeracruz despatch to Spain vs vessels arriving from Veracruz:")
    print(dec.round(0).to_string())


if __name__ == "__main__":
    main()
