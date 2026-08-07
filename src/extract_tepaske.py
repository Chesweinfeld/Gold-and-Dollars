"""Extract the appendix tables from TePaske, A New World of Gold and Silver (Brill, 2010).

Input: page-range PDFs exported from the Brill/EBSCO ebook (text layer intact).
Output: two long-format CSVs — year-keyed series and decade-keyed matrices.

Table families
--------------
SERIES  year-keyed runs laid out as repeating column blocks, 2-3 blocks per
        page. The value columns vary by chapter: (PESOS, KILOS) for silver
        output, (MARKS, PESOS, KILOGRAMS) for the chapter-6 mintage tables,
        (QUINTALES) for mercury. Emitted long, one row per value.
MATRIX  wide region/caja x decade tables. Many are typeset ROTATED 90 deg and
        only decode with pdfplumber line_dir="btt", char_dir="ltr"; on those
        pages a visual row is a run of constant x0 and columns run along `top`.

Columns are assigned by nearest header anchor, never by token order — blank
cells are common and order-based parsing silently shifts values left.
"""

import csv
import re
import sys

import pdfplumber

TITLE_RE = re.compile(r"Table\s+(\d+)[–-](\d+)\*?\.?\s*(.*)")
NUM_RE = re.compile(r"^-?[\d,]+(?:\.\d+)?$")
YEAR_RE = re.compile(r"^1[45678]\d{2}$")
WELL_FORMED = re.compile(r"^\d{1,3}(,\d{3})*$")
DECADE_RE = re.compile(r"^(1\d{3})[–-](1\d{3})$")
FRAG_RE = re.compile(r"^(1\d{3})[–-]?$")

# header tokens that name a value column
UNITS = {"PESOS", "KILOS", "KILOGRAMS", "KILO-", "MARKS", "QUINTALES", "QUIN-",
         "QUINT", "KGS", "MONTO"}
UNIT_FIX = {"KILO-": "KILOGRAMS", "KILOS": "KILOGRAMS", "KGS": "KILOGRAMS",
            "QUIN-": "QUINTALES", "QUINT": "QUINTALES"}


def num(t):
    s = t.replace(",", "").strip()
    if not NUM_RE.match(s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def split_merged(tok):
    """Tight typesetting can emit two adjacent cells as one token with no space
    ('73,48013,010' == 73,480 and 13,010). Scan longest-first: a left-to-right
    scan splits '248,89010,450' into 2 / 4 / 8,890 instead of 248,890 / 10,450."""
    if not re.fullmatch(r"[\d,]+", tok) or WELL_FORMED.match(tok) or "," not in tok:
        return [tok]
    for i in range(len(tok) - 1, 0, -1):
        a, b = tok[:i], tok[i:]
        if not WELL_FORMED.match(a):
            continue
        if WELL_FORMED.match(b):
            return [a, b]
        rest = split_merged(b)
        if len(rest) > 1:
            return [a] + rest
    return [tok]


def is_rotated(page):
    ups = [c.get("upright", True) for c in page.chars]
    return bool(ups) and sum(1 for u in ups if not u) / len(ups) > 0.5


def lines_of(page, rotated, gap=4.0):
    """Group words into visual lines -> [(key, [(pos, text), ...]), ...].

    Lines are clustered by proximity along the cross-axis, not by fixed-width
    bins. Bins split a row whenever it straddles a bin edge, and columns are
    rarely typeset on exactly the same baseline: in the rotated table 6-7 the
    KGS numerals sit a shade off their row, so every kilogram figure was
    landing one row away from the year it belongs to.
    """
    kw = dict(line_dir="btt", char_dir="ltr") if rotated else {}
    items = []
    for w in page.extract_words(**kw):
        if rotated:
            axis, lo, hi = w["x0"], -w["bottom"], -w["top"]
        else:
            axis, lo, hi = w["top"], w["x0"], w["x1"]
        parts = split_merged(w["text"])
        if len(parts) == 1:
            items.append((axis, (lo + hi) / 2, w["text"]))
            continue
        span, off, total = hi - lo, 0, sum(len(p) for p in parts)
        for p in parts:
            a = lo + span * off / total
            b = lo + span * (off + len(p)) / total
            items.append((axis, (a + b) / 2, p))
            off += len(p)

    lines, cur, ref = [], [], None
    for axis, pos, text in sorted(items):
        if ref is None or abs(axis - ref) <= gap:
            cur.append((pos, text))
            ref = axis if ref is None else ref
        else:
            lines.append((round(ref), sorted(cur)))
            cur, ref = [(pos, text)], axis
    if cur:
        lines.append((round(ref), sorted(cur)))
    return lines


def find_title(text):
    m = TITLE_RE.search(text)
    if not m:
        return None
    body = m.group(3).strip()
    if body.lower().startswith("(cont"):
        body = ""
    return f"{m.group(1)}-{m.group(2)}", body


def parse_series(lns, state, rows, warns, page_label):
    """Repeating (YEAR, <unit>, ...) blocks. Emits one row per value."""
    anchors = None
    hit = False
    for _, toks in lns:
        texts = [t for _, t in toks]
        newt = find_title(" ".join(texts))
        if newt:
            if newt[1] or newt[0] != state["id"]:
                state["id"] = newt[0]
                if newt[1]:
                    state["title"] = newt[1]
            anchors = None
        up = [(p, t.upper()) for p, t in toks]
        if any(t == "YEAR" for _, t in up):
            cand = [(p, UNIT_FIX.get(t, t)) for p, t in up
                    if t == "YEAR" or t in UNITS]
            if any(t == "YEAR" for _, t in cand):
                anchors = cand
                continue
        if anchors is None:
            continue
        vals = [(p, t) for p, t in toks if num(t) is not None]
        if len(vals) < 2:
            continue
        slots = {}
        for p, t in vals:
            i = min(range(len(anchors)), key=lambda j: abs(anchors[j][0] - p))
            if i in slots:
                warns.append(f"{page_label} {state['id']}: anchor collision ({t})")
            else:
                slots[i] = t
        i = 0
        while i < len(anchors):
            if anchors[i][1] != "YEAR":
                i += 1
                continue
            j = i + 1
            year = slots.get(i)
            while j < len(anchors) and anchors[j][1] != "YEAR":
                v = slots.get(j)
                if year and YEAR_RE.match(year.replace(",", "")) and v is not None:
                    rows.append({
                        "table": state["id"], "table_title": state["title"],
                        "page": page_label, "year": int(year.replace(",", "")),
                        "unit": anchors[j][1], "value": num(v),
                    })
                    hit = True
                j += 1
            i = j
    return hit


def parse_matrix(lns, state, rows, warns, page_label):
    """Wide region/caja x decade tables."""
    header = None
    hit = False

    def neighbour_frags(idx):
        """A decade label may be split across the rows either side of its data
        row ('1661–' / '1670'), in either order."""
        out = []
        for j in (idx - 1, idx + 1):
            if 0 <= j < len(lns):
                tj = lns[j][1]
                if sum(1 for _, t in tj if num(t) is not None) <= 1:
                    out += [t for _, t in tj if FRAG_RE.match(t)]
        return out

    for li, (_, toks) in enumerate(lns):
        texts = [t for _, t in toks]
        newt = find_title(" ".join(texts))
        if newt:
            if newt[1] or newt[0] != state["id"]:
                state["id"] = newt[0]
                if newt[1]:
                    state["title"] = newt[1]
            header = None
        labels = [(p, t) for p, t in toks if num(t) is None]
        vals = [(p, t) for p, t in toks if num(t) is not None]
        if any(t.upper().rstrip("*") == "DECADE" for t in texts) and len(labels) >= 2:
            header = [(p, t) for p, t in labels
                      if t.upper().rstrip("*") not in ("DECADE",)]
            # Two-level headers (OUTPUT / MINTAGE above PESOS | KGS | PESOS | KGS)
            # repeat the unit names; qualify them with the group label above,
            # otherwise the two halves collapse into one column.
            names = [t.upper() for _, t in header]
            if len(set(names)) < len(names):
                groups = []
                if li > 0:
                    groups = [(p, t) for p, t in lns[li - 1][1] if num(t) is None]
                header = [
                    (p, (min(groups, key=lambda g: abs(g[0] - p))[1] + "_" + t)
                        if groups else f"{t}_{k}")
                    for k, (p, t) in enumerate(header)]
            continue
        if header is None or not vals:
            continue
        dec = None
        for _, t in toks:
            m = DECADE_RE.match(t)
            if m:
                dec = f"{m.group(1)}-{m.group(2)}"
        if dec is None:
            frags = [t for _, t in toks if FRAG_RE.match(t)] + neighbour_frags(li)
            joined = "".join(f.rstrip("–-") for f in frags[:2])
            m = re.match(r"^(1\d{3})(1\d{3})$", joined)
            if m:
                dec = f"{m.group(1)}-{m.group(2)}"
        if dec is None:
            if any(t.upper() == "TOTAL" for t in texts):
                dec = "TOTAL"
            else:
                continue
        for p, t in vals:
            if DECADE_RE.match(t) or FRAG_RE.match(t):
                continue
            i = min(range(len(header)), key=lambda j: abs(header[j][0] - p))
            rows.append({
                "table": state["id"], "table_title": state["title"],
                "page": page_label, "decade": dec,
                "column": header[i][1].upper().rstrip("*"), "value": num(t),
            })
            hit = True
    return hit


def page_number(flat, pi):
    for f in flat:
        m = re.match(r"^(\d{2,3})\s+chapter", f)
        if m:
            return m.group(1)
    for f in flat:
        m = re.search(r"[a-z?]\s(\d{2,3})$", f)
        if m:
            return m.group(1)
    return f"pdf{pi+1}"


def main(paths, prefix):
    series, matrix, warns = [], [], []
    for path in paths:
        pdf = pdfplumber.open(path)
        state = {"id": None, "title": None}
        for pi, page in enumerate(pdf.pages):
            rot = is_rotated(page)
            lns = lines_of(page, rot)
            flat = [" ".join(t for _, t in toks) for _, toks in lns]
            label = page_number(flat, pi)
            if state["id"] is None:
                state["id"] = f"?{label}"
            # Run BOTH handlers on every page: a page can carry a year-keyed
            # table and a decade-keyed one (ch.5 mintage-vs-output). Stopping
            # at the first success drops the second table silently.
            if any(re.search(r"\bYEAR\b", f.upper()) for f in flat):
                parse_series(lns, state, series, warns, label)
            parse_matrix(lns, state, matrix, warns, label)

    for name, data in (("series", series), ("matrix", matrix)):
        if not data:
            continue
        with open(f"{prefix}_{name}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
        print(f"{len(data):,} rows -> {prefix}_{name}.csv")
    print(f"  ({len(warns)} warnings)")
    for w in warns[:6]:
        print("   ", w)


if __name__ == "__main__":
    main(sys.argv[1:-1], sys.argv[-1])
