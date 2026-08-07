"""Tidy the raw extraction and run the unit validators."""

import re

import pandas as pd

# Fine silver per peso of 272 maravedis, by monetary period. Implied by the
# book's own paired columns; the breaks are the 1728/1772/1786 reforms.
SILVER_F = [(1728, 0.025560), (1772, 0.024810), (1786, 0.024430), (9999, 0.024245)]
# kg fine gold per silver peso, era-stepped at the 1772/1786 reforms
GOLD_F = [(1771, 0.001551), (1785, 0.001525), (9999, 0.001480)]

def gold_factor(y):
    for cut, f in GOLD_F:
        if y <= cut:
            return f

# kg fine metal per Castilian mark (230.0465 g), by metal and era:
# gold 22k to 1771 then 21k; silver 0.9306 fine to 1727 then 0.9028
def mark_factor(metal, y):
    if metal == "gold":
        return 0.2109 if y <= 1771 else 0.2013
    return 0.2141 if y <= 1727 else 0.2077



def silver_factor(y):
    for cut, f in SILVER_F:
        if y <= cut:
            return f


def entity(title):
    if not isinstance(title, str) or not title.strip():
        return None
    t = re.sub(r"\s*\(?in .*$", "", title, flags=re.I)
    t = re.sub(r"\s*\d{4}[–-]\d{4}.*$", "", t)
    t = re.sub(r"(Registered\s+)?(Annual\s+)?(Silver|Gold)\s+"
               r"(Production|Output|Mintage|Shipments).*$", "", t, flags=re.I)
    t = re.sub(r"^(Caja of|Estimated|Early)\s+", "", t, flags=re.I)
    t = re.sub(r"Mercury.*$", "", t, flags=re.I)
    return re.sub(r"[,\.\*\s]+$", "", t).strip() or None


def main():
    s = pd.read_csv("tep_series.csv")
    m = pd.read_csv("tep_matrix.csv")

    # carry each table's substantive title across its (cont.) pages
    names = {}
    for t, g in s.groupby("table"):
        cand = [x for x in g.table_title.dropna().unique() if str(x).strip()]
        names[t] = max(cand, key=len) if cand else None
    s["table_title"] = s.table.map(names)

    w = (s.pivot_table(index=["table", "table_title", "page", "year"],
                       columns="unit", values="value", aggfunc="sum")
           .reset_index())
    w["entity"] = w.table_title.map(entity)
    ttl = w.table_title.fillna("")
    w["metal"] = "silver"
    w.loc[ttl.str.contains("Gold", case=False), "metal"] = "gold"
    w.loc[ttl.str.contains("Mercury", case=False), "metal"] = "mercury"
    w["measure"] = "output"
    w.loc[ttl.str.contains("Mintage", case=False), "measure"] = "mintage"

    cols = ["table", "entity", "metal", "measure", "page", "year",
            "PESOS", "KILOGRAMS", "MARKS", "QUINTALES"]
    for c in cols:
        if c not in w.columns:
            w[c] = pd.NA
    w = w[cols].rename(columns=str.lower)

    # Table 6-7's printed KILOGRAMS column does not correspond to the marks and
    # pesos on its own row — verified against raw token positions, so this is a
    # defect in the book, not the parse. The pesos and marks are sound and agree
    # with each other, so a recomputed column is supplied and the printed one is
    # left in place, clearly labelled.
    w["kilograms_recomputed"] = pd.NA
    six7 = w.table == "6-7"
    w.loc[six7, "kilograms_recomputed"] = (
        w.loc[six7, "pesos"] * w.loc[six7, "year"].map(gold_factor)).round(1)

    w.to_csv("tepaske_annual.csv", index=False)

    mm = m.copy()

    # Decade labels are typeset across two lines ('1541–' / '1550') and the
    # halves are occasionally paired with the wrong neighbour, yielding spans
    # that run backwards: '1541-1540', '1671-1670'. An end year one BEFORE the
    # start is impossible, so those are repaired to the ten-year span they must
    # be. Genuine short spans such as '1801-1805' are left alone.
    def fix_decade(d):
        m_ = re.match(r"^(1\d{3})-(1\d{3})$", str(d))
        if not m_:
            return d
        y0, y1 = int(m_.group(1)), int(m_.group(2))
        return f"{y0}-{y0 + 9}" if y1 < y0 else d

    bad = mm.decade.map(lambda d: fix_decade(d) != d).sum()
    mm["decade"] = mm.decade.map(fix_decade)
    if bad:
        print(f"repaired {bad} backwards decade labels")

    mnames = {}
    for t, g in mm.groupby("table"):
        cand = [x for x in g.table_title.dropna().unique() if str(x).strip()]
        mnames[t] = max(cand, key=len) if cand else None
    mm["table_title"] = mm.table.map(mnames)
    mm.to_csv("tepaske_decade.csv", index=False)

    # ---------------- validation ----------------
    print(f"annual rows  : {len(w):,}   tables {w.table.nunique()}   "
          f"entities {w.entity.nunique()}")
    print(f"decade rows  : {len(mm):,}   tables {mm.table.nunique()}")

    v = w.dropna(subset=["pesos", "kilograms"])
    v = v[(v.pesos > 0) & (v.kilograms >= 50)]
    sil = v[v.metal == "silver"]
    dev_s = (sil.kilograms / sil.pesos / sil.year.map(silver_factor) - 1).abs()
    gld = v[v.metal == "gold"]
    gld = gld[gld.kilograms >= 5]
    gld = gld[gld.table != "6-7"]  # Guatemala gold: provisional, see README
    dev_g = (gld.kilograms / gld.pesos / gld.year.map(gold_factor) - 1).abs()
    mk = w.dropna(subset=["marks", "kilograms"])
    mk = mk[(mk.marks > 0) & (mk.kilograms >= 50) & (mk.table != "6-7")]
    fac = mk.apply(lambda r: mark_factor(r.metal, r.year), axis=1)
    dev_m = (mk.kilograms / mk.marks / fac - 1).abs()

    print(f"\nsilver peso->kg  : {(dev_s < 0.015).mean():.2%} of {len(sil):,} rows within 1.5%")
    print(f"gold   peso->kg  : {(dev_g < 0.03).mean():.2%} of {len(gld):,} rows within 3%")
    print(f"mark->kg         : {(dev_m < 0.02).mean():.2%} of {len(mk):,} rows within 2%")

    ok = tot = 0
    for t, g in mm.groupby("table"):
        piv = g.pivot_table(index="decade", columns="column", values="value", aggfunc="sum")
        if "TOTAL" not in piv.columns:
            continue
        d = ((piv.drop(columns=["TOTAL"]).sum(axis=1) - piv["TOTAL"]).abs()
             / piv["TOTAL"].replace(0, float("nan"))).dropna()
        ok += int((d < 0.02).sum())
        tot += len(d)
    print(f"decade rows reconciling to printed TOTAL: {ok}/{tot}")

    print("\ncoverage by metal / measure:")
    print(w.groupby(["metal", "measure"])
           .agg(rows=("year", "size"), entities=("entity", "nunique"),
                first=("year", "min"), last=("year", "max")).to_string())


if __name__ == "__main__":
    main()
