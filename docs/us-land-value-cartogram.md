# American land, drawn at its price

The [global land-value cartogram](land-value-cartogram.md) has to model urban
land from GDP, because no global measurement of urban land value exists. The
United States is the one large country where that compromise is unnecessary,
and this is what the map looks like when you do not have to make it up.

Twenty-one figures, all built by `src/land/make_us_cartogram.py`:

| figure | tile | tiles | what it covers |
| --- | --- | --- | --- |
| `docs/figures/land_value_cartogram_us.html` | 3.84 km | 533,958 | the conterminous United States |
| `docs/figures/land_value_cartogram_<metro>.html` | 480 m | 28k&ndash;307k | one metropolitan area, cut to its Census boundary |

The metro cuts are not written out one by one. A cut is derived from the metro
itself — its name gives the file name, its Census boundary gives the shape —
so every metropolitan area the map names has one, and `CUT_N` decides how many
are built for the site. All of them are, which is **81**: the Census
delineates 82 over the population floor, and Honolulu is not on the
conterminous lattice, so it has no tiles to draw and is not offered.

That last exclusion is tested against the lattice rather than against a list
of states, so Anchorage or San Juan would fall out the same way if the floor
ever reached them.

A metropolitan area is not a square, so a cut is not one either. The boundary
is rasterised onto the same 480 m lattice the tiles are cut from, and a tile
is in or out by where its own centre falls; the state lines, the water and the
town labels are selected against the same boundary. That is what keeps
Washington, Philadelphia and Harrisburg off a map of Baltimore. It also means
the cut holds the metro and only the metro: the San Francisco cut is the
five-county San Francisco&ndash;Oakland&ndash;Fremont MSA, and San Jose, which
is a metropolitan area in its own right, is not in it.

Every tile is the same patch of ground. What varies is what the ground is
worth, and a density-equalising cartogram then gives each tile an area equal to
its share of the money. The tile that swells is the expensive one.

There is a companion map of **GDP** on the same lattice —
[`docs/us-gdp-cartogram.md`](us-gdp-cartogram.md) — and the two can be divided
by each other, because they are cut from the same tiles.

## The source

Christoph Nolte trained tree-based ensembles on six million arm's-length land
sales and published fair-market-value estimates for every 480 m cell of the
conterminous US ([Nolte 2020](https://doi.org/10.1073/pnas.2012865117); data
CC-0). Nothing else at national extent comes close to it. Two rasters are
released: one fitted to all sales, one fitted only to sales of vacant land.
The maps here use the **vacant** model, because it prices the dirt rather than
the dirt plus whatever is standing on it, which is the same thing the national
accounts mean by land (SNA asset AN.211).

The raster stores the natural log of value per hectare, so it has to be
exponentiated before anything is summed — adding the stored values would
silently compute a geometric mean.

Totals over the conterminous states:

| | |
| --- | --- |
| vacant-sales model (used here) | **$11.26 tn** |
| all-sales model | $19.09 tn |
| this repository's modelled US figure | $41.31 tn |

## How concentrated it is

Sorting all 33.7 million 480 m cells by value:

| the most expensive… | …is this much ground | …and holds this much of US land value |
| --- | --- | --- |
| 10,000 cells | 2,300 km² | 6.4% |
| 100,000 cells | 23,000 km² (0.29% of the country) | 23.0% |
| 1,000,000 cells | 230,000 km² (2.9%) | 53.3% |

Half the land value of the United States sits on three per cent of its
surface. That single sentence is the map.

## Two numbers that do not agree

The median 480 m cell prices at **$0.46 per m²**, which is $1,860 an acre —
farmland, and in the right neighbourhood: USDA put the 2020 average US farm
real estate value at **$3,160 an acre**, cropland at $4,100 and pasture at
$1,400 ([Land Values 2020
Summary](https://www.nass.usda.gov/Publications/Todays_Reports/reports/land0820.pdf)).

The World Bank's *Changing Wealth of Nations*, the source behind the farmland
half of the global map, values **all** US agricultural land at **$182 billion**
in 2020 — $83bn cropland, $100bn pastureland. USDA's own total for US farmland
and buildings in 2019 was **$2,732 billion**. That is a factor of fifteen. The
gap is methodological rather than arithmetic — CWON capitalises resource rents
over a finite horizon rather than observing prices — but it means the global
map's American farmland is not a market value in the sense the rest of the map
implies, and that the US total in that map is essentially all modelled urban
land.

This is the same shape of problem as the [circularity
test](circularity-test.md) elsewhere in this repository: a published series
that looks like a measurement and is not one.

## Where the model runs out

The highest-priced 480 m cell in the country comes out at **$2,618 per m²**.
Manhattan land trades well above that. The distribution is compressed at the
top — which is what a tree ensemble does when the training data thins out — so
the cartogram *understates* the biggest cities rather than exaggerating them.
Whatever the map shows of New York and San Francisco is a floor.

The error is largest where sales are thinnest, which is the empty interior;
Nolte reports the out-of-sample accuracy by region in the paper.

## What the flow does, and whether it worked

Same machinery as the global map: Gastner–Newman diffusion (`src/land/cartogram.py`),
run in EPSG:5070 Albers, which is equal-area, so the input areas mean
something. Three relaxation passes — the deformed map is fed back in as the new
density each time, because one diffusion pass cannot span a density range of a
million to one.

Every figure prints its own check: each tile's drawn area against its share of
land value.

| cut | median \|error\| | top 2,000 tiles | value-weighted mean | correlation of area with value |
| --- | ---: | ---: | ---: | ---: |
| `us` (3.84 km) | 6.9% | 4.2% | 13.9% | 0.950 |
| `new-york` (480 m) | 4.6% | 0.9% | 3.4% | 0.9994 |
| `san-francisco` (480 m) | 2.9% | 1.2% | 2.9% | 0.9995 |
| `riverside` (480 m) | 1.6% | 0.8% | 3.1% | 0.9995 |

Across the twenty metro cuts the median tile error runs from 1.5% (Detroit) to
6.5% (Boston).

The metro cuts converge much better than the global grid map does, for the
obvious reason: within one metro the price range is a factor of a few hundred,
not a factor of ten million.

## Drawing half a million tiles

At this tile count SVG is not an option — 534,000 paths is tens of megabytes of
markup and a browser that will not scroll. The figures are WebGL: the mesh is
uploaded once as triangles, pan and zoom are a uniform, and the tile under the
cursor is identified by rendering a second pass in which every tile is painted
its own index as a colour and reading back a single pixel.

The file carries the *shared* lattice — one vertex per tile corner, quantised
to 16 bits over the drawing box, deflate-compressed and base64'd — and the
browser expands it to four vertices per tile at load, because each tile needs
its own colour and a shared vertex cannot carry two. That is the difference
between a 5 MB page and a 40 MB one.

Colour is continuous in log price per km², with the two ends set from the
**value-weighted** distribution of the tiles. Weighting matters: on a cartogram
a tile's share of the page *is* its share of value, so a scale set on the
unweighted distribution spends most of its range on tiles too small to see, and
the visible map comes out one flat colour. The first version of the New York
figure did exactly that.

## What is drawn over the tiles

Everything above the tiles rides the same flow they do, so a boundary lands
where the cartogram put the ground it encloses rather than where it sits on an
undeformed map. On a metro cut there are five such layers.

**State lines and water.** Water only on the metro cuts — the national map
would need a TIGER file per county for three thousand counties to draw rivers
a pixel wide. On a cartogram worthless ground is squeezed to almost nothing,
so the Hudson is a thin dark line, which is exactly what tells Manhattan from
Jersey City.

**Metro outlines**, behind a switch, dashed.

**City limits**, behind a second switch — and this one is not one kind of
object. In most of the country a municipality is an *incorporated place*, with
unincorporated county in between. In twenty states it is also, or instead, a
*county subdivision*: the towns of New England and New York, the townships of
New Jersey, Pennsylvania and the Midwest, which are general-purpose
governments covering every acre with no gaps. Drawing only places gave Nassau
County its villages and left out Hempstead, Oyster Bay, Islip, Babylon and
Brookhaven, which are towns and therefore not places at all.

Which units count is not a judgement made here. The Census records a
`FUNCSTAT` against every unit, and the layer reads it:

| flag | meaning | drawn |
| --- | --- | --- |
| `A` | active government | yes |
| `N`, `F`, `B` | a real government filed oddly — Washington, and the "(balance)" of a consolidated city-county | places only |
| `S` | statistical only — every CDP, and the survey townships of thirty states | no |
| `I` | inactive | no |

For subdivisions the test is `A` alone, and it reproduces the twenty
strong-MCD states from the data rather than from a list written here: it keeps
Pennsylvania's and Michigan's townships, which have budgets, and discards the
three thousand identically named townships of Iowa, Arkansas and North
Carolina, which are lines on a survey. For places `A` is too strict, and
quietly so — Washington is `N` because its government is filed against the
District, Indianapolis and Nashville are `F` — so a place is kept unless the
flag says statistical or inactive. That still admits not one CDP.

A boundary can then arrive twice: every New Jersey municipality is both a
place and a subdivision with one outline. A dedupe drops the duplicate on
geometry — symmetric difference under a hundredth of the area — and not on
name, which would keep Boston's town beside Boston's city and drop a
Springfield that shares a name with a township one county over.

**Neighbourhood names**, for the metro's own principal city, at a lighter
weight and never below 2.5×. There is no national dataset of American
neighbourhoods: the Census does not delineate them, and the cities that
publish their own do it in fifty formats. OpenStreetMap has them in one schema
nationwide, contributed by the people who live there. It is neither
authoritative nor evenly covered, and the page says so and carries the ODbL
attribution — for a landmark that is a fair source, for a number it would not
be. There being no population to rank them by, they are ranked by the thing
the map is about: the land value of the tile each name stands on, most expensive
first, which on a cartogram is also where a name has room.

The coverage is uneven in ways worth stating. Baltimore has 248 names against
18 city limits, because Baltimore County contains no incorporated place at
all. Miami has 11, because the city proper is small and Coral Gables, Hialeah
and Kendall are other municipalities — the rule that is right for New York
leaves that one cut thin.

### Price, or price per resident

The colour has a switch. By default it is land value per square kilometre of
real ground — a price. **Per resident** divides that by the people living on
the same tile, which asks a different question: not where the expensive
land is, but where the expensive land is carrying few people. A tower block and a golf
course can cost the same by the acre and differ a thousandfold by the head.
On Baltimore the price spans 45-fold across the page and the price per
resident spans 860-fold, so the two are not restatements of each other.

Nothing about the geometry changes — area is still land value — so the switch
rewrites one byte per tile through the same ramp rather than loading a second
map.

Ground with nobody on it is drawn grey, not expensive. A price per resident there
is a division by zero, and colouring it at the top of the scale would be a
claim about the emptiest land on the map. Each figure prints how many tiles
that is and what share of the page's land value they hold — on Baltimore,
2,369 tiles and 8.4%.

The people are counted, not modelled. The 2020 Census publishes population by
block, which is the finest unit it publishes for: the median occupied block is
**0.031 km², seven times smaller than a 480 m tile**. `build_us_population.py`
lays those counts on the shared lattice and reconciles to the person —
**329,260,619**, which is the published national count less Alaska and Hawaii,
both off this lattice.

Two thirds of occupied blocks are smaller than a 480 m cell and win no cell
centre of their own; their people go on the tile holding the block's interior
point, and the rest are spread evenly over the cells they cover. The build
reports the split, because "spread over its cells" and "dropped on one tile"
are different claims about where somebody lives.

This replaces GHS-POP at 30 arc-seconds for this purpose. That grid is about
800 m — finer than the 3.84 km national tile and *coarser than the 480 m tile
of a metro cut*, which is the scale at which the question is interesting.

### Checking the city limits

`audit_municipal.py` runs the boundary layer against all 81 metros and prints
what it finds. It asks the questions a wrong answer shows up in: does every
metro have a boundary at all; does its own principal city have one, since that
is the row a cut searches to find the city whose neighbourhoods it names; do
the strong-MCD states draw subdivisions **and the other thirty not**; and how
much of each metro's land and people sit inside a municipality.

All four checks pass across 81 metros — 5,198 incorporated places and 2,651
towns and townships in total, with 52 of the 81 metros drawing no subdivision
at all, which is exactly the thirty states where subdivisions do not govern.

The coverage figures are the layer's own evidence. Every metro that reaches
100% of land *and* 100% of people is in a strong-MCD state, because
subdivisions tile a county with no gaps — Dayton, South Bend, Milwaukee,
Bridgeport. The median metro is 20% of land and 79% of people. The bottom is
not a defect either: Richmond, Baltimore and Washington run at 3–5% of land
and 24–27% of people, because their counties are largely unincorporated. That
gap between land and people is the fact — American metros are mostly
unincorporated ground with the population concentrated in the incorporated
part.

### When a name appears

Room on a page is an area, so the count that fits grows with the square of the
zoom and the i-th name's turn comes at `sqrt(i / 60)`. Rank alone is not
enough, though: a name is unreadable with another name sitting on it, however
high its rank, so each also waits until it has come clear of the names around
it. That test is run on the *drawn* positions, after the flow — a cartogram
pulls Oakland away from San Francisco, so on that map the two separate earlier
than on a flat one, and the rule follows the map instead of second-guessing
it.

The test is the drawn box. It used to be a 40-unit circle around the anchor,
which is the wrong shape for a word: "South Farmingdale" is two hundred units
wide and fourteen tall, so a circle that cleared its height cleared a fifth of
its width, and on Long Island the names ran into each other. Two boxes come
apart once the zoom has separated them on *either* axis, so what a pair needs
is the cheaper of the two separations.

Two things about that are easy to get wrong, and both were, and neither was
visible from reading the code:

- **Which pairs need testing.** A pair is on the page together at every zoom
  above the *later* of the two, so what must hold is that the later one is not
  below what the pair needs. Asking instead whether a neighbour is on the page
  *yet* skips every neighbour that appears later — which is how North Merrick
  came out at 1.95 against North Bellmore's 2.00 and the two were drawn on top
  of each other from 2.0 up.
- **That a gap is two things.** The ground between two anchors is map and
  grows with the zoom; the offset that lifts a name above its dot is drawn at
  a constant size on screen and so *shrinks*. Adding them makes separation a
  straight line in zoom when it is really a V — two names can be apart,
  converge, and collide again further in. That is SoHo under New York from
  4.9× up.

Counting overlapping rectangles on the New York cut at sixteen zooms from 1×
to 300×: no overlapping pair at any of them, against nine at 3× before. It
costs nothing — 719 names still stand at full zoom, the same as before. The
rule delays a name; it does not drop it.

## What this cannot tell you

- The values are **model predictions, not transactions**.
- They are **land only** — a city block is priced as the dirt under the
  building, not the building.
- The source stops at the conterminous states: **no Alaska, no Hawaii**.
- The estimates are for a **hypothetical arm's-length sale** of every parcel at
  once, which is not a thing that could happen.
- A cartogram equalises density **approximately**; the table above is the
  honest version of how approximately.

## Could this be done for the rest of the world?

`src/land/parcel_feasibility.py` sorts countries by what a stranger can
actually obtain, and weights them by this repository's own estimate of world
land value. The tier is about **access**, not about whether a valuation
exists: almost every country with a property tax values land, and the ones in
`none` simply keep it inside the tax administration.

| tier | what it means | countries | share of world land value |
| --- | --- | ---: | ---: |
| `parcel` | an official value for individual parcels, published or queryable | 9 | **13.5%** |
| `zone` | official land values for price zones, reference points or street frontages, but not per parcel | 8 | **15.8%** |
| `sales` | no official surface, but open transaction microdata with enough location to train a model — the American recipe | 12 | **51.6%** |
| `none` | nothing public at national scale | 181 | **19.1%** |

Read that as: a US-style map is buildable today from published valuations over
**29% of world land value**, and over **81%** if transactions are modelled the
way Nolte modelled the United States. Every source URL is re-checked when the
script runs and the HTTP status is written into
`data/land/parcel_feasibility.csv`, so a link that has rotted is visible rather
than implied.

Some of what that hides:

- **The `sales` tier is two countries.** The United States (20.6%) and China
  (20.5%) are four-fifths of it. China's share is open in an unexpected way:
  every state land grant is published individually, with area and price, on the
  national land-market site. It is not a valuation roll, but it is millions of
  priced transactions.
- **The best data is in small countries.** Korea publishes an official land
  price for *every parcel*, annually, as shapefiles. Denmark, Lithuania and New
  Zealand are comparable. Together they are under 3% of world land value.
- **Japan is the largest genuinely fine-grained country** at 5.1%: the
  *rosenka* system assigns a land value to every street frontage in the
  country, which is closer to parcel level than anything the US has.
- **India (6.0%) is the biggest zone-tier country and the hardest.** Circle
  rates and guidance values are fine-grained and legally published, but state
  by state, in incompatible formats, mostly as HTML tables behind form posts.
- **Germany's Bodenrichtwerte (3.8%) are the model everyone should copy**: an
  official land value per price zone, nationwide, free, under an open licence.
- **The `none` tier is 181 countries and a fifth of the world's land value**,
  and it is almost all of Africa, Central Asia, the Middle East and most of
  Latin America.

Two hosts refused this network outright — Russia's public cadastral map and the
Indian state registry used as the example — which is recorded as status `0` in
the CSV. That is a fact about this network, not about those registries.

The honest summary: the obstacle is not modelling. The American map took one
researcher and six million sales. For four-fifths of the world's land value the
raw material exists in public; what is missing is the assembly. For the
remaining fifth, no amount of assembly helps.

## Files

| path | what |
| --- | --- |
| `src/land/make_us_cartogram.py` | the national map and every metro cut |
| `src/land/build_us_population.py` | census-block population on the shared lattice |
| `src/land/audit_municipal.py` | the city-limits layer, checked against all 81 metros |
| `src/land/publish_maps.py` | copies the built figures to the public site repository, all or none |
| `src/land/parcel_feasibility.py` | the coverage study below |
| `data/land/us_cartogram_check_<cut>.csv.gz` | every tile: grid position, value, price per km², and its share of the drawing (which should equal its share of the value) |
| `data/land/parcel_feasibility.csv` | 29 countries, their best available land valuation, and whether the link still answers |
| `data/land/inputs/places_fmv/` | the two source rasters, unmodified |
| `data/land/us_pop_480m.npy` | 329,260,619 residents on the 480 m lattice |

## Reproducing

```bash
python3 src/land/build_us_population.py             # once: 5.6 GB of blocks
python3 src/land/make_us_cartogram.py us
python3 src/land/make_us_cartogram.py new-york      # or any metro's slug
python3 src/land/audit_municipal.py                # check the city limits
python3 src/land/parcel_feasibility.py
```

The source raster is fetched by `src/land/fetch_inputs.py`. It is a 299 MB
zip; the copy on Zenodo is used rather than the one on Dryad, because Dryad now
sits behind a proof-of-work bot check that a script should not be trying to get
past.

The transported meshes are cached under `data/land/cache/` (gitignored), so
re-running only the drawing takes seconds.

## Sources

- Christoph Nolte, "High-resolution land value maps reveal underestimation of
  conservation costs in the United States", *PNAS* 117:47 (2020), 29577–29583.
  Data: [Zenodo 4073355](https://doi.org/10.5281/zenodo.4073355), CC-0.
- USDA National Agricultural Statistics Service, *Land Values 2020 Summary*,
  August 2020.
- World Bank, *The Changing Wealth of Nations 2024*, indicators
  `NW.NCA.CROP.TO.CD`, `NW.NCA.PAST.TO.CD`, `NW.NCA.AGRI.TO.CD`.
- U.S. Census Bureau, *Cartographic Boundary Files* 2023,
  `cb_2023_us_state_500k` — the state outlines and coastline, at 1:500,000.
  Public domain.
- Natural Earth, `ne_10m_populated_places`, and
  `ne_10m_admin_1_states_provinces` as the outline fallback. Public domain.
- Michael T. Gastner and M. E. J. Newman, "Diffusion-based method for producing
  density-equalizing maps", *PNAS* 101:20 (2004), 7499–7504.
