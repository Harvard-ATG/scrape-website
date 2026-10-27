# fetch.py
"""Tier-2 (curl_cffi impersonate=chrome) sitemap fetch. Discovery mirrors
corpus_crossover (robots.txt Sitemap: -> standard paths) but recursion is FULL:
every child of a <sitemapindex> is followed (cycle-guarded, depth-capped) so we
capture every leaf's <lastmod>, which the cadence stats need. Read-only; any
per-host failure is captured as status rather than raised."""
import asyncio
from urllib.parse import urljoin

from curl_cffi.requests import AsyncSession

from sitemap_parse import parse_sitemap

TIMEOUT = 25
STD_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")
MAX_DEPTH = 5


async def _get(session, url):
    try:
        r = await session.get(url, impersonate="chrome", timeout=TIMEOUT, allow_redirects=True)
        return r.status_code, r.content
    except Exception:
        return None, None


async def _resolve_sitemap_url(session, host, seed_url):
    """Return a working sitemap URL or None. Prefer the seed; else robots.txt;
    else standard paths."""
    candidates = []
    if seed_url:
        candidates.append(seed_url)
    base = f"https://{host}"
    st, body = await _get(session, urljoin(base, "/robots.txt"))
    if st == 200 and body:
        for line in body.decode("utf-8", "ignore").splitlines():
            low = line.strip().lower()
            if low.startswith("sitemap:"):
                candidates.append(line.split(":", 1)[1].strip())
    candidates += [urljoin(base, p) for p in STD_PATHS]
    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        st, body = await _get(session, c)
        if st == 200 and body:
            children, entries = parse_sitemap(body)
            if children or entries:
                return c
    return None


async def _collect(session, url, depth, visited):
    """Recurse fully into a sitemap/index, returning (entries, is_index_root)."""
    if url in visited or depth > MAX_DEPTH:
        return [], False
    visited.add(url)
    st, body = await _get(session, url)
    if st != 200 or not body:
        return [], False
    children, entries = parse_sitemap(body)
    if children:
        out = []
        for child in children:
            child_entries, _ = await _collect(session, child, depth + 1, visited)
            out.extend(child_entries)
        return out, True
    return entries, False


async def discover_and_fetch(session, host, seed_url):
    try:
        sm_url = await _resolve_sitemap_url(session, host, seed_url)
        if not sm_url:
            return {"host": host, "sitemap_url": None, "status": "no_sitemap",
                    "is_index": False, "entries": [], "lastmod_coverage": 0.0,
                    "error": None}
        entries, is_index = await _collect(session, sm_url, 0, set())
        with_lm = sum(1 for e in entries if e.get("lastmod"))
        cov = round(with_lm / len(entries), 3) if entries else 0.0
        return {"host": host, "sitemap_url": sm_url, "status": "ok",
                "is_index": is_index, "entries": entries,
                "lastmod_coverage": cov, "error": None}
    except Exception as e:
        return {"host": host, "sitemap_url": seed_url, "status": "error",
                "is_index": False, "entries": [], "lastmod_coverage": 0.0,
                "error": f"{type(e).__name__}: {e}"[:200]}


async def fetch_all(seeds, concurrency=8):
    sem = asyncio.Semaphore(concurrency)

    async def one(seed):
        async with sem, AsyncSession() as s:
            return await discover_and_fetch(s, seed["host"], seed.get("sitemap_url"))

    results = await asyncio.gather(*(one(s) for s in seeds))
    return {r["host"]: r for r in results}
