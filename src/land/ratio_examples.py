"""The worked examples printed on the land-versus-output map, from the data.

The figure's caption names a dozen places and quotes a ratio for each.  Prose
drifts; this script exists so it cannot.  Every number in that caption is
printed here, read off data/land/us_land_vs_gdp.csv.gz, and any edit to the
underlying surfaces will show up as a changed table rather than as a caption
that has quietly become false.

The places were chosen to break the reading that expensive land is brown and cheap
land is teal.  Midtown Manhattan is the most expensive ground in the country
and comes out teal; the Cleveland Flats are cheap industrial ground and come
out teal too, for the same reason -- the work standing on both dwarfs the price
of the dirt.  Cape Cod is neither productive nor cheap, and is brown.

Gary is in the table and flagged, not used as an exemplar.  It reads as the
most extreme teal in the country and that is an artefact: the land surface
gives Indiana's industrial districts about an eighth of the price its peers in
other states carry.  See src/land/land_model_gaps.py.

Writes data/land/us_land_vs_gdp_examples.csv.
"""

import sys
from pathlib import Path

import pandas as pd
from pyproj import Transformer

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "land"

# The lattice both surfaces are cut from, blocked 8x for the national cuts.
SIDE = 3840.0
X0, Y1 = -2357205.0, 3173925.0

# (label, lon, lat, why it is here)
PLACES = [
    ("Cleveland, Ohio (the Flats)", -81.68, 41.47,
     "cheap industrial ground carrying real output"),
    ("Gary, Indiana (mill district)", -87.34, 41.62,
     "FLAGGED: Indiana's urban land is under-priced by the model"),
    ("Midtown Manhattan", -73.984, 40.755,
     "the most expensive land in America, and still teal"),
    ("Iowa farmland (Story County)", -93.60, 42.03, "row crop"),
    ("Beverly Hills", -118.40, 34.07, "expensive, but worked"),
    ("Bakersfield, California", -119.02, 35.37, "oil and agriculture"),
    ("Houston Ship Channel", -95.15, 29.73, "refining and port"),
    ("Aspen, Colorado", -106.82, 39.19, "resort"),
    ("Mountain View, California", -122.08, 37.39,
     "productive, and priced ahead of it"),
    ("Napa Valley", -122.35, 38.45, "priced on future vintages"),
    ("Cape Cod", -70.05, 41.77, "priced on wanting to be there"),
]


def main():
    src = DATA / "us_land_vs_gdp.csv.gz"
    if not src.exists():
        sys.exit(f"missing {src}; run src/land/us_land_vs_gdp.py first")
    d = pd.read_csv(src).set_index(["tile_row", "tile_col"])

    # The map's baseline is total land over total output including the land
    # that carries no workplace, so it is not recoverable from this file; it is
    # printed by make_us_cartogram.py and quoted here for scale.
    base = d.land_usd.sum() / d.gdp_usd.sum()

    to_albers = Transformer.from_crs("EPSG:4326", "EPSG:5070", always_xy=True)
    rows = []
    for label, lon, lat, why in PLACES:
        x, y = to_albers.transform(lon, lat)
        key = (int((Y1 - y) // SIDE), int((x - X0) // SIDE))
        if key not in d.index:
            print(f"  {label}: no tile with recorded output")
            continue
        t = d.loc[key]
        rows.append(dict(place=label, note=why, tile_row=key[0], tile_col=key[1],
                         land_usd=int(t.land_usd), gdp_usd=int(t.gdp_usd),
                         years=round(float(t.years), 4),
                         vs_national=round(float(t.years) / base, 3)))

    out = pd.DataFrame(rows).sort_values("years")
    print(f"\nbaseline over tiles that have output: {base:.4f} years\n")
    print(f"{'place':32s}{'land':>12s}{'output/yr':>12s}{'years':>9s}{'vs U.S.':>9s}")
    for r in out.itertuples():
        print(f"{r.place:32s}{r.land_usd/1e6:11,.0f}m{r.gdp_usd/1e6:11,.0f}m"
              f"{r.years:9.2f}{r.vs_national:8.1f}x")

    flagged = out.note.str.startswith("FLAGGED")
    if flagged.any():
        print("\n  flagged, not to be quoted as findings: "
              + "; ".join(out.place[flagged]))
    dest = DATA / "us_land_vs_gdp_examples.csv"
    out.to_csv(dest, index=False)
    print(f"\n-> data/land/{dest.name}")


if __name__ == "__main__":
    main()
