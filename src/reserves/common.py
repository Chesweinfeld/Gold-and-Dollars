"""Shared fetch helper for the reserve-currency pipeline.

Python's default SSL context on this machine (miniforge) does not pick up
certifi's bundle, so a plain urlopen dies with CERTIFICATE_VERIFY_FAILED
against api.imf.org and api.worldbank.org. Try certifi first, fall back to
curl, which has the system roots and is what the rest of this repo uses.
"""

import os
import ssl
import subprocess
import sys
import time
import urllib.request

UA = "gold-and-dollars-reserve-map/1.0 (+https://github.com/Chesweinfeld/Gold-and-Dollars)"

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA = os.path.join(REPO, "data", "reserves")
SITE_DATA = os.path.join(REPO, "site", "data")


def _context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def http_get(url, timeout=90, tries=4):
    """Bytes at `url`, or raise. Retries with backoff; both hosts rate-limit."""
    last = None
    for attempt in range(tries):
        if attempt:
            time.sleep(2 ** attempt)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=_context()) as r:
                body = r.read()
            if body:
                return body
            last = "empty body"
        except Exception as exc:  # noqa: BLE001 - fall through to curl
            last = exc
        try:
            out = subprocess.run(
                ["curl", "-sL", "--max-time", str(timeout), "-A", UA, url],
                capture_output=True,
                check=True,
            ).stdout
            if out:
                return out
            last = "empty body (curl)"
        except subprocess.CalledProcessError as exc:
            last = exc
    raise RuntimeError(f"failed after {tries} tries: {url} ({last})")


def ensure_dirs():
    for d in (DATA, SITE_DATA):
        os.makedirs(d, exist_ok=True)


def report(label, ok, detail=""):
    """Every script in this repo prints its own validation report."""
    mark = "ok  " if ok else "FAIL"
    print(f"  [{mark}] {label}{(' — ' + detail) if detail else ''}")
    if not ok:
        report.failed = True


report.failed = False


def finish():
    if report.failed:
        print("\nVALIDATION FAILED — do not commit this output.")
        sys.exit(1)
    print("\nAll checks passed.")
