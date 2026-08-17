"""Which ground is in a market at all, cell by cell.

The land surface this project draws is a model of fair market value, and it
predicts one for every 480 m of the country -- including ground that has no
market and no owner who could sell it.  Sampled straight out of the raster:
the north rim of the Grand Canyon at $1.32m per km2, the White Sands Missile
Range at $1.17m, the interior of Yellowstone at $1.04m.  None of that is for
sale.  All of it was in the numerator of the land-versus-output ratio, against
a denominator of almost nothing, which is most of why the American West came
out as the brownest ground in the country.

This script builds the correction: the share of each 480 m cell that is in
private hands, from the USGS Protected Areas Database, PAD-US 4.1, whose
raster analysis file classifies every 30 m of the conterminous states by who
manages it.  Two things are treated as outside the market: land the National Park Service
manages, and military installations -- 2.3% of the lower 48 between them.
Everything else keeps its modelled price, including the Forest Service and BLM
holdings that make up most of the federal estate.  That is a judgement rather
than a fact.  Taking out everything a government manages, which an earlier
version did, is defensible on the letter of "could this be sold" and removes
31.9% of the country, almost all of it in the West; taking out only the parks
and the bases keeps the ground that is leased, logged and grazed, and where a
value is at least arguable.

The output is a share rather than a mask because a 480 m cell can be half a
national forest and half a town.  What consumes it, src/land/
make_us_cartogram.py, multiplies each cell's modelled value by its private
share before summing tiles, so the map's land value becomes the value of land
that could actually change hands.

Writes data/land/us_private_share.npy, one byte per cell of the 480 m lattice.
"""

import struct
import sys
from pathlib import Path

import numpy as np
import rasterio
import rasterio.windows

ROOT = Path(__file__).resolve().parents[2]
IN = ROOT / "data" / "land" / "inputs"
DATA = ROOT / "data" / "land"
PADUS = IN / "padus" / "PADUS4_1_Raster_CONUS.img"
VAT = IN / "padus" / "PADUS4_1_Raster_CONUS.img.vat.dbf"

# The 480 m CONUS Albers lattice everything here is cut on.  Kept in step with
# GRID in make_us_cartogram.py.
X0, Y1, RES, NX, NY = -2357205.0, 3173925.0, 480.0, 9618, 6054

# Only ground that is genuinely withdrawn from any market: the national parks
# and monuments the Park Service runs, and military installations.  An earlier
# version took out everything a government manages -- Forest Service, BLM,
# state trust land, tribal land, 31.9% of the country -- which is defensible
# on the letter of "could this be sold" and takes out most of the West.  These
# two are 2.3% and are the ones nobody would argue about.
PUBLIC_MANAGERS = ("NPS", "DOD")
PUBLIC_DESIGNATIONS = ("MIL",)
ROWS = 32                      # target rows done at a time


def manager_lookup():
    """value -> True if that PAD-US class is outside the ordinary market.

    The raster's values index a 307,052-row attribute table, read here with a
    small DBF parser rather than a dependency.
    """
    f = open(VAT, "rb")
    n, hdr, rl = struct.unpack("<IHH", f.read(32)[4:12])
    fields, pos = [], 1
    while True:
        d = f.read(32)
        if d[0:1] == b"\r":
            break
        fields.append((d[:11].rstrip(b"\x00").decode(), d[16], pos))
        pos += d[16]
    f.seek(hdr)
    a = np.frombuffer(f.read(n * rl), dtype=np.uint8).reshape(n, rl)
    at = {name: (p, ln) for name, ln, p in fields}

    def col(name, width):
        p, ln = at[name]
        return np.frombuffer(a[:, p:p + ln].tobytes(),
                             dtype=f"S{ln}").astype(str)

    value = np.array([int(x) if x.strip() else -1
                      for x in col("Value", 10)])
    out = (np.isin(np.char.strip(col("Mang_Name", 70)), PUBLIC_MANAGERS)
           | np.isin(np.char.strip(col("Des_Tp", 75)), PUBLIC_DESIGNATIONS))
    lut = np.zeros(int(value.max()) + 1, dtype=bool)
    lut[value[out]] = True
    print(f"{n:,d} raster classes; {int(out.sum()):,d} of them are a national "
          "park or a military installation")
    return lut


def main():
    if not PADUS.exists():
        sys.exit(f"missing {PADUS} -- run src/land/fetch_inputs.py first")
    lut = manager_lookup()
    src = rasterio.open(PADUS)
    if abs(src.res[0] - 30.0) > 1e-6:
        sys.exit("PAD-US is not on a 30 m grid")

    # Where each 480 m boundary of the target lattice falls in the source.
    # The two grids share a projection but not an origin, so the edges are
    # rounded to the nearest 30 m cell; the error is a fraction of a cell.
    cx = np.round((X0 + np.arange(NX + 1) * RES - src.transform.c) / 30.0)
    ry = np.round((src.transform.f - (Y1 - np.arange(NY + 1) * RES)) / 30.0)
    cx = np.clip(cx, 0, src.width).astype(np.int64)
    ry = np.clip(ry, 0, src.height).astype(np.int64)

    share = np.full((NY, NX), 255, dtype=np.uint8)
    print(f"{src.width:,d} x {src.height:,d} cells of 30 m -> {NX:,d} x "
          f"{NY:,d} of {RES:.0f} m")
    for a in range(0, NY, ROWS):
        b = min(a + ROWS, NY)
        r0, r1 = ry[a], ry[b]
        if r1 <= r0 or cx[NX] <= cx[0]:
            continue
        arr = src.read(1, window=rasterio.windows.Window(
            cx[0], r0, cx[NX] - cx[0], r1 - r0))
        pub = lut[np.clip(arr, 0, len(lut) - 1)]
        seen = arr > 0
        # Sum along columns then along rows, both with reduceat, which is one
        # C call each -- 15 billion cells will not survive anything slower.
        def block(x):
            q = np.add.reduceat(x.astype(np.int32), cx[:NX] - cx[0], axis=1)
            return np.add.reduceat(q, ry[a:b] - r0, axis=0)
        n_pub, n_seen = block(pub), block(seen)
        priv = np.where(n_seen > 0, 1.0 - n_pub / np.maximum(n_seen, 1), 1.0)
        share[a:b] = np.round(np.clip(priv, 0, 1) * 255).astype(np.uint8)
        if (a // ROWS) % 30 == 0:
            print(f"  row {a:,d} of {NY:,d}", flush=True)

    np.save(DATA / "us_private_share.npy", share)
    frac = share.astype(np.float64) / 255.0
    print(f"\n{100*(1-frac.mean()):.1f}% of the lattice is managed outside the "
          f"market; {int((share < 128).sum()):,d} of {NY*NX:,d} cells are more "
          "than half public")
    print("-> data/land/us_private_share.npy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
