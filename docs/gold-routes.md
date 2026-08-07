# Gold from mine to port: what the sources can and cannot support

Short answer: **route-level, yes; parcel-level, no.**

No source in this collection follows a consignment from a placer to a ship's
hold. Nothing digitized here ever could — the Spanish fiscal record was not
built to track parcels, it was built to tax them. What can be built is a chain
of three measured layers plus a stated linkage between them, with each link
labelled by the kind of evidence that supports it.

## The three layers

| layer | file | grain | coverage |
|---|---|---|---|
| origin | `gold_origin_decade.csv` | district × decade | 27 districts, 6 regions, 1492–1810 |
| mint | `gold_mint_annual.csv` | mint × year | 7 mints, 1621–1821 |
| port | `gold_port_annual.csv` | American port × year | 12 ports, 1717–1778 |

`gold_routes.csv` holds the 11 mint→port edges, each with the years it applies,
an assumed share, and an evidence class: `ship` (the port appears in the vessel
appendix and the ratio test below runs), `fiscal` (a treasury transfer edge for
it exists in `colmex_flows.csv`), or `inferred` (geography and the fleet system
only — no series links the two).

**The assumed shares are priors, not measurements.** They are there so the
assumption is visible and editable rather than buried. Do not report a number
that depends on them without saying so.

## Why the port layer does not simply say "gold"

García-Baquero's appendix records **pesos per vessel**, not gold pesos and
silver pesos. The treasury transfer records are worse: of 7,068 transfer edges
in `colmex_flows.csv`, exactly **one** names a metal (`REMITIDO A MEXICO DEL
ORO`). Remittance accounts were kept in money of account, and gold and silver
were commingled inside them.

So "which of these pesos were gold" has to be earned from the composition of the
region upstream, and it can only be earned where a region produced essentially
one metal.

## The test that earns it

Value laded at a port, against gold struck at the mint feeding it, 1717–1778:

| mint | port | port ÷ mint | decade corr |
|---|---|---|---|
| Santa Fe + Popayán | **Cartagena** | **0.82** | **0.674** |
| Lima | Callao | 1.50 | −0.104 |
| Mexico City | Veracruz | 8.01 | 0.112 |

**Cartagena is a gold port.** Its outbound value is 82% of the gold minted
upstream and moves with it. Independently, table 6-1 gives New Granadan silver
as 1.8M pesos against 45M of gold — 4% by value. Value leaving Cartagena is
gold to within about that margin, and the gold route New Granada → Santa
Fe/Popayán → Magdalena → Cartagena → Cádiz is supported end to end.

**Veracruz is not.** Its cargo is eight times all Mexican gold and does not
track it. Veracruz shipped silver, and the Mexican gold inside those holds
cannot be separated out by these sources. Any figure claiming to is fabricated.

The ratio contrast is the finding. It is what distinguishes a port whose cargo
composition is recoverable from one whose is not, and it comes out of the data
rather than being assumed going in.

Callao at 1.50 with a negative correlation is not evidence either way: the
Callao rows in the appendix are sparse Cape Horn register ships after the
galeones lapsed, not a fleet series.

## A route validating itself

Cartagena's series carries the War of Jenkins' Ear in the right place. The
galeones were suspended in 1739 and Vernon besieged the city in 1741:

```
1738   2 ships   6,465,895 pesos
1741   1 ship            0
1742   1 ship       24,000
1746   1 ship       41,682
1747   1 ship       40,450
1750   5 ships  10,398,948      <- the backlog clears
```

Nothing in the extraction knows about the war. The war is in the data because
the ships stopped sailing, which is a decent sign the port series is measuring
what it claims to.

## The gap that matters

**New Granada — the largest gold region in Spanish America, 320 tonnes fine —
is absent from the fiscal layer entirely.** None of the 71 cajas in
`colmex_flows.csv` are New Granadan: no Popayán, no Chocó, no Antioquia, no
Santa Fe, no Cartagena. The Colmex digitization covers New Spain, Peru, Charcas,
Quito, Chile and Río de la Plata, and stops there.

So for the metal that matters most, there is production (decade, and only as a
regional aggregate — table 2-6 has no district breakdown), and there is mintage
(annual, by mint), and there is the port, but there is no treasury movement
record in between. The middle link is inferred for exactly the region where one
would most want it measured.

Closing it means the Archivo General de la Nación (Colombia) cajas reales, or
Colmex's New Granada volumes if they exist in the same series. That is the
highest-value single addition to this collection.

## Other open gaps

- **Table 2-12** (Brazilian gold by region, 1700–1801) parsed with a collapsed
  header — the regional columns came out as `ON_KGS`/`ON_PESOS` instead of Minas
  Gerais / Goiás / Mato Grosso. That is the district layer for Brazil and it is
  currently unusable. Fixable; the page is in the chapter-2 PDF.
- **Chocó, Antioquia, Barbacoas** have no separate series here at all, only the
  New Granada aggregate.
- The Pacific leg (Popayán → Buenaventura/Guayaquil → Callao) is the one route
  marked `inferred` with no series on either side of it.
