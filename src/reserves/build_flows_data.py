"""Turn the two flow extracts into the JSON the flows page draws.

Emits site/data/flows.json with two independent layers:

  tic   directed arcs, holder country -> United States, monthly 2000-2025.
        A real bilateral pair on both ends.

  bis   claims on each counterparty country, split by the currency they are
        denominated in. The arc origin is the *currency's* home, not a lender:
        there is no published lender-by-borrower matrix, so "USD arc into
        Brazil" means "Brazil owes this much in dollars", never "America lent
        it". The page says so in as many words.

Positions come from the map data already built for the holdings page, so the
two pages place the same country in the same spot.

Usage:  python src/reserves/build_flows_data.py
"""

import csv
import json
import os

from common import DATA, SITE_DATA, ensure_dirs, finish, http_get, report

# Where a currency is issued, for the BIS layer's arc origins.
CURRENCY_HOME = {
    "USD": {"name": "US dollar", "c": [-77.04, 38.89], "seat": "Washington"},
    "EUR": {"name": "Euro", "c": [8.68, 50.11], "seat": "Frankfurt"},
    "JPY": {"name": "Japanese yen", "c": [139.77, 35.69], "seat": "Tokyo"},
}

US = [-98.5, 39.5]   # contiguous-US centroid, matching the holdings map


def positions():
    """iso3 -> [lon, lat], from the holdings page's data plus the basemap."""
    pos, names = {}, {}
    with open(os.path.join(SITE_DATA, "holders.json")) as fh:
        for c in json.load(fh)["countries"]:
            pos[c["id"]] = c["c"]
            names[c["id"]] = c["name"]
    with open(os.path.join(SITE_DATA, "world.json")) as fh:
        for c in json.load(fh)["countries"]:
            pos.setdefault(c["id"], c["c"])
            names.setdefault(c["id"], c["name"])
    return pos, names


def fill_missing(pos, names, wanted):
    """Place anything the two map sources between them do not cover.

    Bermuda is the case this exists for: it holds $101bn of Treasuries, has no
    polygon in the 110m basemap, and never enters the holdings gazetteer
    because it reports no official reserves. Its coordinates come from the same
    World Bank country endpoint the rest of the pipeline uses rather than being
    typed in here.
    """
    todo = [iso3 for iso3 in wanted if iso3 not in pos]
    for iso3 in todo:
        body = json.loads(http_get(f"https://api.worldbank.org/v2/country/{iso3}"
                                   "?format=json", timeout=60))
        if not isinstance(body, list) or len(body) < 2 or not body[1]:
            continue
        c = body[1][0]
        if c.get("latitude") and c.get("longitude"):
            pos[iso3] = [round(float(c["longitude"]), 2),
                         round(float(c["latitude"]), 2)]
            names.setdefault(iso3, c["name"])
            print(f"  placed {iso3} ({c['name']}) from the World Bank country endpoint")
    return todo


def iso2_to_iso3():
    out = {}
    with open(os.path.join(DATA, "reserves_by_country.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["is_aggregate"] == "0" and r["iso2"]:
                out[r["iso2"]] = r["iso3"]
    return out


def build_tic(pos, names):
    rows = []
    totals, official = {}, {}
    with open(os.path.join(DATA, "tic_treasury_holders.csv")) as fh:
        for r in csv.DictReader(fh):
            key = f"{r['year']}-{int(r['month']):02d}"
            v = float(r["usd_bn"])
            if r["name"] == "Grand Total":
                totals[key] = v
            elif r["name"] == "For. Official":
                official[key] = v
            elif r["is_aggregate"] == "0" and r["iso3"]:
                rows.append((key, r["iso3"], r["name"], v))

    periods = sorted(totals)
    pi = {p: i for i, p in enumerate(periods)}

    holders, missing = {}, set()
    for key, iso3, name, v in rows:
        if iso3 not in pos:
            missing.add(iso3)
            continue
        h = holders.setdefault(iso3, {
            "id": iso3,
            "name": names.get(iso3, name),
            "c": pos[iso3],
            "v": [None] * len(periods),
        })
        h["v"][pi[key]] = round(v, 1)

    placed = [0.0] * len(periods)
    for h in holders.values():
        for i, v in enumerate(h["v"]):
            if v:
                placed[i] += v

    return {
        "periods": periods,
        "total": [round(totals[p], 1) for p in periods],
        "official": [round(official.get(p), 1) if official.get(p) else None
                     for p in periods],
        "placed": [round(x, 1) for x in placed],
        "target": {"id": "USA", "name": "United States", "c": US},
        "holders": sorted(holders.values(), key=lambda h: h["id"]),
    }, missing


def build_bis(pos, names):
    """Net position of the international banking system with each country.

    net = claims on the country - liabilities to it. Positive means the country
    owes the banking system on balance; negative means it is owed. This is the
    only net direction the public data supports, and it is a net *position*
    against the banking system as a whole, not a net bilateral pair — there is
    no published lender-country by borrower-country matrix.
    """
    iso3_of = iso2_to_iso3()
    by = {}
    periods = set()
    with open(os.path.join(DATA, "bis_claims_by_currency.csv")) as fh:
        for r in csv.DictReader(fh):
            iso3 = iso3_of.get(r["cp_iso2"])
            if not iso3 or iso3 not in pos:
                continue
            periods.add(r["period"])
            by.setdefault(iso3, {}).setdefault(r["currency"], {}) \
              .setdefault(r["position"], {})[r["period"]] = float(r["usd_mn"])

    # Annual snapshots keep the payload small; Q4 is the audited year-end and
    # the final period is carried so the page can show the latest reading.
    ordered = sorted(periods, key=lambda p: (int(p[:4]), int(p[-1])))
    snaps = [p for p in ordered if p.endswith("Q4")]
    if ordered[-1] not in snaps:
        snaps.append(ordered[-1])

    countries = []
    for iso3, cur in sorted(by.items()):
        rec = {"id": iso3, "name": names.get(iso3, iso3), "c": pos[iso3]}
        for code in ("USD", "EUR", "JPY", "TO1"):
            sides = cur.get(code, {})
            cl = sides.get("claims", {})
            li = sides.get("liabilities", {})
            rec[code] = [round((cl.get(p, 0) - li.get(p, 0)) / 1000, 2) for p in snaps]
        # Gross totals are kept for one currency only, so a reader can see the
        # size of the balance sheet the net came out of without tripling the file.
        gross = cur.get("TO1", {})
        rec["cl"] = [round(gross.get("claims", {}).get(p, 0) / 1000, 2) for p in snaps]
        rec["li"] = [round(gross.get("liabilities", {}).get(p, 0) / 1000, 2) for p in snaps]
        if not any(rec["cl"]) and not any(rec["li"]):
            continue
        countries.append(rec)

    return {
        "periods": snaps,
        "currencies": CURRENCY_HOME,
        "countries": countries,
    }


def main():
    ensure_dirs()
    pos, names = positions()

    wanted = set()
    with open(os.path.join(DATA, "tic_treasury_holders.csv")) as fh:
        for r in csv.DictReader(fh):
            if r["is_aggregate"] == "0" and r["iso3"]:
                wanted.add(r["iso3"])
    fill_missing(pos, names, wanted)

    tic, missing = build_tic(pos, names)
    bis = build_bis(pos, names)

    payload = {"tic": tic, "bis": bis}
    path = os.path.join(SITE_DATA, "flows.json")
    with open(path, "w") as fh:
        json.dump(payload, fh, separators=(",", ":"))
    print(f"  -> site/data/flows.json ({os.path.getsize(path) / 1024:.0f} KB)")

    print("\nValidation")
    report("every TIC holder has a position on the map", not missing,
           f"{len(tic['holders'])} holders, {len(tic['periods'])} months"
           + (f"; UNPLACED {', '.join(sorted(missing))}" if missing else ""))

    # The arcs the page can actually draw, against the printed world total.
    share = [p / t for p, t in zip(tic["placed"], tic["total"]) if t]
    report("drawable share of the TIC total", min(share) > 0.65,
           f"{min(share):.0%} to {max(share):.0%} of foreign holdings are "
           f"attributable to a named country")

    report("BIS layer built", len(bis["countries"]) > 100,
           f"{len(bis['countries'])} counterparties, {len(bis['periods'])} snapshots, "
           f"{bis['periods'][0]} to {bis['periods'][-1]}")

    # The net must be exactly the two published sides, not a re-derivation.
    j = len(bis["periods"]) - 1
    bad = [c["id"] for c in bis["countries"]
           if abs((c["cl"][j] - c["li"][j]) - c["TO1"][j]) > 0.02]
    report("net equals claims minus liabilities", not bad,
           f"{len(bis['countries'])} countries reconcile"
           + (f"; OFF {', '.join(bad[:5])}" if bad else ""))

    # Both signs must be present, or the direction encoding is meaningless.
    debt = [c for c in bis["countries"] if c["TO1"][j] > 0]
    cred = [c for c in bis["countries"] if c["TO1"][j] < 0]
    report("net direction runs both ways", debt and cred,
           f"{len(debt)} net debtors, {len(cred)} net creditors to the banking system")

    last = len(tic["periods"]) - 1
    top = sorted(tic["holders"], key=lambda h: -(h["v"][last] or 0))[:5]
    print(f"\n  {tic['periods'][last]}: ${tic['total'][last]:,.0f}bn of Treasuries held abroad")
    for h in top:
        print(f"    {h['name']:<20} {h['v'][last]:8,.1f}")

    order = sorted(bis["countries"], key=lambda c: c["TO1"][j])
    print(f"\n  {bis['periods'][j]}: net position with the international banking "
          f"system (US$ bn, + = the country owes on balance)")
    for c in order[-5:][::-1]:
        print(f"    owes    {c['name']:<18} {c['TO1'][j]:+9,.0f}   "
              f"(of which ${c['USD'][j]:+,.0f} in dollars)")
    for c in order[:5]:
        print(f"    is owed {c['name']:<18} {c['TO1'][j]:+9,.0f}   "
              f"(of which ${c['USD'][j]:+,.0f} in dollars)")

    finish()


if __name__ == "__main__":
    main()
