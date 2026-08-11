"""Vendor a world basemap small enough to ship in the page.

Natural Earth 1:110m admin-0, simplified and rounded, written as a compact
JSON the site parses directly. Natural Earth is public domain, so this can be
committed without a licence obligation, and vendoring it means the site loads
no third-party code at runtime.

Also emits a centroid per country. The centroid is taken from each country's
*largest* polygon, not from all of them area-weighted: weighting every polygon
puts the United States marker in British Columbia (Alaska drags it) and France
in the Atlantic (French Guiana drags it). Largest-polygon lands both on the
mainland, which is what a reader expects a country's dot to mean.

Usage:  python src/reserves/build_geometry.py
"""

import json
import math
import os

from common import SITE_DATA, ensure_dirs, finish, http_get, report

URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
       "master/geojson/ne_110m_admin_0_countries.geojson")

# Natural Earth writes ISO_A3 = "-99" for a handful of sovereignties; ADM0_A3
# carries a usable code for all of them.
PRECISION = 2
TOLERANCE = 0.30  # degrees; visually lossless at the sizes this map is drawn


def simplify(points, tol):
    """Douglas-Peucker. Rings are closed, so the endpoints are pinned."""
    if len(points) < 3:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        lo, hi = stack.pop()
        ax, ay = points[lo]
        bx, by = points[hi]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        worst, idx = 0.0, -1
        for i in range(lo + 1, hi):
            px, py = points[i]
            if norm == 0:
                d = math.hypot(px - ax, py - ay)
            else:
                d = abs(dy * px - dx * py + bx * ay - by * ax) / norm
            if d > worst:
                worst, idx = d, i
        if idx != -1 and worst > tol:
            keep[idx] = True
            stack.append((lo, idx))
            stack.append((idx, hi))
    return [p for p, k in zip(points, keep) if k]


def ring_area(ring):
    """Signed planar area in square degrees. Only used to rank rings by size."""
    a = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        a += x0 * y1 - x1 * y0
    return a / 2.0


def ring_centroid(ring):
    a = ring_area(ring)
    if abs(a) < 1e-12:
        xs = [p[0] for p in ring]
        ys = [p[1] for p in ring]
        return sum(xs) / len(xs), sum(ys) / len(ys)
    cx = cy = 0.0
    for i in range(len(ring) - 1):
        x0, y0 = ring[i]
        x1, y1 = ring[i + 1]
        cross = x0 * y1 - x1 * y0
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross
    return cx / (6 * a), cy / (6 * a)


def polygons(geometry):
    """Every outer ring in a Polygon or MultiPolygon, holes dropped. At 110m the
    only holes are Lesotho and the Vatican-scale enclaves; dropping them costs
    nothing visually and halves the parsing the page has to do."""
    kind = geometry["type"]
    if kind == "Polygon":
        return [geometry["coordinates"][0]]
    if kind == "MultiPolygon":
        return [poly[0] for poly in geometry["coordinates"]]
    return []


def main():
    ensure_dirs()
    print(f"GET {URL}")
    raw = json.loads(http_get(URL, timeout=180))
    print(f"  {len(raw['features'])} features")

    countries, dropped = [], 0
    points_in = points_out = 0
    for feat in raw["features"]:
        props = feat["properties"]
        iso3 = props.get("ISO_A3")
        if not iso3 or iso3 == "-99":
            iso3 = props.get("ADM0_A3")
        name = props.get("NAME_LONG") or props.get("NAME") or iso3
        if not iso3 or iso3 == "-99":
            dropped += 1
            continue

        rings = []
        for ring in polygons(feat["geometry"]):
            points_in += len(ring)
            small = simplify([(float(x), float(y)) for x, y in ring], TOLERANCE)
            if len(small) < 4:
                continue
            points_out += len(small)
            rings.append([[round(x, PRECISION), round(y, PRECISION)] for x, y in small])
        if not rings:
            dropped += 1
            continue

        biggest = max(rings, key=lambda r: abs(ring_area(r)))
        cx, cy = ring_centroid(biggest)
        countries.append(
            {
                "id": iso3,
                "name": name,
                "c": [round(cx, PRECISION), round(cy, PRECISION)],
                "r": rings,
            }
        )

    countries.sort(key=lambda c: c["id"])
    out = {
        "source": "Natural Earth 1:110m admin-0 (public domain)",
        "url": URL,
        "tolerance_deg": TOLERANCE,
        "precision_dp": PRECISION,
        "countries": countries,
    }
    path = os.path.join(SITE_DATA, "world.json")
    with open(path, "w") as fh:
        json.dump(out, fh, separators=(",", ":"))

    size = os.path.getsize(path)
    print(f"  -> site/data/world.json ({size / 1024:.0f} KB, {len(countries)} countries, "
          f"{dropped} without a usable ISO code)")

    print("\nValidation")
    report("geometry small enough to inline", size < 400_000, f"{size / 1024:.0f} KB")
    report("point reduction", points_out < points_in,
           f"{points_in:,} -> {points_out:,} ({points_out / points_in:.0%})")
    report("country count sane", 150 < len(countries) < 260, f"{len(countries)} countries")

    # Centroids must land inside a plausible box for a few known shapes; this is
    # the check that catches a lat/lon swap or a broken largest-ring pick.
    spot = {"USA": (-105, -90, 33, 45), "FRA": (-2, 8, 43, 51),
            "RUS": (30, 120, 50, 72), "CHN": (95, 118, 28, 42),
            "AUS": (128, 143, -28, -20)}
    bad = []
    index = {c["id"]: c["c"] for c in countries}
    for iso3, (x0, x1, y0, y1) in spot.items():
        c = index.get(iso3)
        if not c or not (x0 <= c[0] <= x1 and y0 <= c[1] <= y1):
            bad.append(f"{iso3}={c}")
    report("mainland centroids", not bad, "; ".join(bad) if bad else "USA FRA RUS CHN AUS on land")

    finish()


if __name__ == "__main__":
    main()
