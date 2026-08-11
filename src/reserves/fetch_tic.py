"""US Treasury TIC — foreign holdings of US Treasury securities, by country.

This is the one genuinely bilateral series in the whole reserve-currency
literature: a named foreign country on one end, the United States on the other,
monthly, back to 2000. Nothing else published gives country-to-country holdings
of a reserve asset.

Two warnings that have to travel with the numbers, both from Treasury's own
footnotes:

  Custody, not ownership. The data are collected from US-based custodians, so a
  holding is attributed to the country of the custodian, not the true owner.
  This is why Belgium, Luxembourg, Ireland and the Cayman Islands sit near the
  top: Euroclear is in Belgium, and fund domiciles are in the others. Treasury
  says outright that the table "may not provide a precise accounting of
  individual country ownership".

  Official and private are mixed. Only the world total is split into foreign
  official and private ("For. Official" here). A given country's line is both,
  so it is not a central-bank reserves figure.

Source: https://ticdata.treasury.gov/Publish/mfhhis01.txt (tab separated, one
block per year, most recent first).

Usage:  python src/reserves/fetch_tic.py
"""

import csv
import io
import os
import re

from common import DATA, ensure_dirs, finish, http_get, report

URL = "https://ticdata.treasury.gov/Publish/mfhhis01.txt"

# Rows that are totals, memo items or discontinued composites. Kept in the CSV
# with is_aggregate=1 so the validation can use them, never drawn as an arc.
AGGREGATES = {
    "All Other", "Grand Total", "For. Official", "Treasury Bills",
    "T-Bonds & Notes", "Carib Bnkng Ctrs", "Oil Exporters",
    "Belgium-Luxembourg",
}

MONTHS = {m: i + 1 for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}

ISO3 = {
    "Australia": "AUS", "Bahamas": "BHS", "Belgium": "BEL", "Bermuda": "BMU",
    "Brazil": "BRA", "Canada": "CAN", "Cayman Islands": "CYM", "Chile": "CHL",
    "China, Mainland": "CHN", "Colombia": "COL", "Denmark": "DNK",
    "Egypt": "EGY", "El Salvador": "SLV", "Finland": "FIN", "France": "FRA",
    "Germany": "DEU", "Hong Kong": "HKG", "India": "IND", "Indonesia": "IDN",
    "Iraq": "IRQ", "Ireland": "IRL", "Israel": "ISR", "Italy": "ITA",
    "Japan": "JPN", "Kazakhstan": "KAZ", "Korea, South": "KOR",
    "Kuwait": "KWT", "Luxembourg": "LUX", "Malaysia": "MYS", "Mexico": "MEX",
    "Netherlands": "NLD", "Norway": "NOR", "Oman": "OMN", "Peru": "PER",
    "Philippines": "PHL", "Poland": "POL", "Russia": "RUS",
    "Saudi Arabia": "SAU", "Singapore": "SGP", "South Africa": "ZAF",
    "Spain": "ESP", "Sweden": "SWE", "Switzerland": "CHE", "Taiwan": "TWN",
    "Thailand": "THA", "Turkey": "TUR", "United Arab Emirates": "ARE",
    "United Kingdom": "GBR", "Uruguay": "URY", "Vietnam": "VNM",
}

# " 2/", " 5/", " 4/" etc. are footnote references welded onto the label.
FOOTNOTE = re.compile(r"\s*\d+/\s*$")


def cells(line):
    rows = list(csv.reader(io.StringIO(line), delimiter="\t"))
    return rows[0] if rows else []


def clean(name):
    return FOOTNOTE.sub("", name.strip()).strip()


def parse(text):
    lines = text.split("\n")
    out = []
    unknown = set()

    for i, line in enumerate(lines):
        c = cells(line)
        if not c or c[0].strip() != "Country":
            continue
        # The row above a "Country" header carries the month names; the header
        # row itself carries the years. Pair them by column position — some
        # blocks have 11 columns, not 12, and one carries roman-numeral series
        # markers in the month row.
        months = cells(lines[i - 1]) if i else []
        columns = []
        for col in range(1, len(c)):
            year = c[col].strip()
            month = months[col].strip() if col < len(months) else ""
            if year.isdigit() and month in MONTHS:
                columns.append((col, int(year), MONTHS[month]))
        if not columns:
            continue

        for row in lines[i + 1:]:
            rc = cells(row)
            if not rc:
                continue
            name = clean(rc[0])
            if not name or name == "Of which:":
                continue
            values = {}
            for col, year, month in columns:
                if col >= len(rc):
                    continue
                raw = rc[col].strip().replace(",", "")
                if raw in ("", "*", "-", "------"):
                    continue
                try:
                    # At a series break Treasury prints the same month twice —
                    # the new benchmark first, the superseded estimate beside it
                    # "for comparison only". Keep the leftmost, or the two
                    # vintages mix and the month stops adding up.
                    values.setdefault((year, month), float(raw))
                except ValueError:
                    pass
            # Footnote prose has a long label and no numbers; a data row has
            # numbers. This is what separates them without a hand-kept list.
            if not values:
                if name in AGGREGATES or name in ISO3:
                    continue
                if len(name) > 40 or name.endswith(("/", ".", ":")):
                    break
                continue
            is_agg = name in AGGREGATES
            iso3 = ISO3.get(name, "")
            if not is_agg and not iso3:
                unknown.add(name)
            for (year, month), v in values.items():
                out.append({
                    "name": name, "iso3": iso3, "is_aggregate": int(is_agg),
                    "year": year, "month": month, "usd_bn": v,
                })
            if name == "T-Bonds & Notes":
                break

    return out, unknown


def main():
    ensure_dirs()
    print(f"GET {URL}")
    rows, unknown = parse(http_get(URL).decode("utf-8", "replace"))

    # The file republishes overlapping months across annual blocks; the most
    # recent block is the revised one and comes first, so first-seen wins.
    seen = {}
    for r in rows:
        seen.setdefault((r["name"], r["year"], r["month"]), r)
    rows = sorted(seen.values(),
                  key=lambda r: (r["is_aggregate"], r["name"], r["year"], r["month"]))

    path = os.path.join(DATA, "tic_treasury_holders.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=[
            "name", "iso3", "is_aggregate", "year", "month", "usd_bn"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  -> data/reserves/tic_treasury_holders.csv ({len(rows)} rows)")

    validate(rows, unknown)
    finish()


def validate(rows, unknown):
    print("\nValidation")
    report("every country label mapped to ISO3", not unknown,
           "; ".join(sorted(unknown)) if unknown else f"{len(ISO3)} names known")

    countries = [r for r in rows if not r["is_aggregate"]]
    periods = sorted({(r["year"], r["month"]) for r in countries})
    report("monthly coverage", len(periods) > 280,
           f"{periods[0][0]}-{periods[0][1]:02d} to {periods[-1][0]}-{periods[-1][1]:02d}, "
           f"{len(periods)} months, {len({r['iso3'] for r in countries})} countries")

    # Every non-memo row must reproduce the printed Grand Total. The parts are
    # not all named countries: until 2016 Treasury published "Carib Bnkng Ctrs"
    # and "Oil Exporters" as groups *instead of* their members, and before June
    # 2002 Belgium and Luxembourg share one line. The total is printed in the
    # file rather than derived, so this catches a mis-assigned column or a
    # dropped row.
    memo = {"Grand Total", "For. Official", "Treasury Bills", "T-Bonds & Notes"}
    parts, total = {}, {}
    for r in rows:
        key = (r["year"], r["month"])
        if r["name"] == "Grand Total":
            total[key] = r["usd_bn"]
        elif r["name"] not in memo:
            parts[key] = parts.get(key, 0) + r["usd_bn"]
    worst = None
    for key in sorted(total):
        if key not in parts or not total[key]:
            continue
        ratio = parts[key] / total[key]
        if worst is None or abs(ratio - 1) > abs(worst[1] - 1):
            worst = (key, ratio)
    report("all published parts reproduce the printed Grand Total",
           worst is not None and abs(worst[1] - 1) < 0.002,
           f"worst {worst[0][0]}-{worst[0][1]:02d} ratio {worst[1]:.4f}" if worst else "no totals")

    # How much of each month can actually be drawn as a country-to-US arc. The
    # early years group the Caribbean and the oil exporters, so the map can
    # place a smaller share of the total than it can today; the flows page
    # shows this rather than implying full coverage throughout.
    placed = {}
    for r in rows:
        if not r["is_aggregate"] and r["iso3"]:
            key = (r["year"], r["month"])
            placed[key] = placed.get(key, 0) + r["usd_bn"]
    cov = {k: placed.get(k, 0) / total[k] for k in total if total[k]}
    lo = min(cov.items(), key=lambda kv: kv[1])
    hi = max(cov.items(), key=lambda kv: kv[1])
    report("named-country coverage recorded", True,
           f"{lo[1]:.0%} in {lo[0][0]}-{lo[0][1]:02d} rising to {hi[1]:.0%} in {hi[0][0]}-{hi[0][1]:02d}")

    off = {(r["year"], r["month"]): r["usd_bn"] for r in rows if r["name"] == "For. Official"}
    bad = [k for k in off if k in total and total[k] and off[k] > total[k]]
    report("foreign official is a subset of the total", not bad, f"{len(bad)} months violate")

    latest = periods[-1]
    top = sorted((r for r in countries if (r["year"], r["month"]) == latest),
                 key=lambda r: -r["usd_bn"])[:10]
    share = off.get(latest, 0) / total.get(latest, 1) * 100
    print(f"\n  {latest[0]}-{latest[1]:02d}: ${total.get(latest, 0):,.0f}bn held abroad, "
          f"{share:.0f}% by foreign official institutions")
    for r in top:
        print(f"    {r['name']:<22} {r['usd_bn']:8,.1f}")


if __name__ == "__main__":
    main()
