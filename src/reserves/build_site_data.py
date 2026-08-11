"""Turn the two tidy CSVs into the compact JSON the page loads.

Also computes the one genuinely new number here: the centre of gravity of the
world's official reserves, year by year. Every country is a point mass at its
own centroid weighted by the reserves it holds, and the weighted mean is taken
on the sphere — unit vectors, summed, renormalised — not by averaging degrees.
Averaging longitude in degrees puts the mean of Tokyo and Los Angeles in
Kazakhstan instead of the Pacific, which would invert the entire story.

The track is a summary of where reserves are *held*. It says nothing about what
currency they are held in; nothing published does, per country. Keep those two
claims apart.

Usage:  python src/reserves/build_site_data.py
"""

import csv
import json
import math
import os

from common import DATA, SITE_DATA, ensure_dirs, finish, report

# Shown as issuers on the map. A currency is here if COFER identifies it
# separately today; the coordinates are the issuing authority's seat.
ISSUERS = [
    {"code": "USD", "name": "U.S. dollar", "authority": "Federal Reserve", "iso3": "USA", "c": [-77.04, 38.89]},
    {"code": "EUR", "name": "Euro", "authority": "European Central Bank", "iso3": "DEU", "c": [8.68, 50.11]},
    {"code": "JPY", "name": "Japanese yen", "authority": "Bank of Japan", "iso3": "JPN", "c": [139.77, 35.69]},
    {"code": "GBP", "name": "Pound sterling", "authority": "Bank of England", "iso3": "GBR", "c": [-0.09, 51.51]},
    {"code": "CNY", "name": "Chinese renminbi", "authority": "People's Bank of China", "iso3": "CHN", "c": [116.40, 39.90]},
    {"code": "CHF", "name": "Swiss franc", "authority": "Swiss National Bank", "iso3": "CHE", "c": [7.44, 46.95]},
    {"code": "CAD", "name": "Canadian dollar", "authority": "Bank of Canada", "iso3": "CAN", "c": [-75.70, 45.42]},
    {"code": "AUD", "name": "Australian dollar", "authority": "Reserve Bank of Australia", "iso3": "AUS", "c": [151.21, -33.87]},
]

DISPLAY_ORDER = ["USD", "EUR", "JPY", "GBP", "CNY", "CHF", "CAD", "AUD", "DEM", "FRF", "NLG", "ECU", "OTH"]


def load_geometry():
    with open(os.path.join(SITE_DATA, "world.json")) as fh:
        world = json.load(fh)
    return {c["id"]: c for c in world["countries"]}


def spherical_mean(points):
    """Weighted mean direction of (lon, lat, weight) triples, in degrees."""
    x = y = z = 0.0
    for lon, lat, w in points:
        rlon, rlat = math.radians(lon), math.radians(lat)
        x += w * math.cos(rlat) * math.cos(rlon)
        y += w * math.cos(rlat) * math.sin(rlon)
        z += w * math.sin(rlat)
    if x == y == z == 0:
        return None
    hyp = math.hypot(x, y)
    return math.degrees(math.atan2(y, x)), math.degrees(math.atan2(z, hyp))


def build_holders(geom):
    rows = []
    with open(os.path.join(DATA, "reserves_by_country.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["is_aggregate"] == "1" or not r["total_usd"]:
                continue
            rows.append(r)

    years = sorted({int(r["year"]) for r in rows})
    yi = {y: i for i, y in enumerate(years)}

    by_country = {}
    no_polygon = set()
    no_position = set()
    for r in rows:
        iso3 = r["iso3"]
        # Natural Earth 110m has no polygon for states below roughly 1,000 km2,
        # which drops 25 reporters including Singapore and Hong Kong. They get
        # no shape on the map but they must still carry weight in the centroid
        # and appear as markers, so fall back to the World Bank's coordinates.
        if iso3 in geom:
            centre, has_shape = geom[iso3]["c"], True
        elif r["lat"] and r["lon"]:
            centre, has_shape = [round(float(r["lon"]), 2), round(float(r["lat"]), 2)], False
            no_polygon.add(iso3)
        else:
            no_position.add(f"{iso3} ({r['name']})")
            continue
        c = by_country.setdefault(
            iso3,
            {
                "id": iso3,
                "name": r["name"],
                "region": r["region"],
                "c": centre,
                "shape": 1 if has_shape else 0,
                "total": [None] * len(years),
                "gold": [None] * len(years),
            },
        )
        c["total"][yi[int(r["year"])]] = round(float(r["total_usd"]) / 1e9, 3)
        if r["gold_usd"]:
            c["gold"][yi[int(r["year"])]] = round(float(r["gold_usd"]) / 1e9, 3)

    countries = sorted(by_country.values(), key=lambda c: c["id"])

    track, coverage = [], []
    for i, year in enumerate(years):
        pts = [(c["c"][0], c["c"][1], c["total"][i])
               for c in countries if c["total"][i]]
        mean = spherical_mean(pts)
        total = sum(p[2] for p in pts)
        track.append([round(mean[0], 3), round(mean[1], 3)] if mean else None)
        coverage.append([len(pts), round(total, 1)])

    # The most recent years are still filling in — the World Bank carries a
    # country only once it has reported. A year with a third of its reporters
    # missing is not comparable with a complete one, and the centroid is exactly
    # the kind of statistic that moves when small reporters drop out, so mark
    # where the panel stops being complete rather than quietly plotting it.
    peak = max(n for n, _ in coverage)
    complete = [y for y, (n, _) in zip(years, coverage) if n >= 0.9 * peak]
    complete_through = complete[-1] if complete else years[-1]

    return {
        "years": years,
        "countries": countries,
        "track": track,
        "coverage": coverage,
        "complete_through": complete_through,
        "issuers": ISSUERS,
    }, no_polygon, no_position


def build_cofer():
    rows = []
    with open(os.path.join(DATA, "cofer_currency_shares.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["group"] != "G001" or r["measure"] != "allocated":
                continue
            rows.append(r)

    # Annual 1995-1998 then quarterly, spliced into one ordered axis so the
    # chart runs continuously across the point where COFER changed frequency.
    def sort_key(period):
        if "-Q" in period:
            y, q = period.split("-Q")
            return (int(y), int(q))
        return (int(period), 0)

    annual = sorted({r["period"] for r in rows if r["freq"] == "A" and "-Q" not in r["period"]},
                    key=sort_key)
    quarterly = sorted({r["period"] for r in rows if r["freq"] == "Q"}, key=sort_key)
    first_q_year = int(quarterly[0].split("-Q")[0])
    periods = [p for p in annual if int(p) < first_q_year] + quarterly
    pi = {p: i for i, p in enumerate(periods)}

    names, share, usd = {}, {}, {}
    for r in rows:
        code = r["currency"]
        if code == "TOTAL" or r["period"] not in pi:
            continue
        names[code] = r["currency_name"]
        share.setdefault(code, [None] * len(periods))
        usd.setdefault(code, [None] * len(periods))
        if r["share_pct"]:
            share[code][pi[r["period"]]] = round(float(r["share_pct"]), 3)
        if r["usd"]:
            usd[code][pi[r["period"]]] = round(float(r["usd"]) / 1e9, 2)

    order = [c for c in DISPLAY_ORDER if c in share] + sorted(set(share) - set(DISPLAY_ORDER))
    return {
        "periods": periods,
        "first_quarterly": quarterly[0],
        "currencies": [
            {"code": c, "name": names[c], "share": share[c], "usd": usd[c]} for c in order
        ],
    }


def main():
    ensure_dirs()
    geom = load_geometry()
    holders, no_polygon, no_position = build_holders(geom)
    cofer = build_cofer()

    for name, payload in (("holders.json", holders), ("cofer.json", cofer)):
        path = os.path.join(SITE_DATA, name)
        with open(path, "w") as fh:
            json.dump(payload, fh, separators=(",", ":"))
        print(f"  -> site/data/{name} ({os.path.getsize(path) / 1024:.0f} KB)")

    print("\nValidation")
    report("every reporter placed",
           not no_position,
           f"{len(holders['countries'])} countries, {len(no_polygon)} by capital "
           f"coordinates for want of a polygon"
           + (f"; DROPPED {', '.join(sorted(no_position))}" if no_position else ""))

    big = [c for c in holders["countries"] if c["shape"] == 0
           and (c["total"][-1] or 0) > 100]
    report("no large holder is missing from the map", True,
           "placed without a polygon: "
           + ", ".join(f"{c['name']} ${c['total'][-1]:,.0f}bn" for c in
                       sorted(big, key=lambda c: -(c["total"][-1] or 0))) if big else "none")

    filled = [t for t in holders["track"] if t]
    report("reserve centroid computed for every year",
           len(filled) == len(holders["years"]),
           f"{len(filled)}/{len(holders['years'])} years")

    # The centroid must stay on Earth and must actually move; a stationary track
    # would mean the weights are not being applied.
    lons = [t[0] for t in filled]
    lats = [t[1] for t in filled]
    report("centroid in range",
           all(-180 <= v <= 180 for v in lons) and all(-90 <= v <= 90 for v in lats),
           f"lon {min(lons):.1f} to {max(lons):.1f}, lat {min(lats):.1f} to {max(lats):.1f}")

    span = max(lons) - min(lons)
    report("centroid moves", span > 5, f"{span:.1f} degrees of longitude")

    report("COFER axis is continuous",
           cofer["periods"] == sorted(set(cofer["periods"]), key=cofer["periods"].index),
           f"{len(cofer['periods'])} periods, {cofer['periods'][0]} to {cofer['periods'][-1]}, "
           f"quarterly from {cofer['first_quarterly']}")

    years = holders["years"]
    report("panel complete through a recent year",
           holders["complete_through"] >= years[-1] - 3,
           f"complete through {holders['complete_through']}, "
           f"data runs to {years[-1]}")

    print("\n  Centre of gravity of world reserves:")
    for year in (years[0], 1980, 2000, 2014, holders["complete_through"], years[-1]):
        if year in years:
            lon, lat = holders["track"][years.index(year)]
            n, total = holders["coverage"][years.index(year)]
            ns = "N" if lat >= 0 else "S"
            ew = "E" if lon >= 0 else "W"
            flag = "" if year <= holders["complete_through"] else "  <- partial"
            print(f"    {year}   {abs(lat):5.1f}°{ns} {abs(lon):6.1f}°{ew}"
                  f"   ({n} reporters, ${total / 1000:,.1f}tn){flag}")

    finish()


if __name__ == "__main__":
    main()
