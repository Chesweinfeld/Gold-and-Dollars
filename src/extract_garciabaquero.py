"""Extract CUADRO 2 from Garcia-Baquero Gonzalez (1996), 'Las remesas de metales
preciosos americanos en el siglo XVIII: una aritmetica controvertida',
Hispania LVI/1, no. 192, pp. 203-266. Open access, CC-BY 4.0.

The table gives, year by year for 1717-1778, Garcia-Baquero's own count of
treasure arriving from the Indies beside **Morineau's** figure and the
difference. Where he judged Morineau to have misread a gazette he prints the
corrected reading in parentheses.

This is the practical substitute for Morineau's book on the 18th century: it
reproduces his annual series, which nothing else machine-readable carries.

Spanish typography: '.' is the thousands separator. The scan's OCR is imperfect
(stray letters inside digits, '4-' for '+'), so every row is checked against the
printed difference column and anything that fails is flagged rather than
silently kept.
"""

import csv
import re
import sys

import pdfplumber

# a year, then 2-3 money figures, optional parenthetical correction, then diff
ROW = re.compile(r"^(17\d{2})\s+(.*)$")
MONEY = re.compile(r"\d[\d.\s]*\d|\d")


def money(tok):
    """Parse a Spanish-format figure, rejecting OCR-corrupted tokens."""
    t = tok.strip()
    if re.search(r"[^\d.\s]", t):        # stray OCR letters -> untrustworthy
        return None
    t = t.replace(".", "").replace(" ", "")
    if not t.isdigit():
        return None
    v = int(t)
    return v if 1000 <= v <= 99_000_000 else None


def parse_line(ln):
    m = ROW.match(ln.strip())
    if not m:
        return None
    year, rest = int(m.group(1)), m.group(2)

    paren = None
    pm = re.search(r"\(([^)]*)\)", rest)
    if pm:
        paren = money(pm.group(1))
        rest = rest[:pm.start()] + " " + rest[pm.end():]

    # the difference is the last figure, carrying a sign that OCR mangles
    # OCR renders '+' variously as '+', '4-', '-f', '-h'; a bare '-' or em dash
    # is a genuine minus. Digits inside the amount may be space-separated.
    sign = None
    # the scan often leaves punctuation between the sign and the amount
    # ('— ,3. 845.219'), so allow commas and spaces to intervene
    dm = re.search(r"(4-|-f|-h|\+|—|_|-)[\s,]*([\d.][\d.\s]*)$", rest)
    diff = None
    if dm:
        diff = money(dm.group(2).replace(" ", ""))
        sign = -1 if dm.group(1) in ("-", "—", "_") else 1
        rest = rest[:dm.start()]

    # tokens must not span whitespace, or the two money columns merge into one
    vals = [money(x) for x in re.findall(r"\d[\d.]*", rest)]
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return None
    return dict(year=year, garcia_baquero=vals[0], morineau_printed=vals[1],
                morineau_corrected=paren,
                printed_difference=(diff * sign) if (diff and sign) else None)


def main(path, out):
    pdf = pdfplumber.open(path)
    rows = {}
    for page in pdf.pages[13:16]:                 # pp. 216-217 of the article
        for ln in (page.extract_text() or "").split("\n"):
            r = parse_line(ln)
            if r and 1717 <= r["year"] <= 1778:
                rows[r["year"]] = r

    ok = bad = 0
    for r in rows.values():
        # Garcia-Baquero differences the corrected reading where he supplies one
        base = r["morineau_corrected"] or r["morineau_printed"]
        r["morineau_effective"] = base
        implied = r["garcia_baquero"] - base
        r["implied_difference"] = implied
        d = r["printed_difference"]
        r["reconciles"] = bool(d is not None and abs(abs(implied) - abs(d)) <= 2)
        ok, bad = (ok + 1, bad) if r["reconciles"] else (ok, bad + 1)

    cols = ["year", "garcia_baquero", "morineau_printed", "morineau_corrected",
            "morineau_effective", "printed_difference", "implied_difference",
            "reconciles"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for y in sorted(rows):
            w.writerow({c: rows[y].get(c) for c in cols})

    print(f"years captured: {len(rows)}  ({min(rows)}-{max(rows)})")
    print(f"rows reconciling to the printed difference column: {ok}/{ok+bad}")
    gb = sum(r["garcia_baquero"] for r in rows.values())
    mo = sum(r["morineau_effective"] for r in rows.values())
    print(f"\ntotals 1717-1778 (pesos):")
    print(f"  Garcia-Baquero {gb:>14,}")
    print(f"  Morineau       {mo:>14,}")
    print(f"  difference     {gb-mo:>14,}  ({(gb/mo-1):+.2%})")
    print(f"\n{len(rows)} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
