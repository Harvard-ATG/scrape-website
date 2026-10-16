"""
Deep no-sitemap probe v2 — exhaust the avenues deep_probe.py did NOT try, to
either find a sitemap on the 4 holdout hosts or make "no sitemap" airtight.

New vs v1:
  - Blanket-block sanity: record homepage + robots.txt HTTP status (proves the
    404s are real negatives, not Akamai challenges — Tier 2 already renders the
    homepage, so a clean 404 elsewhere is genuine).
  - HTML/human sitemap pages: /sitemap.html, /site-map, /sitemap.aspx, etc.
  - Footer/anchor scan: any <a href> whose href or text mentions "sitemap".
  - RSS/Atom feeds: /feed, /rss.xml, /atom.xml — an ALTERNATIVE freshness signal
    (pubDate/updated) for the cadence goal, even though not a sitemap.
  - HTTP `Link: rel="sitemap"` response header on the homepage.
  - Extra XML spellings / Drupal variants: /sitemapindex.xml, /default/sitemap.xml.
  - http:// scheme fallback for the core XML candidates.
"""
import concurrent.futures as cf
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

XML_EXTRA = [
    "/sitemapindex.xml",
    "/default/sitemap.xml",     # simple_sitemap named variant
    "/sitemap.xml/",
    "/en/sitemap.xml",          # language-prefixed
]
HTML_SITEMAP = [
    "/sitemap.html", "/sitemap.htm", "/site-map", "/site-map.html",
    "/sitemap.aspx", "/sitemap-page", "/pages/sitemap", "/sitemap/",
]
FEEDS = ["/feed", "/feed/", "/rss.xml", "/rss", "/atom.xml", "/?feed=rss2", "/index.xml"]

TIMEOUT = 25


def variants(host):
    hs = [host]
    hs.append(host[4:] if host.startswith("www.") else "www." + host)
    return hs


def get(url):
    try:
        r = creq.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
        return {"status": r.status_code, "final_url": str(r.url),
                "ctype": r.headers.get("content-type", ""),
                "link_hdr": r.headers.get("link", ""),
                "body": r.content or b""}
    except Exception as e:
        return {"status": None, "error": f"{type(e).__name__}: {e}"[:160], "body": b""}


def is_sitemap_xml(b):
    h = b[:3000].lower()
    return b"<urlset" in h or b"<sitemapindex" in h


def is_feed(b):
    h = b[:3000].lower()
    return b"<rss" in h or b"<feed" in h or b"<rdf" in h


def feed_dates(b):
    n = len(re.findall(rb"<(pubdate|updated|dc:date|lastbuilddate)", b, re.I))
    return n


def probe(host):
    res = {"host": host, "homepage_status": None, "robots_status": None,
           "xml_hits": [], "html_sitemaps": [], "anchor_sitemap_links": [],
           "feeds": [], "link_header_sitemap": []}
    for h in variants(host):
        for scheme in ("https", "http"):
            base = f"{scheme}://{h}"
            # homepage (only https canonical for markup scan)
            if scheme == "https":
                hp = get(base + "/")
                if h == host:
                    res["homepage_status"] = hp.get("status")
                    if hp.get("link_hdr") and "sitemap" in hp["link_hdr"].lower():
                        res["link_header_sitemap"].append(hp["link_hdr"][:300])
                    body = hp.get("body", b"")
                    # anchor scan: any href or link text mentioning sitemap
                    for m in re.finditer(rb'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', body[:400000], re.I | re.S):
                        href = m.group(1).decode("latin1", "replace")
                        text = re.sub(rb"<[^>]+>", b"", m.group(2)).decode("latin1", "replace").strip()
                        if "sitemap" in href.lower() or "sitemap" in text.lower() or "site map" in text.lower():
                            res["anchor_sitemap_links"].append({"href": href, "text": text[:60]})
                rob = get(base + "/robots.txt")
                if h == host:
                    res["robots_status"] = rob.get("status")

            # extra XML spellings
            for c in XML_EXTRA:
                r = get(base + c)
                if r.get("status") == 200 and is_sitemap_xml(r["body"]):
                    res["xml_hits"].append({"url": base + c, "loc": len(re.findall(rb"<loc>", r["body"]))})

            if scheme == "https":
                # HTML sitemaps
                for c in HTML_SITEMAP:
                    r = get(base + c)
                    b = r.get("body", b"")
                    if r.get("status") == 200 and b"<html" in b[:2000].lower():
                        na = len(re.findall(rb"<a\s", b, re.I))
                        # only count as a candidate HTML sitemap if link-dense
                        if na >= 20 and ("sitemap" in c or "site-map" in c):
                            res["html_sitemaps"].append({"url": base + c, "anchors": na})
                # feeds
                for c in FEEDS:
                    r = get(base + c)
                    if r.get("status") == 200 and is_feed(r["body"]):
                        res["feeds"].append({"url": r.get("final_url") or base + c,
                                             "date_tags": feed_dates(r["body"])})
    # de-dupe feeds by final_url
    seen, dedup = set(), []
    for f in res["feeds"]:
        if f["url"] not in seen:
            seen.add(f["url"]); dedup.append(f)
    res["feeds"] = dedup
    res["found_any_sitemap"] = bool(res["xml_hits"] or res["html_sitemaps"] or res["anchor_sitemap_links"] or res["link_header_sitemap"])
    return res


def main():
    print(f"deep-probe v2: {len(HOSTS)} hosts — extra XML, HTML sitemaps, anchors, feeds, Link header, http\n", flush=True)
    results = []
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for r in ex.map(probe, HOSTS):
            results.append(r)
            print(f"{r['host']:38s} home={r['homepage_status']} robots={r['robots_status']} "
                  f"xml={len(r['xml_hits'])} html={len(r['html_sitemaps'])} "
                  f"anchors={len(r['anchor_sitemap_links'])} feeds={len(r['feeds'])} "
                  f"linkhdr={len(r['link_header_sitemap'])}", flush=True)
            for a in r["anchor_sitemap_links"]:
                print(f"      anchor: {a['href']}  ('{a['text']}')", flush=True)
            for f in r["feeds"]:
                print(f"      feed:   {f['url']}  date_tags={f['date_tags']}", flush=True)
            for x in r["xml_hits"]:
                print(f"      XML:    {x['url']}  locs={x['loc']}", flush=True)

    out = {"probed": len(results),
           "found_any_sitemap": [r["host"] for r in results if r["found_any_sitemap"]],
           "feeds_available": [r["host"] for r in results if r["feeds"]],
           "results": results}
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "result_v2.json"), "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nWROTE {os.path.join(here, 'result_v2.json')}")
    print(f"SUMMARY found_sitemap={out['found_any_sitemap']} feeds_available={out['feeds_available']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
