"""Check the city-limits layer against every metro the map can cut.

The layer draws two Census files at once -- incorporated places, and the
county subdivisions that are governments in twenty states -- filtered on
FUNCSTAT and deduplicated on geometry.  Every one of those steps can fail
quietly.  A filter that is one flag too strict drops Washington and nobody
notices until a different feature breaks; a dedupe that is one tolerance too
loose eats a real boundary; a state whose subdivisions govern but whose file
says otherwise comes out looking like Texas.

So this asks the questions that a wrong answer would show up in, for all 82
metros at once, and prints what it finds rather than asserting that it is
fine:

  * Does every metro have any boundary at all?
  * Does the metro's own principal city have one?  That is the row a cut
    searches to find the city whose neighbourhoods it names, so a metro that
    fails here gets no neighbourhood names either.
  * Do the strong-MCD states have subdivisions, and do the other thirty not?
    Both directions matter: the first is the Long Island bug, the second
    would mean drawing survey lines as if they were governments.
  * How much of the metro's land, and of its people, is inside some
    municipality?  Unincorporated country is real -- Baltimore County has no
    municipality at all -- but a metro that is 2% covered when its neighbours
    are 90% is a filter that has gone wrong.

    python3 src/land/audit_municipal.py            # all 82
    python3 src/land/audit_municipal.py baltimore  # one, in detail
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import shapely

sys.path.insert(0, str(Path(__file__).resolve().parent))
import make_us_cartogram as M      # noqa: E402

# The twenty states whose county subdivisions are general-purpose governments.
# Written here only to be checked against what FUNCSTAT actually yields --
# nothing in the build reads this list.
STRONG = set("CT IL IN KS ME MA MI MN MO NE NH NJ NY ND OH PA RI SD VT WI"
             .split())


def rows(only=None):
    metros = M._metros(M.MIN_METRO)
    shapes = M._METRO_CACHE["shapes"].set_index("GEOID")
    label = M._METRO_CACHE["label"]
    muni = M._muni()
    states = _state_of(muni)
    pop = _pop()
    out = []
    for name, cx, cy in metros:
        slug = M.slug(name)
        if only and slug != only:
            continue
        poly = shapes.loc[label[name]].geometry
        hit = muni[muni.intersects(poly)]
        inside = hit.copy()
        inside["geometry"] = inside.geometry.intersection(poly)
        # The same floor the build applies, and for a sharper reason than
        # tidiness: a township on the far side of a state line *touches* the
        # metro, so the intersection is a LineString, which is not empty and
        # has no area.  Keeping those had the audit report Baltimore as 29
        # places and 11 townships across "MD,PA" when its cut draws 18 places
        # in Maryland.  An audit that does not describe what is drawn is
        # worse than no audit.
        inside = inside[inside.geometry.area > M.MUNI_MIN_KM2 * 1e6]
        st = sorted({states.get(g, "??") for g in inside.GEOID})
        # A village sits inside a township and both are drawn, so the areas
        # overlap and summing them is not a coverage.  An earlier version did
        # sum them and reported Chicago as 134% municipal, which is the sort
        # of number that should stop a reader rather than be explained.
        cover = (shapely.unary_union(list(inside.geometry)).area / poly.area
                 if len(inside) and poly.area else 0.0)
        # Which states the *subdivisions* are in, not which states the metro
        # touches.  Reading the metro's whole state list here reported eight
        # states as drawing townships that draw none, because a metro that
        # straddles Maryland and Pennsylvania has Pennsylvania's.
        sub_st = sorted({states.get(g, "??")
                         for g in inside.GEOID[inside.kind == "cousub"]})
        city = inside[(inside.NAME == name)
                      | shapely.contains_xy(inside.geometry, cx, cy)]
        out.append(dict(
            metro=name, slug=slug, states=",".join(st),
            places=int((inside.kind == "place").sum()),
            cousubs=int((inside.kind == "cousub").sum()),
            city=(city.iloc[0].NAME if len(city) else ""),
            sub_states=",".join(sub_st),
            land=cover, people=pop(poly, inside)))
    return pd.DataFrame(out)


def _state_of(muni):
    """GEOID -> postal code.  The first two digits are the state FIPS."""
    fips = {}
    for gaz, in ((M.GAZDIR / "2023_Gaz_place_national.txt",),
                 (M.GAZDIR / "2023_Gaz_cousubs_national.txt",)):
        f = pd.read_csv(gaz, sep="\t", dtype=str)
        f.columns = [c.strip() for c in f.columns]
        fips.update(dict(zip(f.GEOID, f.USPS)))
    return fips


def _pop():
    """A closure over the population grid, or one that admits it has none."""
    if not M.POP_GRID.exists():
        return lambda poly, inside: float("nan")
    import rasterio.features
    from rasterio.transform import from_origin
    g = np.load(M.POP_GRID, mmap_mode="r")

    def share(poly, inside):
        x0, y0, x1, y1 = poly.bounds
        c0 = max(int((x0 - M.GRID["x0"]) / M.GRID["res"]), 0)
        r0 = max(int((M.GRID["y1"] - y1) / M.GRID["res"]), 0)
        c1 = min(int((x1 - M.GRID["x0"]) / M.GRID["res"]) + 1, M.GRID["nx"])
        r1 = min(int((M.GRID["y1"] - y0) / M.GRID["res"]) + 1, M.GRID["ny"])
        w = np.asarray(g[r0:r1, c0:c1], dtype="float64")
        tr = from_origin(M.GRID["x0"] + c0 * M.GRID["res"],
                         M.GRID["y1"] - r0 * M.GRID["res"],
                         M.GRID["res"], M.GRID["res"])
        whole = rasterio.features.rasterize(
            [(poly, 1)], out_shape=w.shape, transform=tr, fill=0).astype(bool)
        if not len(inside):
            return 0.0
        town = rasterio.features.rasterize(
            [(q, 1) for q in inside.geometry], out_shape=w.shape,
            transform=tr, fill=0).astype(bool)
        tot = w[whole].sum()
        return float(w[whole & town].sum() / tot) if tot else 0.0
    return share


def main(argv):
    only = argv[1] if len(argv) > 1 else None
    df = rows(only)
    df = df.sort_values("cousubs", ascending=False).reset_index(drop=True)
    print(f"{'metro':<22}{'states':<10}{'places':>7}{'cousub':>7}"
          f"{'land in':>9}{'people in':>10}  principal city")
    for _, r in df.iterrows():
        print(f"{r.metro[:21]:<22}{r.states[:9]:<10}{r.places:>7,d}"
              f"{r.cousubs:>7,d}{r.land:>8.0%}{r.people:>10.0%}  {r.city}")

    print(f"\n{len(df)} metros checked.")
    bad = df[df.places + df.cousubs == 0]
    print(f"  with no municipal boundary at all: "
          f"{', '.join(bad.metro) if len(bad) else 'none'}")
    nocity = df[df.city == ""]
    print(f"  whose own principal city has no boundary: "
          f"{', '.join(nocity.metro) if len(nocity) else 'none'}")

    # The two directions of the county-subdivision question.
    got = {s for r in df.itertuples() if r.sub_states
           for s in r.sub_states.split(",")}
    missing = sorted(s for s in df.states.str.split(",").explode().unique()
                     if s in STRONG and s not in got)
    extra = sorted(s for s in got if s not in STRONG)
    print(f"  strong-MCD states present in some metro but drawing no "
          f"subdivision: {', '.join(missing) if missing else 'none'}")
    print(f"  subdivisions drawn in a state that should have none: "
          f"{', '.join(extra) if extra else 'none'}")
    print(f"  land inside a municipality: median {df.land.median():.0%}, "
          f"lowest {df.land.min():.0%} ({df.loc[df.land.idxmin()].metro})")
    if df.people.notna().any():
        print(f"  people inside one: median {df.people.median():.0%}, "
              f"lowest {df.people.min():.0%} "
              f"({df.loc[df.people.idxmin()].metro})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
