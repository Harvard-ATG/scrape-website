"""
Deep no-sitemap probe — confirm (or refute) that the 4 hosts the AWS reachability
probe flagged as "no sitemap" truly lack one.

WHY: The prior probe (evidence/aws-reachability/result.json) tried only 3 paths
(/sitemap.xml, /sitemap_index.xml, /wp-sitemap.xml) + robots.txt. A host can still
publish a sitemap at a non-standard path (Yoast per-type sitemaps, gzipped, old
Drupal /system/feeds/sitemap, query-string form, apex-vs-www split). Before the
cadence design treats these 4 as a permanent "no-lastmod" edge case, we exhaust
the realistic locations so the "no sitemap" claim is defensible.

WHAT (per host, read-only, Tier 2 curl_cffi chrome impersonation):
  1. Fetch homepage -> detect CMS (WordPress / Drupal / Yoast) from markup +
     <link rel="sitemap"> hints.
  2. Fetch robots.txt -> parse every `Sitemap:` directive.
  3. Try a wide candidate-path list (standard, WP, Yoast, gzip, Drupal-legacy,
     query-string forms).
  4. Also try the apex<->www sibling host for each candidate.
  5. A hit requires 200 + real sitemap XML (<urlset>/<sitemapindex>), not a
     soft-404 HTML page. gzip bodies are decompressed before the XML check.

OUTPUT: result.json (machine-readable) + prints a per-host verdict.
"""
import concurrent.futures as cf
import gzip
import json
import os
import re

from curl_cffi import requests as creq

HOSTS = [
    "ces.fas.harvard.edu",
    "daviscenter.fas.harvard.edu",
    "careerservices.fas.harvard.edu",
    "www.hio.harvard.edu",
]

# Realistic sitemap locations across CMSes. robots.txt Sitemap: directives are
# probed separately (authoritative) and prepended per host.
CANDIDATES = [
    "/sitemap.xml",
    "/sitemap_index.xml",
    "/sitemap-index.xml",
    "/sitemaps.xml",
    "/sitemap.xml.gz",
    "/sitemap_index.xml.gz",
    "/wp-sitemap.xml",              # WP 5.5+ core
    "/wp-sitemap-posts-post-1.xml",
    "/wp-sitemap-posts-page-1.xml",
    "/sitemap_index.xml",          # Yoast root
    "/page-sitemap.xml",           # Yoast per-type
    "/post-sitemap.xml",
    "/news-sitemap.xml",
    "/sitemap1.xml",
    "/sitemap-1.xml",
    "/sitemap/sitemap.xml",
    "/sitemap/",
    "/sitemap",
    "/sitemap.txt",                # plain-text sitemap
    "/sitemap.php",
    "/system/feeds/sitemap",       # legacy Drupal sitemap module
    "/?sitemap=1",
    "/index.php?sitemap=1",
    "/sitemap.xml?page=1",
]

TIMEOUT = 25
UA_HINT = "chrome"


def variants(host):
    """apex<->www sibling so a sitemap on the 'other' host isn't missed."""
    hs = [host]
    if host.startswith("www."):
        hs.append(host[4:])
    else:
        hs.append("www." + host)
    return hs


def get(url):
    try:
        r = creq.get(url, impersonate=UA_HINT, timeout=TIMEOUT, allow_redirects=True)
        body = r.content or b""
        # transparently decompress .gz bodies (servers don't always set encoding)
        if url.endswith(".gz") or body[:2] == b"\x1f\x8b":
            try:
                body = gzip.decompress(body)
            except Exception:
                pass
        return {
            "status": r.status_code,
            "final_url": str(r.url),
            "ctype": r.headers.get("content-type", ""),
            "bytes": len(body),
            "body": body,
        }
    except Exception as e:
        return {"status": None, "error": f"{type(e).__name__}: {e}"[:200], "body": b""}


def is_sitemap_xml(body):
    head = body[:3000].lower()
    return b"<urlset" in head or b"<sitemapindex" in head


def loc_count(body):
    return len(re.findall(rb"<loc>", body))


def detect_cms(body, headers_gen=""):
    b = body.lower()
    hits = []
    if b"wp-content" in b or b"wp-json" in b or "wordpress" in headers_gen.lower():
        hits.append("wordpress")
    if b"drupal" in b or b"/sites/g/files/" in b or b"/sites/default/files/" in b:
        hits.append("drupal")
    if b"yoast" in b:
        hits.append("yoast")
    m = re.search(rb'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)', b)
    gen = m.group(1).decode("latin1", "replace") if m else ""
    # <link rel="sitemap" href="...">
    sm = re.findall(rb'<link[^>]+rel=["\']sitemap["\'][^>]+href=["\']([^"\']+)', b)
    return {"cms": hits, "generator": gen, "link_rel_sitemap": [s.decode("latin1", "replace") for s in sm]}


def probe_host(host):
    result = {
        "host": host,
        "robots_sitemaps": [],
        "cms": None,
        "hits": [],          # confirmed sitemap XML
        "candidates_tried": 0,
        "notes": [],
    }
    tried = set()

    for h in variants(host):
        base = f"https://{h}"

        # homepage -> CMS detection (only for the canonical host)
        if h == host:
            hp = get(base + "/")
            if hp.get("body"):
                result["cms"] = detect_cms(hp["body"])

        # robots.txt Sitemap: directives (authoritative)
        rob = get(base + "/robots.txt")
        robots_urls = []
        if rob.get("body"):
            for m in re.finditer(rb"(?im)^\s*sitemap:\s*(\S+)", rob["body"]):
                u = m.group(1).decode("utf-8", "replace").strip()
                robots_urls.append(u)
                if u not in result["robots_sitemaps"]:
                    result["robots_sitemaps"].append(u)

        # build the full candidate set for this host variant
        urls = list(robots_urls) + [base + c for c in CANDIDATES]
        for u in urls:
            if u in tried:
                continue
            tried.add(u)
            r = get(u)
            result["candidates_tried"] += 1
            body = r.get("body", b"")
            if r.get("status") == 200 and body and is_sitemap_xml(body):
                result["hits"].append({
                    "url": u,
                    "final_url": r.get("final_url"),
                    "loc_count": loc_count(body),
                    "is_index": b"<sitemapindex" in body[:3000].lower(),
                    "bytes": r.get("bytes"),
                })

    # de-dupe hits by final_url
    seen = set()
    deduped = []
    for hit in result["hits"]:
        key = hit.get("final_url") or hit["url"]
        if key not in seen:
            seen.add(key)
            deduped.append(hit)
    result["hits"] = deduped
    result["has_sitemap"] = len(deduped) > 0
    return result


def main():
    print(f"deep-probing {len(HOSTS)} hosts x {len(CANDIDATES)}+ candidates (x apex/www)\n", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(probe_host, HOSTS):
            results.append(r)
            verdict = "SITEMAP FOUND" if r["has_sitemap"] else "no sitemap"
            print(f"{r['host']:38s} {verdict:16s} "
                  f"cms={r['cms']['cms'] if r['cms'] else '?'} "
                  f"robots={len(r['robots_sitemaps'])} hits={len(r['hits'])} "
                  f"tried={r['candidates_tried']}", flush=True)
            for hit in r["hits"]:
                print(f"      -> {hit['url']}  locs={hit['loc_count']} index={hit['is_index']}", flush=True)

    out = {
        "probed": len(results),
        "found_sitemap": [r["host"] for r in results if r["has_sitemap"]],
        "still_no_sitemap": [r["host"] for r in results if not r["has_sitemap"]],
        "results": results,
    }
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "result.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWROTE {os.path.join(here, 'result.json')}")
    print(f"SUMMARY found={out['found_sitemap']} still_none={out['still_no_sitemap']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
