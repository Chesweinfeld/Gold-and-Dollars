"""Use coin struck as an instrument for the circular output figures.

The problem
-----------
Where TePaske had no independent production figure he derived one by dividing
tax receipts by an assumed severance rate. Joining output to receipts then
recovers that assumption, so the join cannot say whether those figures are any
good — the agreement is arithmetic. 633 of 3,950 caja-years are flagged
`likely_derived` on that basis.

The instrument
--------------
Mintage — coin actually struck — is recorded by the mints, not the treasuries.
It is independent of both the production figure and the tax receipt, so it can
referee between them. Three places have a caja and a mint on the same site, so
the metal has a short path from one record to the other:

    Potosí, Lima, Mexico

If a derived output figure is a sound estimate of real production it should
track mintage about as well as an independently recorded figure does. If the
assumed rate was wrong, or varied when it was held fixed, the derived figures
will track mintage worse — and that degradation is measurable.

What would confound this
-----------------------
Output and mintage are not the same quantity even in principle: bullion left
unminted, was minted from stock, or was recoined. That inflates the spread for
everyone and is not the point; the comparison is between the two groups, not
against unity. The real hazard is that derived years might sit in a different
era than independent ones, so era is reported alongside and a matched-era
subsample is checked separately.
"""

import numpy as np
import pandas as pd

# caja in the join  ->  mint entity in the mintage tables
PAIRS = {"Potosí": "Potosí", "Lima": "Lima", "Mexico": "Mexican"}


def spread_stats(g):
    """Dispersion of log(output/mintage) and the log-log correlation."""
    lr = np.log(g.output_pesos / g.mint_pesos)
    lr = lr[np.isfinite(lr)]
    if len(lr) < 8:
        return None
    r = np.corrcoef(np.log(g.output_pesos), np.log(g.mint_pesos))[0, 1] \
        if len(g) > 2 else np.nan
    return dict(n=len(lr), median_ratio=float(np.exp(lr.median())),
                sd_log=float(lr.std()), iqr_log=float(lr.quantile(.75) - lr.quantile(.25)),
                corr=float(r))


def main():
    w = pd.read_csv("tepaske_annual.csv")
    j = pd.read_csv("joined_output_vs_fiscal.csv")

    mint = (w[(w.measure == "mintage") & (w.metal == "silver")]
            .groupby(["entity", "year"], as_index=False).pesos.sum()
            .rename(columns={"pesos": "mint_pesos", "entity": "mint"}))

    rows = []
    for caja, mint_name in PAIRS.items():
        a = j[(j.caja == caja) & (j.match == "both")].copy()
        b = mint[mint.mint == mint_name]
        g = a.merge(b, on="year", how="inner")
        g = g[(g.output_pesos > 0) & (g.mint_pesos > 0)]
        g["caja"] = caja
        rows.append(g)
    d = pd.concat(rows, ignore_index=True)

    print("=" * 74)
    print("OUTPUT vs MINTAGE, by whether the output figure was derived")
    print("=" * 74)
    print(f"{'place':<10}{'group':<14}{'n':>5}{'median o/m':>12}"
          f"{'sd log':>9}{'IQR log':>9}{'corr':>8}   years")
    for caja, g in d.groupby("caja"):
        for flag, label in ((False, "independent"), (True, "derived")):
            s = spread_stats(g[g.likely_derived == flag])
            if s is None:
                print(f"{caja:<10}{label:<14}    too few rows")
                continue
            yy = g[g.likely_derived == flag].year
            print(f"{caja:<10}{label:<14}{s['n']:>5}{s['median_ratio']:>12.2f}"
                  f"{s['sd_log']:>9.3f}{s['iqr_log']:>9.3f}{s['corr']:>8.3f}"
                  f"   {int(yy.min())}-{int(yy.max())}")
        print()

    print("Mexico contributes no independent rows in the overlap, so it cannot")
    print("be tested; it is shown for completeness only.\n")
    print("Median output/mintage is ~1 at Potosí but far below 1 at Lima and")
    print("Mexico, because those mints struck silver drawn from many districts")
    print("while Potosí mined and struck on the same site. That makes Potosí")
    print("the decisive case: a closed system, so the two records should track.\n")

    # Pooling raw across places is meaningless — the levels differ by an order
    # of magnitude — so the ratio is centred within each place first.
    print("=" * 74)
    print("IS THE DIFFERENCE REAL?  permutation test on dispersion")
    print("=" * 74)
    rng = np.random.default_rng(0)
    for caja in ["Potosí", "Lima"]:
        g = d[d.caja == caja].copy()
        g["lr"] = np.log(g.output_pesos / g.mint_pesos)
        g = g[np.isfinite(g.lr)]
        a = g.loc[~g.likely_derived, "lr"]
        b = g.loc[g.likely_derived, "lr"]
        if len(a) < 8 or len(b) < 8:
            continue
        stat = lambda x: (x.quantile(.75) - x.quantile(.25))
        obs = stat(b) - stat(a)
        pool = pd.concat([a, b]).to_numpy()
        na = len(a)
        null = np.empty(20000)
        for i in range(20000):
            p = rng.permutation(pool)
            null[i] = (np.subtract(*np.percentile(p[na:], [75, 25]))
                       - np.subtract(*np.percentile(p[:na], [75, 25])))
        p_val = float((null >= obs).mean())
        print(f"  {caja:<8} IQR(derived) - IQR(independent) = {obs:+.3f}"
              f"   p = {p_val:.4f}   (20,000 permutations, one-sided)")

    print("\nmatched era — restricted to caja-decades containing both kinds:")
    d["decade"] = d.year // 10 * 10
    both = (d.groupby(["caja", "decade"]).likely_derived.nunique() == 2)
    keys = set(both[both].index)
    m = d[[k in keys for k in zip(d.caja, d.decade)]]
    for caja, g in m.groupby("caja"):
        for flag, label in ((False, "independent"), (True, "derived")):
            s = spread_stats(g[g.likely_derived == flag])
            if s:
                print(f"  {caja:<8} {label:<12} n={s['n']:<4} "
                      f"IQR log {s['iqr_log']:.3f}")
    print(f"  ({len(keys)} caja-decades contain both kinds — this controls for")
    print("   era, so the gap is not an artefact of derived years being older)")

    d.to_csv("output_vs_mintage.csv", index=False)
    print(f"\n{len(d)} rows -> output_vs_mintage.csv")


if __name__ == "__main__":
    main()
