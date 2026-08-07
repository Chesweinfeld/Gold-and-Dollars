"""Extract Hamilton (1929), 'Imports of American Gold and Silver into Spain,
1503-1660', QJE 43(3), 436-472.

Two printed tables:
  Table A (p.464) average annual registered imports by ten-year period, split
          public (crown) / private / total.
  Table B (p.468) silver and gold as percentages of imports BY WEIGHT, by
          ten-year period, 1521-1660. Silver first reached Spain in November
          1519, so the two decades before 1521 are taken as all gold.

Combining them gives decade-level kilograms of fine gold and fine silver split
by crown vs private ownership. Nothing in the modern literature carries that
split, which is the reason for digitizing this article.

Units — an unresolved discrepancy in the source
----------------------------------------------
Hamilton's footnote defines the Table A peso as 450 maravedis = 652.635 grains
of fine silver (42.289 g), and that definition is internally consistent: a peso
of 272 maravedis holds 25.560 g, and 450/272 x 25.560 = 42.289.

But it cannot be reconciled with Hamilton's own stated metal totals. Valuing
the 895.6 million pesos of Table A at 42.289 g implies 37,874 tonnes of
silver-equivalent, whereas the 16,632.6 t of silver and 181.2 t of gold he
reports are worth ~18,935 t — a factor of 2.00. Recovering 42.289 g would
require a gold:silver ratio of 117:1 rather than the ~12-16:1 that actually
prevailed.

TePaske's table 7-1, which restates Hamilton by decade "in Millions of Pesos of
272 Maravedis", resolves it the same way: his figures are a constant 0.8272 of
Table A's across all sixteen decades, i.e. exactly half of the 450/272 = 1.654
that the footnote would require.

So the conversion here is derived from Hamilton's stated metal totals rather
than from his footnote, and the footnote is flagged rather than trusted. The
raw printed values are preserved unchanged so a reader can redo this.
"""

import csv
import re
import sys

import pdfplumber

# Hamilton's stated totals for registered imports, 1503-1660 (p.468)
STATED_AG_KG = 16_632_648.20
STATED_AU_KG = 181_234.95

PESO_272_G = 25.560          # fine silver in a peso of 272 maravedis
FOOTNOTE_PESO_G = 652.635 * 0.06479891   # 42.289 g, per Hamilton's footnote

ROW_A = re.compile(r"^(1\d{3})-(1\d{3})\s+([\d,]+\.\d)\s+([\d,]+\.\d)\s+([\d,]+\.\d)")
ROW_B = re.compile(r"(1\d{3})-(1\d{3})\s+(\d{1,3}\.\d+)\s+(\d{0,3}\.\d+)")


def num(s):
    return float(s.replace(",", ""))


def parse(path):
    """Read Tables A and B exactly as printed."""
    pdf = pdfplumber.open(path)
    a, b = {}, {}
    for page in pdf.pages:
        for ln in (page.extract_text() or "").split("\n"):
            ln = ln.strip()
            m = ROW_A.match(ln)
            if m:
                a[f"{m.group(1)}-{m.group(2)}"] = dict(
                    public=num(m.group(3)), private=num(m.group(4)),
                    total=num(m.group(5)))
                continue
            for mm in ROW_B.finditer(ln):
                ag, au = float(mm.group(3)), float(mm.group(4))
                if abs(ag + au - 100) < 0.01:      # the two columns are shares
                    b[f"{mm.group(1)}-{mm.group(2)}"] = dict(pct_silver=ag,
                                                             pct_gold=au)
    return a, b


def weights(rows, peso_g, ratio):
    """Split each decade's value into fine kg of each metal.

    The peso measures VALUE, so weight follows from the bimetallic ratio: with
    s and g the weight shares, value = W*(s + ratio*g), hence W = value/(s+ratio*g).
    """
    ag = au = 0.0
    for r in rows:
        value_kg = r["total_pesos"] * peso_g / 1000.0
        s, g = r["pct_silver_by_weight"] / 100.0, r["pct_gold_by_weight"] / 100.0
        w = value_kg / (s + ratio * g)
        r["_w"], r["_ag"], r["_au"] = w, w * s, w * g
        ag += r["_ag"]
        au += r["_au"]
    return ag, au


def tepaske_scale(rows, matrix_csv="tep_matrix.csv"):
    """Pin the peso's silver content using TePaske's table 7-1, which restates
    Hamilton by decade in pesos of 272 maravedis.

    Solving for the peso and the bimetallic ratio together is underdetermined —
    the two trade off along a flat ridge — so the peso is fixed by this external
    published restatement and the ratio is then left free as a genuine test.
    """
    import csv as _csv
    tep = {}
    with open(matrix_csv, encoding="utf-8") as fh:
        for r in _csv.DictReader(fh):
            if r["table"] == "7-1" and r["column"] == "HAMILTON" \
                    and r["decade"] != "TOTAL":
                tep[r["decade"]] = float(r["value"])

    pairs = []
    for r in rows:
        # TePaske labels the opening decade 1501-1510; Hamilton's data start 1503
        key = r["period"] if r["period"] in tep else \
            f"1501-{r['last_year']}" if r["first_year"] == 1503 else None
        if key in tep:
            pairs.append((r["total_pesos"], tep[key] * 1e6))

    ratios = sorted(t / h for h, t in pairs)
    # the three opening decades are printed to one decimal on values near 2.0,
    # so their ratios carry visible rounding noise; the median is the signal
    med = ratios[len(ratios) // 2]
    big = [t / h for h, t in pairs if t >= 9e6]
    scale = sum(t for _, t in pairs) / sum(h for h, _ in pairs)
    print(f"\nvalidation 0 - our Table A against TePaske's printed 7-1 restatement")
    print(f"  {len(pairs)} decades matched; TePaske/Hamilton ratio median {med:.4f}, "
          f"value-weighted {scale:.4f}")
    print(f"  across the 13 decades above 9M pesos (free of print rounding): "
          f"{min(big):.4f}-{max(big):.4f}")
    return scale * PESO_272_G


def solve_ratio(rows, peso_g):
    """With the peso fixed, find the gold:silver value ratio that reproduces
    Hamilton's own stated metal totals."""
    best, ratio = None, 5.0
    while ratio <= 25.0:
        ag, au = weights(rows, peso_g, ratio)
        e = abs(ag / STATED_AG_KG - 1) + abs(au / STATED_AU_KG - 1)
        if best is None or e < best[0]:
            best = (e, ratio)
        ratio += 0.001
    return best[1]


def main(path, out):
    a, b = parse(path)
    print(f"parsed Table A: {len(a)} periods   Table B: {len(b)} periods")

    rows = []
    for per, va in sorted(a.items()):
        y0, y1 = (int(x) for x in per.split("-"))
        vb = b.get(per)
        if vb is None:                 # pre-1521: no silver had yet arrived
            vb = dict(pct_silver=0.0, pct_gold=100.0)
        rows.append(dict(
            period=per, first_year=y0, last_year=y1, years=y1 - y0 + 1,
            avg_annual_public_pesos=va["public"],
            avg_annual_private_pesos=va["private"],
            avg_annual_total_pesos=va["total"],
            total_pesos=round(va["total"] * (y1 - y0 + 1), 1),
            public_share=round(va["public"] / va["total"], 4),
            pct_silver_by_weight=vb["pct_silver"],
            pct_gold_by_weight=vb["pct_gold"]))

    peso_g = tepaske_scale(rows)
    ratio = solve_ratio(rows, peso_g)
    ag, au = weights(rows, peso_g, ratio)
    print(f"\nunits:")
    print(f"  fine silver per Table A peso : {peso_g:.2f} g "
          f"(= {peso_g/PESO_272_G*272:.0f} maravedis; "
          f"footnote says {FOOTNOTE_PESO_G:.2f} g = 450 mrv)")
    print(f"  gold:silver value ratio, solved freely : {ratio:.2f}  "
          f"(Castilian mint ratio in this era ~12-13:1)")
    print(f"\nvalidation 1 - Hamilton's stated metal totals")
    print(f"  silver {ag:>14,.0f} kg vs stated {STATED_AG_KG:>14,.0f}"
          f"   dev {abs(ag/STATED_AG_KG-1):.2%}")
    print(f"  gold   {au:>14,.0f} kg vs stated {STATED_AU_KG:>14,.0f}"
          f"   dev {abs(au/STATED_AU_KG-1):.2%}")

    # Table A (value), Table B (weight shares) and the stated metal totals are
    # mildly over-determined and do not close exactly — silver comes out 2.6%
    # high. The decade *shape* comes from Hamilton's own two tables; the level
    # is normalized here so the series sums to the totals he published.
    ag_fix, au_fix = STATED_AG_KG / ag, STATED_AU_KG / au
    print(f"\n  normalizing to published totals: silver x{ag_fix:.4f}, "
          f"gold x{au_fix:.4f}")

    for r in rows:
        v = r["total_pesos"] * peso_g / 1000.0
        r["value_ag_equiv_kg"] = round(v, 1)
        r["total_kg_weight"] = round(r.pop("_w"), 1)
        r["silver_kg"] = round(r.pop("_ag") * ag_fix, 1)
        r["gold_kg"] = round(r.pop("_au") * au_fix, 1)
        r["pesos_272mrv"] = round(r["total_pesos"] * peso_g / PESO_272_G, 1)
        r["public_kg_ag_equiv"] = round(v * r["public_share"], 1)
        r["private_kg_ag_equiv"] = round(v * (1 - r["public_share"]), 1)

    cols = ["period", "first_year", "last_year", "years",
            "avg_annual_public_pesos", "avg_annual_private_pesos",
            "avg_annual_total_pesos", "total_pesos", "pesos_272mrv",
            "public_share", "pct_silver_by_weight", "pct_gold_by_weight",
            "total_kg_weight", "silver_kg", "gold_kg", "value_ag_equiv_kg",
            "public_kg_ag_equiv", "private_kg_ag_equiv"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\n{len(rows)} rows -> {out}")
    return rows


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
