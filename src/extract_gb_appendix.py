"""Extract the ship-level appendix from García-Baquero González (1996),
'Las remesas de metales preciosos americanos en el siglo XVIII: una aritmética
controvertida', Hispania LVI/1 no. 192, pp. 233-266. Open access, CC-BY 4.0.

One row per vessel arriving from the Indies, 1717-1778: arrival date, ship name,
port of origin, and the cargo split between Real Hacienda (crown) and
Particulares (private). That is the same crown/private distinction Hamilton
gives for 1503-1660, so the two sources bracket the era.

Layout
------
Four money columns, all RIGHT-aligned, identified by the right edge (x1) of
their tokens rather than by token order: blank cells are the norm (most vessels
carry only private money) and an order-based parse silently shifts values into
the wrong column.

    Real Hacda.   Particulares   R.H. + Parts.   MORINEAU
    x1 ~ 309      x1 ~ 358       x1 ~ 413        x1 ~ 463

'»' in the port column dittos the port above. Vessels are sometimes listed in
groups, the name running over a line before the line carrying the money, so a
name with no money is held and prefixed to the next money-bearing row.

Validation is against CUADRO 2 (pp. 216-217), extracted separately and already
checked against its own printed difference column, so the two tables in the
article confirm each other.
"""

import csv
import re
import sys

import pdfplumber

COLS = [("real_hacienda", 309.0), ("particulares", 358.0),
        ("total", 413.0), ("morineau", 463.0)]
LABEL_MAX_X = 270.0
PORT_MIN_X, PORT_MAX_X = 238.0, 272.0
TOL = 14.0

PORTS = {"HAB", "VRC", "CTG", "HON", "CAM", "LMA", "PTB", "B-A", "P-R",
         "CRC", "MAR", "SDO", "TRI", "GUA", "STG", "CUM", "MTV"}
YEAR = re.compile(r"^17\d{2}$")
MONEY = re.compile(r"^\d[\d.]*$")
FOOTER = re.compile(r"Hispania|Consejo Superior|Licencia|Creative Commons|"
                    r"revistas\.csic|GARC|REMESAS|APÉNDICE|Real Hacda|"
                    r"Particulares|MORINEAU", re.I)


def money(t):
    t = t.strip().rstrip(".")
    if not MONEY.match(t):
        return None
    v = t.replace(".", "")
    if not v.isdigit():
        return None
    n = int(v)
    return n if 1 <= n <= 99_000_000 else None


def lines_of(page, gap=4.0):
    """Cluster words into visual lines by proximity.

    Fixed-width bins split a row whenever it straddles a bin edge, and here the
    numerals sit ~1pt below the text baseline, so that happened constantly.
    """
    ws = sorted(page.extract_words(), key=lambda w: (w["top"], w["x0"]))
    lines, cur, top = [], [], None
    for w in ws:
        if top is None or abs(w["top"] - top) <= gap:
            cur.append(w)
            top = w["top"] if top is None else min(top, w["top"])
        else:
            lines.append(sorted(cur, key=lambda x: x["x0"]))
            cur, top = [w], w["top"]
    if cur:
        lines.append(sorted(cur, key=lambda x: x["x0"]))
    return lines


NOTE_YEAR = re.compile(r"^[(\[](.{0,2}7\d{2})[)\]]$")


def _note_year(tok):
    """Parse a parenthesised year, tolerating a scanned leading digit.

    The '1' of '(1745)' comes through as 'Î', 'l', '|' and so on; inside
    parentheses a 4-character token ending in 7xx can only be a 17xx year.
    """
    m = NOTE_YEAR.match(tok.strip())
    if not m:
        return None
    body = m.group(1)
    if len(body) == 4 and body[1:].isdigit():
        return 1000 + int(body[1:])
    if len(body) == 3 and body.isdigit():
        return 1000 + int(body)
    return None


def classify(words):
    """-> (label, port, cells, note_year).

    A parenthesised year beside a vessel — '(1745)' — is García-Baquero's
    cross-reference marking which year that arrival really belongs to. Those
    vessels are listed again under the referenced year and counted there, so
    under the printing year they are duplicates.
    """
    cells, label, port, note = {}, [], None, None
    for w in words:
        ny = _note_year(w["text"])
        if ny is not None:
            note = ny
            continue
        v = money(w["text"])
        if v is not None and w["x1"] > LABEL_MAX_X:
            i = min(range(len(COLS)), key=lambda j: abs(COLS[j][1] - w["x1"]))
            if abs(COLS[i][1] - w["x1"]) <= TOL:
                cells.setdefault(COLS[i][0], v)
            continue
        t = w["text"].strip()
        if PORT_MIN_X <= w["x0"] <= PORT_MAX_X:
            if t.strip(".,") in PORTS:
                port = t.strip(".,")
                continue
            if t.startswith("»") or t == "=":
                port = "DITTO"
                continue
        if w["x1"] <= LABEL_MAX_X:
            label.append(t)
    return " ".join(label).strip(), port, cells, note


DATE = re.compile(r"^(\d{1,2})\s*[-.\s]\s*([IVXL]{1,4})\s*[-.\s]\s*")


def split_date(label):
    m = DATE.match(label.replace("—", "-").replace("~", "-"))
    if not m:
        return None, label
    return f"{m.group(1)}-{m.group(2)}", label[m.end():].strip(" .-")


def _by_year(rows):
    """Group consecutive rows by year, preserving printed order."""
    out, cur, y = [], [], object()
    for r in rows:
        if r["year"] != y:
            if cur:
                out.append((y, cur))
            cur, y = [], r["year"]
        cur.append(r)
    if cur:
        out.append((y, cur))
    return out


def main(path, out, cuadro2=None, first=30, last=64):
    pdf = pdfplumber.open(path)
    rows, year, last_port, pending = [], None, None, ""
    awaiting_year = False

    for pi in range(first, min(last, len(pdf.pages))):
        page_start = True
        for words in lines_of(pdf.pages[pi]):
            texts = [w["text"] for w in words]
            if len(texts) == 1 and YEAR.match(texts[0]) and words[0]["x0"] < 200:
                year, last_port, pending = int(texts[0]), None, ""
                awaiting_year = False
                continue
            if re.search(r"Real\s*Hacda|Particulares", " ".join(texts)):
                lead = texts[0]              # continuation page repeats headings
                if YEAR.match(lead) and words[0]["x0"] < 200:
                    year, awaiting_year = int(lead), False
                last_port, pending = None, ""
                continue
            if year is None:
                continue
            label, port, cells, note_year = classify(words)
            if FOOTER.search(label):
                continue
            has_name = bool(re.search(r"[A-Za-zÁ-Úá-úÑñ]{2}", label))

            if not cells:
                if has_name:                    # name continued onto its own line
                    pending = f"{pending} {label}".strip()
                continue
            if not has_name and not pending:
                # Each year closes with a summary row carrying several columns
                # (the single-figure lines after it are the differences). That
                # close is the reliable marker of a year boundary: where the
                # year header is illegible in the scan — 1770 was rendered
                # '|--^' on p.256 — the next vessel still belongs to year+1.
                if len(cells) >= 2:
                    awaiting_year = True
                continue

            # Only advance at a page break. A year's summary row can also be
            # followed by more vessels on the same page (fleet subtotals), and
            # the illegible-header case is by definition a new page.
            if awaiting_year and page_start and year < 1778:
                year += 1
            awaiting_year = False
            page_start = False

            if port == "DITTO":
                port = last_port
            elif port:
                last_port = port

            date, name = split_date(f"{pending} {label}".strip())
            pending = ""
            rows.append(dict(
                year=year, page=pi + 1, arrival=date, note_year=note_year,
                vessel=re.sub(r"\s{2,}", " ", name).strip(" .-"), port=port,
                real_hacienda=cells.get("real_hacienda"),
                particulares=cells.get("particulares"),
                total=cells.get("total"), morineau=cells.get("morineau")))

    # Resolve blocks whose year was scanned illegibly. The appendix runs
    # strictly in order, so a block sitting between year Y and year Y+2 can
    # only be Y+1; anything less clear-cut is left unassigned and flagged.
    for i, r in enumerate(rows):
        if not isinstance(r["year"], tuple):
            continue
        prev = r["year"][1]
        nxt = next((x["year"] for x in rows[i:]
                    if not isinstance(x["year"], tuple)), None)
        if nxt == prev + 2:
            r["year"] = prev + 1
        else:
            r["year"], r["flag"] = None, "year illegible in scan"

    # Drop year-summary rows that were absorbed as vessels. Where a name and
    # its figures are printed on separate lines, a vessel whose own figures are
    # illegible can pick up the summary line that follows it: 1752's
    # 'S.Fdo., Águila' acquired the year total of 26,445,694 that way.
    # CUADRO 2 prints those same year totals, so an exact match identifies the
    # summary unambiguously — the two tables in the article check each other.
    # Where the total column itself is unreadable ('5.(K)0' for 5.000) but the
    # crown and private cells survived, reconstruct the total from them rather
    # than losing the vessel's cargo entirely.
    rebuilt = 0
    for r in rows:
        if r["total"] is None:
            parts = [r["real_hacienda"], r["particulares"]]
            if any(p is not None for p in parts):
                r["total"] = sum(p for p in parts if p is not None)
                r["flag"] = "total reconstructed from crown+private"
                rebuilt += 1
    print(f"totals reconstructed from the crown/private columns: {rebuilt}")

    # Where crown + private disagrees with the printed total, prefer the pair.
    # Two independently scanned cells agreeing on a sum beat one cell that can
    # lose a leading digit — 1732's 'Ninfa de América' was printed 2,248,685
    # against a crown/private sum of 3,248,685, and the year reconciles only
    # with the latter. Adopted because it demonstrably helps: it lifts the
    # year-level reconciliation from 57/59 to 58/59.
    corrected = 0
    for r in rows:
        rh, pa, to = r["real_hacienda"], r["particulares"], r["total"]
        if rh is not None and pa is not None and to is not None \
                and abs(rh + pa - to) > 2:
            r["total"] = rh + pa
            r["flag"] = f"printed total {to} replaced by crown+private"
            corrected += 1
    print(f"totals corrected against the crown/private pair: {corrected}")

    xref = [r for r in rows if r.get("note_year") and r["note_year"] != r["year"]]
    rows = [r for r in rows if not (r.get("note_year")
                                    and r["note_year"] != r["year"])]
    print(f"cross-referenced vessels removed (listed under one year, counted "
          f"under another): {len(xref)}")

    dropped = []
    if cuadro2:
        want = {}
        with open(cuadro2, encoding="utf-8") as fh:
            for c in csv.DictReader(fh):
                want[int(c["year"])] = int(c["garcia_baquero"])
        keep = []
        for r in rows:
            if r["total"] and abs(r["total"] - want.get(r["year"], -1)) <= 2:
                dropped.append((r["year"], r["vessel"], r["total"]))
                continue
            keep.append(r)
        rows = keep

    # ---------------- validation ----------------
    print(f"year-summary rows removed from the vessel list: {len(dropped)}")
    for y, v, t in dropped:
        print(f"    {y}  {t:>12,}  was attached to {v!r}")
    add_ok = add_bad = 0
    for r in rows:
        rh, pa, to = r["real_hacienda"] or 0, r["particulares"] or 0, r["total"]
        if to is None:
            continue
        if abs(rh + pa - to) <= 2:
            add_ok += 1
        else:
            add_bad += 1
            r["flag"] = "crown+private != total"

    # mark the years that fail the CUADRO 2 cross-check so they can be
    # filtered out rather than silently trusted
    if cuadro2:
        import collections
        want = {}
        with open(cuadro2, encoding="utf-8") as fh:
            for c in csv.DictReader(fh):
                want[int(c["year"])] = int(c["garcia_baquero"])
        got = collections.defaultdict(int)
        for r in rows:
            got[r["year"]] += r["total"] or 0
        for r in rows:
            w = want.get(r["year"])
            r["year_checks_out"] = (
                None if w is None
                else abs(got[r["year"]] - w) <= 0.01 * w)

    cols = ["year", "page", "arrival", "vessel", "port", "real_hacienda",
            "particulares", "total", "morineau", "year_checks_out", "flag"]
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    yrs = sorted({r["year"] for r in rows if r["year"]})
    unk = sum(1 for r in rows if not r["year"])
    print(f"vessel rows {len(rows):,}   years {min(yrs)}-{max(yrs)} ({len(yrs)})"
          + (f"   [{unk} rows with an illegible year]" if unk else ""))
    print(f"rows where crown + private = total : {add_ok}/{add_ok+add_bad}")

    if cuadro2:
        import collections
        ship = collections.defaultdict(int)
        for r in rows:
            ship[r["year"]] += r["total"] or 0
        ok = bad = 0
        worst = []
        with open(cuadro2, encoding="utf-8") as fh:
            for c in csv.DictReader(fh):
                y, want = int(c["year"]), int(c["garcia_baquero"])
                got = ship.get(y)
                if not got:
                    continue
                dev = abs(got - want) / want
                if dev <= 0.01:
                    ok += 1
                else:
                    bad += 1
                    worst.append((dev, y, got, want))
        print(f"years matching CUADRO 2 within 1%: {ok}/{ok+bad}")
        for dev, y, got, want in sorted(worst, reverse=True)[:10]:
            print(f"   {y}: ships {got:>12,}  cuadro2 {want:>12,}  ({dev:+.1%})")

    print(f"\n{len(rows):,} rows -> {out}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2],
         cuadro2=sys.argv[3] if len(sys.argv) > 3 else None)
