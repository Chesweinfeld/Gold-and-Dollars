"""World Bank — official reserves held, by country and year.

COFER says what currency the world's reserves are in but never who holds them.
This is the other half: who holds them, but never in what currency. No public
source joins the two, and this project does not pretend otherwise.

Two indicators, because their difference is the gold:

  FI.RES.TOTL.CD   total reserves including gold, current US$
  FI.RES.XGLD.CD   total reserves excluding gold, current US$

Gold is valued at market prices here, so a country's gold line moves with the
gold price even when it has not bought or sold an ounce. Treat the gold column
as a value, never as a quantity.

Usage:  python src/reserves/fetch_wb_reserves.py
"""

import csv
import json
import os

from common import DATA, ensure_dirs, finish, http_get, report

API = "https://api.worldbank.org/v2"
INDICATORS = {"FI.RES.TOTL.CD": "total_usd", "FI.RES.XGLD.CD": "ex_gold_usd"}


def paged(path):
    """Every record for a World Bank endpoint. per_page=2000 keeps each hop small
    enough that the API answers; the whole series in one request times out."""
    out, page = [], 1
    while True:
        url = f"{API}/{path}{'&' if '?' in path else '?'}format=json&per_page=2000&page={page}"
        body = json.loads(http_get(url))
        if not isinstance(body, list) or len(body) < 2:
            raise RuntimeError(f"unexpected response for {url}: {str(body)[:200]}")
        meta, rows = body[0], body[1] or []
        out.extend(rows)
        if page >= meta["pages"]:
            return out
        page += 1


def country_index():
    """ISO3 -> name, region, income. Aggregates carry region id 'NA' and are the
    reason a naive country query double-counts the world several times over."""
    index = {}
    for c in paged("country?"):
        index[c["id"]] = {
            "iso3": c["id"],
            "iso2": c["iso2Code"],
            "name": c["name"],
            "region": c["region"]["value"],
            "is_aggregate": c["region"]["id"] == "NA",
            "lat": c.get("latitude") or "",
            "lon": c.get("longitude") or "",
        }
    return index


def main():
    ensure_dirs()
    print("GET country list")
    countries = country_index()
    real = {k for k, v in countries.items() if not v["is_aggregate"]}
    print(f"  {len(countries)} entities, {len(real)} countries, {len(countries) - len(real)} aggregates")

    series = {}
    for code, column in INDICATORS.items():
        print(f"GET {code}")
        rows = paged(f"country/all/indicator/{code}?")
        kept = 0
        for r in rows:
            if r["value"] is None:
                continue
            iso3 = r["countryiso3code"]
            if not iso3:
                continue
            series.setdefault((iso3, int(r["date"])), {})[column] = float(r["value"])
            kept += 1
        print(f"  {len(rows)} rows, {kept} with a value")

    out_rows = []
    for (iso3, year), vals in series.items():
        meta = countries.get(iso3)
        if meta is None:
            continue
        total = vals.get("total_usd")
        ex_gold = vals.get("ex_gold_usd")
        gold = total - ex_gold if (total is not None and ex_gold is not None) else None
        out_rows.append(
            {
                "iso3": iso3,
                "name": meta["name"],
                "region": meta["region"],
                "is_aggregate": int(meta["is_aggregate"]),
                # The World Bank's own capital coordinates. Carried because the
                # 110m basemap has no polygon for the smallest states, and some
                # of them — Singapore, Hong Kong — hold real money.
                "lat": meta["lat"],
                "lon": meta["lon"],
                "year": year,
                "total_usd": total if total is not None else "",
                "ex_gold_usd": ex_gold if ex_gold is not None else "",
                "gold_usd": round(gold, 2) if gold is not None else "",
            }
        )
    out_rows.sort(key=lambda r: (r["is_aggregate"], r["iso3"], r["year"]))

    path = os.path.join(DATA, "reserves_by_country.csv")
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["iso3", "name", "region", "is_aggregate", "lat", "lon",
                        "year", "total_usd", "ex_gold_usd", "gold_usd"],
        )
        w.writeheader()
        for r in out_rows:
            w.writerow(r)
    print(f"  -> data/reserves/reserves_by_country.csv ({len(out_rows)} rows)")

    validate(out_rows)
    finish()


def _cofer_world_total():
    """Annual world total FX reserves from the COFER extract, if it exists."""
    path = os.path.join(DATA, "cofer_currency_shares.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    with open(path) as fh:
        for r in csv.DictReader(fh):
            if (r["group"] == "G001" and r["freq"] == "A"
                    and r["measure"] == "total" and r["usd"]):
                out[int(r["period"])] = float(r["usd"])
    return out


def validate(rows):
    print("\nValidation")
    cty = [r for r in rows if not r["is_aggregate"] and r["total_usd"] != ""]
    years = sorted({r["year"] for r in cty})
    report("country coverage", len(cty) > 8000,
           f"{len({r['iso3'] for r in cty})} countries, {years[0]}-{years[-1]}, {len(cty)} rows")

    # Gold is a residual of two independently published series, so a negative
    # value means the two disagree, not that a country holds negative gold.
    neg = [r for r in rows if r["gold_usd"] != "" and r["gold_usd"] < -1000]
    report("gold residual non-negative", len(neg) < 20, f"{len(neg)} rows below -$1k")

    # The World Bank publishes this indicator for almost no aggregates (only the
    # euro area), so there is no in-file total to check against. Check across
    # sources instead: summing every country's non-gold reserves should land on
    # COFER's world total FX reserves. The two are compiled by different
    # institutions from different returns, so agreement is real evidence that
    # neither the country filter nor the gold split has gone wrong.
    cofer = _cofer_world_total()
    worst = None
    if cofer:
        for year, total in sorted(cofer.items()):
            s = sum(r["ex_gold_usd"] for r in cty
                    if r["year"] == year and r["ex_gold_usd"] != "")
            if not total or not s:
                continue
            ratio = s / total
            if worst is None or abs(ratio - 1) > abs(worst[1] - 1):
                worst = (year, ratio)
    report("country sum tracks COFER's world total FX",
           worst is not None and 0.90 < worst[1] < 1.10,
           f"worst year {worst[0]} ratio {worst[1]:.3f}" if worst
           else "cofer_currency_shares.csv not built yet — run fetch_cofer.py first")

    latest = max(r["year"] for r in cty)
    top = sorted((r for r in cty if r["year"] == latest),
                 key=lambda r: -r["total_usd"])[:10]
    print(f"\n  Largest holders, {latest} (US$ bn, incl. gold at market):")
    for r in top:
        print(f"    {r['name']:<24} {r['total_usd'] / 1e9:8,.0f}")


if __name__ == "__main__":
    main()
