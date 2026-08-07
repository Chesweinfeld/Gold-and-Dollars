"""Flatten the TePaske/Klein caja real workbooks (Colmex digitization) into one tidy CSV.

Source: https://realhacienda.colmex.mx/  (NE, AP, C, E, P, RdP zips)
Each workbook is one royal treasury. Rows are account lines grouped under a
period header, split into CARGO (revenue) and DATA (expenditure) column blocks.
Four header layouts occur; we locate them by finding the CARGO / DATA cells.
"""

import csv
import glob
import os
import re
import sys

import xlrd

REGION = {
    "NE": "New Spain",
    "AP": "Upper Peru (Charcas)",
    "P": "Peru",
    "C": "Chile",
    "E": "Quito",
    "RdP": "Rio de la Plata",
}

# "1/1560-12/1560", "11/1576-/31577", "ANO DE 1702", "1720"
PERIOD_RE = re.compile(r"\d{1,2}\s*/\s*\d{3,4}\s*-|A[NÑ]O\s+DE\s+\d{4}|^\s*1[5-8]\d{2}\s*$", re.I)
YEAR_RE = re.compile(r"1[5-8]\d{2}")
# legajo / archive references carried under the period header
SOURCE_RE = re.compile(r"^(S\s*\d+|AGI|AHN|AGN|ANB|ANC|LEG|BN)\b", re.I)

# leading artifacts in the SAN JUAN text dump ("0CARGO", "-B  13"); the lookahead
# keeps date strings like "1/1568-12/1568" intact
JUNK = re.compile(r"^[\s0-9.\-|]+(?=[A-Za-zÁ-Úá-úÑñ])")


def clean(s):
    return JUNK.sub("", str(s).strip()).strip()


def num(v):
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def find_header(sheet):
    """Return (header_row, cargo_col, data_col, cargo_names, data_names) or None."""
    for r in range(min(12, sheet.nrows)):
        cells = [clean(c).upper() for c in sheet.row_values(r)]
        if "CARGO" in cells and "DATA" in cells:
            ci, di = cells.index("CARGO"), cells.index("DATA")
            if di <= ci:
                continue
            ncur = di - ci - 1
            norm = lambda h: "ENSAYADOS" if h.startswith("ENSAYADO") else h
            cargo_names = [norm(cells[ci + 1 + k]) for k in range(ncur)]
            data_names = [norm(cells[di + 1 + k]) if di + 1 + k < len(cells) else "" for k in range(ncur)]
            # a blank currency header on one side is filled from the other
            for k in range(ncur):
                cargo_names[k] = cargo_names[k] or data_names[k]
                data_names[k] = data_names[k] or cargo_names[k]
            if not any(cargo_names):
                cargo_names[0] = data_names[0] = "MONTO"
            return r, ci, di, cargo_names, data_names
    return None


def parse_sheet(sheet, caja, region, out):
    hdr = find_header(sheet)
    if hdr is None:
        return 0
    hrow, ci, di, cargo_names, data_names = hdr
    ncur = di - ci - 1
    period = source = ""
    n = 0

    for r in range(hrow + 1, sheet.nrows):
        row = sheet.row_values(r)
        cell = lambda i: clean(row[i]) if i < len(row) else ""

        first = cell(0)
        cargo_lbl, data_lbl = cell(ci), cell(di)
        cargo_amts = [num(row[ci + 1 + k]) if ci + 1 + k < len(row) else None for k in range(ncur)]
        data_amts = [num(row[di + 1 + k]) if di + 1 + k < len(row) else None for k in range(ncur)]
        has_amt = any(a is not None for a in cargo_amts + data_amts)

        # labels wrapped across two columns in the text-dump layout
        for k in range(ncur):
            if cargo_amts[k] is None and ci + 1 + k < len(row) and cell(ci + 1 + k):
                cargo_lbl = (cargo_lbl + " " + cell(ci + 1 + k)).strip()
            if data_amts[k] is None and di + 1 + k < len(row) and cell(di + 1 + k):
                data_lbl = (data_lbl + " " + cell(di + 1 + k)).strip()

        # period header: date-ish text with no money anywhere on the line
        joined = " ".join(cell(i) for i in range(len(row))).strip()
        if joined and not has_amt and PERIOD_RE.search(joined):
            period, source = joined, ""
            if SOURCE_RE.match(first):
                source = first
            continue
        if first and not has_amt and SOURCE_RE.match(first):
            source = first
            continue
        # AÑO[/CTA] layouts put period+legajo in their own leading columns.
        # CARGO sits at column 1 in some workbooks (ZIMAPAN) and column 2 in
        # others; requiring >=2 silently drops every year in the former.
        if ci >= 1:
            if first and PERIOD_RE.search(first):
                period = first
            for j in (1, ci):
                if cell(j) and SOURCE_RE.match(cell(j)):
                    source = cell(j)

        years = YEAR_RE.findall(period)
        y0 = int(years[0]) if years else ""
        y1 = int(years[-1]) if years else ""

        for side, lbl, amts, names in (
            ("cargo", cargo_lbl, cargo_amts, cargo_names),
            ("data", data_lbl, data_amts, data_names),
        ):
            if not lbl or all(a is None for a in amts):
                continue
            if lbl.upper() in {"CARGO", "DATA", "AÑO", "ANO", "CTA"}:
                continue
            for k, amt in enumerate(amts):
                if amt is None:
                    continue
                out.append({
                    "region": region,
                    "caja": caja,
                    "period_raw": period,
                    "year_start": y0,
                    "year_end": y1,
                    "source_ref": source,
                    "side": side,
                    "account": lbl.upper(),
                    "currency": (names[k] or "MONTO").upper(),
                    "amount": amt,
                    "is_total": lbl.strip().upper().startswith("TOTAL"),
                    "sheet_row": r + 1,
                })
                n += 1
    return n


def main(root, dest):
    rows, skipped = [], []
    for path in sorted(glob.glob(os.path.join(root, "*", "*.xls"))):
        region = REGION.get(os.path.basename(os.path.dirname(path)), "?")
        caja = os.path.splitext(os.path.basename(path))[0]
        try:
            book = xlrd.open_workbook(path)
        except Exception as exc:
            skipped.append((path, repr(exc)))
            continue
        got = sum(parse_sheet(book.sheet_by_index(i), caja, region, rows) for i in range(book.nsheets))
        if not got:
            skipped.append((path, "no parseable header/rows"))

    fields = list(rows[0].keys())
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"{len(rows):,} records -> {dest}")
    for path, why in skipped:
        print("  SKIPPED", path, why)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
