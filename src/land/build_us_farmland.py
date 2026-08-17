"""Where the farmland is, so that farm output can be put on it.

BEA reports agriculture, forestry, fishing and hunting -- CAGDP2 line 3, $269bn
-- for every county in the country.  Allocating it by workplace jobs, as the
rest of GDP is allocated, puts it in the wrong place twice over.  LODES counts
jobs covered by unemployment insurance, which excludes farm proprietors and
most farm labour, so the fields hold almost no jobs at all; what jobs the
industry does record sit at the co-op and the grain elevator in town.  The
result was that a quarter of the country's surface -- the part that literally
grows the crop -- carried no output at all.

This script builds the denominator that fixes it: the area of each kind of
productive ground in each cell of a 1.92 km grid, from the USDA Cropland Data
Layer, which classifies every 30 m of the country by what was on it.  Eleven
classes are counted and kept apart, so that a rate can be fitted to each rather
than asserted, and so the split can be inspected:

  row         corn, soybeans, cotton, rice, sorghum and the double crops.
  smallgrain  wheat, barley, oats, rye, millet, triticale.
  hay         alfalfa, other hay, clover, sod and switchgrass.
  veg         potatoes, tomatoes, lettuce, melons and the rest of the truck.
  orchard     apples, cherries, citrus, olives, stone fruit.
  nuts        almonds, walnuts, pecans, pistachios.
  vine        grapes, strawberries, blueberries, cranberries, caneberries.
  fallow      fallow and idle ground.
  pasture     grassland and pasture.
  range       shrubland -- sagebrush and scrub, grazed across most of the West.
  forest      deciduous, evergreen and mixed, which is what forestry happens on.

The crop classes were one class until the rates were checked against the
Census of Agriculture: an acre of vegetables sells for thirty times an acre of
wheat, and lumping them made every county with an orchard in it wrong.

Range and forest were not counted at first, and leaving them out was the single
biggest artefact in the map this feeds.  On a strip across western Nebraska the
crop map calls 56% of the ground shrubland and 22% evergreen forest: 78% of it
counted as nothing, producing nothing, while a neighbouring county whose
identical range the classifier happened to put in grassland took its county's
whole farm allocation.  Whether a county's rangeland lands in one class or the
other is a decision of the classifier, not a fact about the county, and the map
was drawing that decision as a hard edge at the county line.

What the classes cannot do is vary within a county: a county's farm output is
spread over its acres at fitted national rates per class, not at its own.
Between counties the difference is carried by the county figure itself, which
is measured.  That is the same limitation the jobs allocation has everywhere
else on this map.

The grid is 1.92 km rather than the 480 m base lattice because the output is a
point per cell and 480 m would be twenty million of them.  At 1.92 km each
tile of the national cut holds four, which is enough for a tile total.  A
metropolitan cut at 480 m should not lean on this file.

Writes data/land/us_farmland_cells.npz.
"""

import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
import rasterio.features
import rasterio.windows

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
CDL = IN / "cdl" / "2023_30m_cdls.tif"
COUNTIES = IN / "cb_2023_us_county_500k.zip"

# 64 CDL cells of 30 m to a side.
FACTOR = 64
STRIP = 512                      # the raster's own block height


# The classes, in the order they are stored.  What separates them is what an
# acre of each earns, which is the only thing this file exists to measure: an
# acre of almonds and an acre of wheat were both "crop" before, and were handed
# the same share of their county's farm output.  The gap between them is more
# than an order of magnitude, so that was the largest remaining lie in the
# farmland carrier.
KINDS = ("row", "smallgrain", "hay", "veg", "orchard", "nuts", "vine",
         "fallow", "pasture", "range", "forest")

# The published CDL legend, grouped.  Codes not named here -- developed, water,
# wetland, barren, cloud -- are other, and produce nothing.
# The double-crop codes are named one by one rather than swept as a range:
# 227 is lettuce and 229 pumpkins, and 230-233 are the lettuce double-crops,
# all of which belong with the vegetables.
_ROW = [1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 26, 31, 32, 33, 34, 35, 38, 39,
        41, 42, 43, 44, 45, 46, 51, 52, 53, 224,
        225, 226, 228, 234, 235, 236, 237, 238, 239, 240, 241]
_SMALLGRAIN = [21, 22, 23, 24, 25, 27, 28, 29, 30, 205]
_HAY = [36, 37, 58, 59, 60]
_VEG = [47, 48, 49, 50, 54, 55, 56, 57, 206, 207, 208, 209, 213, 214, 216,
        219, 222, 227, 229, 230, 231, 232, 233, 243, 244, 245, 246, 247, 248,
        249]
_ORCHARD = [66, 67, 68, 70, 71, 72, 77, 210, 211, 212, 215, 217, 218, 220, 223]
_NUTS = [74, 75, 76, 204]
_VINE = [69, 221, 242, 250]
_FALLOW = [61]
_PASTURE = [62, 176]
_RANGE = [64, 152]
_FOREST = [63, 141, 142, 143]
_GROUPS = (_ROW, _SMALLGRAIN, _HAY, _VEG, _ORCHARD, _NUTS, _VINE, _FALLOW,
           _PASTURE, _RANGE, _FOREST)


def classes():
    """A 256-entry lookup from CDL code to 0 = other, 1..len(KINDS) = a class."""
    assert len(_GROUPS) == len(KINDS)
    lut = np.zeros(256, dtype=np.uint8)
    seen = {}
    for i, codes in enumerate(_GROUPS):
        for c in codes:
            if c in seen:
                raise SystemExit(f"CDL code {c} is in two classes: "
                                 f"{KINDS[seen[c]]} and {KINDS[i]}")
            seen[c] = i
            lut[c] = i + 1
    # 65 and 73-80 and the rest of 78-203 are unassigned in the legend or are
    # not productive ground; leaving them at 0 is deliberate, not an omission.
    return lut


def main():
    if not CDL.exists():
        sys.exit(f"missing {CDL} -- run src/land/fetch_inputs.py first")
    src = rasterio.open(CDL)
    if src.crs.to_epsg() != 5070:
        sys.exit("the Cropland Data Layer is not in the Albers grid")

    ny, nx = src.height // FACTOR, src.width // FACTOR
    side = src.res[0] * FACTOR
    x0, y1 = src.transform.c, src.transform.f
    lut = classes()
    cells = np.zeros((len(KINDS), ny, nx), dtype=np.int32)

    print(f"{src.width:,d} x {src.height:,d} cells of 30 m -> "
          f"{nx:,d} x {ny:,d} of {side/1000:.2f} km")
    rows = STRIP - STRIP % FACTOR
    for a in range(0, ny * FACTOR, rows):
        b = min(a + rows, ny * FACTOR)
        arr = src.read(1, window=rasterio.windows.Window(
            0, a, nx * FACTOR, b - a))
        k = lut[arr].reshape((b - a) // FACTOR, FACTOR, nx, FACTOR)
        for i in range(len(KINDS)):
            cells[i, a // FACTOR:b // FACTOR] = (k == i + 1).sum(axis=(1, 3))
        if (a // rows) % 20 == 0:
            print(f"  row {a:,d} of {ny*FACTOR:,d}", flush=True)

    ha = (30.0 * 30.0) / 1e4
    print("\n" + "  ".join(f"{n} {cells[i].sum()*ha/1e6:,.1f}M ha"
                           for i, n in enumerate(KINDS)))

    # Which county each cell falls in.  Cells outside every county -- the
    # raster's Canadian and Mexican margin -- are dropped.
    g = gpd.read_file(f"zip://{COUNTIES}")
    g = g[~g.STATEFP.isin(["02", "15", "60", "66", "69", "72", "78"])]
    g = g.to_crs(5070).reset_index(drop=True)
    tr = rasterio.transform.from_origin(x0, y1, side, side)
    idx = rasterio.features.rasterize(
        ((geom, i + 1) for i, geom in enumerate(g.geometry)),
        out_shape=(ny, nx), transform=tr, fill=0, dtype="int32")

    iy, ix = np.nonzero((cells.sum(axis=0) > 0) & (idx > 0))
    out = dict(
        x=(x0 + (ix + 0.5) * side).astype("float32"),
        y=(y1 - (iy + 0.5) * side).astype("float32"),
        county=g.GEOID.to_numpy()[idx[iy, ix] - 1].astype("U5"),
    )
    for i, n in enumerate(KINDS):
        out[f"{n}_ha"] = (cells[i][iy, ix] * ha).astype("float32")
    np.savez_compressed(DATA / "us_farmland_cells.npz", **out)
    total = sum(out[f"{n}_ha"].sum() for n in KINDS)
    print(f"{len(iy):,d} cells carry productive ground in "
          f"{len(np.unique(out['county'])):,d} counties, {total/1e6:,.1f}M ha")
    print("-> data/land/us_farmland_cells.npz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
