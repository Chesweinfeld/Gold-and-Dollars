"""Copy the built figures into the public site repository.

The maps live in two places on purpose.  This repository is the treasure-fleet
project and keeps its name; `american-land` is a second repository that exists
only to be a URL a reader can open, served by GitHub Pages from its root.  The
figures are built here and published there.

Doing that by hand is how a site comes to disagree with the code that made it:
one metro gets missed, or the national map is copied and the cuts it links to
are not, and the page 404s for exactly the reader who clicked the link.  So it
is a script, and it copies the whole set or none of it.

    python3 src/land/publish_maps.py                 # ~/Desktop/american-land
    python3 src/land/publish_maps.py <path>          # or say where

The checkout used to sit in a session scratchpad under /private/tmp, which is
swept: it lost .git/HEAD mid-session and every git command in it failed until
the file was written back by hand.  It lives on the Desktop now, and the
default below is that path, so a rebuild cannot quietly publish into a copy
that is about to be deleted.

It only copies.  Committing and pushing stay manual, because publishing is a
decision and should be made by a person.
"""
import filecmp
import shutil
import sys
from pathlib import Path

SITE = Path("~/Desktop/american-land")
ROOT = Path(__file__).resolve().parents[2]
FIG = ROOT / "docs" / "figures"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from make_us_cartogram import cut_slugs      # noqa: E402


def main(argv):
    site = Path(argv[1] if len(argv) > 1 else SITE).expanduser().resolve()
    if not (site / ".git").is_dir():
        raise SystemExit(f"{site} is not a git repository")
    (site / "figures").mkdir(parents=True, exist_ok=True)

    # The national map is the front door, so it is the site's index.html.  The
    # cuts keep their own names under figures/, which is what the national
    # page's own links expect: see the `prefix` in make_us_cartogram.
    want = [(FIG / "land_value_cartogram_us.html", site / "index.html"),
            (FIG / "preview_land_value_us.png",
             site / "figures" / "preview_land_value_us.png")]
    for slug in cut_slugs().values():
        f = FIG / f"land_value_cartogram_{slug}.html"
        want.append((f, site / "figures" / f.name))

    missing = [str(a.relative_to(ROOT)) for a, _ in want if not a.exists()]
    if missing:
        raise SystemExit("build these first, or the site will link to pages "
                         "that are not there:\n  " + "\n  ".join(missing))

    changed = 0
    for a, b in want:
        if b.exists() and filecmp.cmp(a, b, shallow=False):
            continue
        shutil.copy2(a, b)
        changed += 1
        print(f"  {b.relative_to(site)}")
    print(f"{changed} of {len(want)} files updated in {site}")
    if changed:
        print("now, in that repository: git add -A && git commit && git push")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
