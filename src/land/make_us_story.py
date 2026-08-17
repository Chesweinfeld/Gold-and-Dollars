"""The land-versus-output map, told as a scrolled story.

The flat map at `make_us_cartogram.py usratioflat` shows all 533,958 squares at
once, which is the honest way to publish it and a poor way to read it.  This
script draws the same tiles, from the same buffers and the same colour scale --
it shares `_scene` with that figure precisely so the two can never diverge --
and flies a camera over them while the reader scrolls.

Every number quoted in the prose is computed here, from the tiles, at build
time.  Nothing in the text is typed by hand.  If either surface is rebuilt the
sentences move with it, or the build fails; what cannot happen is a caption
that has quietly stopped being true.

The stops were chosen by mining the tiles for extremes and then checking each
candidate at neighbourhood scale, which killed several of them: single squares
in the mountains and at Disney World read as dramatic outliers and turn out to
be artefacts of where a tile boundary happens to fall.  What survives is the
set below.  Three of the stops exist to show where the map is at its weakest,
because a tour of a dataset that only visits its successes is advertising.

Writes docs/figures/land_vs_output_story_us.html.
"""

import json
import sys
from pathlib import Path

import numpy as np
from pyproj import Transformer

sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_us_cartogram import (   # noqa: E402
    DIVERGE, FIG, MAX_ZOOM, NOVAL, REGIONS, _areas, _esc, _gdp_tiles, _GL_JS,
    _scene,
    build_mesh, cities, pack_points, state_borders, tile_values,
)

CUT = "usratioflat"      # the story is the flat map; the cartogram is a figure
DATA = Path(__file__).resolve().parents[2] / "data" / "land"


def main():
    r = REGIONS[CUT]
    value, geo, real = tile_values(r["block"], r["window"], r["src"],
                                   private=r["diverge"])
    lattice, tiles, quads = build_mesh(value)
    borders, postal = state_borders(
        geo, flat=r["flat"], cell=geo["tx"] * geo["side"] / r["nx"])
    city_name, city_xy = cities(geo, 420)
    pts, bidx, midx, lab0 = pack_points(lattice, geo, borders, city_xy)
    tile_value = value.ravel()[tiles]
    s = _scene(r, geo, tiles, quads, pts, len(lattice), bidx, postal,
               city_name, lab0, real.ravel()[tiles], tile_value,
               _areas(pts, quads))

    land = value                       # (ty, tx) dollars of land
    out = _gdp_tiles(geo)              # (ty, tx) dollars of output a year
    fine = _gdp_tiles(geo, kinds=(0,))  # the part of it placed by workplace
    base = tile_value.sum() / out.ravel()[tiles].sum()

    stats = Stats(geo, land, out, base, s, fine)
    steps = build_steps(stats)
    write(s, steps, stats, geo)
    return 0


# --- reading the tiles ----------------------------------------------------

class Stats:
    """Totals over a square box of tiles, plus that box in page pixels.

    Everything the prose says comes through here.  A box is quoted with its
    own width in kilometres, because the same place answers differently at
    different scales -- a resort town is brown across three squares and teal
    across nine, once the box has swallowed the town that works in it.
    """

    def __init__(self, geo, land, out, base, scene, fine):
        self.geo, self.land, self.out, self.base = geo, land, out, base
        # `fine` is the workplace-allocated part.  A square with none of it is
        # the grey on the map: its output is county data spread by population
        # and land cover, so no ratio is drawn for it.
        self.fine = fine
        self.scene, self.side = scene, geo["side"]
        self.fwd = Transformer.from_crs("EPSG:4326", "EPSG:5070",
                                        always_xy=True)

    def rc(self, lon, lat):
        x, y = self.fwd.transform(lon, lat)
        return (int((self.geo["y1"] - y) // self.side),
                int((x - self.geo["x0"]) // self.side))

    def px(self, lon, lat):
        x, y = self.fwd.transform(lon, lat)
        p = self.scene["to_px"](np.array([[x, y]]))
        return float(p[0, 0]), float(p[0, 1])

    def tile_rect(self, lon, lat, dr, dc, nr, nc):
        """A rectangle in page pixels, snapped to whole tiles.

        The marker on the map has to be the same squares the numbers were
        summed over, not a circle drawn near them, so it is built from the
        tile grid rather than from the point.
        """
        r, c = self.rc(lon, lat)
        r, c = r + dr, c + dc
        x0 = self.geo["x0"] + c * self.side
        y1 = self.geo["y1"] - r * self.side
        p = self.scene["to_px"](np.array([[x0, y1],
                                          [x0 + nc * self.side,
                                           y1 - nr * self.side]]))
        return [round(float(p[0, 0]), 1), round(float(p[0, 1]), 1),
                round(float(p[1, 0] - p[0, 0]), 1),
                round(float(p[1, 1] - p[0, 1]), 1)]

    def box(self, lon, lat, k=0):
        """Totals over the (2k+1)² tiles centred on a point."""
        r, c = self.rc(lon, lat)
        sl = (slice(max(r - k, 0), r + k + 1), slice(max(c - k, 0), c + k + 1))
        lv, gd = self.land[sl], self.out[sl]
        has_land = lv > 0
        tot_l, tot_g = float(lv.sum()), float(gd.sum())
        return dict(
            land=tot_l, gdp=tot_g,
            years=(tot_l / tot_g if tot_g else float("nan")),
            rel=(tot_l / tot_g / self.base if tot_g else float("nan")),
            tiles=int(has_land.sum()),
            grey=int((has_land & (self.fine[sl] <= 0)).sum()),
            # How lumpy the output is inside the box: the share of it sitting
            # on the single busiest square, and on the busiest three.  Where
            # the allocation has piled a county's output onto whichever
            # squares hold an office, this is the number that shows it.
            top1=(float(gd.max() / tot_g) if tot_g else float("nan")),
            top3=(float(np.sort(gd, axis=None)[-3:].sum() / tot_g)
                  if tot_g else float("nan")),
            km=(2 * k + 1) * self.side / 1000.0)

    def biggest_brown(self, years):
        """The largest connected run of squares above `years`, by land value.

        The story calls one place the biggest brown thing in the country.
        Rather than take that on trust it is computed: label every group of
        touching squares whose ratio is above the threshold, and take the group
        holding the most land value.  If the data changes, so does the answer.
        """
        from scipy import ndimage
        has = self.out > 0
        ratio = np.where(has, self.land / np.maximum(self.out, 1), 0.0)
        m = has & (ratio > years) & (self.land > 2e8)
        lab, k = ndimage.label(m, structure=np.ones((3, 3)))
        if not k:
            raise SystemExit("no brown component found; check the surfaces")
        sums = ndimage.sum(self.land, lab, range(1, k + 1))
        i = int(np.argmax(sums)) + 1
        cy, cx = ndimage.center_of_mass(self.land, lab, i)
        inv = Transformer.from_crs("EPSG:5070", "EPSG:4326", always_xy=True)
        lon, lat = inv.transform(self.geo["x0"] + (cx + 0.5) * self.side,
                                 self.geo["y1"] - (cy + 0.5) * self.side)
        sel = lab == i
        lv, gd = float(self.land[sel].sum()), float(self.out[sel].sum())
        runner = float(np.sort(sums)[-2]) if k > 1 else 0.0
        return dict(lon=lon, lat=lat, tiles=int(sel.sum()), land=lv, gdp=gd,
                    years=lv / gd, rel=lv / gd / self.base, runner=runner)

    def ring_direction(self, cbds, inner, outer):
        """How many of these metros are browner at the edge than at the core.

        The pooled table could hide a couple of cities running the other way,
        so the claim that the gradient is general is counted rather than
        assumed.
        """
        ty, tx = self.land.shape
        rr, cc = np.mgrid[0:ty, 0:tx]
        n = 0
        for lon, lat in cbds:
            r0, c0 = self.rc(lon, lat)
            d = np.hypot(rr - r0, cc - c0) * self.side / 1000.0
            def band(a, b):
                m = (d >= a) & (d < b)
                g = float(self.out[m].sum())
                return float(self.land[m].sum()) / g if g else np.nan
            if band(*outer) > band(*inner):
                n += 1
        return n

    def rings(self, cbds, edges):
        """Pooled land and output in distance bands around a list of downtowns.

        Pooled rather than averaged: an average over metros would let a small
        city with an odd county boundary weigh as much as New York.
        """
        ty, tx = self.land.shape
        rr, cc = np.mgrid[0:ty, 0:tx]
        best = np.full((ty, tx), np.inf)
        for lon, lat in cbds:
            r0, c0 = self.rc(lon, lat)
            d = np.hypot(rr - r0, cc - c0) * self.side / 1000.0
            best = np.minimum(best, d)
        rows = []
        for a, b in zip(edges[:-1], edges[1:]):
            m = (best >= a) & (best < b)
            lv, gd = float(self.land[m].sum()), float(self.out[m].sum())
            rows.append((a, b, lv, gd, lv / gd, lv / gd / self.base))
        return rows


def money(x):
    if x >= 1e12:
        return f"${x/1e12:,.2f}tn"
    if x >= 1e9:
        return f"${x/1e9:,.1f}bn"
    if x >= 1e6:
        return f"${x/1e6:,.0f}m"
    return f"${x:,.0f}"


def rel(x):
    """A multiple of the national figure, said the way round that reads."""
    return f"{x:,.1f}&times;" if x >= 1 else f"1/{1/x:,.1f}"


def yrs(x):
    return f"{x*365:,.0f} days" if x < 1 else f"{x:,.1f} years"


# --- the stops ------------------------------------------------------------

# Twelve metropolitan downtowns, for the distance-band table.  They are the
# largest by output; the point of pooling them is that the gradient below is
# not one city's accident.
CBDS = [(-73.984, 40.755), (-87.628, 41.879), (-118.263, 34.059),
        (-96.797, 32.780), (-84.388, 33.755), (-112.074, 33.448),
        (-71.058, 42.342), (-122.331, 47.622), (-104.985, 39.740),
        (-83.045, 42.331), (-95.369, 29.760), (-75.163, 39.952)]


# One coordinate per place, and one only.  The statistics box, the rectangle
# drawn on the map and the camera all read from the same tuple, so the marker
# cannot end up sitting somewhere other than the ground the sentence is about.
MID = (-73.984, 40.755)      # Midtown Manhattan
LIC = (-73.943, 40.757)      # Long Island City, the next square east
UNS = (-73.998, 40.731)      # Union Square and the Village
WIL = (-73.953, 40.723)      # Williamsburg, the next square east again
ATH = (-122.202, 37.456)     # Atherton and Menlo Park
NAN = (-70.05, 41.29)        # Nantucket
ASP = (-106.82, 39.19)       # Aspen and the Roaring Fork
IOW = (-94.93, 41.72)        # Audubon County, Iowa
DET = (-83.045, 42.331)      # downtown Detroit
CHI = (-87.628, 41.879)      # the Chicago Loop
LOV = (-103.57, 31.85)       # Loving County, Texas
USA = (-96.5, 39.5)          # nowhere in particular; the national views fit


def build_steps(st):
    """The tour.  Numbers come from `st`; only the sentences are written."""
    B = st.base
    mid, lic, uns, wil = (st.box(*q) for q in (MID, LIC, UNS, WIL))
    ath = st.box(*ATH)
    nan, asp, iow = (st.box(*q, 3) for q in (NAN, ASP, IOW))
    det, chi, lov = (st.box(*q, 3) for q in (DET, CHI, LOV))
    # Not asserted: the biggest brown mass is found by connected components,
    # so the claim below is whatever the tiles actually say it is.
    brown = st.biggest_brown(4.0)
    HAM = (brown["lon"], brown["lat"])
    ham = st.box(*HAM, 3)
    rings = st.rings(CBDS, [0, 5, 15, 30, 50, 80])
    core, edge = rings[0], rings[-1]
    n_up = st.ring_direction(CBDS, (0, 5), (50, 80))
    # What share of national output is still placed by workplace, read off the
    # allocation itself rather than quoted from build_us_gdp.py.
    z = np.load(DATA / "us_gdp_points.npz")
    jobs_share = float(z["gdp"][z["kind"] == 0].sum() / z["gdp"].sum())

    def step(place, km, title, body, mark=None, kind="", fit=False):
        """One stop: where to look, how wide, and what to say there.

        `fit` frames the whole drawing box instead of a distance, so the two
        national views sit on the map's own extent rather than on a guess at
        how many kilometres wide the country is.
        """
        lon, lat = place
        mx, my = st.px(lon, lat)
        span = st.scene["bx"][2] - st.scene["bx"][0]
        pxm = st.scene["W"] / span                    # page pixels per metre
        hx = hy = km * 500 * pxm
        # The card sits over the left third of the screen, so the camera looks
        # from west of its subject and the place being discussed lands in the
        # clear part of the frame.  The two national views are exempt: they are
        # framed on the map's own extent and have nowhere to shift to.
        cx, cy = (mx - 0.30 * hx), my
        if fit:
            cx, cy = st.scene["W"] / 2, st.scene["H"] / 2
            hx, hy = st.scene["W"] / 2, st.scene["H"] / 2
        return dict(cx=round(cx, 1), cy=round(cy, 1),
                    hx=round(hx, 2), hy=round(hy, 2),
                    mark=(st.tile_rect(lon, lat, *mark) if mark else None),
                    title=title, body=body, kind=kind)

    return [
        step(USA, 0, fit=True,
             title="One number, half a million times",
             body=f"Divide what the land in a square is worth by the output "
             f"produced on it in a year. Dollars over dollars-a-year leaves "
             f"<b>years</b>: how long the work on that ground would have to "
             f"run to equal the price of the ground itself. It is a "
             f"price-to-earnings ratio, with the land as the asset. For the "
             f"whole of the lower 48 the answer is <b>{B:.2f}</b> — American "
             f"land is worth about four months of what is made on it. Here is "
             f"every 3.84 km square of ground in the country against that "
             f"figure. The blank areas are the national parks and the military "
             f"bases &mdash; 1.4% of the lower 48, the ground with no market "
             f"at all &mdash; which the land model prices anyway and this map "
             f"does not. "
             f"<b class='teal'>Teal</b> is cheap for the work it carries; "
             f"<b class='brown'>brown</b> costs more than the work explains."),

        step(MID, 62,
             "Two squares, one river",
             f"Start where the ground is dearest. This square of Midtown "
             f"Manhattan holds <b>{money(mid['land'])}</b> of land. The next "
             f"square east, across the East River in Long Island City, holds "
             f"<b>{money(lic['land'])}</b> — very slightly more. By price they "
             f"are the same ground.<br><br>They are not the same colour. "
             f"Midtown produces {money(mid['gdp'])} a year and comes out at "
             f"{yrs(mid['years'])}; Long Island City produces "
             f"{money(lic['gdp'])} and comes out at {yrs(lic['years'])}. "
             f"<b>{lic['years']/mid['years']:.0f}× apart</b>, on identically "
             f"priced dirt. Two squares south the same trick repeats: the "
             f"Village at {yrs(uns['years'])} against Williamsburg at "
             f"{yrs(wil['years'])}, <b>{wil['years']/uns['years']:.0f}× "
             f"apart</b> on land within "
             f"{abs(wil['land']/uns['land']-1)*100:.0f}% of the same value.",
             mark=(0, 0, 1, 2), kind="pair"),

        step(MID, 31,
             "The teal is the expensive part",
             f"That is the reading to break first: dear ground is not brown "
             f"ground. This one square carries <b>{money(mid['gdp'])}</b> of "
             f"output a year — more than most states — and its "
             f"{money(mid['land'])} of land is {rel(mid['rel'])} the national "
             f"figure, which is to say it is <i>cheap</i> for what stands on "
             f"it. The most expensive dirt in America is at the teal end of "
             f"the scale, and it is there for the same reason the steel ground "
             f"of the Cleveland Flats is &mdash; the work standing on it "
             f"dwarfs the price of it.",
             mark=(0, 0, 1, 1), kind="teal"),

        step(ATH, 105,
             "The sixth most valuable square in the country",
             f"Atherton and Menlo Park, on the Peninsula. "
             f"<b>{money(ath['land'])}</b> of land — sixth in the nation, "
             f"ahead of every square in Boston, Seattle or Washington — "
             f"carrying {money(ath['gdp'])} of output. That is "
             f"{yrs(ath['years'])}, <b>{rel(ath['rel'])}</b> the national "
             f"figure. Silicon Valley's money is made a few squares north and "
             f"east of here; this ground is where it is <i>housed</i>. "
             f"Housing does produce output on this map — the rent tenants pay "
             f"and the rent the BEA imputes to owner-occupiers for living in "
             f"their own houses — but a house earns a small fraction of its "
             f"price in a year, so a square that is only houses is brown "
             f"however dear the houses are.",
             mark=(0, 0, 1, 1), kind="brown"),

        step(HAM, 150,
             "The largest brown thing in America",
             f"Take every square whose ratio is over four years, join the ones "
             f"that touch, and weigh each clump by the land in it. The heaviest "
             f"is the South Fork of Long Island: <b>{brown['tiles']} squares</b> "
             f"holding <b>{money(brown['land'])}</b> of land and producing "
             f"{money(brown['gdp'])} a year — <b>{yrs(brown['years'])}</b>, "
             f"{rel(brown['rel'])} the national figure. The runner-up, the "
             f"Connecticut shore, holds {money(brown['runner'])}: this one is "
             f"nearly twice the size of anything else in the country.<br><br>"
             f"The 27 km box drawn here works out at {yrs(ham['years'])}, "
             f"{rel(ham['rel'])}. Nothing much is produced on any of it. The "
             f"price is what people will pay to be here in August.",
             mark=(-3, -3, 7, 7), kind="brown"),

        step(NAN, 165,
             "And the farthest gone",
             f"Nantucket and Martha's Vineyard, {nan['km']:.0f} km of it: "
             f"{money(nan['land'])} of land against {money(nan['gdp'])} of "
             f"output, <b>{yrs(nan['years'])}</b> — {rel(nan['rel'])} the "
             f"national figure. {nan['grey']} of the {nan['tiles']} squares "
             f"with land on them are grey. Grey does not mean nothing is "
             f"produced there. It means no workplace stands on that square, "
             f"so the only output the map can put on it is county GDP spread "
             f"by where the people and the fields are — a county-wide rate, "
             f"the same on every acre inside the line. That is not a number "
             f"about a 3.84 km square, so none is drawn.",
             mark=(-3, -3, 7, 7), kind="brown"),

        step(ASP, 260,
             "Where the expectation breaks",
             f"So the resort towns should be the brownest ground in America. "
             f"They are not. Aspen and the Roaring Fork valley, over the same "
             f"{asp['km']:.0f} km box: {money(asp['land'])} of land, "
             f"{money(asp['gdp'])} of output, <b>{yrs(asp['years'])}</b> — "
             f"{rel(asp['rel'])} the national figure, but less than a third as "
             f"far out as the Hamptons.<br><br>A ski resort is an industry, "
             f"and it stands on the same squares as the expensive houses. A "
             f"beach colony's expensive land has nothing on it but houses. "
             f"That is the whole difference. Note the blank ground around the "
             f"town: most of this mountain is national forest. An earlier "
             f"version of this map priced it, because the land model does "
             f"&mdash; it puts $1.04m per km&sup2; on the interior of "
             f"Yellowstone. It is not for sale, and it is now left out.",
             mark=(-3, -3, 7, 7), kind="mixed"),

        step(IOW, 430,
             "Why the corn belt is grey",
             f"Audubon County, Iowa — some of the most productive farmland on "
             f"earth, and <b>{iow['grey']} of its {iow['tiles']} squares here "
             f"are left grey</b>.<br><br>Add the box up and it comes to "
             f"{money(iow['land'])} of land against {money(iow['gdp'])} of "
             f"output, {yrs(iow['years'])}, {rel(iow['rel'])} the national "
             f"figure. That number is fine at the size of a county and "
             f"meaningless at the size of a square. Farm output is measured "
             f"once a year for the whole county and then spread over its "
             f"acres at one rate; the rate is 21 times higher in the top tenth "
             f"of counties than the bottom tenth, and it changes at the county "
             f"line, not at the field. Drawn per square it made rectangles. "
             f"So the squares with no workplace on them are not coloured, and "
             f"what is left is the ground the map can actually resolve.",
             mark=(-3, -3, 7, 7), kind="caveat"),

        step(DET, 85,
             "Detroit is cheaper than the Loop",
             f"Downtown Detroit over {det['km']:.0f} km: {money(det['land'])} "
             f"of land carrying {money(det['gdp'])} of output — "
             f"<b>{yrs(det['years'])}</b>, {rel(det['rel'])} the national "
             f"figure. The same box on the Chicago Loop is "
             f"{yrs(chi['years'])}, {rel(chi['rel'])}. Chicago's ground costs "
             f"{chi['land']/det['land']:.0f} times as much and does "
             f"{chi['gdp']/det['gdp']:.0f} times the work, so by the ratio "
             f"Detroit is the better bargain of the two — it is teal on this "
             f"map for exactly the reason Midtown is.",
             mark=(-3, -3, 7, 7), kind="teal"),

        step(LOV, 210,
             "Where this map is worst",
             f"Loving County, Texas, in the Permian Basin — the highest GDP "
             f"per worker of any county in the United States. Over "
             f"{lov['km']:.0f} km it shows {money(lov['land'])} of land and "
             f"{money(lov['gdp'])} of output, a ratio of "
             f"{yrs(lov['years'])}.<br><br>Do not believe it. Mining, oil and "
             f"gas — nearly all of what this county does — is the one line "
             f"still placed by where the jobs are, and there are almost no "
             f"jobs out here. <b>{lov['top1']*100:.0f}% of the output in this "
             f"picture sits on one square</b> and {lov['top3']*100:.0f}% on "
             f"three, while <b>{lov['grey']} of the {lov['tiles']} squares</b> "
             f"have no workplace at all and are grey. The oil comes out of the "
             f"ground across the whole frame and the map puts the money where "
             f"the office is. The few coloured squares here are the artefact, "
             f"and they are the reason this stop exists.",
             mark=(-3, -3, 7, 7), kind="caveat"),

        step((-96.797, 32.780), 260,
             "The one pattern that repeats everywhere",
             f"Pool the twelve largest downtowns and sort every square by how "
             f"far it sits from one of them. The ratio climbs the whole way "
             f"out: <b>{rel(core[5])}</b> the national figure within 5 km of a "
             f"downtown, {rel(rings[1][5])} at 5–15 km, {rel(rings[2][5])} at "
             f"15–30 km, {rel(rings[3][5])} at 30–50 km, and "
             f"<b>{rel(edge[5])}</b> at 50–80 km — a factor of "
             f"{edge[4]/core[4]:.1f} from the middle of a city to its edge, and "
             f"the same direction in {n_up} of the {len(CBDS)} metros taken "
             f"one at a time.<br><br>It is the cleanest structure in the "
             f"data, and it survives the obvious objection. Housing is not "
             f"missing from the denominator here: the rent on every dwelling "
             f"in the ring is counted on the ground the dwelling stands on. "
             f"The suburb still costs more years than it earns, because what "
             f"a house earns in a year is small beside what work earns on the "
             f"same square foot downtown.",
             kind="mixed"),

        step(USA, 0, fit=True,
             title="What it is, and what it is not",
             body=f"Land is Nolte's 2020 model of fair market value, trained on six "
             f"million sales, at 480 m. Output is the Bureau of Economic "
             f"Analysis's county GDP for 2023, placed inside each county by "
             f"where the thing that produces it stands: the output of "
             f"dwellings on the people, agriculture on the farmed hectares, "
             f"and the other {100*jobs_share:.0f}% on the jobs. Both surfaces "
             f"are the best available at this resolution and neither is a "
             f"measurement of a 3.84 km square.<br><br>This is not GDP per "
             f"person. It is not a rate of return. It is not a claim that "
             f"anything is over- or under-priced. It is two national surfaces "
             f"divided by each other, and the interesting thing about it is "
             f"that the quotient has so much structure."),
    ]


# --- the page -------------------------------------------------------------

def write(s, steps, st, geo):
    FIG.mkdir(parents=True, exist_ok=True)
    B = st.base
    html = _PAGE.format(
        W=f"{s['W']:.0f}", H=f"{s['H']:.0f}", n=len(s["draw"]),
        maxk=f"{MAX_ZOOM:.0f}",
        km2=f"{(geo['side']/1000.0)**2:.6f}", base=f"{B:.6f}",
        data=json.dumps(s["payload"]), borders=json.dumps(s["borders"]),
        metros=json.dumps([]),   # the story has no metro layer
        labels=json.dumps(s["labels"]), towns=json.dumps(s["towns"]),
        ramp=json.dumps(DIVERGE), noval=json.dumps(NOVAL),
        ramp_css=", ".join(f"{c} {i/(len(DIVERGE)-1)*100:.0f}%"
                           for i, c in enumerate(DIVERGE)),
        steps=json.dumps(steps),
        teal=DIVERGE[0], brown=DIVERGE[-1], noval_css=NOVAL,
        baseline=f"{B:.2f}",
        title=_esc("Dear ground, cheap ground"),
    )
    out = FIG / "land_vs_output_story_us.html"
    out.write_text(html, encoding="utf-8")
    print(f"\n{len(steps)} stops over {len(s['draw']):,d} tiles")
    print(f"-> docs/figures/{out.name} ({len(html)/1e6:.1f} MB)")


_PAGE = """<!doctype html>
<meta charset="utf-8">
<title>{title}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
:root {{
  color-scheme: light dark;
  --ink:#14171a; --muted:#5b6570; --bg:#ffffff; --line:#d8dee6;
  --panel:rgba(255,255,255,0.97); --teal:{teal}; --brown:{brown};
  --mapbg:#ffffff; --mapink:#14171a;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --ink:#e8ecf1; --muted:#9aa6b2; --bg:#0f1216; --line:#2a323c;
           --panel:rgba(14,17,22,0.96); }}
}}
* {{ box-sizing:border-box; }}
html {{ scroll-behavior:auto; }}
body {{ margin:0; background:var(--bg); color:var(--ink);
  font:16px/1.6 ui-sans-serif,-apple-system,"Segoe UI",Roboto,Helvetica,sans-serif;
  -webkit-font-smoothing:antialiased; }}
#scroller {{ position:relative; }}
#sticky {{ position:sticky; top:0; height:100svh; overflow:hidden; }}
/* The map keeps a light ground and dark ink in either theme, so that the
   held-back tiles and the black outlines read the same way at night. */
#stage {{ position:absolute; inset:0; background:var(--mapbg); }}
/* Held back so the coast and the state lines sit over the data rather than
   under it; the tiles are still the thing being read. */
#cv {{ position:absolute; inset:0; width:100%; height:100%; display:block;
  opacity:.74; }}
.ov {{ position:absolute; inset:0; width:100%; height:100%;
  pointer-events:none; }}
.sb {{ fill:none; stroke:#000; stroke-opacity:.62; stroke-width:.9;
  vector-effect:non-scaling-stroke; stroke-linejoin:round; }}
/* Held back from the city names, as in the figure: the codes are there to
   orient the reader, not to be read.  Sizes are set from the JS at draw time;
   these are the ones that apply before the first frame. */
.sl {{ fill:var(--mapink); font-size:11px; font-weight:600; text-anchor:middle;
  paint-order:stroke; stroke:var(--mapbg); stroke-opacity:.7;
  stroke-width:2.6px; stroke-linejoin:round; opacity:.5; }}
.tn {{ fill:var(--mapink); font-size:12px; font-weight:600; text-anchor:middle;
  paint-order:stroke; stroke:var(--mapbg); stroke-width:3.5px;
  stroke-linejoin:round; }}
.td {{ fill:var(--mapbg); stroke:var(--mapink); stroke-width:1;
  vector-effect:non-scaling-stroke; }}
#mk {{ fill:none; stroke:var(--mapink); stroke-width:2;
  vector-effect:non-scaling-stroke; opacity:0; }}
#hud {{ display:none; }}
#tip {{ position:absolute; pointer-events:none; opacity:0; z-index:6;
  background:var(--panel); border:1px solid var(--line); border-radius:8px;
  padding:7px 10px; font-size:12.5px; line-height:1.45;
  backdrop-filter:blur(8px); transition:opacity .12s; max-width:250px; }}
/* The text rides above the map: one card per stop, each a screen tall. */
#steps {{ position:relative; z-index:4; margin-top:-100svh; }}
.step {{ min-height:100svh; display:flex; align-items:center;
  padding:0 6vw; pointer-events:none; }}
.step:first-child, .step:last-child {{ min-height:120svh; }}
.card {{ max-width:390px; background:var(--panel); border:1px solid var(--line);
  border-radius:14px; padding:20px 22px; pointer-events:auto;
  backdrop-filter:blur(10px); box-shadow:0 10px 34px rgba(0,0,0,.13);
  opacity:.18; transform:translateY(14px);
  transition:opacity .35s ease, transform .35s ease; }}
.card.on {{ opacity:1; transform:none; }}
.card h2 {{ margin:0 0 9px; font-size:20px; line-height:1.25;
  letter-spacing:-.01em; }}
.card p {{ margin:0; font-size:14.5px; line-height:1.62; color:var(--ink); }}
.still #steps {{ display:none; }}
.still #prog {{ display:none; }}
#still {{ display:none; position:fixed; left:6vw; top:50%; z-index:9;
  transform:translateY(-50%); max-width:390px; }}
.still #still {{ display:block; }}
.card .no {{ font-size:11px; letter-spacing:.09em; text-transform:uppercase;
  color:var(--muted); margin:0 0 7px; }}
b.teal {{ color:var(--teal); }} b.brown {{ color:var(--brown); }}
/* The scale sits in a corner and never moves. */
#key {{ position:fixed; right:14px; bottom:14px; z-index:7; width:250px;
  background:var(--panel); border:1px solid var(--line); border-radius:10px;
  padding:10px 12px; font-size:11px; color:var(--muted);
  backdrop-filter:blur(8px); }}
#key .bar {{ height:9px; border-radius:3px; margin-bottom:4px;
  background:linear-gradient(90deg,{ramp_css}); }}
#key .ends {{ display:flex; justify-content:space-between;
  font-variant-numeric:tabular-nums; }}
#key .lab {{ margin-top:6px; line-height:1.45; }}
#key i {{ background:{noval_css}; width:9px; height:9px; display:inline-block;
  border-radius:2px; vertical-align:-1px; font-style:normal; }}
#prog {{ position:fixed; left:0; top:0; height:2px; z-index:8; width:0;
  background:var(--ink); opacity:.4; }}
#end {{ padding:14vh 6vw 12vh; max-width:66ch; margin:0 auto;
  color:var(--muted); font-size:14px; border-top:1px solid var(--line); }}
#end a {{ color:inherit; }}
#end b {{ color:var(--ink); }}
@media (max-width:720px) {{
  .step {{ align-items:flex-end; padding:0 4vw 8vh; }}
  .card {{ max-width:none; }}
  #key {{ display:none; }}
}}
</style>
<div id="prog"></div>
<div id="scroller">
  <div id="sticky">
    <div id="stage">
      <canvas id="cv"></canvas>
      <svg class="ov" id="ov" preserveAspectRatio="none">
        <g id="sc"><g id="bd"></g><g id="lb"></g><g id="tw"></g>
          <rect id="mk"/></g>
      </svg>
      <div id="tip"></div>
      <div id="hud"></div>
      <div id="still"></div>
    </div>
  </div>
  <div id="steps"></div>
</div>
<div id="key">
  <div class="bar"></div>
  <div class="ends"><span>cheap for the work</span><span>dear for it</span></div>
  <div class="lab">land value &divide; a year of the output on it, against the
    national {baseline} years. <i></i> no workplace: county data only.</div>
</div>
<div id="end">
  <b>Sources.</b> Land: Nolte (2020), PLACES fair-market-value model, 480&nbsp;m,
  2020 dollars, land only. Output: BEA county GDP 2023, allocated within each
  county by Census LEHD LODES workplace job counts. Both surfaces are cut to the
  same 3.84&nbsp;km lattice in EPSG:5070, which is equal-area, so no square is
  bigger than another. Alaska and Hawaii are outside the land source.<br><br>
  <b>Every figure quoted above is computed from the tiles at build time</b> by
  <code>src/land/make_us_story.py</code>, which draws from the same buffers as
  the full map. The full map, the cartogram version, the per-tile CSV and the
  accuracy checks are in the repository.
</div>
<script>
""" + _GL_JS + """

// --- the camera ---------------------------------------------------------
// view.k / view.ox / view.oy are the same uniforms the flat figure uses; the
// only difference is that here they are driven by scroll rather than a mouse.
// u_size is the visible rectangle in map units, so it has to follow the shape
// of the viewport rather than the shape of the map.
const STOPS={steps};
let VW=W, VH=H;
const stepsEl=document.getElementById('steps');
stepsEl.innerHTML=STOPS.map((s,i)=>
  `<section class="step"><div class="card">`+
  `<p class="no">${{i===0?'':(i)+' / '+(STOPS.length-2)}}</p>`+
  `<h2>${{s.title}}</h2><p>${{s.body}}</p></div></section>`).join('');
const cards=[...document.querySelectorAll('.card')];
const sections=[...document.querySelectorAll('.step')];
const mk=document.getElementById('mk');

function frameOf(s) {{
  const k=Math.min(VW/(2*s.hx), VH/(2*s.hy));
  return {{k:k, cx:s.cx, cy:s.cy}};
}}
let cam={{k:1,cx:0,cy:0}};

function apply() {{
  view.k=cam.k;
  view.ox=VW/2-cam.cx*cam.k;
  view.oy=VH/2-cam.cy*cam.k;
  draw();
}}

function resize() {{
  const r=stage.getBoundingClientRect();
  if(!r.width) return;
  const dpr=Math.min(devicePixelRatio||1,2);
  cv.width=Math.round(r.width*dpr); cv.height=Math.round(r.height*dpr);
  VW=W; VH=W*r.height/r.width;
  ov.setAttribute('viewBox',`0 0 ${{VW}} ${{VH}}`);
  onScroll();
}}
new ResizeObserver(resize).observe(stage);

function draw() {{
  if(!ready||!cv.width) return;
  gl.viewport(0,0,cv.width,cv.height);
  gl.bindFramebuffer(gl.FRAMEBUFFER,null);
  gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT);
  gl.uniform2f(uSize,VW,VH);
  gl.uniform1f(uK,view.k); gl.uniform2f(uO,view.ox,view.oy);
  gl.uniform1f(uPick,0.0);
  gl.drawElements(gl.TRIANGLES,count,gl.UNSIGNED_INT,0);
  sc.setAttribute('transform',
    `translate(${{view.ox}},${{view.oy}}) scale(${{view.k}})`);
  // Text in the overlay holds its size on screen, so it is divided by the
  // zoom and by the viewBox-to-CSS ratio, exactly as on the static figure.
  const rect=stage.getBoundingClientRect();
  const s=(rect.width ? VW/rect.width : 1)/view.k;
  for(const t of document.querySelectorAll('.sl')) {{
    t.style.fontSize=(13*s)+'px'; t.style.strokeWidth=(3*s)+'px';
  }}
  for(const t of document.querySelectorAll('.tn')) {{
    t.style.fontSize=(12*s)+'px'; t.style.strokeWidth=(3.5*s)+'px';
  }}
  for(const c of document.querySelectorAll('.td')) c.setAttribute('r',2*s);
  for(const g of document.querySelectorAll('.tg'))
    g.style.display = view.k >= +g.dataset.k ? '' : 'none';
  mk.setAttribute('stroke-width', 2*s);
  pickDirty=true;
}}

// The camera holds still over the first third of a card and the last quarter,
// and travels in between, so the reader is never asked to read a moving map.
function ease(t) {{
  t=Math.min(Math.max((t-0.34)/0.42,0),1);
  return t*t*(3-2*t);
}}
function onScroll() {{
  const mid=scrollY+innerHeight/2;
  // Measured against the page, not the offset parent: the step column is
  // pulled up over the sticky map by a negative margin, so offsetTop lies.
  const anchors=sections.map(el=>{{
    const r=el.getBoundingClientRect();
    return scrollY+r.top+r.height/2;
  }});
  let i=0;
  while(i<anchors.length-1 && anchors[i+1]<=mid) i++;
  let t=0;
  if(i<anchors.length-1)
    t=(mid-anchors[i])/Math.max(anchors[i+1]-anchors[i],1);
  t=ease(Math.min(Math.max(t,0),1));
  const a=frameOf(STOPS[i]), b=frameOf(STOPS[Math.min(i+1,STOPS.length-1)]);
  // Zoom moves in log, position in a straight line: the standard way to keep
  // a fly-over from lurching when the two ends are orders of magnitude apart.
  cam.k=Math.exp(Math.log(a.k)+(Math.log(b.k)-Math.log(a.k))*t);
  cam.cx=a.cx+(b.cx-a.cx)*t; cam.cy=a.cy+(b.cy-a.cy)*t;
  const near=t<0.5?i:Math.min(i+1,STOPS.length-1);
  cards.forEach((c,j)=>c.classList.toggle('on',j===near));
  const s=STOPS[near];
  if(s.mark) {{
    mk.setAttribute('x',s.mark[0]); mk.setAttribute('y',s.mark[1]);
    mk.setAttribute('width',s.mark[2]); mk.setAttribute('height',s.mark[3]);
    mk.setAttribute('rx',Math.min(s.mark[2],s.mark[3])*0.10);
    mk.style.opacity=0.85*(1-Math.abs(t-(near===i?0:1))*1.6);
  }} else mk.style.opacity=0;
  document.body.dataset.at=near+' k='+cam.k.toFixed(2)+' y='+Math.round(scrollY)
    +' ready='+ready+' sec='+sections.length;
  const h=document.documentElement.scrollHeight-innerHeight;
  document.getElementById('prog').style.width=
    (100*Math.min(scrollY/Math.max(h,1),1))+'%';
  apply();
}}
addEventListener('scroll',()=>requestAnimationFrame(onScroll),{{passive:true}});
addEventListener('resize',resize);

// #s3 jumps to the fourth stop, so a particular place in the story can be
// linked to -- and so the page can be screenshotted stop by stop.
function jump() {{
  const m=/^#s(\d+)$/.exec(location.hash);
  if(!m) return;
  const el=sections[Math.min(+m[1],sections.length-1)];
  if(!el) return;
  const r=el.getBoundingClientRect();
  scrollTo({{top:scrollY+r.top+r.height*0.82-innerHeight/2,behavior:'instant'}});
  onScroll();
}}
addEventListener('hashchange',jump);

// ?stop=N freezes the page on one stop: no scrolling, the camera parked and
// that card alone on screen.  It is how the stills in docs/figures are made,
// and it is a link to a single beat of the story.
const STILL=/[?&]stop=(\d+)/.exec(location.search);
if(STILL) {{
  const i=Math.min(+STILL[1],STOPS.length-1), s=STOPS[i];
  document.body.classList.add('still');
  document.getElementById('still').innerHTML=
    `<div class="card on"><h2>${{s.title}}</h2><p>${{s.body}}</p></div>`;
  const f=frameOf(s);
  onScroll=function() {{
    const g=frameOf(STOPS[i]);
    cam.k=g.k; cam.cx=g.cx; cam.cy=g.cy;
    if(s.mark) {{
      mk.setAttribute('x',s.mark[0]); mk.setAttribute('y',s.mark[1]);
      mk.setAttribute('width',s.mark[2]); mk.setAttribute('height',s.mark[3]);
      mk.setAttribute('rx',Math.min(s.mark[2],s.mark[3])*0.10);
      mk.style.opacity=0.85;
    }}
    apply();
  }};
  cam.k=f.k; cam.cx=f.cx; cam.cy=f.cy;
}}
// Re-run while the tiles are still decompressing: the camera is set from the
// scroll position, and the scroll position has to survive layout settling.
if(location.hash) {{
  jump();
  addEventListener('load',jump);
  [120, 400, 1200].forEach(ms=>setTimeout(jump,ms));
}}

// Hover still reads a tile, because a story about a number should let you
// check the number.
let pickDirty=true, pickW=0, pickH=0, fb2=null, ftex2=null;
function pick(sx,sy) {{
  if(!ready) return 0;
  if(!fb2) {{ fb2=gl.createFramebuffer(); ftex2=gl.createTexture(); }}
  if(pickW!==cv.width||pickH!==cv.height) {{
    pickW=cv.width; pickH=cv.height; pickDirty=true;
    gl.bindTexture(gl.TEXTURE_2D,ftex2);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA,pickW,pickH,0,gl.RGBA,
                  gl.UNSIGNED_BYTE,null);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
  }}
  gl.bindFramebuffer(gl.FRAMEBUFFER,fb2);
  if(pickDirty) {{
    gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,
                            gl.TEXTURE_2D,ftex2,0);
    gl.viewport(0,0,pickW,pickH);
    gl.clearColor(0,0,0,0); gl.clear(gl.COLOR_BUFFER_BIT);
    gl.uniform1f(uPick,1.0);
    gl.drawElements(gl.TRIANGLES,count,gl.UNSIGNED_INT,0);
    gl.uniform1f(uPick,0.0);
    pickDirty=false;
  }}
  const px=new Uint8Array(4);
  gl.readPixels(Math.round(sx),Math.round(pickH-sy),1,1,gl.RGBA,
                gl.UNSIGNED_BYTE,px);
  gl.bindFramebuffer(gl.FRAMEBUFFER,null);
  return px[0]|(px[1]<<8)|(px[2]<<16);
}}
function money(x) {{
  if(x>=1e12) return '$'+(x/1e12).toFixed(2)+'tn';
  if(x>=1e9) return '$'+(x/1e9).toFixed(1)+'bn';
  if(x>=1e6) return '$'+(x/1e6).toFixed(0)+'m';
  return '$'+Math.round(x).toLocaleString();
}}
stage.addEventListener('pointermove',e=>{{
  const r=stage.getBoundingClientRect(), dpr=cv.width/r.width;
  const id=pick((e.clientX-r.left)*dpr,(e.clientY-r.top)*dpr);
  if(!id) {{ tip.style.opacity=0; return; }}
  const t=id-1, v=Math.pow(10,TVAL[t]/4096+3);
  const g=TGDP&&TGDP[t] ? Math.pow(10,TGDP[t]/4096+3) : 0;
  const yr=g? v/g : 0;
  tip.innerHTML=`<b>${{money(v)}}</b> of land<br><b>${{g?money(g):'&mdash;'}}</b>`+
    ` of output a year<br><span style="color:var(--muted)">`+
    (g? `worth <b>${{yr<1?Math.round(yr*365)+' days':yr.toFixed(1)+' years'}}</b>`+
        ` of it &mdash; ${{yr>=BASE?(yr/BASE).toFixed(1)+'&times;':'1/'+(BASE/yr).toFixed(1)}}`+
        ` the U.S. figure`
      : 'no workplace here: the output is county data only')+`</span>`;
  tip.style.opacity=1;
  const tw=tip.offsetWidth, th=tip.offsetHeight;
  tip.style.left=Math.min(Math.max(e.clientX-r.left+14,4),r.width-tw-4)+'px';
  tip.style.top=Math.min(Math.max(e.clientY-r.top-th-12,4),r.height-th-4)+'px';
}});
stage.addEventListener('pointerleave',()=>{{tip.style.opacity=0;}});
</script>
"""


if __name__ == "__main__":
    raise SystemExit(main())
