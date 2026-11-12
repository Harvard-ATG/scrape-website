"""Corpus-wide crossover: sitemap vs local state.db for every local host.

WHY: The seas analysis showed 14,901 rows collapse to ~5,204 distinct pages
(the rest = http/https + ?page= + slash dupes), the ~990 distinct non-crossover
pages are dupes/dead/faceted junk, and the non-crossover FILES are recoverable
via their found_on parent pages. This script confirms whether that pattern
generalizes across the whole local corpus, so sitemap-as-source + the file
preservation rule can be trusted beyond seas.

WHAT (per host, read-only):
  1. Robust sitemap discovery (robots.txt `Sitemap:` -> /sitemap.xml ->
     /sitemap_index.xml -> /wp-sitemap.xml), recursing one level into any
     sitemap-index. Tier 2 curl_cffi impersonate=chrome.
  2. Read state.db `visited` (url, found_on).
  3. Normalize both (scheme->https, lower host, drop fragment, strip trailing
     slash). Two levels: FULL (keeps query) and BASE (drops query = page id).
  4. Metrics: raw rows, distinct base, sitemap size, crossover, non-crossover
     (full + base), query-string bloat, sitemap-only (missed pages).
  5. Non-crossover categorization by type; for FILES, found_on provenance
     (in-sitemap = recoverable / null / not-in-sitemap = at risk) split by
     real vs Drupal /styles/..?itok= derivative junk.

EVIDENCE: writes summary.json (machine-readable, all hosts) + SUMMARY.md
(human-readable aggregate table + per-host detail) next to this script.

CAVEAT (do not overclaim): fetched from a LOCAL/non-AWS IP. Sitemap EXISTENCE
and contents are IP-independent facts; production reachability from AWS ECS
(the Akamai-gated environment) is NOT proven here.

Data source: ../../../../../../apo-mcp-server/data/{host}/logs/state.db
"""
import asyncio
import json
import os
import re
import sqlite3
import xml.etree.ElementTree as ET
from collections import Counter
from urllib.parse import urljoin, urlparse, urlunparse

from curl_cffi.requests import AsyncSession

HERE = os.path.dirname(os.path.abspath(__file__))
# apo-mcp-server data dir (sibling repo). Resolve absolutely so cwd doesn't matter.
DATA_ROOT = "/Users/kevingray/codebase/harvard-atg/apo-mcp-server/data"
OUT_JSON = os.path.join(HERE, "summary.json")
OUT_MD = os.path.join(HERE, "SUMMARY.md")

TIMEOUT = 25
CONCURRENCY = 8
MIN_ROWS = 50  # skip near-empty crawls (handbook=3, library=1, writingprogram=185 kept)

REAL_FILE = re.compile(r"\.(pdf|docx?|xlsx?|pptx?)$", re.I)   # value-bearing docs
IMG_EXT = re.compile(r"\.(jpe?g|png|gif|svg|webp|ico)$", re.I)
ANY_FILE = re.compile(r"\.(pdf|ics|jpe?g|png|gif|svg|webp|ico|docx?|xlsx?|pptx?|zip|mp4|mp3|css|js)$", re.I)
GARBAGE = re.compile(r"(C:|AppData|INetCache|Temporary%20Internet|\\|Content\.Outlook)", re.I)
JUNK_DERIVATIVE = re.compile(r"/styles/|itok=", re.I)


def _local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def norm_full(u):
    """Normalize but KEEP query -> https, lower host, no fragment, no trailing /."""
    p = urlparse(u.strip())
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", p.netloc.lower(), path, "", p.query, ""))


def norm_base(u):
    """Normalize and DROP query -> canonical page identity."""
    if not u:
        return ""
    p = urlparse(u.strip())
    path = p.path.rstrip("/") or "/"
    return urlunparse(("https", p.netloc.lower(), path, "", "", ""))


async def _get(session, url):
    try:
        r = await session.get(url, impersonate="chrome", timeout=TIMEOUT,
                              allow_redirects=True)
        return r.status_code, r.content
    except Exception:
        return None, None


def _parse_locs(body):
    """Return (child_sitemaps, page_urls) from a sitemap or sitemap-index body."""
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return [], []
    if _local(root.tag) == "sitemapindex":
        children = [loc.text.strip() for sm in root if _local(sm.tag) == "sitemap"
                    for loc in sm if _local(loc.tag) == "loc" and loc.text]
        return children, []
    if _local(root.tag) == "urlset":
        pages = [loc.text.strip() for u in root if _local(u.tag) == "url"
                 for loc in u if _local(loc.tag) == "loc" and loc.text]
        return [], pages
    return [], []


async def discover_sitemap(session, host):
    """Robust discovery: robots.txt Sitemap: -> standard paths. Returns
    (source, page_urls set). source describes how it was found (or NONE)."""
    base = f"https://{host}"
    candidates = []
    # robots.txt declared sitemap(s) first
    st, body = await _get(session, urljoin(base, "/robots.txt"))
    if st == 200 and body:
        for line in body.decode("utf-8", "ignore").splitlines():
            m = re.match(r"\s*sitemap:\s*(\S+)", line, re.IGNORECASE)
            if m:
                candidates.append(("robots", m.group(1).strip()))
    # standard fallbacks
    for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
        candidates.append(("standard", urljoin(base, path)))

    for source, sm_url in candidates:
        st, body = await _get(session, sm_url)
        if st != 200 or not body:
            continue
        children, pages = _parse_locs(body)
        if not children and not pages:
            continue
        urls = set(pages)
        # recurse one level into index children
        for child in children:
            cst, cbody = await _get(session, child)
            if cst == 200 and cbody:
                _, cpages = _parse_locs(cbody)
                urls.update(cpages)
        if urls:
            return f"{source}:{sm_url}", urls
    return "NONE", set()


def categorize_base(base_url, had_query):
    p = urlparse(base_url)
    if GARBAGE.search(base_url):
        return "garbage/local-path"
    if ANY_FILE.search(p.path):
        return "file"
    if had_query:
        return "query-string (pagination/facet)"
    return "distinct-path"


def analyze_host(host, sitemap_urls, sitemap_source):
    db = os.path.join(DATA_ROOT, host, "logs", "state.db")
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT url, found_on FROM visited").fetchall()
    conn.close()

    sm_full = {norm_full(u) for u in sitemap_urls}
    sm_base = {norm_base(u) for u in sitemap_urls}

    visited = [r[0] for r in rows]
    v_full = {norm_full(u) for u in visited}
    v_base = {norm_base(u) for u in visited}

    base_had_query = {}
    for u in visited:
        b = norm_base(u)
        base_had_query[b] = base_had_query.get(b, False) or bool(urlparse(u).query)

    non_full = v_full - sm_full
    non_base = v_base - sm_base
    sitemap_only = sm_base - v_base
    crossover = v_base & sm_base

    cats = Counter()
    for b in non_base:
        cats[categorize_base(b, base_had_query.get(b, False))] += 1

    # ---- file provenance (real docs not in sitemap) ----
    docs = [(u, f) for (u, f) in rows if REAL_FILE.search(urlparse(u).path)]
    imgs = [(u, f) for (u, f) in rows if IMG_EXT.search(urlparse(u).path)]

    def file_provenance(items):
        at_risk = [(u, f) for (u, f) in items if norm_base(u) not in sm_base]
        prov = {"total": len(items), "not_in_sitemap": len(at_risk),
                "real_recoverable": 0, "real_null": 0, "real_at_risk": 0,
                "junk_derivative": 0}
        for u, f in at_risk:
            if JUNK_DERIVATIVE.search(u):
                prov["junk_derivative"] += 1
                continue
            fb = norm_base(f)
            if not f:
                prov["real_null"] += 1
            elif fb in sm_base:
                prov["real_recoverable"] += 1
            else:
                prov["real_at_risk"] += 1
        return prov

    return {
        "host": host,
        "sitemap_source": sitemap_source,
        "sitemap_urls": len(sitemap_urls),
        "sitemap_base": len(sm_base),
        "rows_raw": len(visited),
        "distinct_base": len(v_base),
        "dup_collapse_ratio": round(len(visited) / max(len(v_base), 1), 2),
        "crossover": len(crossover),
        "non_crossover_full": len(non_full),
        "non_crossover_base": len(non_base),
        "query_bloat": len(non_full) - len(non_base),
        "sitemap_only_missed": len(sitemap_only),
        "non_crossover_by_type": dict(cats),
        "docs_provenance": file_provenance(docs),
        "imgs_provenance": file_provenance(imgs),
    }


async def process(host, sem):
    async with sem, AsyncSession() as s:
        try:
            source, urls = await discover_sitemap(s, host)
            result = analyze_host(host, urls, source)
            result["status"] = "ok" if source != "NONE" else "no_sitemap"
            return result
        except Exception as e:  # keep going; record the failure as evidence
            return {"host": host, "status": "error", "error": repr(e)}


def discover_hosts():
    hosts = []
    for name in sorted(os.listdir(DATA_ROOT)):
        db = os.path.join(DATA_ROOT, name, "logs", "state.db")
        if not os.path.isfile(db):
            continue
        try:
            conn = sqlite3.connect(db)
            n = conn.execute("SELECT COUNT(*) FROM visited").fetchone()[0]
            conn.close()
        except Exception:
            continue
        if n >= MIN_ROWS:
            hosts.append((name, n))
    return hosts


def write_markdown(results):
    lines = ["# Corpus-wide sitemap vs state.db crossover\n",
             "Read-only analysis confirming the seas pattern generalizes. "
             "Fetched from a LOCAL/non-AWS IP: sitemap existence + contents are "
             "IP-independent facts; production reachability from AWS is NOT proven here.\n",
             "## Aggregate\n",
             "| Host | Sitemap | SM base | Rows | Distinct | Dup× | Crossover | "
             "Non-x base | Query bloat | SM-only missed | Real docs at-risk (null / not-in-SM) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"]
    ok = [r for r in results if r.get("status") == "ok"]
    nos = [r for r in results if r.get("status") == "no_sitemap"]
    err = [r for r in results if r.get("status") == "error"]
    for r in sorted(ok, key=lambda x: -x["rows_raw"]):
        dp = r["docs_provenance"]
        risk = f"{dp['real_null']} / {dp['real_at_risk']}"
        lines.append(
            f"| {r['host']} | {r['sitemap_base']} | {r['sitemap_base']} | "
            f"{r['rows_raw']} | {r['distinct_base']} | {r['dup_collapse_ratio']} | "
            f"{r['crossover']} | {r['non_crossover_base']} | {r['query_bloat']} | "
            f"{r['sitemap_only_missed']} | {risk} |")
    if nos:
        lines.append("\n### No sitemap discovered (degrade-to-discover fallback applies)\n")
        for r in nos:
            lines.append(f"- {r['host']} (rows={r['rows_raw']}, distinct={r['distinct_base']})")
    if err:
        lines.append("\n### Errors\n")
        for r in err:
            lines.append(f"- {r['host']}: {r['error']}")

    lines.append("\n## Per-host detail\n")
    for r in sorted(ok, key=lambda x: -x["rows_raw"]):
        dp, ip = r["docs_provenance"], r["imgs_provenance"]
        lines.append(f"### {r['host']}")
        lines.append(f"- sitemap source: `{r['sitemap_source']}`")
        lines.append(f"- rows {r['rows_raw']} -> distinct {r['distinct_base']} "
                     f"(dup collapse {r['dup_collapse_ratio']}x); sitemap {r['sitemap_base']}")
        lines.append(f"- crossover {r['crossover']}; non-crossover base {r['non_crossover_base']}; "
                     f"query bloat {r['query_bloat']}; sitemap-only missed {r['sitemap_only_missed']}")
        lines.append(f"- non-crossover by type: {r['non_crossover_by_type']}")
        lines.append(f"- real docs (pdf/doc/xls/ppt) not in sitemap: {dp['total']} total, "
                     f"{dp['real_recoverable']} recoverable via good found_on, "
                     f"{dp['real_null']} null found_on, {dp['real_at_risk']} at-risk, "
                     f"{dp['junk_derivative']} derivative junk")
        lines.append(f"- images not in sitemap: {ip['total']} total, "
                     f"{ip['junk_derivative']} derivative junk, {ip['real_null']} null found_on\n")

    with open(OUT_MD, "w") as f:
        f.write("\n".join(lines) + "\n")


async def main():
    hosts = discover_hosts()
    print(f"Processing {len(hosts)} hosts (>= {MIN_ROWS} rows)...")
    sem = asyncio.Semaphore(CONCURRENCY)
    results = await asyncio.gather(*(process(h, sem) for h, _ in hosts))
    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2)
    write_markdown(results)
    ok = sum(1 for r in results if r.get("status") == "ok")
    nos = sum(1 for r in results if r.get("status") == "no_sitemap")
    err = sum(1 for r in results if r.get("status") == "error")
    print(f"DONE: {ok} ok, {nos} no_sitemap, {err} error")
    print(f"Evidence: {OUT_MD}\n          {OUT_JSON}")


if __name__ == "__main__":
    asyncio.run(main())
