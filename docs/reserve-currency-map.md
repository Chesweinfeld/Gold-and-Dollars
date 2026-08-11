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

| layer | source | what it gives | what it withholds |
|---|---|---|---|
| composition | IMF COFER | share of world reserves by currency, quarterly | any country's own composition |
| holdings | World Bank `FI.RES.TOTL.CD`, `FI.RES.XGLD.CD` | reserves per country per year, gold separable | what currency any of it is in |
| geometry | Natural Earth 1:110m | country outlines and centroids | — |

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

### BIS: not a country pair at all

BIS locational banking statistics give cross-border bank claims on each
counterparty country, split by the currency the claim is denominated in. That
is the mechanism that makes a currency a reserve currency — if your obligations
are in dollars you must hold dollars — but it is emphatically not a lender-to-
borrower matrix.

The public dataflow publishes `L_REP_CTY = 5A` only, the aggregate of all
reporting countries. There is no published lender-country by borrower-country
breakdown, so the arcs on this view run from a *currency's central bank* to the
borrower and mean **denominated in**, never **lent by**. The page says so above
the map. Available denominations are USD, EUR, JPY and an all-currency total;
sterling and the franc are inside the total but not published separately at
this level.

At 2026-Q1: $47.6tn of cross-border claims outstanding, 46% written in dollars,
32% in euro, 5% in yen.

## The centre of gravity

The one figure here that is computed rather than reported. Each country is
treated as a point mass at its own centroid, weighted by the reserves it holds,
and the weighted mean is taken **on the sphere** — coordinates to unit vectors,
summed, renormalised — not by averaging degrees. Averaging longitude in degrees
places the mean of Tokyo and Los Angeles in Kazakhstan rather than the Pacific,
which would invert the result.

| year | centre | reporters | total held |
|---|---|---|---|
| 1960 | 62.3°N, 35.9°W — mid-Atlantic | 87 | $0.1tn |
| 1980 | 57.0°N, 2.9°W — the Channel | 127 | $1.0tn |
| 2000 | 59.0°N, 79.0°E — western Siberia | 169 | $2.1tn |
| 2014 | 48.9°N, 83.7°E — the Altai | 176 | $12.6tn |
| 2024 | 54.1°N, 73.9°E — western Siberia | 164 | $14.9tn |

The track moves 110° east between 1960 and 2024 and then, after 2014, comes back
west a little: China's reserves peaked at $4.0tn in 2014 and the rest of the
world kept accumulating.

The centroid is sensitive to which countries reported in a given year, so the
site marks any year whose panel is materially incomplete. 2025 is currently
partial — 124 of 182 reporters — and is flagged in the interface rather than
quietly plotted.

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

33 checks in total. Two are worth keeping.

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
- **Natural Earth 110m has no polygon for 25 reporters**, including Singapore
  ($432bn) and Hong Kong. They are placed from the World Bank's own capital
  coordinates and carry a `shape: 0` flag; dropping them would have quietly
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
