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

### Global land value — `data/land/`

A modern side-piece: what the world's land is worth today, and a cartogram
drawing every country at its share of it. Agricultural land is measured;
urban land is modelled from GDP on the fourteen countries whose national
accounts actually report total land.

| file | contents |
|---|---|
| `land_value_2020.csv` | 210 countries: agricultural, urban, total, and a sensitivity variant |
| `urban_land_calibration.csv` | the 18 SNA reporters, observed against fitted, and which were used |
| `cartogram_area_check.csv` | each country's share of value against its share of the drawing |
| `subnational_land_value.csv` | the same value split across 4,405 states and provinces |
| `cartogram_area_check_subnational.csv` | the area check at unit level |

See [`docs/land-value-cartogram.md`](docs/land-value-cartogram.md). Two figures
in `docs/figures/`: countries, and a zoomable version at state and province
level. Note the boundary between measurement and model: 17.8% of the total is
measured, and the doc is mostly about what the other 82.2% can and cannot
support.

### American land value at 480 m — `src/land/make_us_cartogram.py`

The United States is the one large country where the urban half does not have
to be modelled: Nolte (2020) fitted six million arm's-length land sales and
published a fair-market value for every 480 m cell of the conterminous states.
Three zoomable WebGL cartograms in `docs/figures/` — the country on a 3.84 km
grid (533,958 tiles), and New York and the Bay Area at the source's native
480 m — plus a study of how much of the rest of the world could be done the
same way.

See [`docs/us-land-value-cartogram.md`](docs/us-land-value-cartogram.md).

### American GDP on the same lattice — `src/land/build_us_gdp.py`

BEA measures GDP by county and nothing finer. Placing it inside each county
puts $27.5tn of 2023 output on the same 3.84 km tiles as the land map, so the
two can be divided by each other. Each part of it goes on the thing that
produces it: **85.7% on the jobs**, from 2.3 million census blocks of workplace
counts in the Census LEHD; **13.4% on the housing**, because BEA's largest
single line below the total is the output of dwellings — rent paid, plus the
rent imputed to owner-occupiers — which is produced by the house rather than at
its occupant's office; and **0.8% on the land cover**, from the USDA crop
map, because payroll records cannot see a farmer working his own land. Before
that split, 62% of the tiles carrying land value had no output at all; after
it, 0.8%.

Crucially it is not all jobs at one rate. BEA reports county GDP on twenty
industry lines and LODES counts jobs in the same twenty NAICS sectors in every
block, so **each line rides the jobs of its own industry** — from $66,576 a job
in accommodation and food to $432,406 in information. A refinery block and a school
block in the same county used to receive identical output. One place the
mapping had to be undone: BEA's education and health lines are *private* only,
while a public school's teachers sit in the same LODES sector as a private
one's, so matched one to one government came out at $446,032 a job and
education at $6,019 in the median county. Those three lines are pooled and
carried together.

Three registers put the work where LODES cannot. **MSHA** counts a mine's
employees at the mine, **EIA-860** puts 1,274 GW of generating capacity at its
plants, and **FracFocus** puts 61,936 hydraulically fractured wells at their
coordinates — all added as carrier points, because a mining company or a
utility reports its payroll at the head office. The wells are the largest
single correction: Loving County, Texas carries $10.7bn of output and had **not
one census block with a mining job in it**, so its oil was stranded and drawn
on the county's gas stations. It now sits on 2,332 points. 57% of the mining
line's weight is at a site rather than an office, and the sector's rate fell
from $685,529 a job to $303,952 as the real workplaces entered the
denominator. And the eleven classes of ground the
crop map distinguishes — from vegetables at $33,362 a hectare to sagebrush at
$35 — get their rates **fitted against the 2022 Census of Agriculture** rather
than asserted. That fit is honest about what it cannot do: regressed on
livestock sales, grazing land scores R² −0.278, worse than predicting the mean,
because the animals that earn most are raised in barns the crop map sees as
buildings. So crops are fitted on census sales and grazing on BEA's own farm
line, and any class the fit cannot separate is folded into a sibling and said
to be. Every county still reconciles to its BEA figure exactly — 100.0000%,
checked on every build — and how well LODES counts the country at all is
measured against BLS QCEW by `src/land/check_lodes_coverage.py`: 1.03 overall,
within 20% on 85% of county-sectors.

Two further figures divide the two. The quantity is a **price-to-earnings ratio
for the ground**: a tile's land value over the output produced on it, a stock
over a flow, so it has units of years. Over the ground that has output on it the
baseline is 0.4038 — privately held American land is worth about five months of
what is made on it. Low is working ground (the
Cleveland Flats at 0.09 years, Midtown Manhattan at 0.04 despite being the
dearest dirt in the country); high is ground priced for something other than the
work on it (Cape Cod at 4.06, Napa at 1.22). The worked examples are printed
from the shipped tiles by `src/land/ratio_examples.py`. Two things have to be
distrusted. Indiana's cities carry almost no urban premium in the land model, so
the state reads far more teal than it should — measured, and separated from a
real state-level effect, by `src/land/land_model_gaps.py`. And the map is not
equally fine everywhere: on ground that has workplaces, three quarters of the
ratio's variance is within counties and the pattern is real geography. On the
ground that has none, 73% of it is between counties — the county figure showing
through — so **that ground is not given a ratio at all**: it is drawn in one
flat grey, 20.2% of the land value on the page. The county farm multiplier
spans 21× between counties and no allocator fixed it, so the map stops where
its denominator stops. Ground with no market at all — the national parks and
the military bases, 1.4% of the lower 48 — is left out of the numerator
entirely, because the land model prices it anyway: $1.04m per km² for the
interior of Yellowstone. That exclusion applies only to this ratio map; the
land-value cartograms draw every acre, Yellowstone included, and say so in
their own note. Both variance readings are printed on every build by
`src/land/us_land_vs_gdp.py`.

There is also a **scrolled version** of the flat map — twelve stops, each
framing the ground it is about. Every number in its text is computed from the
tiles at build time and the rectangle it was summed over is drawn on the map,
so a caption cannot drift away from what it describes. Its sharpest stop is the
East River: the two most valuable squares in America sit next to each other,
hold the same $17.7bn of land, and come out 8x apart because one of them has
Midtown on it.

See [`docs/us-gdp-cartogram.md`](docs/us-gdp-cartogram.md).

## Findings

**American output is nearly five times as concentrated as American land
value.** On the same 3.84 km tiles, half of GDP is produced on 45,240 km² —
0.6% of the conterminous states — against 212,145 km² for half of land value. A
tenth of GDP comes off 988 km², an area smaller than New York City. Detail in
[`docs/us-gdp-cartogram.md`](docs/us-gdp-cartogram.md).

**The ratio of land value to output climbs by a factor of 5.7 from the middle
of a city to its edge.** Pooling the twelve largest downtowns and banding every
square by its distance from one: 1/4.9 of the national figure within 5 km, then
1/1.5, 1/1.3, 1/1.0, and 1.1x at 50–80 km. The direction holds in all twelve
metros taken one at a time. It is the cleanest structure in the data, and it
survives the obvious objection: the rent on every dwelling in the ring is
counted on the ground the dwelling stands on, and the suburb still costs more
years than it earns, because what a house earns in a year is small beside what
work earns on the same square foot downtown. The median dollar of American land
value sits on ground worth 0.619 years of its own output against a national
0.4046, and 64.8% of it is dearer than the national figure implies. Those are
measured over the coloured ground — the ground with a workplace on it — and are
printed on every build rather than typed here.

**Half of American land value sits on 3% of American ground.** Sorting all
33.7 million 480 m cells of the conterminous US by fair market value, the top
230,000 km² — 2.9% of the surface — holds 53.3% of the total; the top 23,000
km², 0.29%, holds 23.0%. Detail in
[`docs/us-land-value-cartogram.md`](docs/us-land-value-cartogram.md).

**The World Bank values all US agricultural land at $182 billion.** *Changing
Wealth of Nations* gives US cropland $83bn and pastureland $100bn for 2020.
USDA's own total for US farmland and buildings was $2,732bn in 2019 — a factor
of fifteen. CWON capitalises resource rents rather than observing prices, so
the two are not measuring the same thing, but the gap is large enough that the
farmland half of any CWON-based world map should not be read as a market value.

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

**The World Bank's urban land value is a constant.** *Changing Wealth of
Nations* reports produced capital both including and excluding urban land, which
looks like an urban land series for 150 countries. The ratio of the two is
1.2400000000 for every country in every year, across 3,858 country-years, with a
standard deviation of 2.4e-15. Urban land there is 0.24 × produced capital by
assumption and carries no country information of its own — the same failure as
the derived output figures below, in a series published in 2024. See
`docs/land-value-cartogram.md`.

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
