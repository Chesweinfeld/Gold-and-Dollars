"""Join TePaske's registered silver OUTPUT to the Colmex caja FISCAL RECEIPTS.

Two different measurements of the same mining districts:
  * TePaske (2010) appendix tables  -> registered production, pesos + kilograms
  * Colmex caja real accounts       -> what the treasury actually booked

Joining them at caja-year gives the implied effective severance rate, which is
the quantity every "tax receipts -> output" reconstruction has to assume.
Here it is measured instead.
"""

import re
import unicodedata

import pandas as pd

# A peso de ocho / peso of 272 maravedis is TePaske's unit. The peso ensayado
# used in the early Andean accounts is 450 maravedis.
ENSAYADO_TO_OCHO = 450 / 272

# TePaske caja -> Colmex workbook name(s).
# Mexico and San Juan de Matucana/Jauja are split across sequential workbooks
# (verified non-overlapping in years, so summing is safe).
# CHIHUAHA is a byte-identical duplicate of CHIHUAHUA in the Colmex zip and is
# deliberately excluded — summing both would double every Chihuahua year.
CROSSWALK = {
    "Mexico": ["MEXICO01", "MEXICO02", "MEXICO03", "MEXICO04"],
    "San Juan De Matucana-Jauja": ["SAN JUAN DE MATUCANA", "JAUJA"],
    "Pachua": ["PACHUCA"],
    "Pasco": ["VICO Y PASCO"],
    "Rosario/Los Alamos/Cosala": ["ROSARIO"],
    "San Luis Potosi": ["SANLUISPOTOSI"],
    "Chihuahua": ["CHIHUAHUA"],          # NOT CHIHUAHA (duplicate file)
    "Bolanos": ["BOLAÑOS"],
    "Zimapan": ["ZIMAPAN"],
    "Veracruz": ["VERACRUZ"],
}


def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^A-Z]", "", s.upper())


def build_crosswalk(tep_cajas, col_cajas):
    by_norm = {}
    for c in col_cajas:
        by_norm.setdefault(norm(c), []).append(c)
    out, unmatched = {}, []
    for t in tep_cajas:
        if t in CROSSWALK:
            hits = [c for c in CROSSWALK[t] if c in set(col_cajas)]
        else:
            hits = by_norm.get(norm(t), [])
        if hits:
            out[t] = hits
        else:
            unmatched.append(t)
    return out, unmatched


def main():
    tep = pd.read_csv("tepaske_silver_annual.csv")
    col = pd.read_csv("colmex_mining_annual.csv")
    col = col[col.tax_class == "silver_tax"].copy()

    xwalk, unmatched = build_crosswalk(sorted(tep.caja.dropna().unique()),
                                       sorted(col.caja.unique()))
    print(f"crosswalk: {len(xwalk)} TePaske cajas matched, {len(unmatched)} unmatched")
    if unmatched:
        print("  unmatched:", unmatched)

    # Colmex side: convert ensayados to pesos de ocho so both sides share a unit.
    col["pesos8"] = col.amount * col.currency.map(
        lambda c: ENSAYADO_TO_OCHO if c == "ENSAYADOS" else 1.0)
    col["mixed_currency"] = col.currency == "ENSAYADOS"

    rows = []
    for t, srcs in xwalk.items():
        g = col[col.caja.isin(srcs)]
        a = (g.groupby("year")
               .agg(tax_pesos8=("pesos8", "sum"),
                    any_ensayado=("mixed_currency", "any"))
               .reset_index())
        a["caja"] = t
        rows.append(a)
    colx = pd.concat(rows, ignore_index=True)

    tepx = (tep.dropna(subset=["year"])
               .groupby(["caja", "year"], as_index=False)
               .agg(output_pesos=("pesos", "sum"), output_kg=("kilograms", "sum")))

    j = tepx.merge(colx, on=["caja", "year"], how="outer", indicator=True)
    # float NaN, not pd.NA: dividing by pd.NA yields an object column and the
    # rounding below then fails on NAType
    j["implied_tax_rate"] = j.tax_pesos8 / j.output_pesos.replace(0, float("nan"))
    j["match"] = j._merge.map({"both": "both", "left_only": "tepaske_only",
                               "right_only": "colmex_only"})

    # Where TePaske derived output by dividing receipts by an assumed rate, the
    # ratio recovers that constant exactly and the join is circular: such rows
    # cannot be used to *measure* the effective rate. Flag them by spotting
    # implied rates repeated to 4dp across many caja-years.
    rr = j.implied_tax_rate.round(4)
    j["rate_cluster_n"] = rr.map(rr.value_counts()).fillna(0).astype(int)
    j["likely_derived"] = j.rate_cluster_n >= 20

    j = j.drop(columns=["_merge"]).sort_values(["caja", "year"])
    j.to_csv("joined_output_vs_fiscal.csv", index=False)

    both = j[j.match == "both"]
    print(f"\njoined rows: {len(j):,}   overlapping caja-years: {len(both):,}")
    print(j.match.value_counts().to_string())

    r = both.dropna(subset=["implied_tax_rate"])
    r = r[(r.output_pesos > 1000) & (r.tax_pesos8 > 0)]
    print(f"\nimplied effective severance rate ({len(r):,} caja-years):")
    print(r.implied_tax_rate.describe(percentiles=[.1, .25, .5, .75, .9]).round(3).to_string())
    pre = r[r.year <= 1700].implied_tax_rate.median()
    post = r[r.year > 1700].implied_tax_rate.median()
    print(f"  median to 1700: {pre:.3f}   after 1700: {post:.3f}")

    print("\nby caja (median rate, overlapping years):")
    tab = (r.groupby("caja")
             .agg(years=("year", "size"), first=("year", "min"), last=("year", "max"),
                  median_rate=("implied_tax_rate", "median"))
             .sort_values("years", ascending=False).round(3))
    print(tab.to_string())


if __name__ == "__main__":
    main()
