"""IMF COFER — currency composition of official foreign exchange reserves.

COFER is the only published measurement of *what currency* the world's reserves
are held in. It is deliberately anonymous: the IMF publishes world and group
aggregates only, never a country's own composition, because a handful of large
holders would be identifiable. Everything downstream has to respect that — this
file gives the "what", never the "who".

Source: IMF Data, dataflow IMF.STA:COFER, via the SDMX 2.1 REST endpoint.
Annual 1995-1998, quarterly from 1999Q1, ~3 month release lag.

Two dataset changes matter and are visible in the output:

  1999Q1   the euro replaces the separately-identified DEM, FRF, NLG and ECU.
  2012Q4   AUD and CAD are split out of "other currencies".
  2025Q3   the IMF removed the unallocated portion entirely, revised back to
           2000Q1, so allocated reserves now account for 100% of the total.
           Shares before 2000 are shares of *allocated* reserves only.

Usage:  python src/reserves/fetch_cofer.py
"""

import csv
import os
import xml.etree.ElementTree as ET

from common import DATA, ensure_dirs, finish, http_get, report

URL = "https://api.imf.org/external/sdmx/2.1/data/IMF.STA,COFER/all"

MSG = "http://www.sdmx.org/resources/sdmxml/schemas/v2_1/message"

GROUPS = {
    "G001": "World",
    "G110": "Advanced economies",
    "G200": "Emerging and developing economies",
}

# COFER's own currency codes. The four legacy ones stop at 1998Q4 by construction.
CURRENCIES = {
    "CI_USD": ("USD", "U.S. dollar", 1965),
    "CI_EUR": ("EUR", "Euro", 1999),
    "CI_JPY": ("JPY", "Japanese yen", 1965),
    "CI_GBP": ("GBP", "Pound sterling", 1965),
    "CI_CNY": ("CNY", "Chinese renminbi", 2016),
    "CI_CAD": ("CAD", "Canadian dollar", 2012),
    "CI_AUD": ("AUD", "Australian dollar", 2012),
    "CI_CHF": ("CHF", "Swiss franc", 1965),
    "CI_DEM": ("DEM", "Deutsche mark", 1965),
    "CI_FRF": ("FRF", "French franc", 1965),
    "CI_NLG": ("NLG", "Netherlands guilder", 1965),
    "CI_ECU": ("ECU", "European currency unit", 1979),
    "CI_OTHC": ("OTH", "Other currencies", 1965),
    "CI_T": ("TOTAL", "All currencies", 1965),
}

# INDICATOR codes we keep. AFXRA is the allocated total broken down by currency.
INDICATORS = {
    "AFXRA": "allocated",
    "TFXRA": "total",
    "UFXRA": "unallocated",
}

MEASURE = {"NV_USD": "usd", "SHRO_PT": "share_pct"}


def parse(xml_bytes):
    root = ET.fromstring(xml_bytes)
    dataset = root.find(f".//{{{MSG}}}DataSet")
    if dataset is None:
        raise RuntimeError("no DataSet in the SDMX response")

    rows = {}
    skipped = 0
    for series in dataset:
        if not series.tag.endswith("Series"):
            continue
        a = series.attrib
        group, indicator = a.get("COUNTRY"), a.get("INDICATOR")
        currency, measure = a.get("FXR_CURRENCY"), a.get("TYPE_OF_TRANSFORMATION")
        if indicator not in INDICATORS or measure not in MEASURE:
            skipped += 1
            continue
        code, name, _ = CURRENCIES.get(currency, (currency, currency, 0))
        for obs in series:
            period = obs.attrib.get("TIME_PERIOD")
            value = obs.attrib.get("OBS_VALUE")
            if value in (None, ""):
                continue
            key = (group, a.get("FREQUENCY"), period, INDICATORS[indicator], code)
            rec = rows.setdefault(
                key,
                {
                    "group": group,
                    "group_name": GROUPS.get(group, group),
                    "freq": a.get("FREQUENCY"),
                    "period": period,
                    "measure": INDICATORS[indicator],
                    "currency": code,
                    "currency_name": name,
                    "usd": "",
                    "share_pct": "",
                },
            )
            rec[MEASURE[measure]] = float(value)
    return list(rows.values()), skipped


def validate(rows):
    print("\nValidation")

    world_q = [r for r in rows if r["group"] == "G001" and r["freq"] == "Q"]
    periods = sorted({r["period"] for r in world_q})
    report("quarterly coverage", len(periods) > 90, f"{periods[0]} to {periods[-1]}, {len(periods)} quarters")

    # Shares of allocated reserves must sum to 100 in every period, excluding
    # the CI_T total row. This is the real check on the parse: if a currency
    # were dropped or a period mis-keyed, the sum moves off 100.
    by_period = {}
    for r in world_q:
        if r["measure"] != "allocated" or r["currency"] == "TOTAL" or r["share_pct"] == "":
            continue
        by_period.setdefault(r["period"], 0.0)
        by_period[r["period"]] += r["share_pct"]
    worst = max(by_period.items(), key=lambda kv: abs(kv[1] - 100.0)) if by_period else None
    report(
        "currency shares sum to 100%",
        worst is not None and abs(worst[1] - 100.0) < 0.15,
        f"worst period {worst[0]} = {worst[1]:.3f}%" if worst else "no rows",
    )

    # value / total must reproduce the published share, independently of it.
    checked = good = 0
    tot = {
        r["period"]: r["usd"]
        for r in world_q
        if r["measure"] == "allocated" and r["currency"] == "TOTAL" and r["usd"] != ""
    }
    for r in world_q:
        if r["measure"] != "allocated" or r["currency"] == "TOTAL":
            continue
        if r["usd"] == "" or r["share_pct"] == "" or not tot.get(r["period"]):
            continue
        checked += 1
        if abs(r["usd"] / tot[r["period"]] * 100 - r["share_pct"]) < 0.05:
            good += 1
    report(
        "USD values reproduce published shares",
        checked and good == checked,
        f"{good}/{checked} rows",
    )

    # The euro must appear exactly when the legacy currencies stop.
    eur = sorted(r["period"] for r in rows if r["currency"] == "EUR" and r["usd"] not in ("", None))
    dem = sorted(r["period"] for r in rows if r["currency"] == "DEM" and r["usd"] not in ("", None))
    report(
        "euro succeeds the legacy currencies",
        bool(eur) and bool(dem) and dem[-1] < eur[0],
        f"DEM ends {dem[-1] if dem else '-'}, EUR starts {eur[0] if eur else '-'}",
    )

    latest = max(periods)
    snap = {
        r["currency"]: r["share_pct"]
        for r in world_q
        if r["period"] == latest and r["measure"] == "allocated" and r["share_pct"] != ""
    }
    print(f"\n  {latest} world shares, allocated reserves:")
    for cur, share in sorted(snap.items(), key=lambda kv: -kv[1]):
        if cur != "TOTAL":
            print(f"    {cur:<6} {share:6.2f}%")


def main():
    ensure_dirs()
    print(f"GET {URL}")
    rows, skipped = parse(http_get(URL))
    print(f"  {len(rows)} observations parsed, {skipped} series skipped")

    rows.sort(key=lambda r: (r["group"], r["freq"], r["period"], r["measure"], r["currency"]))
    out = os.path.join(DATA, "cofer_currency_shares.csv")
    with open(out, "w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "group", "group_name", "freq", "period", "measure",
                "currency", "currency_name", "usd", "share_pct",
            ],
        )
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"  -> {os.path.relpath(out, os.path.dirname(DATA))}")

    validate(rows)
    finish()


if __name__ == "__main__":
    main()
