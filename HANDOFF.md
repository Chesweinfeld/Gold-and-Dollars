# Handoff — Spanish American bullion project

Everything an agent picking this up cold needs. **The scratchpad is wiped
between sessions**, so nothing below assumes it survives; every artefact is
either committed to a repo or rebuildable from a link here.

---

## 1. Where the work lives

| repo | visibility | contents |
|---|---|---|
| <https://github.com/Chesweinfeld/spanish-american-bullion> | **private** | complete — includes the TePaske production data |
| <https://github.com/Chesweinfeld/Gold-and-Dollars> | **public** | publishable subset — no Brill-derived data, all code |

Local clones: `~/Desktop/spanish-american-bullion`, `~/Desktop/Gold-and-Dollars`.

The split is a copyright line, not an accident. TePaske (Brill, 2010) is in
copyright, so `data/production/`, `output_vs_mintage.csv`,
`joined_output_vs_fiscal.csv`, `production_to_arrivals.csv` and
`docs/tepaske-production.md` are private-only. **Push data changes to both
repos deliberately** — the public one must never gain a `data/production/`.

---

## 2. Source documents

### Already on this machine (user-supplied, do not re-download)

| file | contents |
|---|---|
| `~/Downloads/JohnJ.TePaskeKe_2010__ANewWorldofGoldandSil.pdf` | ch.3, pp. 112–140 |
| `…-2.pdf` | duplicate of the above (differs only in EBSCO timestamp) |
| `…-3.pdf`, `…-4.pdf` | ch.7, pp. 314–315 (tables 7-1, 7-2) — duplicates of each other |
| `…-5.pdf` | ch.4, pp. 181–212 |
| `…-6.pdf` | ch.2 gold, pp. 54–67 |
| `…-7.pdf` | ch.5 mintage, pp. 248–259 |
| `…-8.pdf` | ch.1, pp. 19–21 |
| `…-9.pdf` | ch.6, pp. 287–303 |
| `~/Desktop/Hamilton-ImportsAmericanGold-1929.pdf` | QJE 43(3) 1929, Tables A and B |

These came from the user's Swarthmore/EBSCO access. **Do not attempt to log in
anywhere, and do not ask for or accept credentials.** If more pages are needed,
the user retrieves them.

### Downloadable, no login

```bash
# García-Baquero 1996 (CC-BY) — Morineau's annual series + the ship appendix
curl -L -o garciabaquero1996.pdf \
  "https://hispania.revistas.csic.es/index.php/hispania/article/download/757/754"

# Colmex royal treasury workbooks
curl -LO "https://realhacienda.colmex.mx/wp-content/uploads/2021/07/NE.zip"
for z in AP C E P RdP; do
  curl -LO "https://realhacienda.colmex.mx/wp-content/uploads/2021/08/$z.zip"
done

# Palma, REStud 2022 — annual gold, Potosí, European mint output
curl -L -o palma_restud.zip \
  "https://zenodo.org/api/records/5338362/files/ReproductionFiles.zip/content"

# Brzezinski–Chen–Palma–Ward, REStat 2024 — arrivals, money stock, shipwrecks
curl -L -o vagaries.tab       "https://dataverse.harvard.edu/api/access/datafile/6314606?format=original"
curl -L -o vagaries_money.tab "https://dataverse.harvard.edu/api/access/datafile/6314608?format=original"
# both are Stata files despite the .tab name — read with pandas.read_stata

# Sousa 2008, Brazilian gold at Lisbon (open access)
curl -L -o costa_lisbon.pdf \
  "https://repositorio.ulisboa.pt/bitstreams/710112d0-49b3-40b5-b75b-939c8684722b/download"

# Charotti–Palma–Santos 2025 (macro outcomes only, no metal flows)
curl -L -o charotti_data.xlsx \
  "https://zenodo.org/api/records/17312592/files/data_sep_2025.xlsx/content"
```

### Blocked or unavailable

- **openICPSR** (Chen/Palma/Ward money supply, `10.3886/E139761V2`) — Cloudflare
  challenge plus account required. Not needed: its key series (`in_esp`
  arrivals, `sisto_esp` money stock) are inside the Vagaries Dataverse file.
- **Wiley supplement** for Goldilocks (*RoIW* 2026) — 403. Working paper is open
  at <https://papers.tinbergen.nl/22063.pdf>.
- **Morineau's book** — no digital copy exists anywhere. Catalogued as
  "**Ces** incroyables gazettes et fabuleux métaux" (the leading *Ces* is why
  catalogue searches fail). OCLC **9413383**, LCCN **83007177**, LC class
  **HC240 .M73 1985**, 687 pp. HathiTrust holds a search-only scan:
  <https://catalog.hathitrust.org/Record/000657148> ·
  `babel.hathitrust.org/cgi/pt?id=txu.059173024311473`. Confirmed page
  references: **pp. 144–145** Brazilian gold by decade, **pp. 135–137, 194–195**
  Dutch gazette figures on Portuguese gold. **You almost certainly don't need
  it** — his decade series is in TePaske's table 7-1 and his annual series is in
  García-Baquero's CUADRO 2, both already extracted.

---

## 3. Rebuilding from scratch

```bash
uv venv venv                       # python3 -m venv fails silently on this machine
uv pip install --python venv/bin/python pdfplumber pandas openpyxl xlrd numpy
```

`xlrd` is required for the legacy BIFF `.xls` workbooks; `openpyxl` for the
Zenodo xlsx. Pipeline order:

```bash
# production (private repo only)
python src/extract_tepaske.py ~/Downloads/JohnJ.TePaskeKe_2010__ANewWorldofGoldandSil{,-4,-5,-6,-7,-8,-9}.pdf tep
python src/build_tidy.py                       # -> tepaske_annual.csv, tepaske_decade.csv

# taxation + movement
unzip '*.zip' -d books/                        # into books/NE, books/AP, ... one dir per region
python src/fiscal/parse_colmex_cajas.py books/ colmex_cajas_long.csv   # 204,277 records
python src/fiscal/build_mining.py
python src/fiscal/build_flows.py colmex_cajas_long.csv colmex_flows.csv
python src/fiscal/analyse_flows.py
python src/fiscal/join_output_vs_fiscal.py     # needs tepaske_silver_annual.csv, see below

# arrivals
python src/extract_hamilton.py ~/Desktop/Hamilton-ImportsAmericanGold-1929.pdf hamilton_1929_arrivals.csv
python src/extract_garciabaquero.py garciabaquero1996.pdf morineau_annual_1717_1778.csv
python src/extract_gb_appendix.py garciabaquero1996.pdf gb_ships_1717_1778.csv morineau_annual_1717_1778.csv
python src/test_circularity.py
```

`join_output_vs_fiscal.py` expects a `tepaske_silver_annual.csv` that is not
committed; make it with:

```python
w = pd.read_csv("tepaske_annual.csv")
s = w[(w.metal == "silver") & (w.measure == "output")].rename(columns={"entity": "caja"})
s.dropna(subset=["caja"])[["caja", "year", "pesos", "kilograms"]].to_csv("tepaske_silver_annual.csv", index=False)
```

`colmex_cajas_long.csv` (19 MB) is deliberately uncommitted — it rebuilds in
minutes and should reproduce **exactly 204,277 records**. If it doesn't,
something regressed.

---

## 4. Constants and facts that were expensive to establish

```python
# kg fine silver per peso of 272 maravedís, stepping at the Bourbon reforms
SILVER_F = [(1728, 0.025560), (1772, 0.024810), (1786, 0.024430), (9999, 0.024245)]
# kg fine gold per SILVER peso — steps at the same 1772/1786 dates
GOLD_F   = [(1771, 0.001551), (1785, 0.001525), (9999, 0.001480)]
# kg fine metal per Castilian mark (230.0465 g gross)
#   gold 22k to 1771 then 21k; silver 0.9306 fine to 1727 then 0.9028
ENSAYADO_TO_OCHO = 450 / 272   # ≈ 1.6544
```

- These were **recovered from the book's own paired columns**, not assumed.
- Hamilton's Table A peso resolves to **21.14 g**, not the 42.29 g his footnote
  implies — his footnote is irreconcilable with his own stated metal totals by a
  factor of 2.00, and TePaske's restatement agrees with the totals. Documented
  in `src/extract_hamilton.py`.
- Three sources ninety years apart agree on 25.56 g/peso: Hamilton's 1929 grain
  figure, TePaske's printed columns, Palma's `pesograms` constant.

### Expected validation numbers — treat a change as a regression

| check | value |
|---|---|
| silver peso→kg | 100.00% of 4,690 rows |
| gold peso→kg | 98.73% of 551 rows |
| mark→kg | 90.84% of 513 rows |
| decade rows vs printed TOTAL | 386/388 |
| Colmex records | 204,277 |
| ship-years vs CUADRO 2 | 58/59 |
| Veracruz in/out balance | 0.94 |

---

## 5. Traps already paid for — do not rediscover

- **Line grouping must cluster by proximity, never fixed-width bins.** Bins
  split a row whenever it straddles a bin edge. This bug appeared three separate
  times (TePaske rotated tables, the ship appendix, decade labels).
- **Assign columns by nearest header anchor, never token order.** Blank cells
  are the norm; order-based parsing silently shifts values one column left.
- Rotated PDF pages decode **only** with pdfplumber
  `line_dir="btt", char_dir="ltr"`.
- The Colmex JUNK stripper needs its lookahead `(?=[A-Za-zÁ-Úá-úÑñ])`, or it
  eats date strings and 93% of rows lose their year.
- ZIMAPAN puts CARGO in column 1, so period detection needs `ci >= 1`.
- **CHIHUAHA is a byte-identical duplicate of CHIHUAHUA** in the Colmex zip;
  summing both double-counts 465,492 pesos.
- `pd.NA` division yields an object column that later `.round()` calls choke on
  — use `float("nan")`.
- `split_merged` must scan longest-first, or `248,89010,450` becomes `2/4/8,890`.

### Known source defects (the book is wrong, not the parser)

- **Table 6-7** (Guatemala gold): the printed KILOGRAMS column does not
  correspond to the marks and pesos on its own row — verified against raw token
  positions. Recomputed from pesos it totals 943 kg against the book's own
  printed TOTAL of 944. Use `kilograms_recomputed`.
- **472 decade labels ran backwards** (`1541-1540`, `1671-1670`) from two-line
  labels pairing with the wrong neighbour. Repaired in `build_tidy.py`.
- **1752** in the ship appendix stays 4.7% short: the `S.Fdo., Águila` figures
  are illegible in the scan. Imputing from the printed total would be inventing
  a datum — left alone deliberately.

---

## 6. Substantive findings so far

1. **Hamilton's post-1630 collapse is mostly measurement.** His arrivals run at
   128% of the modern composite in the 1590s and 17% by the 1650s, while
   production held up. Use Hamilton unadjusted only through ~1620.
2. **The crown's share collapsed** from 26.2% (1503–1660, Hamilton) to 10.5%
   (1717–1778, ship-level).
3. **Circular rows are measurably worse, not just circular.** Checked against
   mintage — which knows nothing about tax receipts — derived output scatters 5×
   more widely at Potosí (permutation p = 0.0004), and the gap survives an
   era-matched control.
4. **Veracruz was a conduit**, in/out 0.94, validating the flow network by
   double entry.
5. **The situado network** quantified: Havana 41M pesos, Chile 25M, Panama 21M,
   Manila 10M (only from 1789), Louisiana 10M (only after 1779).
6. Our extraction **independently reproduces Palma's REStud series to the tonne
   from 1580** (r = 0.995), disaggregated by caja where his is one aggregate.

**Do not present `atlantic_despatch_vs_arrival.csv` as a leakage or contraband
estimate.** Only three treasuries in the Colmex sample despatched to Spain, so
the ratio measures sample coverage. This is stated in the code and the README;
keep it that way.

---

## 7. Open items

- `data/production/output_vs_mintage.csv` covers only Potosí, Lima and Mexico.
  Mexico has no independent rows in the overlap and cannot be tested.
- Mercury table 3-19 is missing **1701–1709** — worth one look at the source
  page to see whether that block exists.
- The ship appendix has **~19 rows** where crown + private still disagrees with
  the printed total; all are flagged, none are silently altered.
- The public repo includes two small tables containing a handful of
  TePaske-derived aggregates (`morineau_decade_series.csv`, 23 values;
  `arrivals_comparison.csv`, 17 rows). Judged de minimis. Easy to remove if a
  stricter line is wanted.
- Never explored: the Manila galleon beyond the situado line, VOC/EIC re-export
  to Asia, and Chaunu's ship movements for literal routes on a map.
