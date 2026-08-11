"""BIS locational banking statistics — cross-border claims by currency.

The second flow layer. For each counterparty country it gives the stock of
cross-border bank claims *on* that country, split by the currency the claim is
denominated in: dollars, euro, yen, and an all-currency total.

What this is and is not, precisely, because the distinction is the whole point:

  It IS a currency map. "Claims on Brazil denominated in USD" means Brazil's
  banks, firms and households owe that money in dollars, whoever lent it. That
  is what makes a currency a reserve currency — the world's obligations are
  written in it, so everyone must hold it.

  It is NOT a bilateral country pair. The public dataflow publishes only
  L_REP_CTY = 5A, the aggregate of all reporting countries. There is no
  published lender-country by borrower-country matrix here, so an arc drawn
  from Washington to Brasilia would mean "denominated in dollars", never "lent
  by the United States". The flows page labels it that way.

Source: https://stats.bis.org/api/v1 — dataflow WS_LBS_D_PUB. Key order is
FREQ.L_MEASURE.L_POSITION.L_INSTR.L_DENOM.L_CURR_TYPE.L_PARENT_CTY.
L_REP_BANK_TYPE.L_REP_CTY.L_CP_SECTOR.L_CP_COUNTRY.L_POS_TYPE

Values arrive with UNIT_MULT=6, i.e. millions of USD.

Usage:  python src/reserves/fetch_bis.py
"""

import csv
import math
import os
import xml.etree.ElementTree as ET

from common import DATA, ensure_dirs, finish, http_get, report

BASE = "https://stats.bis.org/api/v1/data/WS_LBS_D_PUB"

# S=stocks, C=claims, A=all instruments, 5J=all bank nationalities,
# A=all bank types, 5A=all reporting countries, A=all counterparty sectors,
# N=unadjusted. Only L_DENOM and L_CP_COUNTRY vary.
KEY = "Q.S.C.A.{denom}.A.5J.A.5A.A..N"

CURRENCIES = {
    "USD": "US dollar",
    "EUR": "Euro",
    "JPY": "Japanese yen",
    "TO1": "All currencies",
}

# BIS identifies counterparties by ISO2, alongside its own numeric-prefixed
# codes for the regional aggregates it also publishes ("5J" all countries, "1C"
# and so on). Those aggregates are dropped downstream by the ISO2 -> ISO3 join
# in build_flows_data.py, rather than by a hand-kept exclusion list here.


def fetch(denom, start="2000"):
    url = f"{BASE}/{KEY.format(denom=denom)}/all?startPeriod={start}"
    root = ET.fromstring(http_get(url, timeout=180))
    rows = []
    for series in root.iter():
        if not series.tag.endswith("Series"):
            continue
        cp = series.attrib.get("L_CP_COUNTRY")
        for obs in series:
            v = obs.attrib.get("OBS_VALUE")
            if v in (None, ""):
                continue
            # A handful of observations come through as the literal "NaN";
            # float() accepts it happily and it then poisons every sum.
            if not math.isfinite(float(v)):
                continue
            rows.append({
                "cp_iso2": cp,
                "period": obs.attrib.get("TIME_PERIOD"),
                "currency": denom,
                "usd_mn": float(v),
            })
    return rows


def main():
    ensure_dirs()
    all_rows = []
    for denom in CURRENCIES:
        print(f"GET BIS claims denominated in {denom}")
        rows = fetch(denom)
        print(f"  {len(rows)} observations")
        all_rows.extend(rows)

    path = os.path.join(DATA, "bis_claims_by_currency.csv")
    all_rows.sort(key=lambda r: (r["currency"], r["cp_iso2"], r["period"]))
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["cp_iso2", "period", "currency", "usd_mn"])
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    print(f"  -> data/reserves/bis_claims_by_currency.csv ({len(all_rows)} rows)")

    validate(all_rows)
    finish()


def validate(rows):
    print("\nValidation")
    periods = sorted({r["period"] for r in rows})
    entities = sorted({r["cp_iso2"] for r in rows})
    report("coverage", len(periods) > 90 and len(entities) > 150,
           f"{periods[0]} to {periods[-1]}, {len(periods)} quarters, {len(entities)} counterparties")

    for cur in CURRENCIES:
        n = sum(1 for r in rows if r["currency"] == cur)
        report(f"{cur} series present", n > 1000, f"{n} observations")

    # The three named currencies must not exceed the all-currency total for the
    # same counterparty and quarter. They will not sum to it — sterling, the
    # franc and everything else are inside TO1 but not published separately —
    # so this is an inequality, not an identity.
    idx = {}
    for r in rows:
        idx.setdefault((r["cp_iso2"], r["period"]), {})[r["currency"]] = r["usd_mn"]
    # Everything is rounded to the nearest million, so on a counterparty with a
    # $7mn total the rounding alone can put the parts 14% over. Test only where
    # the base is big enough for the ratio to mean anything.
    # The currency breakdown and the all-currency total are separately
    # estimated series, so a few country-quarters sit marginally over 100%.
    # Tolerate 3% and report anything past 100.5% rather than smoothing it away.
    FLOOR = 1000.0  # US$ mn
    checked = bad = skipped = noted = 0
    worst = 0.0
    for cur in idx.values():
        if "TO1" not in cur or cur["TO1"] <= 0:
            continue
        if cur["TO1"] < FLOOR:
            skipped += 1
            continue
        named = sum(cur.get(c, 0) for c in ("USD", "EUR", "JPY"))
        checked += 1
        ratio = named / cur["TO1"]
        worst = max(worst, ratio)
        if ratio > 1.005:
            noted += 1
        if ratio > 1.03:
            bad += 1
    report("named currencies fit inside the all-currency total",
           checked and bad == 0,
           f"{checked} country-quarters over $1bn checked, worst fill {worst:.1%}, "
           f"{noted} past 100.5%; {skipped} smaller ones skipped as rounding-dominated")

    # Report BIS's own "5J" all-counterparties row, not a sum over the file:
    # the extract also contains regional and income aggregates, so adding every
    # row up counts most of the world several times over.
    latest = periods[-1]
    tot = {r["currency"]: r["usd_mn"] for r in rows
           if r["cp_iso2"] == "5J" and r["period"] == latest}
    print(f"\n  {latest}, cross-border claims outstanding, all counterparties (US$ tn):")
    for c, name in CURRENCIES.items():
        v = tot.get(c)
        print(f"    {name:<16} {v / 1e6:7.2f}" if v else f"    {name:<16}       —")


if __name__ == "__main__":
    main()
