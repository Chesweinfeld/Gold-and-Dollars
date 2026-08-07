# Gold and Dollars

Machine-readable datasets for the movement of silver and gold out of Spanish
and Portuguese America, roughly 1503–1825, digitized from sources that had no
machine-readable form, with the arithmetic checked at every step.

Metal was measured at four points by four separate record-keeping systems, and
the interesting questions live in the gaps between them:

```
production            taxation             movement            arrival
(colonial mines) -> (royal treasuries) -> (transfers) -> (Seville / Cádiz)
```

## What is here

### Atlantic arrivals — `data/arrivals/`

| file | source | contents |
|---|---|---|
| `hamilton_1929_arrivals.csv` | Hamilton 1929 | registered arrivals at Seville by decade, 1503–1660, **split crown vs private** |
| `gb_ships_1717_1778.csv` | García-Baquero 1996 | **1,153 individual vessels** — arrival date, ship, port of origin, crown/private split |
| `morineau_annual_1717_1778.csv` | García-Baquero 1996 | **annual** figures, Morineau's beside García-Baquero's recount |
| `morineau_decade_series.csv` | — | Morineau's Dutch-gazette series by decade, 1581–1805 |
| `arrivals_comparison.csv` | derived | Hamilton beside the modern composite |

Hamilton's crown/private split is the piece nothing modern carries, and it is
the only way to connect Atlantic arrivals to the fiscal records on the American
side.

### Movement and taxation — `data/fiscal/`

Built from the Colmex digitization of the TePaske/Klein royal treasury books —
204,277 account lines across 75 treasuries.

| file | contents |
|---|---|
| `colmex_flows.csv` | **7,068 transfer edges** — origin treasury, destination, year, pesos, 1528–1825 |
| `situado_network.csv` | the empire's internal subsidy payments by destination |
| `colmex_mining_annual.csv` | mining revenue classified silver / gold / mercury |
| `atlantic_despatch_vs_arrival.csv` | metal despatched to Spain against metal recorded arriving |

### Gold routes — `data/routes/`

Mining district -> mint -> American port, with each link labelled by the
evidence supporting it. Route-level, not parcel-level: no source here follows a
consignment from a placer to a hold.

| file | contents |
|---|---|
| `gold_routes.csv` | 11 mint->port edges, with years, assumed share, evidence class |
| `gold_port_annual.csv` | value laded by American port and year, crown/private |
| `port_gold_ratio_test.csv` | the test that decides which ports were gold ports |

The origin and mint layers this builds on are TePaske production data and are
therefore not published here — `src/gold_routes.py` regenerates them for anyone
with the book. See `docs/gold-routes.md`.

## Findings

**Hamilton's post-1630 collapse is mostly a measurement artifact.** His
registered arrivals run at 128% of the modern composite in the 1590s and 17% by
the 1650s, while American production held up through exactly those decades.
Registration at Seville broke down as crown confiscations taught merchants not
to declare. *Use Hamilton unadjusted only through about 1620.*

**The crown's share of Atlantic treasure collapsed.** Hamilton's decades give
the king 26.2% of registered arrivals across 1503–1660 — a figure our extraction
reproduces from his own decade rows, matching the 26.2% he states in the text.
The ship-level eighteenth-century data gives the Real Hacienda **10.5%**.
Bourbon-era treasure was overwhelmingly private.

**Veracruz was a conduit, not a reservoir.** It received 366M pesos and
despatched 389M — agreeing within 6%. Silver arrived from Mexico City (292M of
it, 1606–1792) and left for Spain, Havana and the Caribbean garrisons without
settling. A transfer is booked twice, by the sender as expenditure and the
receiver as revenue, so that balance is a real check on the network.

**The empire subsidised itself in one direction.** The `situado` payments went
to garrisons and colonies that never paid their own way: Havana 41M pesos,
Chile 25M, Panama 21M, Buenos Aires 14M, Valdivia 12M, Louisiana 10M, Manila
10M. The dates are as telling as the amounts — Manila's subsidy appears only
from 1789 and Louisiana's only after 1779, both late acquisitions bolted onto an
existing fiscal machine.

**Cartagena was a gold port and Veracruz was not.** The ship appendix records
pesos per vessel, not gold pesos, and of 7,068 treasury transfer edges exactly
one names a metal — so metal composition has to be earned from the region
upstream. Against the gold struck at the mint feeding it, Cartagena's outbound
value is 0.82 and tracks it (decade r = 0.67); Veracruz's is 8.01 and does not
(r = 0.11). New Granadan silver was 4% of its gold by value, so value leaving
Cartagena is gold to within that margin and the route holds end to end. Veracruz
shipped silver, and the Mexican gold inside it cannot be separated out by these
sources. The series also carries the War of Jenkins' Ear unprompted: Cartagena
runs 6.5M pesos in 1738, near zero 1741–47, then 10.4M in 1750 as the backlog
clears.

**New Granada is missing from the fiscal layer entirely.** The largest gold
region in Spanish America — 320 tonnes fine — has no caja among the 71 in
`colmex_flows.csv`. Production, mintage and port are all present; the treasury
movement record in between is absent for exactly the region where it would
matter most.

**Beware circular joins.** Where the production literature had no independent
output figure, one was derived from tax receipts at an assumed rate. Joining
output back to receipts then recovers that assumption — 248 caja-years share a
ratio of exactly 0.11350, the diezmo plus the cobos on the remainder. Checked
against coin struck, which is recorded by the mints and knows nothing about tax
receipts, those derived figures scatter five times more widely than
independently recorded ones (permutation test p = 0.0004). See
`docs/circularity-test.md`.

## What is deliberately not here

The production series — every quantitative table from TePaske, *A New World of
Gold and Silver* (Brill, 2010) — is **not** published, because that book is in
copyright. Individual facts are not copyrightable in the United States
(*Feist*), but a complete reproduction of the selection and arrangement of a
commercial book's entire appendix is a different matter, and Brill would have a
reasonable objection.

The **extraction code is here** (`src/extract_tepaske.py`, `src/build_tidy.py`),
so anyone with legitimate access to the book can regenerate the data in a couple
of minutes. Files omitted for this reason: the TePaske annual and decade tables,
the raw extraction, the output-vs-mintage table, and the production/receipts
join.

## Sources and rights

| source | status |
|---|---|
| Hamilton, *QJE* 43(3), 1929 | **US public domain** (published 1929) |
| García-Baquero González, *Hispania* 56(192), 1996 | **CC-BY 4.0** — reuse with attribution |
| Sousa, *e-JPH* 6(1), 2008 | open access |
| Colmex *Real Hacienda* treasury books | public download |
| TePaske, Brill 2010 | in copyright — **code only, no data** |

Full citations:

- Earl J. Hamilton, "Imports of American Gold and Silver into Spain,
  1503–1660", *Quarterly Journal of Economics* 43:3 (1929), 436–472.
- Antonio García-Baquero González, "Las remesas de metales preciosos americanos
  en el siglo XVIII: una aritmética controvertida", *Hispania* 56:192 (1996),
  203–266. <https://doi.org/10.3989/hispania.1996.v56.i192.757>
- Rita Martins de Sousa, "Brazilian Gold and the Lisbon Mint House
  (1720–1807)", *e-Journal of Portuguese History* 6:1 (2008).
- Michel Morineau, *Ces incroyables gazettes et fabuleux métaux* (Cambridge UP /
  MSH, 1985) — reached here through García-Baquero's reprint of his series, not
  from the book.

Code in `src/` is MIT licensed. Data files carry the rights of their sources.

## Reproducing

```bash
python3 -m venv venv && ./venv/bin/pip install pdfplumber pandas openpyxl xlrd
```

Every script prints its own validation report. The open-access sources download
directly:

```bash
curl -L -o garciabaquero1996.pdf "https://hispania.revistas.csic.es/index.php/hispania/article/download/757/754"
```

`src/fiscal/README.md` documents the Colmex rebuild and the parsing traps it
already handles.
