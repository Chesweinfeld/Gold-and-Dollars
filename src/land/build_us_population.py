"""Resident population on the national 480 m lattice, from census blocks.

The population already in this repository is GHS-POP at 30 arc-seconds, about
800 m at these latitudes.  That is finer than the 3.84 km national tile and
*coarser than the 480 m tile of a metro cut*, which is the scale at which a
population figure would actually be interesting: build_us_gdp.pop_cells says
as much in its own docstring, that it "should not be cut at 480 m without
saying so".

The United States does not need a modelled population surface.  It counts
people, block by block, once a decade.  A census block is the finest unit the
count is published for, and in the 2020 file the median occupied block is
0.031 km2 -- seven times smaller than a 480 m tile.  The count is enumerated
rather than estimated, and it is the same geography LODES already uses to
place jobs, so population and employment end up on one lattice instead of two.

TIGER carries POP20 inside the block geometry, so there is nothing to join.

    python3 src/land/build_us_population.py

-> data/land/us_pop_480m.npy, one float32 per cell of the shared lattice.
"""
import sys
import zipfile
from pathlib import Path

import numpy as np
import pyogrio
import rasterio.features
from rasterio.transform import from_origin

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
BLOCKS = IN / "blocks"
OUT = ROOT / "data" / "land" / "us_pop_480m.npy"
ALBERS = 5070
# The lattice everything in this strand is cut on; see make_us_cartogram.GRID.
GRID = dict(x0=-2357205.0, y1=3173925.0, res=480.0, nx=9618, ny=6054)
TIGER = ("https://www2.census.gov/geo/tiger/TIGER2023/TABBLOCK20/"
         "tl_2023_{st}_tabblock20.zip")
# The conterminous states, plus DC.  Alaska and Hawaii are not on this lattice.
STATES = ["01", "04", "05", "06", "08", "09", "10", "11", "12", "13", "16",
          "17", "18", "19", "20", "21", "22", "23", "24", "25", "26", "27",
          "28", "29", "30", "31", "32", "33", "34", "35", "36", "37", "38",
          "39", "40", "41", "42", "44", "45", "46", "47", "48", "49", "50",
          "51", "53", "54", "55", "56"]


def fetch(st):
    """One state's blocks, cached like every other input here."""
    import subprocess
    f = BLOCKS / f"tl_2023_{st}_tabblock20.zip"
    if f.exists() and f.stat().st_size > 100_000:
        return f
    BLOCKS.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["curl", "-sS", "-L", "--fail", "-m", "1800",
                        "-o", str(f), TIGER.format(st=st)])
    if r.returncode or not f.exists():
        f.unlink(missing_ok=True)
        raise SystemExit(f"could not fetch blocks for state {st}")
    return f


def state_pop(f, out):
    """Add one state's people to the national grid, losing nobody.

    Blocks tile the country without overlapping, so painting each block's index
    onto the lattice gives every cell exactly one block, and counting the cells
    that came out with a given index gives that block's footprint in cells.
    Its people are then spread evenly over them.

    A block smaller than a cell can win no cell at all -- the median block is
    a seventh of a tile, so this is most of them -- and those people are put
    on the tile holding the block's own interior point instead.  Which way
    each block went is reported, because "spread over its cells" and "dropped
    on one tile" are different claims about where somebody lives, and at 480 m
    the difference is a city block against a neighbourhood.
    """
    g = pyogrio.read_dataframe(
        f"/vsizip/{f}", columns=["POP20", "INTPTLAT20", "INTPTLON20"])
    g = g[g.POP20.astype("int64") > 0]
    if not len(g):
        return 0, 0, 0
    pop = g.POP20.astype("float64").to_numpy()
    g = g.to_crs(ALBERS)

    x0b, y0b, x1b, y1b = g.total_bounds
    c0 = max(int((x0b - GRID["x0"]) / GRID["res"]) - 1, 0)
    r0 = max(int((GRID["y1"] - y1b) / GRID["res"]) - 1, 0)
    c1 = min(int((x1b - GRID["x0"]) / GRID["res"]) + 2, GRID["nx"])
    r1 = min(int((GRID["y1"] - y0b) / GRID["res"]) + 2, GRID["ny"])
    if c1 <= c0 or r1 <= r0:
        return 0, 0, 0
    tr = from_origin(GRID["x0"] + c0 * GRID["res"],
                     GRID["y1"] - r0 * GRID["res"], GRID["res"], GRID["res"])

    idx = rasterio.features.rasterize(
        ((geom, i + 1) for i, geom in enumerate(g.geometry)),
        out_shape=(r1 - r0, c1 - c0), transform=tr, fill=0,
        all_touched=False, dtype="int32")
    cells = np.bincount(idx.ravel(), minlength=len(g) + 1)[1:]

    win = out[r0:r1, c0:c1]
    big = cells > 0
    if big.any():
        # Every cell of a block gets the same share of its people.
        share = np.zeros(len(g) + 1)
        share[1:][big] = pop[big] / cells[big]
        np.add.at(win, np.nonzero(idx), share[idx[idx > 0]])

    small = ~big
    if small.any():
        import pyproj
        t = pyproj.Transformer.from_crs(4326, ALBERS, always_xy=True)
        lat = g.INTPTLAT20.to_numpy()[small].astype(float)
        lon = g.INTPTLON20.to_numpy()[small].astype(float)
        x, y = t.transform(lon, lat)
        ix = np.clip(((x - GRID["x0"]) / GRID["res"]).astype(int),
                     0, GRID["nx"] - 1)
        iy = np.clip(((GRID["y1"] - y) / GRID["res"]).astype(int),
                     0, GRID["ny"] - 1)
        np.add.at(out, (iy, ix), pop[small])
    return pop.sum(), int(big.sum()), int(small.sum())


def main():
    out = np.zeros((GRID["ny"], GRID["nx"]), dtype="float64")
    total = spread = dropped = 0.0
    for i, st in enumerate(STATES):
        f = fetch(st)
        p, b, s = state_pop(f, out)
        total += p
        spread += b
        dropped += s
        print(f"  [{i+1:2d}/{len(STATES)}] state {st}: {p:>11,.0f} people, "
              f"{b:>7,d} blocks spread, {s:>7,d} placed on one tile",
              flush=True)
    got = out.sum()
    print(f"\n{total:,.0f} people in the conterminous states and DC")
    print(f"  {spread + dropped:,.0f} occupied blocks; "
          f"{dropped / (spread + dropped):.1%} were smaller than a 480 m cell "
          "and went to the tile holding their interior point")
    if abs(got - total) > 1.0:
        raise SystemExit(f"lost {total - got:,.0f} people on the lattice")
    print(f"  the lattice holds {got:,.0f}, which is all of them")
    nz = out > 0
    print(f"  {nz.sum():,d} of {out.size:,d} cells have a resident "
          f"({nz.mean():.1%} of the country)")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    np.save(OUT, out.astype(np.float32))
    print(f"-> {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size / 1e6:,.0f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
