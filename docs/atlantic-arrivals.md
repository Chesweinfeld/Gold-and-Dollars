# Atlantic arrivals: Hamilton (1929) digitized, and the modern series

This extends the project from **production** (TePaske, already done) to
**movement** — how much metal actually crossed the Atlantic, who owned it, and
how the sources disagree.

## Files

| file | contents |
|---|---|
| `hamilton_1929_arrivals.csv` | Hamilton's Tables A and B, 1503–1660, by decade: crown/private split in pesos, gold and silver percentages by weight, derived kg of each metal |
| `arrivals_comparison.csv` | Hamilton beside the modern composite arrivals and our TePaske production, by decade |
| `production_to_arrivals.csv` | annual 1500–1810: production (ours), arrivals, Spanish money stock, shipwreck losses |
| `costa_table1_remittances.csv` | Brazilian gold reaching Lisbon 1720–1807, four independent sources side by side |
| `extract_hamilton.py`, `compare_arrivals.py`, `build_chain.py` | the pipeline |

## What Hamilton uniquely provides

The **crown vs. private split**. Every modern series carries totals only.
Hamilton's Table A separates the king's receipts from merchants' across
sixteen decades, and that column is what connects Atlantic arrivals to the
fiscal records on the American side (`colmex_cajas_long.csv`).

Over 1503–1660 the crown took **26.2%** of registered arrivals, and the decade
figures move in a politically legible way: a peak of 34.1% in the 1570s,
falling to 18.3% in the 1620s as private trade outgrew the royal share.

## Validation

1. **Against TePaske's independent restatement.** TePaske's table 7-1 reprints
   Hamilton by decade "in Millions of Pesos of 272 Maravedís". Our extracted
   Table A tracks it at a constant ratio (median 0.8270; 0.8232–0.8306 across
   the thirteen decades large enough to be free of print rounding). The two
   digitizations, from different books, agree.
2. **Against Hamilton's own stated metal totals**, 16,632,648.20 kg of silver
   and 181,234.95 kg of gold — reproduced to 2.6% and 0.0% before
   normalization.
3. **Against Hamilton's own stated crown share.** Our decade figures imply
   26.2% for the whole period; he writes on p.462 that public receipts were
   "26.2 per cent of the total" for 1536–1660.

## A units discrepancy in the source, unresolved

Hamilton's footnote defines the Table A peso as 450 maravedís = 652.635 grains
of fine silver (42.29 g). That is internally consistent — a peso of 272
maravedís holds 25.560 g, and 450/272 × 25.560 = 42.289.

It cannot be reconciled with his own results. Valuing Table A's 895.6 million
pesos at 42.29 g implies 37,874 t of silver equivalent, against the ~18,935 t
his stated metal totals are worth: a factor of **2.00**. Recovering the
footnote value would require a gold:silver ratio near 117:1 instead of the
10–15:1 that actually prevailed.

TePaske resolves it the same way we do — his restatement is a constant 0.8272
of Table A, exactly half the 1.654 the footnote implies. So the conversion here
uses **21.14 g of fine silver per Table A peso**, derived from that
restatement, and the footnote is flagged rather than trusted. All raw printed
values are preserved so this can be redone under different assumptions.

Residual: Table A (value), Table B (weight shares) and the stated totals are
mildly over-determined and do not close exactly — silver lands 2.6% high. The
decade *shape* is Hamilton's; the *level* is normalized to his published
totals. A freely solved gold:silver ratio comes out at 10.27:1, which is
reasonable given that gold arrived overwhelmingly in the early decades when
Castile's ratio was near 10.5:1.

## The headline result: Hamilton's post-1630 collapse is measurement

Comparing Hamilton's registered arrivals to the modern composite, by decade:

| decade | Hamilton ÷ modern |
|---|---|
| 1591–1600 | 1.28 |
| 1601–1610 | 0.95 |
| 1621–1630 | 0.84 |
| 1641–1650 | 0.35 |
| 1651–1660 | **0.17** |

Hamilton's series falls to a sixth of the modern estimate within fifty years.
This is the Morineau critique made arithmetic: registration at Seville broke
down as crown confiscations taught merchants not to declare, so the famous
"collapse of Spanish treasure" after 1630 is substantially a collapse of
*recording*. Our own TePaske production series confirms it from the other end —
American output holds up through exactly the decades when Hamilton's arrivals
fall away.

Use Hamilton unadjusted only through about 1620.

## Provenance of the modern series

- **Arrivals, money stock, shipwreck losses**: Brzezinski, Chen, Palma & Ward,
  *Review of Economics and Statistics* 106(5), 2024 — replication data at
  Harvard Dataverse `doi:10.7910/DVN/PSOYNM`. The money-supply variables in it
  come from Chen, Palma & Ward, *Explorations in Economic History*, 2021.
- **Annual gold, Potosí, European mint output**: Palma, *Review of Economic
  Studies* 89(3), 2022 — Zenodo `10.5281/zenodo.5338362`. Note that his silver
  series is built from the same TePaske volume we digitized; our extraction
  reproduces it to the tonne from 1580 on (correlation 0.995), and his
  `pesograms` constant of 25.561 g matches the 0.025560 kg/peso factor we
  derived independently from TePaske's printed columns.
- **Brazilian gold**: Sousa, "Brazilian Gold and the Lisbon Mint House
  (1720–1807)", *e-Journal of Portuguese History* 6(1), 2008 — open access.

## Still missing

- **Annual arrivals 1660–1790** — Morineau's gazette series exists only in the
  1985 book; even the 2022–2025 literature cites it from print. Our
  `production_to_arrivals.csv` covers this span via the modern composite, but
  the underlying gazette observations are not public.
- **Annual Brazilian gold** — Sousa's article gives five-year periods; the
  year-by-year *Livros dos Manifestos* figures are in the 2013 book
  *O ouro do Brasil*.
- **The Pacific leg**. Manila galleon flows remain estimates, and official
  figures are known to understate badly.
- Chen/Palma/Ward's own replication package is on openICPSR, which requires a
  free account; its key series are already present in the Dataverse file above,
  so this is optional.
