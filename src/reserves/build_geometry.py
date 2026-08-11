"""Vendor a world basemap small enough to ship in the page.

Natural Earth 1:50m admin-0, simplified and rounded, written as a compact JSON
the site parses directly. Natural Earth is public domain, so this can be
committed without a licence obligation, and vendoring it means the site loads
no third-party code at runtime.

50m rather than 110m because the map now zooms. At the Europe view one degree
of latitude is about twelve pixels, so 110m's 0.30° simplification showed as a
three-pixel error on every coastline and swallowed most of the small states
outright — Singapore, Malta, Luxembourg, Hong Kong, all of them reserve holders.

The tolerance is per ring rather than global: `min(TOLERANCE, span / 25)`, so a
long coastline is thinned hard and a country a fifth of a degree across keeps
enough points to still be that country. A flat tolerance coarse enough to keep
the file small drops forty of them.

Holes are kept, so Lesotho is a hole in South Africa rather than something South
Africa paints over. The page draws each country's rings as one path with
fill-rule: evenodd, which needs no assumption about winding order.

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
       "master/geojson/ne_50m_admin_0_countries.geojson")

# Natural Earth writes ISO_A3 = "-99" for a handful of sovereignties; ADM0_A3
# carries a usable code for all of them.
PRECISION = 2     # 0.01 deg is a tenth of a pixel at the deepest zoom here
TOLERANCE = 0.10  # degrees, and less than that on anything small — see SPAN_DIV
SPAN_DIV = 25


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
    """Every ring in a Polygon or MultiPolygon, holes included. The page fills
    them with fill-rule: evenodd, so an enclave comes out as a hole without
    anyone having to trust Natural Earth's winding order."""
    kind = geometry["type"]
    if kind == "Polygon":
        return list(geometry["coordinates"])
    if kind == "MultiPolygon":
        return [ring for poly in geometry["coordinates"] for ring in poly]
    return []


def ring_tolerance(points):
    """Small countries are simplified less. A flat tolerance loose enough to
    keep the file shippable erases anything under about a degree across, and
    several of those hold serious reserves."""
    span = max(max(p[0] for p in points) - min(p[0] for p in points),
               max(p[1] for p in points) - min(p[1] for p in points))
    return min(TOLERANCE, span / SPAN_DIV)


def dedupe(points):
    """Rounding can put two neighbours on the same coordinate; a ring of three
    distinct points is not a shape."""
    out = [points[0]]
    for p in points[1:]:
        if p != out[-1]:
            out.append(p)
    return out


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
            pts = [(float(x), float(y)) for x, y in ring]
            small = simplify(pts, ring_tolerance(pts))
            if len(small) < 4:
                continue
            rounded = dedupe([[round(x, PRECISION), round(y, PRECISION)] for x, y in small])
            if len(rounded) < 4:
                continue
            points_out += len(rounded)
            rings.append(rounded)
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
        "source": "Natural Earth 1:50m admin-0 (public domain)",
        "url": URL,
        "tolerance_deg": TOLERANCE,
        "tolerance_span_div": SPAN_DIV,
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
    # Roughly 110 KB over the wire once Pages gzips it. Both pages fetch it.
    report("geometry small enough to ship", size < 600_000, f"{size / 1024:.0f} KB")
    report("point reduction", points_out < points_in,
           f"{points_in:,} -> {points_out:,} ({points_out / points_in:.0%})")
    report("country count sane", 200 < len(countries) < 280, f"{len(countries)} countries")

    # The small states are the reason for the per-ring tolerance; if the
    # adaptive step regresses they vanish silently and the map still looks fine.
    tiny = {"SGP": "Singapore", "HKG": "Hong Kong", "MLT": "Malta",
            "LUX": "Luxembourg", "BHR": "Bahrain", "CYP": "Cyprus"}
    have = {c["id"] for c in countries}
    missing = [n for k, n in tiny.items() if k not in have]
    report("small reserve holders kept", not missing,
           ", ".join(missing) if missing else "Singapore, Hong Kong, Malta, Luxembourg, Bahrain, Cyprus")

    # Enclaves only come out as holes if the hole rings survived.
    zaf = next((c for c in countries if c["id"] == "ZAF"), None)
    report("holes preserved", bool(zaf) and len(zaf["r"]) > 1,
           f"South Africa has {len(zaf['r']) if zaf else 0} rings (Lesotho is one of them)")

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
