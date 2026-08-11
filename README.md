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
| `silver_chain_edges.csv` | the silver chain, per edge, with which side's books recorded it |
| `silver_hop1_remittance_test.csv` | silver tax against silver output, clean vs derived caja-years |
| `veracruz_despatch_vs_ships.csv` | Veracruz despatch beside vessels arriving from Veracruz |

The origin and mint layers this builds on are TePaske production data and are
therefore not published here — `src/gold_routes.py` regenerates them for anyone
with the book. See `docs/gold-routes.md` and `docs/silver-routes.md` — silver
completes the chain gold could not, because its treasury transfers exist.

### The modern reserve currency map — `site/`, `data/reserves/`

A published website doing for today's reserve money what the rest of this
repository does for silver: where the world's official reserves sit, how the
centre of that mass moved 110° east between 1960 and 2024, and what currency
the reserves are denominated in.

| file | contents |
|---|---|
| `data/reserves/cofer_currency_shares.csv` | IMF COFER — world reserve shares by currency, 1995–2026Q1, including the pre-euro DEM, FRF, NLG and ECU |
| `data/reserves/reserves_by_country.csv` | World Bank — reserves per country per year, 1960–2025, gold separable |
| `data/reserves/tic_treasury_holders.csv` | US Treasury TIC — **foreign holdings of US Treasuries by country, monthly 2000–2025**, 50 named countries |
| `data/reserves/bis_claims_by_currency.csv` | BIS — cross-border bank claims **and** liabilities with each country by currency, quarterly; their difference is the net direction |
| `site/` | the pages themselves; no frameworks, no CDN, no third-party code at runtime |

Two pages: `index.html` for where reserves sit and what they are made of, and
`flows.html` for the lines between countries — who holds US Treasuries, and
whose currency the world owes its debts in.

Both are drawn looking down on the North Pole, in an equal-area projection.
Every reserve currency but the Australian dollar is issued north of the tropics,
as is every one of the twenty largest holders, so a rectangular map splits the
one neighbourhood that matters across two edges. On the pole, the centre of
gravity's 110° east reads as the rotation it physically is, and the flow arcs
can be real great circles — Tokyo to Washington over the Arctic, which is the
way round the world you would actually go. Seen from above the pole the Earth
turns anticlockwise, so east runs anticlockwise and the Americas are on the
right; drawing them on the left mirrors every coastline.

Each map zooms to Europe, where a dozen holders otherwise sit inside ten units
of each other. The zoom is a camera and not a filter — it enlarges the globe and
frames a window, leaving every circle and arc width the size it was, so the
marks stay comparable with the ones now off the frame.

`src/reserves/` rebuilds all of it from four public APIs, 36 validation checks.
See `docs/reserve-currency-map.md`.

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

**The treasury books are single-sided.** A transfer should be booked twice, by
sender and receiver. Of the 46 named district->hub edges, exactly one is. Mexico
City records 20.8M pesos sent to Veracruz; Veracruz records 292.5M received —
reading the sender side alone loses 93% of the empire's largest silver artery.
Potosi records 50.1M sent to Lima against Lima's 2.3M received, a factor of
twenty the other way. `silver_chain_edges.csv` reports which side recorded each
edge. This also qualifies the Veracruz finding below: 366M in against 389M out is
a *node* balance, not a matched pair of books.

**The circularity constant is empire-wide.** Silver tax over silver output should
vary by district. On caja-years recorded independently it does, spreading 0.039
to 0.233. On the years derived from receipts the cross-district IQR is 3.8x
tighter and **13 of 21 districts sit within one point of 0.1135** — Zacatecas
0.1109, Guadalajara 0.1123, Zimapan 0.1123, Carangas 0.1130, Huancavelica
0.1135. Different centuries, different viceroyalties, same number.

**Beware circular joins.** Where the production literature had no independent
output figure, one was derived from tax receipts at an assumed rate. Joining
output back to receipts then recovers that assumption — 248 caja-years share a
ratio of exactly 0.11350, the diezmo plus the cobos on the remainder. Checked
against coin struck, which is recorded by the mints and knows nothing about tax
receipts, those derived figures scatter five times more widely than
independently recorded ones (permutation test p = 0.0004). See
`docs/circularity-test.md`.

**The modern record has the same hole as the colonial one.** The IMF publishes
what currency the world's reserves are held in; the World Bank publishes who
holds reserves. Neither publishes both, and COFER is collected on the explicit
condition that no country is ever identified. So the modern data supports a map
of holders and a chart of currencies and *no* link between them — the same
single-sidedness that loses 93% of the Mexico City→Veracruz silver artery.
Meanwhile the two sources, compiled independently, agree on the world total to
within 6% in every one of the 31 years they overlap.

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
| IMF COFER | public API — © IMF, redistributed under its terms of use |
| World Bank development indicators | public API — **CC-BY 4.0** |
| US Treasury TIC | **US public domain** (work of the federal government) |
| BIS locational banking statistics | public API — © BIS, reuse with attribution |
| Natural Earth 1:110m | **public domain** |

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
