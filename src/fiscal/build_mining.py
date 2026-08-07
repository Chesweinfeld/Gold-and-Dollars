"""Extract the mining-related revenue lines from the flattened caja data.

Silver/gold severance taxes (quinto, diezmo, cobos, senoreaje) are the standard
proxy for registered bullion production. Mercury (azogue) sales are kept as a
separate class: mercury is an *input* the crown monopolised, so its receipts
track amalgamation output with a lead/lag, and it must not be summed with the
severance taxes.
"""

import re

import pandas as pd

SRC = "colmex_cajas_long.csv"

SILVER = re.compile(r"(QUINTO|DIEZMO|COBOS|SENOREA|SE[NÑ]OREA|SEN\b).*PLATA|PLATA.*(QUINTO|DIEZMO|COBOS|SENOREA)")
GOLD = re.compile(r"(QUINTO|DIEZMO|COBOS|SENOREA|SEN\b|3%|1\.5%|1%).*\bORO\b|\bORO\b.*(QUINTO|DIEZMO|COBOS|SENOREA|DERECHO)")
MERCURY = re.compile(r"AZOGUE")
# lines that merely move or freight bullion — not production taxes
EXCLUDE = re.compile(r"FLETES|FALTA DE|REMITIDO|REINTEGRO|DEBIDO|EXISTENCIA|SOBRANTE")


def classify(a):
    if EXCLUDE.search(a):
        return None
    if MERCURY.search(a):
        return "mercury_sales"
    if SILVER.search(a):
        return "silver_tax"
    if GOLD.search(a):
        return "gold_tax"
    if re.search(r"\bPLATA\b", a):
        return "silver_other"
    if re.search(r"\bORO\b", a):
        return "gold_other"
    return None


def main():
    d = pd.read_csv(SRC, low_memory=False)
    d = d[(d.side == "cargo") & (~d.is_total)].copy()
    d["tax_class"] = d.account.fillna("").map(classify)
    m = d[d.tax_class.notna()].copy()
    m.to_csv("colmex_mining_lines.csv", index=False)

    ann = (
        m[m.year_start.notna()]
        .groupby(["region", "caja", "year_start", "tax_class", "currency"], as_index=False)["amount"]
        .sum()
        .rename(columns={"year_start": "year"})
    )
    ann["year"] = ann.year.astype(int)
    ann.to_csv("colmex_mining_annual.csv", index=False)

    print(f"mining lines: {len(m):,}  annual rows: {len(ann):,}")
    print(m.groupby("tax_class").agg(rows=("amount", "size"), cajas=("caja", "nunique")).to_string())


if __name__ == "__main__":
    main()
