# American land, drawn at its price

The [global land-value cartogram](land-value-cartogram.md) has to model urban
land from GDP, because no global measurement of urban land value exists. The
United States is the one large country where that compromise is unnecessary,
and this is what the map looks like when you do not have to make it up.

Three figures, all built by `src/land/make_us_cartogram.py`:

| figure | tile | tiles | what it covers |
| --- | --- | --- | --- |
| `docs/figures/land_value_cartogram_us.html` | 3.84 km | 533,958 | the conterminous United States |
| `docs/figures/land_value_cartogram_nyc.html` | 480 m | 148,854 | 220 km around New York |
| `docs/figures/land_value_cartogram_bay.html` | 480 m | 145,267 | 220 km around San Francisco |

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
| `nyc` (480 m) | 4.1% | 0.8% | 3.4% | 0.972 |
| `bay` (480 m) | 2.9% | 1.0% | 3.1% | 0.9995 |

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
| `src/land/make_us_cartogram.py` | all three cuts |
| `src/land/parcel_feasibility.py` | the coverage study below |
| `data/land/us_cartogram_check_<cut>.csv.gz` | every tile: grid position, value, price per km², and its share of the drawing (which should equal its share of the value) |
| `data/land/parcel_feasibility.csv` | 29 countries, their best available land valuation, and whether the link still answers |
| `data/land/inputs/places_fmv/` | the two source rasters, unmodified |

## Reproducing

```bash
python3 src/land/make_us_cartogram.py us && python3 src/land/make_us_cartogram.py nyc && python3 src/land/make_us_cartogram.py bay && python3 src/land/parcel_feasibility.py
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
