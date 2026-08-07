"""Assemble the gold chain: mining district -> mint -> American port -> Cadiz.

This does NOT trace parcels. No source in this collection follows a consignment
from a placer to a hold. What it does is build the three layers that exist and
state, per route, what kind of evidence links them:

  origin   gold output by named caja/district and decade   (TePaske ch.2)
  mint     gold struck, by mint and year                   (TePaske ch.5, ch.6)
  port     value laded, by American port and year          (Garcia-Baquero app.)

The port layer is NOT metal-typed: Garcia-Baquero's appendix records pesos per
vessel, not gold pesos and silver pesos. So the mint->port link has to be earned
rather than assumed. It is earned where a region produced essentially one metal:
New Granada's silver was 4% of its gold by value (table 6-1), so value leaving
Cartagena is gold to within that margin. It is NOT earned at Veracruz, where
Mexican gold is a rounding error against Mexican silver -- and the ratio test
below shows exactly that, which is the point of running it.

Outputs -> data/routes/
"""

import re
import pandas as pd

# Caja codes as printed in the column heads of tables 2-4/2-5 (Mexico) and
# 2-8/2-9 (Peru). 2-9 prints ARI and PNO merged into a single ARIPNO column.
MEXICO_CAJAS = {
    "CHI": "Chihuahua", "DUR": "Durango", "GDA": "Guadalajara",
    "GTO": "Guanajuato", "MEX": "Mexico City", "PCA": "Pachuca",
    "ROS": "Rosario", "SLP": "San Luis Potosi", "ZAC": "Zacatecas",
    "ZIM": "Zimapan",
}
PERU_CAJAS = {
    "ARI": "Arica", "ARQ": "Arequipa", "CBY": "Carabaya",
    "CTO": "Castrovirreyna", "CZO": "Cuzco", "HVA": "Huancavelica",
    "LIM": "Lima", "LPZ": "La Paz", "ORO": "Oruro", "PNO": "Puno",
    "POT": "Potosi", "TJO": "Trujillo", "ARIPNO": "Arica and Puno",
}

# Garcia-Baquero's port abbreviations in the ship appendix.
PORTS = {
    "VRC": "Veracruz", "HAB": "Havana", "CRC": "Caracas",
    "B-A": "Buenos Aires", "CTG": "Cartagena", "LMA": "Callao (Lima)",
    "HON": "Honduras", "P-R": "Puerto Rico", "CUM": "Cumana",
    "CAM": "Campeche", "PTB": "Portobelo", "GUA": "Guatemala",
}

# Annual gold mintage tables, by mint.
MINTS = {
    "5-2": "Mexico City", "5-7": "Lima", "5-11": "Potosi",
    "6-2": "Santa Fe de Bogota", "6-4": "Popayan",
    "6-7": "Guatemala", "6-8": "Santiago de Chile",
}

# Mint -> Atlantic port of embarkation, with the basis for the claim. `share`
# is what fraction of that mint's gold is asserted to leave by that port; it is
# a stated prior, not a measurement, and every route carries its evidence class.
#   ship      port appears in the vessel appendix and the ratio test is run
#   fiscal    a treasury transfer edge exists in colmex_flows
#   inferred  geography and the fleet system only -- no series links the two
ROUTES = [
    ("Santa Fe de Bogota", "Cartagena",    1621, 1810, 0.70, "ship",
     "Magdalena down from Honda; Cartagena is the only Atlantic outlet"),
    ("Santa Fe de Bogota", "Portobelo",    1621, 1739, 0.30, "ship",
     "galeones leg, ends with the 1739 suspension of the fleet"),
    ("Popayan",            "Cartagena",    1758, 1810, 0.60, "ship",
     "Cauca valley gold, minted Popayan, shipped Cartagena"),
    ("Popayan",            "Callao (Lima)", 1758, 1810, 0.40, "inferred",
     "Pacific leg via Buenaventura/Guayaquil; no series measures the split"),
    ("Mexico City",        "Veracruz",     1733, 1810, 0.95, "ship",
     "sole legal Atlantic port for New Spain"),
    ("Mexico City",        "Acapulco",     1733, 1810, 0.05, "fiscal",
     "Manila galleon; Acapulco is a caja in colmex_flows"),
    ("Lima",               "Portobelo",    1696, 1739, 0.60, "ship",
     "Callao-Portobelo-galeones, the pre-1739 route"),
    ("Lima",               "Buenos Aires", 1740, 1821, 0.50, "ship",
     "Cape Horn register ships after the galeones lapse"),
    ("Potosi",             "Buenos Aires", 1778, 1810, 0.80, "fiscal",
     "Rio de la Plata viceroyalty 1776 redirects Upper Peru"),
    ("Santiago de Chile",  "Buenos Aires", 1756, 1810, 0.60, "fiscal",
     "overland to Mendoza; Chile-Buenos Aires edges exist in colmex_flows"),
    ("Guatemala",          "Honduras",     1733, 1810, 0.90, "ship",
     "Golfo Dulce / Omoa; tiny volumes throughout"),
]


def _units(d, table_pesos, table_kg, codes, region):
    """Tables 2-4/2-8 print millions of pesos, 2-5/2-9 the same cells in kg."""
    out = []
    for tbl, unit, scale in ((table_pesos, "pesos", 1e6), (table_kg, "kg", 1.0)):
        p = (d[d.table == tbl]
             .pivot_table(index="decade", columns="column", values="value",
                          aggfunc="sum"))
        for code, name in codes.items():
            if code not in p.columns:
                continue
            for dec, v in p[code].dropna().items():
                if not re.match(r"^1\d{3}-1\d{3}$", str(dec)):
                    continue
                out.append({"region": region, "district": name, "decade": dec,
                            "unit": unit, "value": v * scale})
    return out


def build_origin(d):
    rows = _units(d, "2-4", "2-5", MEXICO_CAJAS, "Mexico")
    rows += _units(d, "2-8", "2-9", PERU_CAJAS, "Peru")

    # Regions the book gives only as a single series, no district breakdown.
    for tbl, region in (("2-6", "New Granada"), ("2-7", "Ecuador"),
                        ("2-10", "Chile"), ("2-11", "Brazil")):
        p = (d[d.table == tbl]
             .pivot_table(index="decade", columns="column", values="value",
                          aggfunc="sum"))
        for col, unit in (("PESOS", "pesos"), ("KILOGRAMS", "kg")):
            if col not in p.columns:
                continue
            for dec, v in p[col].dropna().items():
                if not re.match(r"^1\d{3}-1\d{3}$", str(dec)):
                    continue
                rows.append({"region": region, "district": f"{region} (all)",
                             "decade": dec, "unit": unit, "value": v})
    return pd.DataFrame(rows)


def ratio_test(a, s):
    """Value laded at a port against gold struck at the mint feeding it.

    A ratio near 1 says the port's cargo is about the size of that gold stream;
    a ratio in the tens says the cargo is something else (silver). This is the
    only handle the data gives on whether a port was a gold port.
    """
    out = []
    for mint, tbl, port in (("Santa Fe + Popayan", ("6-2", "6-4"), "CTG"),
                            ("Mexico City", ("5-2",), "VRC"),
                            ("Lima", ("5-7",), "LMA")):
        mint_y = (a[(a.metal == "gold") & (a.table.isin(tbl))]
                  .groupby("year").pesos.sum())
        port_y = s[s.port == port].groupby("year").total.sum()
        j = pd.DataFrame({"mint_pesos": mint_y, "port_pesos": port_y})
        j = j.loc[1717:1778].fillna(0)
        j["decade"] = (j.index // 10) * 10
        g = j.groupby("decade").sum()
        g = g[g.mint_pesos > 0]
        if g.empty:
            continue
        out.append({
            "mint": mint, "port": PORTS[port],
            "decades": len(g),
            "mint_pesos": int(g.mint_pesos.sum()),
            "port_pesos": int(g.port_pesos.sum()),
            "port_over_mint": round(g.port_pesos.sum() / g.mint_pesos.sum(), 2),
            "corr_decade": round(g.port_pesos.corr(g.mint_pesos), 3),
        })
    return pd.DataFrame(out)


def main():
    a = pd.read_csv("data/production/tepaske_annual.csv")
    d = pd.read_csv("data/production/tepaske_decade.csv")
    s = pd.read_csv("data/arrivals/gb_ships_1717_1778.csv")

    origin = build_origin(d)
    origin.to_csv("data/routes/gold_origin_decade.csv", index=False)

    mint = (a[(a.metal == "gold") & (a.table.isin(MINTS))]
            .assign(mint=lambda x: x.table.map(MINTS))
            [["mint", "year", "pesos", "kilograms", "marks", "table"]]
            .sort_values(["mint", "year"]))
    mint.to_csv("data/routes/gold_mint_annual.csv", index=False)

    port = (s.assign(port_name=s.port.map(PORTS).fillna(s.port))
             .groupby(["port_name", "year"])
             .agg(vessels=("vessel", "size"),
                  real_hacienda=("real_hacienda", "sum"),
                  particulares=("particulares", "sum"),
                  total_pesos=("total", "sum"))
             .reset_index())
    port.to_csv("data/routes/gold_port_annual.csv", index=False)

    routes = pd.DataFrame(ROUTES, columns=[
        "mint", "port", "year_from", "year_to", "assumed_share",
        "evidence", "basis"])
    routes.to_csv("data/routes/gold_routes.csv", index=False)

    test = ratio_test(a, s)
    test.to_csv("data/routes/port_gold_ratio_test.csv", index=False)

    print(f"origin : {len(origin):,} rows  "
          f"{origin.district.nunique()} districts  "
          f"{origin.region.nunique()} regions")
    print(f"mint   : {len(mint):,} rows  {mint.mint.nunique()} mints  "
          f"{int(mint.year.min())}-{int(mint.year.max())}")
    print(f"port   : {len(port):,} rows  {port.port_name.nunique()} ports  "
          f"{int(port.year.min())}-{int(port.year.max())}")
    print(f"routes : {len(routes)} edges  "
          f"{(routes.evidence == 'ship').sum()} ship-evidenced, "
          f"{(routes.evidence == 'fiscal').sum()} fiscal, "
          f"{(routes.evidence == 'inferred').sum()} inferred")
    print("\nport value against the gold struck upstream, 1717-1778:")
    print(test.to_string(index=False))
    print("\nCartagena near 1 means its cargo IS the New Granadan gold.")
    print("Veracruz in the tens means its cargo is silver, and the Mexican")
    print("gold inside it cannot be separated out by these sources.")


if __name__ == "__main__":
    main()
