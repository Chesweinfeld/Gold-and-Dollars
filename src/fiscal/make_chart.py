"""Small multiples: registered silver output vs treasury receipts, per caja.

Both measures are in pesos, so they share one log-log space and the implied
severance rate reads directly off the diagonal. Circular rows (output derived
from receipts) sit exactly on a diagonal — the point of the second colour.
"""

import math

import pandas as pd

W, H = 214, 176           # panel box
PL, PR, PT, PB = 40, 10, 22, 30   # panel padding
COLS = 4

# log10 peso bounds, shared by every panel. Data spans 10^0.3–10^6.9, so these
# cover it with no point outside the plot rect and no wasted empty decades.
LO, HI = 0.0, 7.0


def sx(v):
    return PL + (math.log10(v) - LO) / (HI - LO) * (W - PL - PR)


def sy(v):
    return H - PB - (math.log10(v) - LO) / (HI - LO) * (H - PT - PB)


def panel(caja, g, idx):
    parts = [f'<g class="panel" transform="translate({(idx % COLS) * (W + 14)},'
             f'{(idx // COLS) * (H + 16)})">']
    parts.append(f'<rect class="pbg" x="{PL}" y="{PT}" width="{W-PL-PR}" '
                 f'height="{H-PT-PB}" rx="3"/>')
    # iso-rate diagonals: receipts = rate x output
    for rate, lab in ((0.20, "20%"), (0.10, "10%")):
        x1, y1 = LO, LO + math.log10(rate)
        x2, y2 = HI, HI + math.log10(rate)
        parts.append(
            f'<line class="iso" x1="{sx(10**x1):.1f}" y1="{sy(10**y1):.1f}" '
            f'x2="{sx(10**x2):.1f}" y2="{sy(10**y2):.1f}"/>')
        if idx == 0:
            parts.append(f'<text class="isolab" x="{sx(10**(HI-0.15)):.1f}" '
                         f'y="{sy(10**(HI-0.15+math.log10(rate))):.1f}" dy="-3">{lab}</text>')
    for _, r in g.iterrows():
        cls = "derived" if r.likely_derived else "measured"
        parts.append(
            f'<circle class="pt {cls}" cx="{sx(r.output_pesos):.1f}" '
            f'cy="{sy(r.tax_pesos8):.1f}" r="3.1" '
            f'data-c="{caja}" data-y="{int(r.year)}" '
            f'data-o="{r.output_pesos:,.0f}" data-t="{r.tax_pesos8:,.0f}" '
            f'data-r="{r.implied_tax_rate:.3f}"/>')
    # axes
    parts.append(f'<line class="axis" x1="{PL}" y1="{H-PB}" x2="{W-PR}" y2="{H-PB}"/>')
    parts.append(f'<line class="axis" x1="{PL}" y1="{PT}" x2="{PL}" y2="{H-PB}"/>')
    for e in (3, 5, 7):
        parts.append(f'<text class="tick" x="{sx(10**e):.1f}" y="{H-PB+11}">10<tspan dy="-4" font-size="7">{e}</tspan></text>')
        parts.append(f'<text class="tick ytick" x="{PL-5}" y="{sy(10**e):.1f}" dy="3">10<tspan dy="-4" font-size="7">{e}</tspan></text>')
    med = g.loc[~g.likely_derived, "implied_tax_rate"].median()
    sub = f"n={len(g)} · {int(g.year.min())}–{int(g.year.max())}"
    if pd.notna(med):
        sub += f" · med {med:.0%}"
    parts.append(f'<text class="ptitle" x="{PL}" y="14">{caja}</text>')
    parts.append(f'<text class="psub" x="{PL}" y="{H-4}">{sub}</text>')
    parts.append("</g>")
    return "".join(parts)


def main():
    j = pd.read_csv("joined_output_vs_fiscal.csv")
    d = j[(j.match == "both") & (j.output_pesos > 0) & (j.tax_pesos8 > 0)].copy()
    order = d.groupby("caja").size().sort_values(ascending=False).index.tolist()

    panels = "".join(panel(c, d[d.caja == c].sort_values("year"), i)
                     for i, c in enumerate(order))
    rows = (COLS - 1 + len(order)) // COLS
    svg_w, svg_h = COLS * (W + 14), rows * (H + 16)

    tbl = (d.groupby("caja")
             .agg(years=("year", "size"), first=("year", "min"), last=("year", "max"),
                  median_rate=("implied_tax_rate", "median"),
                  circular=("likely_derived", "sum"))
             .sort_values("years", ascending=False).reset_index())
    trs = "".join(
        f"<tr><td>{r.caja}</td><td>{r.years}</td><td>{int(r.first)}–{int(r.last)}</td>"
        f"<td>{r.median_rate:.1%}</td><td>{int(r.circular)}</td></tr>"
        for r in tbl.itertuples())

    n_meas, n_der = int((~d.likely_derived).sum()), int(d.likely_derived.sum())

    html = f"""<div class="viz-root">
<style>
.viz-root {{
  color-scheme: light;
  --surface-1:#fcfcfb; --panel:#f4f3f0;
  --text-primary:#0b0b0b; --text-secondary:#52514e; --text-muted:#78766f;
  --measured:#2a78d6; --derived:#eb6834; --rule:#c9c7c0;
  background:var(--surface-1); color:var(--text-primary);
  font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif;
  padding:20px; max-width:100%;
}}
@media (prefers-color-scheme: dark) {{
  :root:where(:not([data-theme="light"])) .viz-root {{
    color-scheme: dark;
    --surface-1:#1a1a19; --panel:#242423;
    --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8d84;
    --measured:#3987e5; --derived:#d95926; --rule:#46453f;
  }}
}}
:root[data-theme="dark"] .viz-root {{
  color-scheme: dark;
  --surface-1:#1a1a19; --panel:#242423;
  --text-primary:#fff; --text-secondary:#c3c2b7; --text-muted:#8f8d84;
  --measured:#3987e5; --derived:#d95926; --rule:#46453f;
}}
.viz-root h1 {{ font-size:17px; margin:0 0 4px; font-weight:650; }}
.viz-root p.sub {{ font-size:13px; color:var(--text-secondary); margin:0 0 14px; max-width:76ch; line-height:1.5; }}
.legend {{ display:flex; gap:18px; flex-wrap:wrap; align-items:center; margin:0 0 14px; font-size:12.5px; color:var(--text-secondary); }}
.key {{ display:inline-flex; align-items:center; gap:6px; }}
.dot {{ width:10px; height:10px; border-radius:50%; display:inline-block; }}
.scroller {{ overflow-x:auto; }}
.pbg {{ fill:var(--panel); }}
.axis {{ stroke:var(--rule); stroke-width:1; }}
.iso {{ stroke:var(--rule); stroke-width:1.5; stroke-dasharray:3 3; }}
.isolab {{ fill:var(--text-muted); font-size:9px; text-anchor:end; }}
.tick {{ fill:var(--text-muted); font-size:9px; text-anchor:middle; }}
.ytick {{ text-anchor:end; }}
.ptitle {{ fill:var(--text-primary); font-size:12px; font-weight:600; }}
.psub {{ fill:var(--text-muted); font-size:9.5px; }}
.pt {{ stroke:var(--panel); stroke-width:1.4; cursor:pointer; }}
.pt.measured {{ fill:var(--measured); }}
.pt.derived  {{ fill:var(--derived); }}
.pt:hover {{ stroke:var(--text-primary); stroke-width:1.6; }}
#tip {{ position:fixed; pointer-events:none; opacity:0; transition:opacity .1s;
  background:var(--surface-1); color:var(--text-primary); border:1px solid var(--rule);
  border-radius:6px; padding:7px 9px; font-size:12px; line-height:1.45;
  box-shadow:0 4px 14px rgba(0,0,0,.16); z-index:50; }}
#tip b {{ font-weight:650; }}
.viz-root details {{ margin-top:18px; font-size:13px; color:var(--text-secondary); }}
.viz-root table {{ border-collapse:collapse; margin-top:10px; font-size:12px; }}
.viz-root th, .viz-root td {{ text-align:right; padding:3px 10px; border-bottom:1px solid var(--rule); }}
.viz-root th:first-child, .viz-root td:first-child {{ text-align:left; }}
.viz-root th {{ color:var(--text-secondary); font-weight:600; }}
</style>

<h1>Registered silver output vs. treasury receipts, by caja</h1>
<p class="sub">Each point is one caja-year: registered production (TePaske 2010) on the horizontal,
silver severance-tax receipts booked by the treasury (Colmex <i>caja real</i> accounts) on the vertical.
Both axes are pesos on a log scale, so the dashed diagonals are fixed tax rates and a point's
distance between them <em>is</em> its effective rate.</p>

<div class="legend">
  <span class="key"><span class="dot" style="background:var(--measured)"></span> Independently measured ({n_meas:,} caja-years)</span>
  <span class="key"><span class="dot" style="background:var(--derived)"></span> Output derived from receipts — circular ({n_der:,})</span>
  <span class="key" style="color:var(--text-muted)">– – –&nbsp; iso-rate lines at 20% (quinto) and 10% (diezmo)</span>
</div>

<div class="scroller">
<svg viewBox="0 0 {svg_w} {svg_h}" width="{svg_w}" height="{svg_h}" role="img"
     aria-label="Small multiple scatter plots of silver output against tax receipts for each treasury district">
{panels}
</svg>
</div>

<details><summary>Table view</summary>
<table><thead><tr><th>Caja</th><th>Caja-years</th><th>Span</th><th>Median rate</th><th>Circular rows</th></tr></thead>
<tbody>{trs}</tbody></table>
</details>

<div id="tip"></div>
<script>
(function(){{
  var tip=document.getElementById('tip');
  document.querySelectorAll('.viz-root .pt').forEach(function(el){{
    el.addEventListener('mouseenter',function(e){{
      var d=el.dataset;
      tip.innerHTML='<b>'+d.c+' &middot; '+d.y+'</b><br>output '+d.o+' pesos<br>receipts '+d.t+
                    ' pesos<br>rate '+(parseFloat(d.r)*100).toFixed(1)+'%';
      tip.style.opacity=1;
    }});
    el.addEventListener('mousemove',function(e){{
      tip.style.left=Math.min(e.clientX+14, window.innerWidth-190)+'px';
      tip.style.top=(e.clientY+14)+'px';
    }});
    el.addEventListener('mouseleave',function(){{ tip.style.opacity=0; }});
  }});
}})();
</script>
</div>"""
    with open("silver_output_vs_receipts.html", "w", encoding="utf-8") as fh:
        fh.write(html)
    print(f"{len(d):,} points across {len(order)} cajas -> silver_output_vs_receipts.html")


if __name__ == "__main__":
    main()
