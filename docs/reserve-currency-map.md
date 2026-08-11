# The reserve currency map

A website, not a dataset: `site/` is a self-contained page showing where the
world's official reserves are held and what currency they are denominated in,
1960 to 2026. It is published to GitHub Pages by
`.github/workflows/pages.yml`.

This is the modern counterpart to the rest of the repository. The silver peso
was the reserve asset of the seventeenth century and its movement had to be
reconstructed from treasury books; the modern equivalent is measured
continuously by two institutions and published quarterly. The interesting thing
is that the modern record has a hole in exactly the place the colonial one does
— see *The join that does not exist* below.

## What is measured

| layer | source | side | what it gives | what it withholds |
|---|---|---|---|---|
| composition | IMF COFER | asset | share of world reserves by currency, quarterly | any country's own composition |
| holdings | World Bank `FI.RES.TOTL.CD`, `FI.RES.XGLD.CD` | asset | reserves per country per year, gold separable | what currency any of it is in |
| Treasury holdings | US Treasury TIC | asset of the holder, liability of the US | who holds US Treasuries, monthly | ownership behind the custodian |
| banking positions | BIS locational statistics | liability, net | which way obligations run, by currency | who the creditor country is |
| geometry | Natural Earth 1:50m | — | country outlines and centroids | — |

The **side** column is the distinction the site now states outright, because
without it the same country reads as two unrelated dots. The United States holds
$910bn of reserves and owes $9.27tn of Treasuries abroad and $3.96tn net to the
banking system. That asymmetry is not an oddity to be explained away — it is
what a reserve currency *is*. The issuer's money is everyone else's asset, so
the issuer is structurally the debtor.

## The join that does not exist

COFER is collected on the condition that no individual country is ever
identified. A handful of holders are large enough that a country breakdown
would amount to publishing their reserve managers' positions, so the IMF
publishes world and group aggregates only.

The consequence is strict and the site states it plainly: the map is **who
holds, never in what**, and the chart is **in what, never who**. There is no
published series joining them, and any map drawing arrows from issuers to
holders is inventing those arrows. The site draws none.

This is the same shape of problem as `docs/silver-routes.md`, where 46 of 47
district-to-hub edges are recorded by only one side of the transaction. In both
cases the temptation is to fill the gap with a plausible allocation rule. In
both cases the honest output is to name the gap.

## The flows page

`site/flows.html` answers the obvious follow-up — draw the lines between
countries — with the two datasets that can support a line, and it keeps them
apart because they mean different things.

### TIC: a real country pair on both ends

The US Treasury's International Capital reporting publishes foreign holdings of
US Treasury securities by country, monthly since March 2000. It is the only
bilateral reserve-asset series anyone publishes, and it carries two warnings
from Treasury's own footnotes:

- **Custody, not ownership.** Holdings are attributed to the country of the
  US-based custodian. Euroclear is in Belgium, which is why Belgium holds
  $477bn; Ireland, Luxembourg and the Caymans are fund domiciles. Treasury
  states the table "may not provide a precise accounting of individual country
  ownership".
- **Official and private are mixed.** Only the world total is split. It is
  currently 42% foreign official, so a country's line is not its central bank's
  reserves.

Coverage is not constant. Until 2016 Treasury published *Caribbean Banking
Centers* and *Oil Exporters* as groups instead of their members, so the share
of the total attributable to a named country runs from 71% at the low point to
96% today. The page prints that share under the map and it moves as you scrub.

### BIS: a net direction, not a country pair

BIS locational banking statistics give cross-border bank positions with each
counterparty country, split by the currency they are denominated in. That is the
mechanism that makes a currency a reserve currency — if your obligations are in
dollars you must hold dollars — but it is emphatically not a lender-to-borrower
matrix.

Both sides are published, so the view shows the **net**: claims on a country
minus liabilities to it. Positive means the country owes the international
banking system on balance and the arrow points at the country; negative means it
is owed and the arrow reverses. At 2026-Q1, 87 countries are net debtors and 94
net creditors.

| | claims | liabilities | net |
|---|---:|---:|---:|
| US dollar | $21.80tn | $19.52tn | +$2.28tn |
| Euro | $15.27tn | $13.91tn | +$1.36tn |
| Japanese yen | $2.26tn | $1.25tn | +$1.01tn |
| All currencies | $47.62tn | $41.99tn | +$5.64tn |

Netting is what makes the map readable, and it is also what makes it
incomplete — so both are on the page:

- **It cuts the financial centres down to size.** London carries $7.2tn of gross
  claims because it intermediates; the net position is a small fraction of that.
  On gross the United Kingdom ranks second in the world and means almost nothing
  by it.
- **It hides the balance sheet.** $2tn against $1.9tn and $150bn against $50bn
  both show as a $100bn arrow. Gross claims and gross liabilities are in the
  tooltip and the table for exactly this reason.
- **It is still not bilateral.** The public dataflow publishes `L_REP_CTY = 5A`
  only, the aggregate of all reporting countries, so this is a net position
  against the banking system *as a whole*. The arc begins at a currency's
  central bank and means **denominated in**, never **lent by**.

Available denominations are USD, EUR, JPY and an all-currency total; sterling
and the franc sit inside the total but are not published separately at this
level.

### Why there is no full net international investment position

The correctly-scoped net measure would be the IIP, and it is not obtainable at
world scale from these APIs. `IMF.STA:IIPCC` — IIP by currency composition, and
otherwise ideal for this subject — is reported by **22 countries**. `IMF.STA:BOP`
covers 213 countries but holds balance-of-payments *flows*; its indicator
codelist contains no position stocks. So the banking-system net above is the
widest honest net available, and it is labelled as what it is rather than as an
external balance sheet.

This matters because a naive substitute is badly wrong. Reserves held minus
cross-border bank claims owed puts **Japan at −$537bn**, reading as a net
debtor, when Japan is the largest net creditor nation on earth. Reserves are
only the official slice of a country's external assets and bank claims are only
part of its external debt; differencing two differently-scoped stocks produces a
confident number and misclassifies the biggest case in the data.

## What a circle is made of

Each country's circle has its area proportional to the reserves it holds and is
cut into the two parts the World Bank publishes separately: gold at market, and
everything else — foreign exchange, SDRs and the reserve position in the Fund.
The split is available for **every one of the 9,489 country-years** in the
extract, which is why it can be a wedge rather than a footnote.

It divides the map in a way the sizes do not:

| holder | reserves, 2024 | in gold |
|---|---:|---:|
| United States | $910bn | **75.0%** |
| Germany | $378bn | **74.4%** |
| France | $283bn | 72.3% |
| Portugal | $42bn | 75.7% |
| Russia | $608bn | 32.2% |
| India | $643bn | 11.4% |
| Switzerland | $909bn | 9.6% |
| Japan | $1,231bn | 5.8% |
| China | $3,456bn | **5.5%** |
| Korea | $418bn | **2.1%** |

The countries that accumulated reserves over the last thirty years hold other
people's money. The countries that ran the system before 1971 still hold metal,
and mostly the same metal — these are stocks that have barely moved since the
London Gold Pool closed.

Two things to keep straight about the wedge. **Gold is at market**, so a
country's gold slice grows when the gold price rises and it has not touched an
ounce; this is a value, never a quantity, and 2024 was a strong year for the
price. And **this is not the currency split** — that is the one thing COFER
will not give per country, and the section above is about why. Blue means
"not gold", not "dollars".

Colours are validated slots 1 and 4 of the project palette, blue against amber:
worst adjacent ΔE 29.6 under tritanopia, 31.5 under protanopia, against a
target of 8. The amber sits at 2.11:1 against the light surface, below the 3:1
line, which obliges relief — so the share is a number in the tooltip and a
column in the table as well as an angle on the map.

## The centre of gravity

The one figure here that is computed rather than reported. Each country is
treated as a point mass at its own centroid, weighted by the reserves it holds,
and the weighted mean is taken **on the sphere** — coordinates to unit vectors,
summed, renormalised — not by averaging degrees. Averaging longitude in degrees
places the mean of Tokyo and Los Angeles in Kazakhstan rather than the Pacific,
which would invert the result.

| year | centre | reporters | total held |
|---|---|---|---|
| 1960 | 62.4°N, 35.9°W — mid-Atlantic | 87 | $0.1tn |
| 1980 | 57.0°N, 3.0°W — the Channel | 127 | $1.0tn |
| 2000 | 59.3°N, 79.1°E — western Siberia | 169 | $2.1tn |
| 2014 | 49.0°N, 83.8°E — the Altai | 176 | $12.6tn |
| 2024 | 54.3°N, 73.9°E — western Siberia | 164 | $14.9tn |

The track moves 110° east between 1960 and 2024 and then, after 2014, comes back
west a little: China's reserves peaked at $4.0tn in 2014 and the rest of the
world kept accumulating.

The centroid is sensitive to which countries reported in a given year, so the
site marks any year whose panel is materially incomplete. 2025 is currently
partial — 124 of 182 reporters — and is flagged in the interface rather than
quietly plotted.

## The projection

All three maps are drawn looking straight down on the North Pole, in a Lambert
azimuthal equal-area projection. `site/assets/projection.js` is the whole of it,
shared by both pages so a country lands in the same place on each.

The reason is the subject. Every reserve currency except the Australian dollar
is issued north of the tropics, as is every one of the twenty largest holders,
and a rectangular map splits that single neighbourhood across two edges: Tokyo
and New York are the full width of the page apart on a Robinson map and near
neighbours on the globe. Two things fall out of moving the pole to the middle.
The centre-of-gravity track becomes what it physically is — 110° east is a
rotation about the pole, not a slide across a rectangle. And a great circle from
Tokyo to Washington is one short line over the Arctic instead of an arc that has
to leave one edge of the map and come back in the other.

Equal-area rather than equidistant because area is the property this map must
not lie about: a country covers its true share of the canvas, which is the same
reason the holdings map draws circles instead of colouring countries in. The
price is shape. It smears progressively outwards, and the rim of the disc is the
South Pole, one point opened out into a whole circle. Everything the data
contains falls inside 91% of that radius — New Zealand is the outermost thing on
the map — so the worst of it happens where there is nothing to see.

### East runs anticlockwise, and it is not a choice

Seen from above the North Pole the Earth turns anticlockwise — the angular
velocity vector points north, and rotation carries a point east — so with
Greenwich at the top, 90°E is at nine o'clock and the Americas are on the right.

Putting east clockwise instead reproduces the familiar left-to-right order of a
Mercator map, which is exactly why it is easy to ship by accident, and it
mirrors every coastline while doing it. The first version of this projection had
that bug. **Check any change to `project` against the NSIDC polar grid**, whose
standard layout with 45°W pointing down is Alaska left, Canada bottom-left,
Greenland bottom, Scandinavia right — the mirrored version puts all four on the
opposite side.

### The zoom is a camera, not a filter

A view in `VIEWS` sets `disc`, the radius of the whole globe in viewBox units,
and which meridian points up, and then frames a window on the result. The window
stays 430 units wide in every view and the stylesheet caps it at 820px, so one
unit is 1.9 pixels whichever view is showing.

That is the whole point. Zooming enlarges the geography and leaves every circle,
arc width and label at the size it was, because those encode values rather than
distances — a European circle stays comparable with the Chinese one now outside
the frame. Nothing is filtered: the readouts and tables under each map still
describe the world, and arcs still run to wherever they run, with the ends that
fall outside the window simply outside it. The legends say so when zoomed.

`lonUp` for a regional view is its central meridian minus 180, which puts the
region at the *bottom* of the enlarged disc. Down there the outward direction is
south and anticlockwise reads rightwards, so a regional view comes out the
normal way up with east to the right, without rotating anything — which matters,
because rotating a group would rotate the text with it.

Three more consequences worth knowing before editing any of this:

- **A segment that is straight in longitude and latitude is a curve here.** Two
  coastline points twenty degrees apart in longitude lie on an arc of a
  parallel, and joining them with a chord visibly cuts the corner. `projectRing`
  subdivides anything longer than 4° of longitude before projecting; north–south
  segments need no help, because meridians really are straight radial lines.
  The 4° threshold is set by the regional views, not the globe — at world scale
  the error is a fraction of a unit, and a zoom multiplies it by three and a
  half.
- **The flow arcs are sampled great circles, not curves between two projected
  points.** This is not decoration. A straight line drawn on this map from
  Washington to Canberra runs over Siberia. `geoLine` interpolates on the sphere
  and projects each sample, then pushes the path off the great circle by a small
  amount so that twenty lines converging on one point stay countable. Swapping
  the endpoints flips both the plane's normal and the sign of the bow, so
  `arcPath(a, b, 1)` and `arcPath(b, a, −1)` trace the same curve in opposite
  directions — which is how the net-direction arrowheads change ends without the
  line moving.
- **The basemap is 1:50m, and the tolerance is per ring.** 110m was chosen when
  the map did not zoom; at the Europe view its 0.30° simplification is a
  three-pixel error on every coastline, and it has no polygon at all for most
  of the small states. 50m simplified at `min(0.10°, span / 25)` is 397 KB, or
  131 KB once Pages gzips it, and keeps all 242 countries — a flat tolerance
  coarse enough to hit that size drops forty of them, Singapore and Malta and
  Luxembourg among them. Holes are kept too, so Lesotho is a hole in South
  Africa rather than something South Africa paints over; the page fills with
  `fill-rule: evenodd`, which needs no assumption about winding order.
  because it took half a cropped rectangle. Now it is dropped because its ring
  closes along the line of 90°S, and this projection stretches that line into the
  entire rim: the continent would be drawn as a disc covering the map. It holds
  no reserves and appears in none of the four datasets.

## Things that will be misread if not stated

- **Gold is at market value.** A country's gold line moves with the gold price
  whether or not it has traded. The gold measure is a value, never a quantity.
- **The euro band before 1999 is its predecessors** — DEM, FRF, NLG and ECU,
  which COFER identified separately until they were replaced. Stacking them into
  the euro band shows the continuity, but it is a construction and the seam is
  annotated on the chart.
- **Shares are of allocated reserves.** Before 2000 a large unallocated slice
  existed — countries that reported a total but no currency split — so early
  shares describe the reporting subset only. In December 2025 the IMF removed
  the unallocated portion entirely and revised back to 2000Q1, which is why the
  published series now accounts for 100%.
- **Two dataset changes look like events but are not.** The euro's appearance in
  1999Q1 and the renminbi's in 2016Q4 are changes in what COFER identifies, not
  moments when the currencies began or stopped being held. Both are annotated.

## Validation

Each script prints a report and exits non-zero rather than writing output that
fails. The checks that matter:

| check | result |
|---|---|
| COFER currency shares sum to 100% | worst period 100.000% |
| COFER values reproduce published shares independently | 800/800 rows |
| euro succeeds the legacy currencies | DEM ends 1998, EUR starts 1999 |
| gold residual (total − ex-gold) non-negative | 0 rows below −$1k |
| **country sum vs COFER world total FX** | **0.94–1.03 across 31 overlapping years** |
| every reporter placed on the map | 182 countries, 0 dropped |
| reserve centroid in range and moving | 130.6° of longitude |
| **TIC parts reproduce Treasury's printed Grand Total** | **worst month 1.0002, all 310 months** |
| TIC foreign official ⊆ total | 0 months violate |
| BIS named currencies ⊆ all-currency total | worst 102.0%, 3 of 15,893 past 100.5% |
| BIS net equals claims minus liabilities | 181 countries reconcile |
| net direction runs both ways | 87 net debtors, 94 net creditors |

34 checks in total. Two are worth keeping.

The World Bank's country-level reserves and the IMF's world total are compiled
by different institutions from different returns; that they agree within 6% in
every overlapping year is evidence that neither the country/aggregate filter nor
the gold split has gone wrong.

The TIC reconciliation is the other. Treasury prints a Grand Total that is not
derived from the parts this parser extracts, so summing every published line
back to it in all 310 months is a real check on the column assignment — and it
is what caught two bugs: the pre-2016 group rows (*Caribbean Banking Centers*,
*Oil Exporters*) which are part of the total but are not named countries, and
the series-break months where Treasury prints the same month twice, new
benchmark beside superseded estimate.

## Rebuilding

```bash
python src/reserves/fetch_cofer.py        # -> data/reserves/cofer_currency_shares.csv
python src/reserves/fetch_wb_reserves.py  # -> data/reserves/reserves_by_country.csv
python src/reserves/fetch_tic.py          # -> data/reserves/tic_treasury_holders.csv
python src/reserves/fetch_bis.py          # -> data/reserves/bis_claims_by_currency.csv
python src/reserves/build_geometry.py     # -> site/data/world.json
python src/reserves/build_site_data.py    # -> site/data/holders.json, cofer.json
python src/reserves/build_flows_data.py   # -> site/data/flows.json
```

Order matters three times: `fetch_wb_reserves.py` cross-checks itself against
the COFER extract, `build_site_data.py` needs the geometry for its centroids,
and `build_flows_data.py` needs both of those — it takes country positions from
`holders.json` and the basemap so the two pages place a country identically,
and the ISO2-to-ISO3 join for BIS from the World Bank extract.

Serve it locally with `python3 -m http.server 8817 --directory site` — the page
fetches three JSON files and will not run from `file://`.

### Notes for whoever runs this next

- **`api.imf.org/external/sdmx/2.1` is the endpoint that works.** The legacy
  `dataservices.imf.org` service is dead, `sdmxcentral.imf.org` does not carry
  COFER, and the SDMX 3.0 `/data/dataflow/...` form hangs. The whole dataset is
  270 KB; fetch it with an empty key rather than constructing series keys.
- **Python on this machine cannot verify TLS** against either API — the
  miniforge default context does not pick up certifi. `src/reserves/common.py`
  builds a context from certifi and falls back to `curl`.
- **The World Bank API times out on large pages.** `per_page=2000` with
  pagination works; `per_page=25000` in one request does not.
- **A country with no polygon still has to be placed.** At 110m, 25 reporters
  had none, including Singapore ($432bn) and Hong Kong; at 50m with the
  per-ring tolerance it is down to one, Kosovo, which Natural Earth files
  without an ISO code. They are placed from the World Bank's own capital
  coordinates and carry a `shape: 0` flag. Dropping them would have quietly
  removed a major holder from the map and biased the centroid west.
- **Bermuda holds $101bn of Treasuries and reports no official reserves**, so it
  is in neither gazetteer. `build_flows_data.py` fetches the one missing
  coordinate from the World Bank country endpoint rather than having it typed
  in.
- **The TIC file is tab separated with a footnote apparatus** that has to be
  told apart from data. Prose rows are identified by having no numeric cells,
  not by a maintained list of strings.
- **Summing the BIS extract counts the world several times.** It contains
  regional and income aggregates alongside countries; use BIS's own `5J`
  all-counterparties row for a total, or join to ISO3 first and sum that.
- **CSS keyed to element ids will not carry to a second page.** The basemap is
  styled by class for this reason — an unstyled graticule path falls back to
  SVG's default black fill and renders the meridians as solid wedges.
- **A globe is a disc, so the figure is square.** The stylesheet caps it at
  820px, which is where 430 viewBox units come out at the 1.9 pixels per unit
  every stroke width, font size and bubble radius in the JS was drawn for.
  Changing `DISC` in `projection.js` without changing that cap silently resizes
  every label on both pages.
