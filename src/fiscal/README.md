# Colmex fiscal pipeline

The taxation link in the chain: what the royal treasuries actually booked,
against which TePaske's production figures can be checked.

Run in order. Source data is a public download, so this reproduces from scratch:

```bash
for z in NE AP C E P RdP; do
  curl -LO "https://realhacienda.colmex.mx/wp-content/uploads/2021/0${z:+8}/$z.zip"
done   # NE lives under 2021/07/, the rest under 2021/08/
unzip -q '*.zip' -d workbooks/

python parse_colmex_cajas.py workbooks/   # -> colmex_cajas_long.csv (~204k lines, 75 cajas)
python build_mining.py                    # classifies lines into silver/gold/mercury
python join_output_vs_fiscal.py           # -> joined_output_vs_fiscal.csv
python make_chart.py                      # -> silver_output_vs_receipts.html
```

## Traps these scripts already handle

- **Leading-junk stripper needs a lookahead.** Without it the regex eats date
  strings like `1/1568-12/1568` and 93% of rows lose their year.
- **ZIMAPAN puts CARGO in column 1**, not column 2. Period detection has to
  accept `ci >= 1` or that treasury silently loses every year.
- **CHIHUAHA is a byte-identical duplicate of CHIHUAHUA** in the Colmex zip.
  The crosswalk uses only CHIHUAHUA; summing both double-counts 465,492 pesos.
- **Circularity.** Where TePaske had no independent output figure he derived one
  from receipts at an assumed rate, so the join can rediscover that constant and
  mistake it for a result. 248 caja-years share a ratio of exactly 0.11350
  (diezmo plus cobos on the remainder). `likely_derived` flags them; a ratio
  above 1.0 is arithmetically impossible as a tax and marks the same problem.
