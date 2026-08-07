# Silver from mine to port: the chain gold could not complete

For gold, the middle of the chain was missing — New Granada has no caja in the
fiscal record, so district→port had to be inferred. For silver the treasury
transfers exist, so every hop is an observed quantity and the chain can be
checked at its joints instead of only at its ends.

## The chain

| leg | edges | pesos of 272 mrv | span |
|---|---|---|---|
| mining caja → hub | 46 | 308.7M | 1528–1836 |
| hub → Atlantic port | 4 | 342.9M | 1590–1809 |
| port → Spain | 7 | 311.4M | 1569–1812 |
| port → Havana (rendezvous) | 3 | 156.6M | 1630–1801 |

A further **413.7M pesos** arrives at the hubs from an origin **the ledgers never
record**. That is larger than every named district put together, and it is
excluded from the arithmetic rather than distributed across the named ones. See
"Why so much origin is unnamed" below — it is a property of the source, not of
the parse.

Havana is kept separate from Spain deliberately. It was the fleet rendezvous,
not a destination — folding it into "to Spain" would count the same silver
twice.

The dominant arteries, in order: Mexico City → Veracruz (292.5M), Veracruz →
Spain (158.1M), Veracruz → Havana (150.5M), Lima → Spain (113.1M), Potosí → Lima
(50.1M), Guanajuato → Mexico City (42.5M), Zacatecas → Mexico City (39.8M).

## The books are single-sided

A transfer should be booked twice — expenditure for the sender, revenue for the
receiver. In this digitization it almost never is. **Of the 46 named
district→hub edges, exactly one appears in both parties' books.**

That is not a rounding problem, it changes how the totals must be read:

- **Mexico City → Veracruz.** Mexico City's books record 20.8M pesos sent.
  Veracruz's books record **292.5M** received. Reading the sender side alone
  loses 93% of the largest silver artery in the empire.
- **Potosí → Lima.** The other direction: Potosí records 50.1M sent, Lima
  records 2.3M received. Agreement 0.046 — a factor of twenty.

So `silver_chain_edges.csv` reports, per edge, which side recorded it, the other
side's figure where one exists, and their ratio. **Use the larger side and say
which it was.** An edge with no `agreement` value has not been verified against
anything.

This also qualifies a finding already in the README. Veracruz taking in 366M and
sending out 389M is a *node* balance — everything in against everything out —
not an edge-level double-entry match. It still says Veracruz did not accumulate.
It is not the independent confirmation that a matched pair of books would be.

## Hop 1: what the crown actually took

Hop 1 does not carry a district's metal. The silver stayed with the miners net
of tax; what moved to the hub was the crown's revenue. So silver tax collected
divided by silver produced should land near the royal share, and whether it does
is a real test of whether these edges carry what they claim to.

Restricted to caja-years TePaske did **not** derive from receipts, the median
across 22 districts with 20+ clean years is **0.127** — with real spread, from
Guanajuato at 0.039 to Mexico at 0.233. That spread is what an effective rate
should look like: different ores, different exemptions, different smuggling.

## The circularity constant, seen empire-wide

Now run the same ratio on the caja-years TePaske *did* derive from receipts:

| | cross-district IQR |
|---|---|
| independently recorded years | 0.0628 |
| TePaske-derived years | **0.0164** (3.8× tighter) |

**13 of 21 districts land within one percentage point of 0.1135** — the diezmo
plus the cobos on the remainder. Zacatecas 0.1109, Guadalajara 0.1123, Zimapán
0.1123, Carangas 0.1130, Huancavelica 0.1135, Trujillo 0.1139, Arica 0.1157 —
different ores, different centuries, different viceroyalties, same number.

`docs/circularity-test.md` established this at Potosí against mintage. This is
the same artifact seen from above: not one caja's assumption, but a constant
propagating across twenty-one unrelated districts spanning three centuries.
Independent effective tax rates do not agree to four decimals across an empire.

Two districts to be careful with. **Mexico** shows a derived share of 1.036 —
tax exceeding output, which is arithmetically impossible for a real rate and
marks those rows as unusable rather than merely circular. **Bolaños** shows a
clean share of 0.0069, two orders below its neighbours; its silver tax is likely
booked under an account the classifier did not catch.

## Veracruz despatch against vessels arriving

| decade | despatched (fiscal) | at Cádiz (vessels) |
|---|---|---|
| 1710s | 3.6M | 12.4M |
| 1720s | 5.1M | 27.6M |
| 1730s | 9.5M | 15.4M |
| 1740s | 6.2M | 14.7M |
| 1750s | 12.2M | 89.7M |
| 1760s | 6.3M | 48.7M |
| 1770s | 14.3M | 44.4M |

**This is not a contraband estimate and must not be presented as one.** The
despatch column is what three treasuries in the sample recorded sending; the
arrival column is every vessel that reached Cádiz from Veracruz, crown and
private together. The gap is mostly private silver that never passed through a
royal treasury account, plus treasuries the Colmex sample does not cover. It
measures coverage, not leakage. The same warning applies to
`atlantic_despatch_vs_arrival.csv`.

## Why so much origin is unnamed

Across the whole network, **39.4% of all flow value has no named counterparty**.
That is not a parsing gap. Two account headings account for nearly all of it:

| heading | meaning | lines | pesos |
|---|---|---|---|
| `OTRAS TESORERIAS` | "other treasuries" | 1,212 | 589.2M |
| `VENIDO DE FUERA` | "come from outside" | 360 | 291.0M |

These are the complete account names as written. The clerk booked a lump sum
under a generic category; the counterparty was never itemized. `build_flows.py`
matches both patterns deliberately — dropping them would silently discard 39% of
the network's value, so they are carried with an honest `unspecified` label
instead.

**They are terminal lines, not headings over detail.** In the same Lima books in
the 1780s, the outbound side names every recipient — `SITUADO DE PANAMA`
1,979,617, `SITUADO DE VALDIVIA` 371,737, `SITUADO DE CHILOE` 174,612 — while
the inbound side records `VENIDO DE FUERA` 6,404,594 and `OTRAS TESORERIAS`
3,649,811 against no one at all. The clerk could itemize. On revenue, they
chose not to.

That asymmetry is systematic:

| direction | value unnamed | lines named : unnamed |
|---|---|---|
| revenue (in) | **61.1%** | 917 : 1,002 |
| expenditure (out) | 22.8% | 4,496 : 653 |

Expenditure was itemized nearly seven to one by line count; revenue barely half.
The reason is what the accounts were *for*. A treasurer had to show that money
paid out went where it was ordered — a garrison's situado is a discharge of a
specific obligation and must name it. Money coming in only had to total
correctly. Provenance was the sender's problem.

It also concentrates where you would expect: **Lima 302.6M and Mexico City
223.1M**, the two hubs receiving from dozens of treasuries at once, and heavily
after 1750 (632.6M of the 882.2M), as Bourbon accounting consolidated detail
into summary categories.

**This is therefore not recoverable from the Colmex workbooks.** Closing it means
the individual cajas' own remission records in the AGI and national archives —
matching a hub's lump-sum receipt against the sending treasuries' despatch
entries, year by year. That is archival work, not parsing.

## Open
- The Potosí → Lima 20:1 discrepancy is unexplained and worth a look at the
  underlying account lines before either figure is used.
- Bolaños' silver tax is almost certainly under an unclassified account.
