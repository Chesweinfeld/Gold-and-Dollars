# American output, drawn where it is produced

A companion to [the land-value map](us-land-value-cartogram.md), cut from the
same 480 m lattice so the two can be divided by each other.

The honest starting point: **there is no gridded measurement of GDP anywhere in
the world.** The finest official American figure is county GDP, published by
the BEA for about 3,100 counties, and everything below that is allocation.
This map is explicit about the seam:

| | |
| --- | --- |
| **measured** | BEA county GDP, table CAGDP2, by industry line, 2023 |
| **allocated** | within each county, by where the thing that produces it stands — **the jobs of that same industry** for 85.7% of it, tract housing services for 13.4%, farmed hectares for 0.8% |

Jobs are the right allocator for most GDP in a way population is not. Output is
produced where people work, so a downtown block with forty thousand jobs and
nobody living in it gets the output, and the subdivision housing those workers
gets none of it.

## Not all jobs at one rate

The single largest improvement to this map came from a column that was already
on disk and being thrown away.

BEA reports county GDP on twenty industry lines. LODES counts jobs in the same
twenty two-digit NAICS sectors, in every census block — the `CNS01`–`CNS20`
columns, which sit in the same file as the `C000` total the code used to read
alone. They map one to one. So each line can ride the jobs of its own industry
rather than all jobs at one county-wide rate.

The rates are not close to equal:

| sector | national $ per job | median county |
| --- | ---: | ---: |
| information | $432,406 | $225,528 |
| finance and insurance | $325,749 | $214,858 |
| mining, oil and gas | $303,952 | $166,000 |
| utilities | $277,526 | $146,000 |
| manufacturing | $217,718 | $154,432 |
| construction | $150,324 | $131,238 |
| education, health, government | $121,984 | $96,118 |
| retail trade | $114,801 | $96,596 |
| accommodation and food | **$66,576** | $48,968 |

Six to one between the top and bottom of that table. Under a single flat
rate, a refinery block and a school block in the same county received the same
output per job. They no longer do.

**One place the one-to-one mapping is a lie, and has to be undone.** BEA's
lines 69 and 70 are *private* education and health; the output of a state
university or a county hospital is not there but in line 83, government. LODES
draws no such distinction — a public school's teachers are counted in `CNS15`
with the private ones, and `CNS20` holds only public administration proper.
Matched one to one the error was gross in both directions: government came out
at **$446,032 a job** and education at **$6,019 in the median county**, which
is not a wage bill, let alone an output. The three lines are pooled and carried
by the three sectors together. That gives up telling a school from a hospital
and buys back not putting a state university's output in the county courthouse.

## Where LODES puts the work, and where the work is

LODES places a job at the worksite the employer reports, which for a mining
company or a utility is routinely the head office. Two registers say where the
work actually happens, and are added as further carrier points by
`src/land/build_us_facilities.py`:

- **MSHA** — 11,933 producing mines, with a coordinate and a headcount measured
  at the mine. 187,736 employees.
- **EIA-860** — 12,246 generating plants, 1,274 GW of nameplate capacity,
  converted to job-equivalents at the national ratio of utility jobs to
  installed megawatts (0.64 jobs per MW, printed on every build because it is
  the one number here that is a choice rather than a measurement).
- **FracFocus** — 61,936 wells fracked 2019–2023, carrying 926bn gallons of
  base water, converted the same way (0.61 mining jobs per million gallons).
  The window matters: a shale well loses most of its rate in two years, so
  counting the registry back to 2011 would put weight on ground that has
  largely stopped paying.

They are *added* to the LODES blocks rather than replacing them. A mine's
employees may also appear in the LODES count for the block the mine sits in, so
this double counts them — which is harmless, because allocation is
within-county: every county still receives exactly its BEA figure, and all the
double count does is shift weight from the office towards the pit. What it
deliberately does not do is take the whole line off the jobs, because a county
can hold both a quarry and an oilfield and only one of them is in MSHA.

**The wells are the largest single correction on this map.** Before them, BEA's
mining line had nowhere to go in exactly the counties where it is biggest:

| county | BEA output | blocks with a mining job | mining jobs on them | wells now |
| --- | ---: | ---: | ---: | ---: |
| Loving, TX | $10.7bn | **0** | 0 | 1,736 |
| Martin, TX | $14.7bn | 7 | 103 | 2,982 |
| Reeves, TX | $14.7bn | 32 | 1,372 | 2,413 |
| McKenzie, ND | $4.4bn | 72 | 1,697 | 1,400 |
| Midland, TX | $40.4bn | 399 | 33,058 | 3,054 |

Loving County is the clearest case: $10.7bn of output, 432 jobs of any kind in
the county, and **not one census block with a mining job in it**. Its oil was
stranded, fell through to the county's other jobs, and was drawn on its gas
stations. It now sits on 2,332 points, of which the largest five hold 1.1% of
the county's output.

The effect on the sector rate is the same story from the other end: $685,529 a
job before any facilities were added, $529,694 with the mines, **$303,952 with
the wells** — the denominator filling up with the places the work is actually
done. 57% of the mining line's weight now sits at a site rather than an office.

## Does LODES count the country?

Everything above rests on LODES, so how well it counts is measured rather than
assumed. `src/land/check_lodes_coverage.py` compares it against BLS QCEW —
same unemployment-insurance source, different agency — by county and sector:

| | |
| --- | --- |
| LODES against QCEW, all eighteen sectors | **1.03** (146.5M against 142.1M) |
| county-sectors within 20%, of 19,519 with 500+ QCEW jobs | **85%** |
| worst sector | educational services, **1.31** |

The worst sector being education is not a coincidence: it is the same
public/private seam that showed up independently in the BEA line mapping,
found here from the other side. An exact match is not possible — QCEW counts by
the establishment's reported county and suppresses disclosive cells — so what
matters is the shape of the disagreement, not that it is nonzero.

## The two exceptions

There are two, and an earlier version of this map ignored both. They
left 62% of the tiles carrying land value with no output at all.

**CAGDP2 line 56, "Real estate and rental and leasing" — $3.78tn, 13.8% of the
national total — is mostly the output of dwellings**: the rent tenants pay plus
the rent BEA imputes to owner-occupiers for living in their own houses. That is
produced by the house, on the ground the house stands on, and has nothing to do
with where the occupant goes to work. Allocating it by jobs put the entire
housing stock's output in the office districts. It now goes by resident
population, from the GHS-POP 2020 grid at 30 arc-seconds.

**CAGDP2 line 3, agriculture, forestry, fishing and hunting — $269bn, 1.0% —
is produced on the fields, and LODES cannot see it.** The workplace file counts
jobs covered by unemployment insurance, which excludes farm proprietors and
most farm labour; the jobs the industry does record sit at the co-op in town.
It now goes by land cover, over the 662.9M ha the USDA Cropland Data Layer
classes as productive, on a 1.92 km grid built by
`src/land/build_us_farmland.py`. Getting there took three corrections, and each
is worth naming because the first draft made all three mistakes:

- **Range and forest have to be counted at all.** The first version counted
  only cropland and grassland, and that was the single biggest artefact on the
  map. On a strip across western Nebraska the crop map calls 56% of the ground
  shrubland and 22% evergreen forest — **78% of it counted as nothing** — while
  the county next door, whose identical range the classifier happened to put in
  grassland, took its whole farm allocation spread thinly across it. Whether a
  county's rangeland lands in one class or the other is a decision of the
  classifier, not a fact about the county, and the map drew that decision as a
  hard rectangle. Counting every class took coverage from 275.1M ha to
  662.9M — against the 356M the USDA calls land in farms, the excess being
  ungrazed forest, which the fit prices accordingly.
- **Eleven classes, not four, and the weights are fitted rather than
  asserted.** Cropland was one class until the rates were checked against the
  Census of Agriculture, which was enough to show that lumping an almond
  orchard with a wheat field made every county holding either one wrong. The
  eleven are fitted by non-negative least squares, weighted so a few huge
  counties do not decide them:

  | | $ per hectare per year | |
  | --- | ---: | --- |
  | vegetables | **$33,362** | potatoes, lettuce, melons, the truck crops |
  | vines and berries | $30,746 | grapes, strawberries, cranberries |
  | orchard and nuts | $6,517 | one rate; the fit cannot separate them |
  | hay | $1,382 | alfalfa, clover, sod |
  | row and small grain | $1,117 | one rate; corn, soy, wheat, cotton, fallow |
  | forest | $153 | |
  | pasture | $138 | |
  | range (shrubland) | $35 | |

  **Two targets, because one measure cannot do both jobs.** The crop classes
  are fitted against the Census of Agriculture — it counts gross sales at every
  farm and separates them by commodity, which is what makes an almond
  distinguishable from an acre of wheat (R² 0.602 across 2,962 counties).

  The grazing classes cannot be fitted that way, and it took three attempts to
  accept it. Regressed on census sales — animal sales alone, or total sales —
  pasture, range and forest all come out at **exactly zero**, and the
  animal-only fit scores **R² −0.278**, worse than predicting the mean. The
  reason is real rather than numerical: the animals that earn most are raised
  in confinement, in poultry houses and hog barns the crop map sees as a
  building, so hectares of grass genuinely do not predict what a county sells.
  Zero is the one answer that cannot be shipped, because it hands a Wyoming
  ranching county's whole allocation to whatever scrap of cropland it has. So
  grazing is fitted against BEA's own farm line instead — the thing actually
  being spread, which counts grazing and forestry value added — with the crop
  classes carried as a single column whose coefficient converts census sales
  into value-added dollars, $0.638 to the dollar (R² 0.591).

  **A class the fit cannot identify is folded into a sibling, and said to be.**
  Almonds fall back to orchards, not to the corn belt; sagebrush falls back to
  pasture, not to the vineyards. Three folds happen as built — nuts into
  orchard, small grain and fallow into row — and each is printed. That is a
  real loss of resolution, and it is preferable to the alternative, which is
  asserting that almonds grow for free. These remain within-county allocation
  weights, not estimates of what each land cover earns nationally, and they
  should not be quoted as the latter.
- **Agriculture is read as a five-year average, 2019–2023.** County farm value
  added is *net* of costs and swings by an order of magnitude year to year:
  Jackson County, Kansas reports $2m, $16m, $17m, $2m over four consecutive
  years, while its land price does nothing of the kind. Only the *share* of a
  county's output attributed to farming is averaged; the county still receives
  exactly its BEA total for 2023, so the reconciliation is untouched.

Four further seams. Line 56 also holds commercial leasing and equipment rental,
which are not produced at homes. Line 3 also holds fishing and hunting, which
are not produced on fields — the 28 counties where the implied output per
hectare comes out more than twenty times what its land cover predicts (Monroe
County, Florida lands the Keys' catch on a few hectares of field) are detected
and left with their jobs. BEA suppresses line 56 in 730 mostly rural counties, 9.7% of
the national figure, and the state residual is put back over them in proportion
to population; the other eighteen lines are suppressed far more often — 1,122
counties for management of companies alone — and each is refilled over its own
sector's jobs.

And **the oil that is not fracked still lands at the office.** FracFocus is a
disclosure registry for hydraulic fracturing, so it holds the Permian, the
Bakken, the Eagle Ford, the Marcellus and the Anadarko, and largely misses
California's steam-flooded heavy oil and Appalachia's legacy gas. Because the
well points are added to the LODES jobs rather than replacing them, a county
with no fracked wells is left exactly as it was — the gap costs coverage, not
correctness.

What the allocation still cannot do is vary productivity *within* a county
*inside one sector*: two blocks of manufacturing jobs in the same county get
the same output per job, whether one is a chip fab and the other a sawmill.
Across sectors it now does vary, which is the whole point of the split.

## What went in

- 2,309,465 census blocks with at least one job, holding **150.0 million jobs**
- 5,020,036 population cells holding **333.2 million people**
- 2,098,747 land-cover cells holding **662.9 million hectares** — 91.1M row
  crop, 20.9M small grain, 19.5M hay, 0.4M vegetables, 1.0M orchard, 1.5M nuts,
  0.5M vine, 6.4M fallow, 133.9M pasture, 185.0M range, 203.1M forest
- 24,179 facility points — **11,933 producing mines** with 187,736 employees
  between them, from MSHA, and **12,246 generating plants** holding 1,274 GW of
  nameplate capacity, from EIA-860
- **$27.48 trillion** of 2023 GDP across 3,080 BEA areas in the conterminous
  states plus DC
- The allocation reconciles to BEA at 100.0000%

Two seams worth naming:

- **31 BEA areas match no county FIPS** ($658bn, 2.39% of the total). These are
  combinations — Virginia's independent cities are reported with the county
  that surrounds them. Rather than hard-code the membership list, that GDP is
  pooled at state level and spread over the state's remaining jobs: exact in
  state aggregate, approximate inside it, and flagged per area in
  `us_gdp_county_check.csv`.
- **Michigan's latest LODES is 2021**, not 2023. Every other state is 2023.
  That shifts only *where inside a county* Michigan's jobs sit; the county
  totals are still BEA's for 2023. Vintages are written to
  `us_gdp_lodes_vintage.csv`.

The three rates, across counties:

| | lowest | median | highest |
| --- | ---: | ---: | ---: |
| output per job | $0 | $125,881 | $24,822,727 |
| housing output per resident | $1,709 | $6,709 | $56,252 |
| farm output against what the county's land cover predicts | 0.00× | 0.61× | 12.3× |

The extreme at the top of the first row is not an error: it is Loving,
Glasscock, Martin and Reeves counties in the Permian Basin, plus Butte County,
Idaho — places that produce billions from oil, gas, or a national laboratory
with almost no payroll. Inside them the allocation is at its weakest, because it
puts the output at the few blocks with workers rather than across the wells.

The top of the second row is Manhattan, which is the answer it should be. It was
not, at first: filling the suppressed counties in proportion to their
all-industry GDP handed Storey County, Nevada — a car factory and 1,100 people
— $264,000 of housing output per resident. Each line is now filled in
proportion to the carrier it will be allocated over.

## The headline: output is twice as concentrated as land value

Both surfaces on the same 3.84 km tiles, over the 529,827 tiles that carry
both:

| | half of it sits on | a tenth of it sits on |
| --- | --- | --- |
| land value | 14,387 tiles — 212,145 km² | 402 tiles — 5,928 km² |
| **GDP** | **3,068 tiles — 45,240 km²** | **67 tiles — 988 km²** |

Half of American output is produced on **0.6% of American ground**. A tenth of
it is produced on 988 km² — an area smaller than New York City.

The twelve highest-output tiles are exactly where they should be, which is the
best available check that the allocation is not inventing structure:

| | | GDP | land value | years |
| --- | --- | ---: | ---: | ---: |
| 40.765, −73.988 | Midtown Manhattan | $418.8bn | $17.65bn | 0.04 |
| 40.731, −73.998 | Union Square / Village | $241.8bn | $13.29bn | 0.05 |
| 41.876, −87.619 | the Chicago Loop | $109.5bn | $1.21bn | 0.01 |
| 40.698, −74.009 | Lower Manhattan | $108.6bn | $3.98bn | 0.04 |
| 37.799, −122.419 | San Francisco, Financial District | $104.9bn | $2.21bn | 0.02 |
| 47.622, −122.331 | Seattle | $88.6bn | $2.99bn | 0.03 |
| 42.342, −71.058 | Boston | $75.8bn | $6.92bn | 0.09 |
| 37.766, −122.407 | San Francisco, SoMa / Mission | $75.0bn | $3.99bn | 0.05 |
| 38.918, −77.025 | Washington, D.C. | $59.3bn | $6.13bn | 0.10 |
| 34.059, −118.263 | downtown Los Angeles | $57.4bn | $1.64bn | 0.03 |
| 40.757, −73.943 | Long Island City | $56.8bn | $17.87bn | 0.31 |
| 38.884, −77.034 | Washington, D.C. (the Mall) | $54.6bn | $2.53bn | 0.05 |

"Years" is land value divided by annual output — a stock over a flow, so the
units are years of its own production that the ground under it is worth.
Nationally that ratio is **0.41 years**; weighted by output the median tile is
**0.17**. Read that carefully in both directions: it is partly a real fact
about how much output a small amount of expensive ground carries, and partly an
artefact of the land model, which compresses the top of the price distribution
(its most expensive 480 m cell is $2,618/m², where Manhattan land trades far
above that). The ratio is a comparison of two maps, not a measured statistic.

## The differential map

`docs/figures/land_vs_output_cartogram_us.html`, built as
`make_us_cartogram.py usratio`.

### What the number is

Take one 3.84 km square. It holds some quantity of land, worth some number of
dollars, and some number of jobs, which produce some number of dollars of output
every year. Divide the first by the second. Dollars over dollars-a-year leaves
**years**: how long the work done on that ground would have to run to equal the
price of the ground itself. It is a price-to-earnings ratio, with the land as the
asset and the local economy as the earnings. Nationally it is 0.41 — all the
privately valued land in the lower 48 is worth about five months of what is
produced on it.

The reading that has to be broken first is *dear land is brown, cheap land is
teal*. It is not that axis at all. These ten squares are printed by
`src/land/ratio_examples.py`, straight off the shipped tiles, so the prose here
cannot drift away from the map:

| | land | output/yr | years | vs U.S. |
| --- | ---: | ---: | ---: | ---: |
| Gary, Indiana (mill district) | $10m | $876m | 0.01 | 0.0× ⚠ |
| Midtown Manhattan | $17,650m | $418,818m | 0.04 | 0.1× |
| Cleveland, Ohio (the Flats) | $210m | $2,497m | 0.08 | 0.2× |
| Iowa farmland (Story County) | $118m | $1,139m | 0.10 | 0.3× |
| Beverly Hills | $1,978m | $18,384m | 0.11 | 0.3× |
| Bakersfield, California | $433m | $3,012m | 0.14 | 0.4× |
| Houston Ship Channel | $89m | $229m | 0.39 | 1.0× |
| Aspen, Colorado | $656m | $1,288m | 0.51 | 1.2× |
| Mountain View, California | $5,877m | $7,115m | 0.83 | 2.0× |
| Napa Valley | $51m | $42m | 1.22 | 3.0× |
| Cape Cod | $236m | $58m | 4.06 | 10.1× |

The Cleveland Flats and Midtown Manhattan are eighty-fold apart in price per
square and sit next to each other at the teal end, because on both the work
standing on the ground dwarfs the price of the ground. Cape Cod is a hundred
times Manhattan's ratio: expensive because people want to be there, not
because anyone works there. Napa is priced on decades of future vintages rather
than this year's payroll. Mountain View is genuinely productive and its land has
still run ahead of it.

⚠ **Gary is in the table flagged, and is not used as an exemplar.** It reads as
the most extreme teal in the country, and that is an artefact of the land
surface rather than a fact about Gary — see *Indiana* below.

**What brown means, and what it does not.** A subdivision is not brown *by
construction* here: the rent on every dwelling in it is counted on the ground
the dwelling stands on. It is brown because what a house earns in a year is
small beside what it costs. Read brown as "this ground is not paid for by
production happening on it", then ask what is paying for it. Grey is what is
left over — 4,131 tiles holding 0.3% of the land value, where the map found no
job, no resident and no productive ground of any kind, and declines to divide
by nothing.

It is **not** GDP per person. It is not a rate of return, and it is not a
verdict that anything is over- or under-priced.

### The map

Rather than draw output — which, as the section below shows, does not draw —
this map keeps the geometry of the **land-value** cartogram and changes only
what the colour says. Area is still each tile's share of the $11.26tn of
American land value, with that map's validated 6.9% median error, because it
reuses the same transported mesh. It costs a render, not a solve.

The colour asks what the ground earns: a tile's own land value divided by the
output produced on it, against the national ratio of **0.4046** — total land
value over total GDP, or about five months of output. The scale is symmetric in
log, so a factor of ten either side of the baseline is the same distance from
the middle. Teal is ground carrying more output than its price implies; brown
is ground costing more than the work done on it.

A note on the arithmetic, since the question was posed as GDP *per capita*
against land value: if the comparison is a **ratio**, per capita cancels.
(land ÷ people) ÷ (output ÷ people) is land ÷ output. The map is the same
either way, and it needs no population data.

What it shows, weighted by land value, over the ground that gets a colour:

| | |
| --- | --- |
| national baseline | 0.4046 years of output |
| median tile | **0.619 years** |
| 10th / 90th percentile | 0.146 / 5.4 years |
| share of land value dearer than the baseline | **64.8%** |
| land value given no ratio, drawn grey | **20.2%** |
| land value the map found nothing at all on | **0.03%** |

Those are printed by `make_us_cartogram.py` on every build, from the same
arrays the colour scale is set from. They read differently from an earlier
draft of this table, which quoted a median of 0.99 years and a 90th percentile
of 77.6, because that draft was measured over *all* ground rather than the
coloured ground: the enormous ratios were rural squares whose output was a
county figure spread by land cover, which the map no longer claims to know and
no longer draws. Restricting to ground with a workplace on it cuts the 90th
percentile from 77.6 years to 5.4 — a good measure of how much of the old
spread was the allocator rather than the country.

Two things fall out of it.

**The median dollar of coloured American land value sits on ground worth 0.62
years of its own output, against a national average of 0.40.** The aggregate is
dragged down by a handful of central business districts producing enormous
output on small footprints; the typical piece of valuable ground is nothing
like the aggregate. Sixty-three per cent of land value is dearer than the
average implies.

**The ratio climbs steadily with distance from downtown.** Pooling the twelve
largest downtowns and banding every square by how far it sits from the nearest
of them:

| distance from a downtown | land | output/yr | years | vs U.S. |
| --- | ---: | ---: | ---: | ---: |
| 0–5 km | $123.5bn | $1,689bn | 0.07 | **1/5.6** |
| 5–15 km | $429.0bn | $1,734bn | 0.25 | 1/1.7 |
| 15–30 km | $802.7bn | $2,746bn | 0.29 | 1/1.4 |
| 30–50 km | $801.5bn | $2,147bn | 0.37 | 1/1.1 |
| 50–80 km | $671.0bn | $1,523bn | 0.44 | **1.1×** |

A factor of 6.0 from the core to the edge, and the same direction in 12 of the
12 metros taken one at a time. Note what this does *not* say: the suburban ring
is close to the national figure, not far above it. The brown in the ring is the
residential squares within it, not the ring as a whole — an earlier draft of
this doc said the ring "costs far more than the output produced there", which
the banding does not support.

What is true is the gradient, and it survives the objection that used to be
fatal to it. Housing is no longer missing from the denominator: the rent on
every dwelling in every ring is counted on the ground the dwelling stands on,
and the gradient only fell from 6.4 to 6.0. The suburb still costs more years
than it earns, because what a house earns in a year is small beside what work
earns on the same square foot downtown.

### The same thing undeformed

`docs/figures/land_vs_output_map_us.html`, built as
`make_us_cartogram.py usratioflat`.

A ratio is an attribute of a place, not a quantity to be summed, so there is
nothing for a cartogram to encode in area — deforming space only gets in the
way of seeing where the ratio is high and where it is low. The flat version
draws the same 533,958 tiles on the ground they actually occupy, with the same
colours. No flow is run at all, so there is no accuracy question: the script
says so instead of printing a check.

It is the more useful of the two. The core-and-ring signature is far more
legible undeformed, and it is visible in every metropolitan area in the country
at once.

**How much of it is the county rule showing through.** Every rate in the
allocation — output per job, per resident, per farmed hectare — is constant
inside a county by construction, so a large smooth patch in the ratio could be
a county rather than real geography. `src/land/us_land_vs_gdp.py` prints two
readings of that on every build, so it cannot quietly get worse. First, the
variance of log(land ÷ output) split between and within counties:

| | between counties | within counties | share of land value |
| --- | ---: | ---: | ---: |
| tiles with workplace output | 25.4% | **74.6%** | 77.8% |
| tiles with none | **73.3%** | 26.7% | 20.0% |
| all tiles | 57.6% | 42.4% | 97.8% |

Second, the seam. A raw ratio of the step across a county line to the step
inside one cannot be read on its own, because county lines follow rivers and
ridges: a field that has never heard of counties still steps at them. So it is
measured twice, once against a placebo where the county map is rolled a
county's width sideways — keeping the shape of the boundaries and destroying
their placement — and once on the land surface, which has no county rule in it
at all and is therefore the floor:

| | real | placebo | excess |
| --- | ---: | ---: | ---: |
| the land surface alone | 1.31 | 1.06 | **1.24** |
| the ratio | 1.52 | 1.20 | **1.27** |

The ratio's county edges are no sharper, relative to their own placebo, than
those of the land surface it is built from. Whatever county structure the map
shows, the allocation is barely adding to it. Both rows read higher than they
did when the map excluded all public land; that is the federal rangeland now
back on the page, where the 480 m land surface itself steps hard at boundaries.
The comparison between the rows, which is the thing being tested, is unchanged.

**That table is the reason the map now stops where it does.** On ground that
has a workplace on it — 77.8% of American land value — three quarters of the
structure is within-county, coming from the 480 m land surface and from where
the jobs actually sit. That ground gets a colour.

On ground with no workplace, 73% of the structure is the county figure showing
through, because the only things varying inside the county are where the people
are and what the land cover is; the *rate* is a county constant. Drawn per
square it produced county rectangles, and no amount of work on the allocator
removed them: the county farm multiplier — a county's farm output over what its
land cover predicts — spans 21× from the tenth to the ninetieth percentile, and
splitting BEA's line 3 into crops and livestock by NASS county sales made it
worse, 21× to 27×, because crop output per acre is even less predictable from
land cover than the total.

So that ground is not given a ratio at all. It is drawn in one flat grey, and
the legend says what the grey means: no workplace here, so the output is known
only by county. It is 316,128 tiles and 20.2% of the land value on the page. The wells cut it: 5,753 tiles that had no workplace at all now have one, which is the Permian getting a ratio instead of a flat grey.
That share nearly doubled when the map stopped treating all public land as
unpriceable and narrowed the white to national parks and military bases: the
ordinary federal rangeland that came back onto the page is the least resolvable
ground in the country, so almost all of it arrived in the grey.
The alternative — smoothing the county rates across their boundaries, which is
arguably more accurate since a county line is not an economic discontinuity in
farming — was rejected because it would have broken the exact reconciliation to
BEA that the rest of this document rests on.

One measurement did not survive that decision, and it is worth recording why. A
seam ratio compares *neighbouring* squares, and the tile-to-tile noise on rural
ground is 60%, so a coherent county-wide offset of 2× vanishes into the median
while being perfectly obvious to the eye, which integrates over the region. The
seam test below reads near 1.0 throughout and was reassuring about a map that
was visibly made of rectangles. The between-county variance is the number that
was telling the truth. On an earlier version of this map, before housing and agriculture were
placed, the same decomposition over the 202,397 tiles that then had output came
out 10.2% between and 89.8% within.

Some of that between-county variance is real and measured: Cuming County,
Nebraska genuinely produces $615m of farm value added on 135,000 hectares of
feedlot country, and a sagebrush county three hundred miles west produces a
thousandth of that per hectare. The part that was *not* real — a single year of
net farm income, and treating range as though it were cropland — is what the
five-year average and the fitted crop weight took out.

## The scrolled version

`docs/figures/land_vs_output_story_us.html`, built as
`src/land/make_us_story.py`.

The same flat map, with a camera flown over it: twelve stops, each one a card
of text and a frame. It draws from the same buffers and the same colour scale
as the figure above — both call `_scene()` in `make_us_cartogram.py`, so the
two cannot end up showing different maps.

**Every number in the prose is computed at build time from the tiles.** Nothing
in the text is typed by hand: the script sums a box, formats the sentence around
the result, and draws the rectangle it summed on the map, snapped to the tile
grid, so the reader can see exactly which ground a claim is about. `?stop=N`
freezes the page on one stop, which is how the stills are made; `#sN` links to
one.

The stops were picked by mining the tiles for extremes and then re-checking each
candidate at neighbourhood scale, which killed several of them. A single square
at Walt Disney World reads as 3.7× the national figure and its 27 km
neighbourhood reads as 0.5×; the square happened to fall on undeveloped land.
Jackson, Wyoming looked like the most surprising teal in the country at
one square and is 1.1× across nine. Nothing that failed that check is in the
story.

Three of the twelve stops exist to show where the map is weakest — the Permian
allocation, which is the one industry still placed by jobs alone; the federal
land the model prices although no one could sell it; and Indiana, where
the land surface has no urban premium.

Two of the stops are worth repeating here:

**The two most valuable squares in America are next to each other and 7× apart
in ratio.** Midtown Manhattan holds $17.65bn of land; the next square east,
across the East River in Long Island City, holds $17.87bn — slightly more.
Midtown produces $418.8bn a year and Long Island City $56.8bn, so the same
price of ground comes out at 15 days against 115. Two squares south the pattern
repeats between the Village and Williamsburg, 19× apart on land within 4% of
the same value.

**The largest brown mass in the country is found, not asserted.** Join every
touching square above four years and weigh the clumps by land value: the
heaviest is the South Fork of Long Island, 53 squares holding $49.6bn of land
and producing $3.2bn a year — 15.3 years, 37.3× the national figure. The
runner-up, the Connecticut shore, holds $24.3bn. If either surface is rebuilt
the answer is recomputed rather than left stale.

## Indiana, and one thing the land surface does not do

A deep teal blob over north-east Indiana on the flat map turned out, on
inspection, to be a defect rather than a finding. It is Fort Wayne, with a
second one over South Bend and Elkhart. Three tests, all in
`src/land/land_model_gaps.py`, which writes `data/land/land_model_gaps.csv`:

**Fort Wayne's output is unremarkable; its land is the outlier.** Over a 27 km
box its output density, $34.6m per km², sits mid-pack among Midwestern metros
of similar size — below Toledo, Dayton and Grand Rapids. Its land density,
$0.81m per km², is 6–14× below every one of them, and *below the Indiana state
average of $1.04m*. A metro of 400,000 people priced below its own state's
average is backwards.

**It is not a state-level discount.** A rural transect across the Indiana/Ohio
line at latitude 41.00 shows no step at all: the Indiana side averages $0.826m
per km² and the Ohio side $0.789m, a ratio of 1.05. Rural Indiana is priced
exactly like rural Ohio. What is missing is not a level, it is the *urban
premium*.

**Matched by land use, Indiana's industrial ground prices about an eighth of
its peers.** Ten heavy-industry districts across seven states, all steel or
auto plants on river or lake ground:

| | | $m per km² |
| --- | --- | ---: |
| Gary, Indiana (US Steel) | IN | **0.85** |
| Burns Harbor, Indiana | IN | **1.52** |
| Weirton, West Virginia | WV | 1.84 |
| East Chicago, Indiana | IN | **2.44** |
| Granite City, Illinois | IL | 3.62 |
| South Works, Chicago | IL | 5.60 |
| Dearborn, Michigan (the Rouge) | MI | 6.96 |
| Middletown, Ohio (AK Steel) | OH | 7.65 |
| Sparrows Point, Maryland | MD | 10.21 |
| Cleveland, Ohio (the Flats) | OH | 10.73 |

Gary is 8.2× below the non-Indiana median; Fort Wayne is 15.2× below the median
of its peer metros. Statewide, Indiana's land surface is the least peaked of any
state with a metropolitan hierarchy — a 99.9th-percentile-over-median of 11.8,
against 32.6 for Ohio, 32.0 for Michigan and 112.4 for Illinois.

**What this does to the map.** Every Indiana tile reads as cheaper ground, and
so as more teal, than it should. Non-Indiana heavy industry lands at 0.06–0.13
years; Gary's 0.01 is the artefact, not the industry. Scaled to its peers'
prices Gary would run near 0.10 years — still teal, and unremarkably so.

This does not show the Nolte surface is wrong in general: its rural values agree
across the border test, and the paper reports its own out-of-sample accuracy.
What it shows is a place where a reader should not draw a conclusion, which is
worth knowing about a map that otherwise invites drawing them everywhere.

## Why there is no 480 m version

The land-value map has metro cuts at the source's native 480 m. **The GDP map
does not, and the reason is worth stating rather than hiding.**

LODES gives each census block a single centroid. At 3.84 km a tile is much
larger than an urban census block, so binning by centroid is a mild
approximation. At 480 m it is not: one 480 m cell in Midtown Manhattan comes
out holding **$40.4 billion** — 1.4% of the entire New York window's output —
because that is where LODES puts the jobs of a handful of very large office
blocks. A contiguous cartogram cannot place a point mass. The diffusion pushes
everything away from it and the figure becomes one enormous smooth disc
surrounded by wreckage; the accuracy check on the attempt read median |error|
58.7% against 4.1% for the land map at the same resolution.

That failure was informative in two ways:

1. **Relaxation is not universally good.** Feeding the deformed map back in as
   the new density improves the land field over three passes and makes the
   output field steadily *worse* (50.5% → 59.0% → 66.1%). Land prices vary
   smoothly; output stands in point masses, and a map full of collapsed tiles
   is a bad density to re-diffuse. The GDP cut therefore runs **one pass** and
   the land cuts run three — a per-cut setting, not a global one.
2. **The resolution ceiling is set by the data, not the renderer.** For land
   value the ceiling is 480 m because that is Nolte's grid. For GDP it is the
   size of a census block, which in a downtown is finer than 480 m in *area*
   but is delivered as a point.

## What the flow does, and whether it worked

Same machinery as the land maps: Gastner–Newman diffusion, EPSG:5070 Albers,
uniform tiles, WebGL rendering. One difference. Some American ground has nothing
recorded on it at all — at 3.84 km, **4,131 of 533,958 land tiles**, down from
331,561 before housing and agriculture were placed. Those tiles stay in the mesh
so the sheet does not tear, held at a floor density equal to the 1st percentile
of the occupied tiles, and are **not drawn**. The floor absorbs a fraction of a
percent of the page and the script reports exactly how much.

| cut | tiles drawn | median \|error\| | top 2,000 tiles | value-weighted mean | correlation |
| --- | ---: | ---: | ---: | ---: | ---: |
| `usgdp` (3.84 km), by sector, with facilities | 530,601 | 93.7% | **32.7%** | **61.6%** | **0.919** |
| `usgdp`, all jobs at one county rate | 529,991 | 90.6% | 31.6% | 59.7% | 0.927 |
| `usgdp`, before the housing and farm split | 202,399 | 96.3% | 35.0% | 61.2% | 0.923 |
| `us` land (3.84 km), for comparison | 533,958 | 6.9% | 4.2% | 13.9% | 0.950 |

**The sector split made this table slightly worse, and that is not a mistake in
either the split or the table — it is the table measuring something else.**
These numbers describe how well the diffusion solver equalised the density it
was given, not how well the output was placed. Giving each industry its own
rate makes the input surface *more* concentrated: a refinery block that used to
carry a county-average rate now carries eight times one. A spikier field is
harder to equalise, so the solver's residual rises. Nothing here can measure
whether the refinery's output is now on the refinery, because there is no
finer-than-county measurement to check it against — which is the reason the
allocation exists in the first place. The checks that *can* be run were: every
county reconciles to BEA at 100.0000%, and LODES matches QCEW at 1.03.

**Read that table before reading the figure.** The GDP cartogram is
qualitatively right and quantitatively weak. The metros land where they should,
their relative sizes are broadly correct, and drawn area tracks output at a
correlation of 0.93 — but the typical tile is drawn at roughly twice the size it
should be or half of it, against 7% for the same lattice carrying land value.

The median got worse when the map was filled in and everything that is weighted
by money got better. That is the arithmetic of adding 327,592 mostly rural tiles
carrying small amounts: the new tiles are hard to size and there are a great
many of them, so they dominate an unweighted median, while the tiles that hold
the output are placed slightly better than before.

The cause of the weakness is the same one that killed the 480 m version, only
milder: output is too spiky for a contiguous cartogram. Land value is a smooth
field over the whole surface; output is a scatter of point masses. Diffusion is a smoothing process, and asking it to open a hole of one
particular size around each of two hundred thousand spikes is asking more than
it can do.

### Blurring the density does not help

The obvious suspect was resolution: the diffusion is solved spectrally, and a
spike narrower than a grid cell is barely present in the cosine modes, so the
velocity field around it is too weak to open the hole it needs. The standard
remedy is the Gaussian smoothing the method already applies before diffusing
(`blur` in `src/land/cartogram.py`, 0.8 grid cells everywhere here). A solver
cell is 1.30 km against a 3.84 km tile, and a LODES block centroid sits at an
arbitrary point inside its tile, so smearing by roughly one tile width is
arguably undoing an artefact rather than adding one.

It was worth testing and it failed. One pass each, everything else held fixed.
These runs predate the housing and farm split, so they are on the 202,399-tile
version; the conclusion is about the solver, not about the allocation:

| blur (cells) | km | median | 90th pct | value-weighted | correlation | top 2,000 |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **0.8** (shipped) | 1.04 | **96.3%** | 2454.7% | **61.2%** | **0.9230** | **35.0%** |
| 2.0 | 2.60 | 97.5% | 2086.9% | 64.8% | 0.8136 | 42.3% |
| 4.0 | 5.21 | 219.4% | 2816.5% | 79.4% | 0.6209 | 51.8% |
| 8.0 | 10.42 | 410.4% | 4564.7% | 94.0% | 0.4594 | 63.0% |

Monotonically worse on every measure that matters, and the setting already in
use is the best of them. The one number that improves at blur 2.0 is the 90th
percentile, and that is the tail being flattened by smearing rather than placed
correctly — which is exactly what the collapsing correlation says: 0.92 to 0.46
is drawn area coming loose from output. Blur buys a tidier tail by moving value
between tiles that genuinely differ, which is a worse failure than the one it
fixes.

The lesson is not about a parameter. Diffusion is a smoothing operator, and no
amount of tuning makes a smoothing operator good at opening two hundred
thousand holes of precisely specified size. If this map needs to be
quantitatively right rather than indicative, the fix is a different instrument:
coarser tiles, where the range the flow must span is smaller, or a
non-contiguous form (Dorling or Olson), which achieves exact areas by giving up
the contiguity constraint that is doing all the damage here.

So use the figure for shape and the tables for numbers. Everything in the two
sections above comes straight from the tile data and is exact; only the drawing
is approximate.

## Files

| path | what |
| --- | --- |
| `src/land/build_us_gdp.py` | fetches BEA and LODES, allocates, writes the block file |
| `src/land/make_us_cartogram.py` | draws it (`usgdp`), sharing everything with the land cuts |
| `src/land/us_land_vs_gdp.py` | the two surfaces divided by each other |
| `src/land/ratio_examples.py` | the named worked examples, read off the tiles |
| `src/land/make_us_story.py` | the scrolled version, twelve stops, numbers computed |
| `src/land/land_model_gaps.py` | the Indiana test: peakedness, border transect, matched industry |
| `data/land/us_gdp_points.npz` | 9.3M points: Albers coordinates, carrier weight, kind (job block / population cell / farmland cell), allocated GDP |
| `data/land/us_farmland_cells.npz` | 2.0M cells of 1.92 km: cropland and pasture hectares, county |
| `data/land/us_gdp_county_check.csv` | every BEA area: measured GDP, jobs found, GDP allocated back, whether it matched a county |
| `data/land/us_gdp_lodes_vintage.csv` | which LODES year each state contributed |
| `data/land/us_land_vs_gdp.csv.gz` | 519,061 tiles with both quantities and the ratio |
| `data/land/us_land_vs_gdp_examples.csv` | the squares quoted above, with the flagged one marked |
| `data/land/land_model_gaps.csv` | the three tests behind the Indiana section |

## Reproducing

```bash
python3 src/land/build_us_gdp.py && python3 src/land/make_us_cartogram.py usgdp && python3 src/land/us_land_vs_gdp.py && python3 src/land/ratio_examples.py && python3 src/land/make_us_story.py
```

`build_us_gdp.py` pulls about 190 MB of LODES files, two per state, and reuses
them on a rerun. The BEA table comes from `src/land/fetch_inputs.py`.

## Sources

- U.S. Bureau of Economic Analysis, *GDP by County, Metro, and Other Areas*,
  table CAGDP2, "All industry total", 2023.
- U.S. Census Bureau, Longitudinal Employer-Household Dynamics,
  *LEHD Origin-Destination Employment Statistics* (LODES8), Workplace Area
  Characteristics, segment S000, job type JT00, with the geography crosswalk.
- U.S. Department of Agriculture / Nolte (2020) — see
  [the land-value map](us-land-value-cartogram.md) for the other surface.
- Michael T. Gastner and M. E. J. Newman, "Diffusion-based method for producing
  density-equalizing maps", *PNAS* 101:20 (2004), 7499–7504.
