# Exploration: URL Protocol Deduplication (http vs https)

**Date**: 2026-07-01 | **Scope**: Medium | **Status**: ✅ Complete

## 1. Foundation (What exists)

**Tech stack**: Python 3.x, aiohttp, lxml, trafilatura, SQLite (via `URLStore`)
**Architecture**: Async domain crawler — `WebsiteScraper` drives the crawl loop; URL dedup is SQLite-backed exact-string match.
**Key file**: `scrape_website/scraper.py` — all crawl/dedup logic lives here.

## 2. The Bug

URL deduplication is **exact-string** throughout. If the same page exists as both `http://example.com/foo` and `https://example.com/foo`, the scraper treats them as **two distinct URLs** and will crawl both.

### Where exact-string comparison happens

| Location | Code | Problem |
|---|---|---|
| `URLStore.contains` (line 386) | `WHERE url=?` SQLite PRIMARY KEY lookup | exact string |
| `URLStore._cache` (line 382) | Python `set` membership | exact string |
| `process_url` queue check (line 817) | `if not self.url_store.contains(link)` | exact string |
| `crawl()` main loop (line 897) | `if not self.url_store.contains(url)` | exact string |
| `crawl()` sitemap seeding (line 880) | `if not self.url_store.contains(normalized)` | exact string |

### How urls enter the system with mixed protocols

1. **Sitemap**: `_fetch_sitemap_urls` → returns whatever URLs the sitemap declares (could mix http/https).
2. **Link extraction**: `_extract_links_lxml` (line 233) → calls `_normalize_url` which **preserves the original scheme** (line 223: `f"{parsed.scheme}://..."`). `lxml.html.make_links_absolute` also preserves whatever scheme the href uses.
3. **domain check** (line 260): `parsed.netloc == base_domain` — `netloc` is hostname only (no scheme), so an `http://example.com/foo` link passes the same-domain check and gets queued even when the crawler started on `https://`.

### `_normalize_url` does NOT canonicalize scheme

```python
def _normalize_url(url: str, strip_tracking: bool = False) -> str:
    parsed = urlparse(url)
    url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"  # scheme preserved verbatim
    ...
```

There is no step that maps `http://` → `https://` (or vice versa).

## 3. Constraints

- **No test suite** — verify by direct call to `_extract_text_trafilatura` or manual crawl inspection.
- `URLStore` primary key is the raw URL string; changing the stored form would require a migration shim or a schema reset (`--fresh` flag).
- `_normalize_url` is a **module-level function** also used in `_extract_links_lxml` (process-pool workers) and the main `WebsiteScraper` methods — any change to it is automatically applied everywhere.
- The fix must be safe for both `http` and `https` links discovered during a crawl; it should NOT change the URL actually fetched (only the dedup key).

## 4. Fix Location

**Single, minimal fix**: canonicalize the scheme to `https` inside `_normalize_url` (line 216). Every URL dedup path flows through this function, so one change covers:
- link extraction in workers
- sitemap seeding in `crawl()`
- queue checks in `process_url` and the main loop
- CLI `--file` / `--retry` seeding (line 1083)

The actual fetch URL passed to `aiohttp` is the same normalized URL that was stored — so normalizing `http` → `https` means the scraper will always fetch the `https` version. This is correct for modern sites (most redirect `http` → `https` anyway, and `allow_redirects=True` is set).

**Alternative approach** (more conservative): keep `_normalize_url` as-is and add a scheme-stripping step only inside `URLStore.contains` and `URLStore.add`. This would preserve the original scheme for fetching while deduplicating across protocols. More complex, harder to reason about.

## 5. Handoff (What's next)

**For PLAN/CODE**:
- Fix is in `_normalize_url` (~line 216). Add one line: canonicalize scheme to `https` (or at minimum: normalize both `http` and `https` to the same canonical form).
- `URLStore` SQL schema uses `url TEXT PRIMARY KEY` — no schema change needed if normalization is done before any store call (which it already is).
- Update docstring of `_normalize_url` to document the scheme canonicalization.
- No migration needed for fresh crawls; existing `state.db` files from prior runs may contain `http://` URLs, but that only matters if someone uses `--retry` on an old run.

**Gaps**: None — cause is clear and fix location is unambiguous.
