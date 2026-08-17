"""Could the American map be built for the rest of the world?

The US cartogram exists because one country has both the raw material (six
million geocoded arm's-length land sales) and someone who did the work.  The
question this script answers is how much of the world's land value sits in
countries where the same thing is possible, and what the obstacle is where it
is not.

Countries are sorted into four tiers by what a stranger can actually obtain:

  parcel   an official value for individual parcels, published or queryable
  zone     official land values for sub-municipal areas -- price zones,
           reference points, roadside values -- but not per parcel
  sales    no official valuation surface, but open transaction microdata with
           enough location to train a model, which is what the US map is
  none     nothing public at national scale

The tier is about *access*, not about whether a valuation exists.  Almost every
country with a property tax values land; the ones in `none` keep it inside the
tax administration.

The weights come from data/land/land_value_2020.csv, so the shares are shares
of this repository's own estimate of world land value, with all the modelling
caveats that carries.  Every source URL is re-checked when the script runs and
the HTTP status goes into the output, so a link that has rotted is visible
rather than implied.

Writes data/land/parcel_feasibility.csv.
"""

import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data" / "land"

# iso3, tier, what exists, url
SOURCES = [
    ("KOR", "parcel", "Individual official land price (개별공시지가) for every "
     "parcel, annual, SHP and CSV",
     "https://www.data.go.kr/data/15029071/standard.do"),
    ("RUS", "parcel", "Cadastral value per parcel on the public cadastral map; "
     "queryable, no bulk export",
     "https://pkk.rosreestr.ru/"),
    ("ESP", "parcel", "Valor de referencia per parcel since 2022, with a land "
     "component; query-only",
     "https://www.sedecatastro.gob.es/"),
    ("DNK", "parcel", "Grundværdi (land value) per property, public valuation "
     "register",
     "https://datafordeler.dk/dataoversigt/ejendomsvurdering-vur/"),
    ("AUS", "parcel", "Unimproved land value per parcel from state Valuers-"
     "General; NSW publishes bulk, other states vary",
     "https://www.valuergeneral.nsw.gov.au/land_value_summaries/lvsearch.php"),
    ("NZL", "parcel", "Land value per rating unit in council valuation rolls; "
     "national layer via LINZ",
     "https://data.linz.govt.nz/layer/105689/"),
    ("LTU", "parcel", "Mass valuation land values per parcel, Registrų centras",
     "https://www.registrucentras.lt/masvert/"),
    ("JPN", "parcel", "Rosenka (路線価) assign a land value to every street "
     "frontage, plus the L01/L02 valuation points",
     "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-L01-v3_0.html"),
    ("CAN", "parcel", "Provincial assessment rolls carry land value; BC "
     "publishes, Ontario does not",
     "https://bcassessment.ca/"),

    ("DEU", "zone", "Bodenrichtwerte: an official land value per price zone, "
     "nationwide through BORIS-D, open in most states",
     "https://www.bodenrichtwerte-boris.de/"),
    ("ITA", "zone", "OMI zones give a value band per micro-zone per use class",
     "https://www.agenziaentrate.gov.it/portale/schede/fabbricatiterreni/omi"),
    ("EST", "zone", "Land value zones from the 2022 revaluation, Maa-amet",
     "https://geoportaal.maaamet.ee/est/ruumiandmed/maa-hindamine-p309.html"),
    ("IND", "zone", "Circle rates / guidance values per locality, published "
     "state by state in incompatible formats",
     "https://igrs.rajasthan.gov.in/"),
    ("IDN", "zone", "NJOP land value classes per zone for property tax",
     "https://www.pajak.go.id/"),
    ("BRA", "zone", "Planta genérica de valores per municipality; a few large "
     "cities publish the per-square-metre land table",
     "http://dados.prefeitura.sp.gov.br/dataset/iptu"),
    ("CZE", "zone", "Municipal cenové mapy where they exist, plus the national "
     "valuation decree tables",
     "https://www.cuzk.cz/"),
    ("ZAF", "zone", "Municipal valuation rolls are public by statute; format "
     "and land/improvement split vary by municipality",
     "https://www.cogta.gov.za/"),

    ("FRA", "sales", "DVF: every transaction since 2014, with parcel id and "
     "coordinates, fully open",
     "https://files.data.gouv.fr/geo-dvf/latest/csv/"),
    ("GBR", "sales", "Price Paid Data: every registered sale, address-level, "
     "open licence",
     "https://use-land-property-data.service.gov.uk/datasets/price-paid"),
    ("NLD", "sales", "WOZ values are per address but price the property, not "
     "the land; Kadaster sells the transaction file",
     "https://www.wozwaardeloket.nl/"),
    ("SWE", "sales", "Taxeringsvärde splits out markvärde per property, but "
     "Lantmäteriet charges for the file",
     "https://www.lantmateriet.se/"),
    ("NOR", "sales", "Registered sale prices per property in the cadastre, "
     "licensed rather than open",
     "https://www.kartverket.no/"),
    ("FIN", "sales", "Kauppahintarekisteri, the price register of real estate "
     "transactions",
     "https://www.maanmittauslaitos.fi/"),
    ("CHE", "sales", "Cantonal transaction registers; no federal series",
     "https://www.bfs.admin.ch/"),
    ("AUT", "sales", "Kaufpreissammlung, obtainable per district for a fee",
     "https://www.bev.gv.at/"),
    ("CHN", "sales", "State land grants are published transaction by "
     "transaction with area and price on the national land market site",
     "https://www.landchina.com/"),
    ("POL", "sales", "Rejestr cen nieruchomości, per-county, patchy",
     "https://www.gov.pl/web/gugik"),
    ("MEX", "sales", "Valores catastrales per state; a handful of states "
     "publish, most do not",
     "https://www.inegi.org.mx/"),
    ("USA", "sales", "No national valuation roll; the map in this directory "
     "exists because six million sales were assembled privately and modelled",
     "https://doi.org/10.1073/pnas.2012865117"),
]

TIER_ORDER = ["parcel", "zone", "sales", "none"]


def main():
    vals = pd.read_csv(DATA / "land_value_2020.csv").set_index("iso3")
    world = float(vals.total_land_usd.sum())

    df = pd.DataFrame(SOURCES, columns=["iso3", "tier", "what", "url"])
    df["country"] = vals.country.reindex(df.iso3).values
    df["land_usd"] = vals.total_land_usd.reindex(df.iso3).values
    missing = df[df.land_usd.isna()]
    if len(missing):
        print("no land-value figure for:", ", ".join(missing.iso3))
    df["share"] = df.land_usd / world

    df["http"] = check(df.url.tolist())
    df = df.sort_values(["tier", "share"], ascending=[True, False],
                        key=lambda s: s.map(
                            {t: i for i, t in enumerate(TIER_ORDER)}).fillna(s)
                        if s.name == "tier" else s)

    covered = df.groupby("tier").share.sum()
    listed = float(df.share.sum())

    print(f"World land value in this repository's series: "
          f"${world/1e12:,.0f}tn across {len(vals)} countries\n")
    print(f"{'tier':8s} {'countries':>9s} {'share of world land value':>26s}")
    for t in TIER_ORDER[:-1]:
        n = int((df.tier == t).sum())
        print(f"{t:8s} {n:9d} {covered.get(t, 0.0):25.1%}")
    print(f"{'none':8s} {len(vals)-len(df):9d} {1-listed:25.1%}")
    print(f"\nA US-style map is buildable today from open data over "
          f"{covered.get('parcel', 0)+covered.get('zone', 0):.0%} of world land "
          f"value without modelling, and over "
          f"{listed:.0%} if transactions are modelled the way Nolte modelled "
          f"the United States.")

    dead = df[~df.http.isin([200, 301, 302, 403])]
    if len(dead):
        print("\nsources that did not answer from this network:")
        for _, r in dead.iterrows():
            print(f"  {r.iso3} {r.http}  {r.url}")

    out = df[["iso3", "country", "tier", "land_usd", "share", "what",
              "url", "http"]]
    out.to_csv(DATA / "parcel_feasibility.csv", index=False)
    print(f"\n-> data/land/parcel_feasibility.csv ({len(out)} rows)")
    return 0


def check(urls):
    """Ask each source whether it is still there.

    403 counts as alive -- several of these hosts refuse a bare request but
    serve a browser.  0 means the connection was refused or reset, which for
    the Russian and Indian registries is what this network gets rather than
    evidence about the registry.
    """
    def one(u):
        p = subprocess.run(
            ["curl", "-sS", "-o", "/dev/null", "-w", "%{http_code}", "-L",
             "--max-time", "25", "-A", "Mozilla/5.0", u],
            capture_output=True, text=True)
        try:
            return int(p.stdout.strip())
        except ValueError:
            return 0
    with ThreadPoolExecutor(8) as pool:
        return list(pool.map(one, urls))


if __name__ == "__main__":
    raise SystemExit(main())
