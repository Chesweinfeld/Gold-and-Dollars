"""Build the intra-imperial bullion flow network from the caja expenditure side.

Every earlier pass over the Colmex accounts used the CARGO (revenue) side and
deliberately threw the transfers away, because a remittance is not production.
They are, however, exactly what a flow map is made of: each `remitido a ...` or
`situado de ...` line is an edge with an origin treasury, a destination, a year
and an amount.

Both directions are captured. The sending treasury books the transfer as DATA
(expenditure) and the receiving one books it as CARGO (revenue), so the same
shipment can be seen from each end — which is the validation.

Units
-----
peso de a ocho   = 272 maravedis  (the reporting unit here)
peso ensayado    = 450 maravedis  -> x450/272 = 1.6544
peso de oro      left unconverted; the gold peso's silver value moved over the
                 period, so those rows are kept separate rather than merged in.
"""

import csv
import re
import sys

ENSAYADO_TO_OCHO = 450 / 272

# Pure carriage charges. 'FLETES DE PLATA REMITIDO A MEXICO' is the freight bill
# on a shipment, not the shipment, and would double-count against the remittance
# line that sits beside it.
DROP = re.compile(r"^FLETES|^COSTOS|^GASTOS DE REMISION|^CONDUCCION DE CAUDALES$", re.I)

OUT = re.compile(r"REMITID[OA]\s+A\b|ENVIAD[OA]\s+A\b|SITUADO|SITUADOS|"
                 r"REMESA|OTRAS TESORERIAS|ENTREGAD", re.I)
IN_ = re.compile(r"REMITID[OA]\s+D[EO]\b|VENIDO DE|RECIBID|CAJAS DE\b|"
                 r"OTRAS TESORERIAS|SITUADO", re.I)

# Destination rules, applied in order: the first match wins, so the specific
# entries must precede the general ones ('CASTILLA DE MEXICO' is metal going to
# Spain out of Mexico, not metal going to Mexico).
PLACES = [
    (r"CASTILLA|ESPA[NÑ]A|SEVILLA|CADIZ", "Spain"),
    (r"FILIPINAS|MANILA", "Manila"),
    (r"HAVANA|HABANA", "Havana"),
    (r"BARLOVENTO", "Windward squadron"),
    (r"PRESIDIOS INTERNOS", "Internal presidios"),
    (r"LUISIANA", "Louisiana"),
    (r"FLORIDA", "Florida"),
    (r"PUERTO RICO", "Puerto Rico"),
    (r"SANTO DOMINGO", "Santo Domingo"),
    (r"TRINIDAD", "Trinidad"),
    (r"YSLA DEL CARMEN|ISLA DEL CARMEN", "Isla del Carmen"),
    (r"CAMPECHE", "Campeche"),
    (r"YUCATAN", "Yucatan"),
    (r"CARTAGENA", "Cartagena"),
    (r"PANAMA|PORTOBELO|PUERTO BELO", "Panama"),
    (r"BUENOS AIRES", "Buenos Aires"),
    (r"MONTEVIDEO", "Montevideo"),
    (r"VALDIVIA", "Valdivia"),
    (r"CHILOE", "Chiloe"),
    (r"CONCEPCION", "Concepcion"),
    (r"\bCHILE\b", "Chile"),
    (r"HUANCAVELICA", "Huancavelica"),
    (r"POTOSI", "Potosi"),
    (r"\bLIMA\b", "Lima"),
    (r"QUITO", "Quito"),
    (r"GUAYAQUIL", "Guayaquil"),
    (r"CUENCA", "Cuenca"),
    (r"GUATEMALA", "Guatemala"),
    (r"VERACRUZ|VERA CRUZ", "Veracruz"),
    (r"GUADALAJARA", "Guadalajara"),
    (r"GUANAJUATO", "Guanajuato"),
    (r"DURANGO", "Durango"),
    (r"SAN BLAS", "San Blas"),
    (r"ALAMOS", "Alamos"),
    (r"PUEBLA", "Puebla"),
    (r"CASA DE MONEDA", "Mint"),
    (r"\bMEXICO\b", "Mexico City"),
    (r"OTRAS TESORERIAS|CAJAS DE FUERA|VENIDO DE FUERA|CAJAS FORANEAS",
     "unspecified"),
]
PLACES = [(re.compile(p), name) for p, name in PLACES]


def place(label):
    for rx, name in PLACES:
        if rx.search(label):
            return name
    return None


def to_ocho(amount, currency):
    if currency == "OCHO" or currency == "MONTO":
        return amount, currency == "MONTO"
    if currency == "ENSAYADOS":
        return amount * ENSAYADO_TO_OCHO, False
    return None, False           # ORO handled separately


def main(src, dest):
    rows, gold = [], []
    with open(src, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["is_total"] == "True":
                continue
            acct = r["account"].strip()
            if DROP.match(acct):
                continue
            side = r["side"]
            rx = OUT if side == "data" else IN_
            if not rx.search(acct):
                continue
            dst = place(acct)
            if dst is None:
                continue
            try:
                amt = float(r["amount"])
            except (TypeError, ValueError):
                continue
            if amt <= 0:
                continue
            year = r["year_start"]
            if not year:
                continue

            rec = dict(
                caja=r["caja"], region=r["region"], year=int(float(year)),
                direction="out" if side == "data" else "in",
                counterparty=dst, account=acct, currency=r["currency"],
                amount_raw=amt)
            if r["currency"] == "ORO":
                gold.append(rec)
                continue
            pesos, approx = to_ocho(amt, r["currency"])
            if pesos is None:
                continue
            rec["pesos_272mrv"] = round(pesos, 2)
            rec["currency_assumed"] = approx
            rec["includes_freight"] = bool(re.search(r"FLETE", acct, re.I))
            rows.append(rec)

    cols = ["caja", "region", "year", "direction", "counterparty", "account",
            "currency", "currency_assumed", "amount_raw", "pesos_272mrv",
            "includes_freight"]
    with open(dest, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    out = [r for r in rows if r["direction"] == "out"]
    inn = [r for r in rows if r["direction"] == "in"]
    tot = lambda xs: sum(x["pesos_272mrv"] for x in xs)
    print(f"edges {len(rows):,}   out {len(out):,}  in {len(inn):,}   "
          f"gold-peso rows held back {len(gold)}")
    print(f"years {min(r['year'] for r in rows)}-{max(r['year'] for r in rows)}"
          f"   treasuries {len({r['caja'] for r in rows})}")
    print(f"outflows  {tot(out):>16,.0f} pesos of 272 mrv")
    print(f"inflows   {tot(inn):>16,.0f}")

    import collections
    by = collections.defaultdict(float)
    for r in out:
        by[r["counterparty"]] += r["pesos_272mrv"]
    print("\ndestinations of recorded outflows (millions of pesos):")
    for k, v in sorted(by.items(), key=lambda kv: -kv[1])[:16]:
        print(f"  {k:<22} {v/1e6:>9,.1f}")

    print(f"\n{len(rows):,} rows -> {dest}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
