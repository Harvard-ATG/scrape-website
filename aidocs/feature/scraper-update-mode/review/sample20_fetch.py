"""Fetch 20 pages (HTML and the served .md copy) from 4 hosts chosen from the 2026-10-15 XML sitemap snapshot.

Live: 2 GETs per page, 2 s apart (40 requests). Selection is deterministic: per host, the 2 most recent in-scope pages
(older than 2 days), 2 around the median lastmod, 1 near the oldest.
  SITES_TOML=<file> python -I sample20_fetch.py <out_dir>   (out_dir must not exist)
"""
import json, re, sys, time
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from curl_cffi import requests as cr  # noqa: E402
from loaders import SNAP_OCT, load_sites, load_snapshot  # noqa: E402
from rules import evaluate, parse_lastmod, url_kind  # noqa: E402

HOSTS = ["english.fas.harvard.edu", "sociology.fas.harvard.edu", "www.physics.harvard.edu", "philosophy.fas.harvard.edu"]
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=False)
snap, sites = load_snapshot(SNAP_OCT), load_sites()
CUT = parse_lastmod("2026-10-13T00:00:00+00:00")


def pick(host):
    rows = []
    for loc, lm in snap[host]["entries"]:
        d = parse_lastmod(lm) if lm else None
        if not d or d > CUT or urlsplit(loc).path in ("", "/"):
            continue
        if url_kind(loc) != "page" or not evaluate(loc, host, sites[host]).in_scope:
            continue
        rows.append((d, loc, lm))
    rows.sort(reverse=True)
    n = len(rows)
    idx = [0, 1, n // 2, n // 2 + 1, n - 2]
    return [rows[i] for i in idx]


def get(url):
    for _ in range(2):
        try:
            return cr.get(url, impersonate="chrome", timeout=90)
        except Exception:
            time.sleep(3)
    return None


k = 0
for host in HOSTS:
    for _, loc, lm in pick(host):
        k += 1
        slug = re.sub(r"[^a-z0-9]+", "-", urlsplit(loc).path.lower()).strip("-")[:60]
        d = out / host / f"{k:02d}-{slug}"
        d.mkdir(parents=True)
        meta = {"url": loc, "xml_lastmod": lm}
        for name, url in (("page.html", loc), ("page.md", loc.rstrip("/") + ".md")):
            r = get(url)
            time.sleep(2)
            if r is None:
                meta[name] = {"error": "request failed"}
                continue
            (d / name).write_bytes(r.content)
            meta[name] = {"url": url, "status": r.status_code, "bytes": len(r.content),
                          "headers": {h: v for h, v in r.headers.items() if h.lower() in
                                      ("content-type", "last-modified", "etag", "date", "cache-control", "age", "x-drupal-dynamic-cache", "link")}}
        json.dump(meta, open(d / "meta.json", "w"), indent=1)
        print(k, host, slug, meta["page.html"].get("status"), meta["page.md"].get("status"), lm, flush=True)
