# Testing the circular output figures against coin struck

## The problem

Where TePaske had no independent production figure, he derived one by dividing
tax receipts by an assumed severance rate. Joining output to receipts then
recovers that assumption: the two agree because one was computed from the other.
248 caja-years share an implied rate of exactly 0.11350 — the diezmo plus the
cobos on the remainder — and 633 of 3,950 caja-years are flagged
`likely_derived` on that pattern.

The flag identifies rows whose agreement is arithmetic. It does not, by itself,
say whether those figures are any *good*. The join cannot answer that, because
the join is the thing that is compromised.

## The instrument

Mintage — coin actually struck — is recorded by the mints rather than the
treasuries. It is independent of both the production figure and the tax receipt,
so it can referee between them.

Three places have a caja and a mint on the same site: Potosí, Lima and Mexico.
**Potosí is the decisive case.** Its median output/mintage ratio is 0.83, near
unity, because silver was mined and struck in the same town — a closed system in
which the two records should track each other. At Lima and Mexico the ratio is
0.18 and 0.08, because those mints struck bullion drawn from many districts.

Mexico contributes no independent rows in the overlap and so cannot be tested.

## Result

Derived figures track mintage substantially worse than independently recorded
ones. Dispersion is the interquartile range of log(output ÷ mintage):

| place | group | n | median o/m | IQR log | corr |
|---|---|---:|---:|---:|---:|
| Potosí | independent | 93 | 0.83 | **0.229** | +0.140 |
| Potosí | derived | 131 | 1.06 | **1.194** | −0.235 |
| Lima | independent | 66 | 0.18 | **0.548** | +0.606 |
| Lima | derived | 59 | 0.19 | **1.269** | +0.558 |

At Potosí the derived figures scatter more than five times as widely, and their
correlation with mintage is *negative*.

A permutation test on the difference in IQR, 20,000 resamples, one-sided:

| place | IQR(derived) − IQR(independent) | p |
|---|---:|---:|
| Potosí | +0.965 | 0.0004 |
| Lima | +0.721 | <0.0001 |

## Controlling for era

Derived years might simply be older years with worse records everywhere.
Restricting to the 22 caja-decades that contain both kinds removes that
possibility, and the gap survives:

| place | independent | derived |
|---|---:|---:|
| Lima | 0.270 | 1.369 |
| Potosí | 1.172 | 1.695 |

## What this means

The circularity flag is not merely a technical annotation. It marks figures that
are **measurably worse** when checked against a record that knows nothing about
tax receipts. Any analysis using TePaske's output series should down-weight or
exclude the flagged caja-years rather than treating all rows as equivalent
observations.

Two honest limits. Output and mintage are not the same quantity even in
principle — bullion was exported unminted, struck from stock, or recoined — which
inflates the spread for both groups; the comparison is between groups, not
against unity. And some rows are probably flagged spuriously, where output
genuinely happened to sit near receipts ÷ a round rate. False positives dilute
the contrast rather than manufacture it, so the measured gap is if anything
conservative.

Reproduce with `src/test_circularity.py`; row-level output in
`data/production/output_vs_mintage.csv`.
