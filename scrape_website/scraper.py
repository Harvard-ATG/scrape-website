import argparse
import asyncio
import aiohttp
import aiofiles
import fcntl
import os
import random
import re
import sqlite3
import logging
import json
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode
import xml.etree.ElementTree as ET
from pathlib import Path
from collections import deque
from concurrent.futures import ProcessPoolExecutor
from typing import Deque
from collections.abc import Awaitable, Callable
import mimetypes
import hashlib
from datetime import datetime, timezone

import lxml.html
import trafilatura
from trafilatura.deduplication import LRU_TEST

from scrape_website.filename import generate_filename_web, generate_filename_binary
from scrape_website.manifest import build_manifest, write_manifest


def compute_hash(content: bytes | str) -> str:
    """Return hash in algorithm:digest format, e.g. 'sha256:a1b2c3...' — industry standard (Docker, OCI, SRI)."""
    if isinstance(content, str):
        content = content.encode()
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


# Configuration defaults
CONFIG = {
    'max_concurrent': 100,  # Number of concurrent downloads
    'timeout': 30,  # Request timeout in seconds
    'max_retries': 3,  # Max retries for failed requests
    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36',
    'delay_between_requests': 0.1,  # Politeness delay in seconds
    'max_file_size': 100 * 1024 * 1024,  # 100MB max file size
    'checkpoint_interval': 30,  # Seconds between queue checkpoints
    'progress_interval': 5,  # Seconds between progress reports
}

# HTTP status codes that warrant retry (transient server issues).
# 429 is NOT here — it escalates to Tier 2/3 immediately rather than
# burning retries against a WAF that won't relent on the same fingerprint.
RETRYABLE_STATUS = {500, 502, 503, 504}

# Sticky Tier 2: after this many consecutive Tier 1 (aiohttp) 403/429s on a host,
# start every later fetch at Tier 2. Saves one rejected round trip per page and
# stops feeding the bot wall a stream of bot-fingerprint hits. Any Tier 1 success
# resets the count; Tier 1 is still the last resort if Tier 2/3 fail.
_TIER1_SKIP_AFTER = 5

# File extensions to download
DOWNLOADABLE_EXTENSIONS = {
    '.pdf', '.doc', '.docx', '.ppt', '.pptx',
    '.xls', '.xlsx', '.txt', '.csv', '.zip',
    '.rtf', '.odt', '.ods', '.odp'
}

# MIME types to download
DOWNLOADABLE_MIMES = {
    'application/pdf',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-powerpoint',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'text/plain',
    'text/csv',
    'application/zip',
    'application/rtf',
    'application/vnd.oasis.opendocument.text',
    'application/vnd.oasis.opendocument.spreadsheet',
    'application/vnd.oasis.opendocument.presentation',
}


# Regex patterns for URLs commonly worth skipping on blog/CMS sites.
# These are matched against the full URL (re.search). Override via
# --exclude-pattern (repeatable) or programmatic API.
# Hosts whose /event/ pages are this year's advising items (registration steps, placement
# exams) rather than seminars or old calendars. Checked 2026-10-27 against the sitemap
# lastmod: every page on every host here is dated 2026, so a host-level keep cannot serve a
# stale date. histlit, socialstudies, espp, specialconcentrations and psychology were tried and
# dropped: their event pages are 2013-2020 calendars.
_R7_KEEP_EVENT_HOSTS = (
    "incomingstudents.college.harvard.edu",
    "firstyear.college.harvard.edu",          # incomingstudents now redirects here
    "www.hio.harvard.edu",                    # international-student orientations; 32 of 32 dated 2026
    "ofa.fas.harvard.edu",                    # Clay 101 sections, workshops, artist talks; 42 of 42 dated 2026
)
_R7_KEEP_EVENT_HOSTS_RE = "|".join(re.escape(h) for h in _R7_KEEP_EVENT_HOSTS)

# R7: one page per event. Matched against the full URL; the keep hosts above are exempt.
# A scraper built with event_keep_since=<ISO date> also seeds event pages whose sitemap
# lastmod is on or after that date (see WebsiteScraper.run), so current-year department
# events come in while 2013-2025 calendars stay out.
_R7_EVENT_PATTERN = rf"(?i)^(?!https?://(?:{_R7_KEEP_EVENT_HOSTS_RE})/).*/events?/[^/]+/?$"

_DEFAULT_EXCLUDE_PATTERNS: list[str] = [
    r"/tag/",
    r"/author/",
    r"/feed/?$",
    r"/print/",
    r"\?print=",
    r"/comments/",
    r"/page/\d+",
    r"/cdn-cgi/",
    r"/search\?",
    r"\.ics$",
    # Drupal bibcite citation exports (EndNote, RIS, BibTeX, MARC, tagged, PubMed ID): each
    # publication list is offered in six formats as small text files that ingest never reads
    # (it only takes .pdf, .docx, .pptx and .doc), so they cost crawl time for no content.
    r"/bibcite/export",
    # Individual event pages (R7): one page per seminar or talk, almost all past by the time they
    # are read; on economics they are 74% of the sitemap. Listings (/events, /calendar,
    # /event-topic/x) stay: the pattern needs exactly one path segment after the events folder.
    # Kept on purpose (Splunk, Jul-Oct 2026: the only event content users actually hit):
    #   - /calendar_event/ and /calendar-event/ pages: registrar-style deadlines on OUE and SAS,
    #     ~40 pages across all hosts, the most-cited event URLs in the logs.
    #   - the _R7_KEEP_EVENT_HOSTS above, whose /event/ pages are this year's advising
    #     items, not seminars (26 pages).
    _R7_EVENT_PATTERN,
]

# Query-string params that are tracking only — safe to drop to prevent
# `/page?utm_source=email` and `/page?utm_source=twitter` from being
# stored as two different pages. Add more as you encounter them.
_DEFAULT_TRACKING_PARAMS: frozenset[str] = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "gclid", "fbclid", "mc_eid", "mc_cid", "ref",
    "_ga", "_gl", "igshid", "msclkid", "dclid",
})


# ---------------------------------------------------------------------------
# Cross-process browser slot limiter
# ---------------------------------------------------------------------------
# When scrape_and_ingest.py runs 8 workers in parallel, each is a separate OS
# process with its own WebsiteScraper. Without coordination, all 8 could launch
# a headed Chromium (~300 MB each), risking OOM on the 8 GB Fargate task.
#
# We cap concurrent browsers across all processes using POSIX advisory locks
# (fcntl.flock). Each slot is a file: /tmp/scrape-browser-slots/browser-{0,1,2}.lock
# A process holds LOCK_EX on one file while its browser is alive. If all slots
# are taken, the next process skips Tier 3 (graceful degradation — URLs get
# logged as denied, same as if Playwright weren't installed).
#
# Why flock and not a semaphore or lockdir:
# - Kernel auto-releases on process crash or OOM-kill (no stale locks)
# - Visible for debugging: lsof /tmp/scrape-browser-slots/browser-*.lock
# - Works across unrelated processes (multiprocessing.Semaphore doesn't)
# ---------------------------------------------------------------------------

_BROWSER_SLOT_DIR = Path("/tmp/scrape-browser-slots")
_MAX_BROWSER_SLOTS = int(os.environ.get("SCRAPE_MAX_BROWSERS", "3"))


def _acquire_browser_slot(logger: logging.Logger) -> int | None:
    """Try to acquire an exclusive lock on one of the N browser slot files.

    Returns the file descriptor (held for the lifetime of the browser) or None
    if all slots are taken. The caller MUST pass the fd to _release_browser_slot
    when the browser is closed.
    """
    _BROWSER_SLOT_DIR.mkdir(parents=True, exist_ok=True)
    for i in range(_MAX_BROWSER_SLOTS):
        lock_path = _BROWSER_SLOT_DIR / f"browser-{i}.lock"
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            logger.info(f"Acquired browser slot {i}/{_MAX_BROWSER_SLOTS}")
            return fd
        except OSError:
            # LOCK_NB raises OSError (EAGAIN/EWOULDBLOCK) if already held
            try:
                os.close(fd)
            except Exception:
                pass
            continue
    logger.warning(
        f"All {_MAX_BROWSER_SLOTS} browser slots taken — skipping Tier 3 for this worker. "
        f"(Set SCRAPE_MAX_BROWSERS env var to increase limit)"
    )
    return None


def _release_browser_slot(fd: int | None, logger: logging.Logger) -> None:
    """Release a browser slot by closing the lock file descriptor."""
    if fd is None:
        return
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
        logger.debug("Released browser slot")
    except OSError as e:
        logger.debug(f"Error releasing browser slot: {e}")


# ---------------------------------------------------------------------------
# Top-level helper functions
# ---------------------------------------------------------------------------

def _strip_tracking_params(url: str,
                           tracking_params: frozenset[str] = _DEFAULT_TRACKING_PARAMS) -> str:
    """Return *url* with tracking-only query-string keys removed.

    Preserves order of non-tracking params.  Returns the URL unchanged
    when it has no query string or all params are tracking-only (in which
    case the ``?`` is also dropped).
    """
    parts = urlsplit(url)
    if not parts.query:
        return url
    cleaned = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
               if k not in tracking_params]
    new_query = urlencode(cleaned)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, new_query, ''))


def _url_excluded(url: str, patterns: list[re.Pattern]) -> bool:
    """True iff any compiled regex pattern matches *url*.

    Empty *patterns* list means nothing is excluded (returns False).
    """
    for pat in patterns:
        if pat.search(url):
            return True
    return False


def _url_within_path_prefix(path: str, prefix: str) -> bool:
    """True if *path* is at or below *prefix*."""
    p = prefix.rstrip('/')
    return path == p or path.startswith(p + '/')


def _parse_robots_sitemaps(robots_bytes: bytes | None) -> list[str]:
    """Extract absolute sitemap URLs from a robots.txt body.

    Parses the ``Sitemap:`` directive (case-insensitive, may appear multiple
    times and anywhere in the file). Returns [] on empty/undecodable input.
    """
    urls: list[str] = []
    if not robots_bytes:
        return urls
    text = robots_bytes.decode("utf-8", errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("sitemap:"):
            url = stripped[len("sitemap:"):].strip()
            if url:
                urls.append(url)
    return urls


async def _fetch_sitemap_urls(fetch: Callable[[str], Awaitable[bytes | None]],
                              host: str,
                              scheme: str = "https",
                              max_urls: int = 50000) -> list[str]:
    """Sitemap discovery returning ``<loc>`` URLs only; see ``_fetch_sitemap_entries``."""
    return [loc for loc, _ in await _fetch_sitemap_entries(fetch, host, scheme, max_urls)]


async def _fetch_sitemap_entries(fetch: Callable[[str], Awaitable[bytes | None]],
                                 host: str,
                                 scheme: str = "https",
                                 max_urls: int = 50000) -> list[tuple[str, str | None]]:
    """Best-effort sitemap discovery via a tier-escalating fetch callable.

    Returns ``(loc, lastmod)`` pairs; ``lastmod`` is the entry's text as published (None when absent).

    Discovery order:
      1. ``robots.txt`` ``Sitemap:`` directives (authoritative when present)
      2. only if (1) found nothing: standard fallbacks ``/sitemap.xml``, ``/sitemap_index.xml``,
         ``/wp-sitemap.xml`` (WordPress)
    Recurses into ``<sitemap><loc>`` (sitemap-index) entries up to one level.
    Returns a deduped list of ``<loc>`` URLs, capped at *max_urls* (a warning is logged when the cap cuts the list).
    Fallbacks are probed only when robots.txt advertised no sitemap that yielded URLs.

    *fetch* takes a URL and returns the body as bytes on HTTP 200, else None.
    Routing discovery through the crawler's tier-escalating fetcher (Tier 1
    aiohttp -> Tier 2 curl_cffi) is required: a naive client 403s on
    Akamai-gated hosts and silently returns []. Any fetch/parse failure
    degrades to [] (caller falls back to BFS).
    """
    def _local(tag: str) -> str:
        return tag.split("}")[-1] if "}" in tag else tag

    def _parse_entries(xml_bytes: bytes, tag: str = "url") -> list[tuple[str, str | None]]:
        """(loc, lastmod) for every <tag> element, namespace-agnostic; <sitemap> and <url> are
        parent-scoped so an index's <sitemap><loc> is never read as a page entry or vice versa."""
        entries: list[tuple[str, str | None]] = []
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError:
            return entries
        for parent in root.iter():
            if _local(parent.tag) != tag:
                continue
            loc = lastmod = None
            for child in parent:
                name = _local(child.tag)
                if name == "loc" and child.text:
                    loc = child.text.strip()
                elif name == "lastmod" and child.text:
                    lastmod = child.text.strip()
            if loc:
                entries.append((loc, lastmod))
        return entries

    def _parse_locs(xml_bytes: bytes, tag: str = "url") -> list[str]:
        return [loc for loc, _ in _parse_entries(xml_bytes, tag)]

    # robots.txt Sitemap: directives are authoritative. The standard fallbacks are probed only when robots
    # advertised nothing that yielded URLs: each probe that gets a 403 can escalate to Tier 2/3, which is costly.
    robots = await fetch(f"{scheme}://{host}/robots.txt")
    advertised = _parse_robots_sitemaps(robots)
    fallbacks = [f"{scheme}://{host}{path}" for path in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")]

    seen: set[str] = set()
    result: list[tuple[str, str | None]] = []
    tried: set[str] = set()
    truncated = False

    def _add(entries: list[tuple[str, str | None]]) -> bool:
        """Append new entries; return False once max_urls is reached."""
        nonlocal truncated
        for loc, lastmod in entries:
            if loc not in seen:
                seen.add(loc)
                result.append((loc, lastmod))
                if len(result) >= max_urls:
                    truncated = True
                    return False
        return True

    async def _read(sitemap_url: str) -> bool:
        """Read one sitemap (and its sub-sitemaps); return False once max_urls is reached."""
        if sitemap_url in tried:
            return True
        tried.add(sitemap_url)
        data = await fetch(sitemap_url)
        if not data:
            return True
        # Check for sitemap index (contains <sitemap> elements)
        for sub_url in _parse_locs(data, tag="sitemap"):
            sub_data = await fetch(sub_url)
            if sub_data and not _add(_parse_entries(sub_data, tag="url")):
                return False
        # Also parse direct <url><loc> entries
        return _add(_parse_entries(data, tag="url"))

    for group in (advertised, fallbacks):
        for sitemap_url in group:
            if not await _read(sitemap_url):
                break
        if result:
            break   # advertised sitemaps worked: do not probe the fallbacks

    if truncated:
        # TODO: return a completeness flag so the update planner (R11, R15) can tell a cut-off list from a full one.
        logging.getLogger("scraper.sitemap").warning(
            "Sitemap discovery for %s stopped at max_urls=%d; the list is incomplete", host, max_urls)
    return result


# ---------------------------------------------------------------------------
# Top-level functions for ProcessPoolExecutor (must be picklable)
# ---------------------------------------------------------------------------

def _normalize_url(url: str, strip_tracking: bool = False) -> str:
    """Normalize URL by removing fragments and trailing slashes.

    Canonicalizes the scheme: http is treated as https so that the same
    page linked under both protocols is not crawled twice.

    When *strip_tracking* is True, also removes well-known tracking
    query parameters (utm_*, fbclid, gclid, etc.).
    """
    parsed = urlparse(url)
    scheme = "https" if parsed.scheme == "http" else parsed.scheme
    url = f"{scheme}://{parsed.netloc}{parsed.path}"
    if parsed.query:
        url += f"?{parsed.query}"
    if url.endswith('/') and parsed.path != '/':
        url = url[:-1]
    if strip_tracking:
        url = _strip_tracking_params(url)
    return url


def _decide_crawl_gen(baseline: int, *, fresh: bool, resuming: bool) -> int:
    """Choose this run's crawl generation from the highest one recorded.

    `baseline` = COALESCE(MAX(crawl_gen), 0) from state.db.
      - fresh:    state was cleared → start at generation 1.
      - resuming: continue the in-flight pass (its rows already carry `baseline`);
                  max(baseline, 1) guards the one-time post-migration case.
      - update:   the last pass completed → new pass, advance to baseline + 1.

    The queue (not this value) decides fresh/resume/update; see _should_fetch.
    """
    if fresh:
        return 1
    if resuming:
        return max(baseline, 1)
    return baseline + 1


def _should_fetch(url: str, seen_this_run: set[str], url_store: "URLStore") -> bool:
    """Decide whether to fetch a URL during this pass.

    Foundation behavior (zero regression):
      - skip if already fetched this run (`seen_this_run`, in-run loop prevention), OR
      - skip if visited in a prior run (`url_store.contains`, cross-run skip).

    The deferred --update flag later extends ONLY the cross-run half to re-fetch
    rows whose crawl_gen < the current generation. Resume vs. new-pass is decided
    by the queue, never here.
    """
    # NOTE(review): the crawl loop adds a URL to url_store before it is fetched, so a page that fails or is
    # denied counts as visited here and is never retried by a later run. See review/REVIEW_FINDINGS.md (O2).
    if url in seen_this_run:
        return False
    return not url_store.contains(url)


def _should_write_manifest(*, crawl_complete: bool, capped: bool, has_entries: bool) -> bool:
    """Only (re)write manifest.json after a complete, non-capped pass with entries.

    NOTE(review): "complete" means the queue drained. Pages that failed or were denied are not counted, so a
    manifest can omit them and downstream ingest then retires them. R17 (retire only after a complete run) is
    not enforced here. See review/REVIEW_FINDINGS.md (O1).

    Guards the 'complete & authoritative' invariant: a partial, crashed, or capped
    run leaves the last complete manifest untouched, so downstream ingest /
    deprecate_removed_urls never sees a shrunken set. `capped` is always False
    today; the guard is installed for the deferred --max-pages stream.
    """
    return crawl_complete and not capped and has_entries


def _extract_links_lxml(html_content: str, base_url: str, base_domain: str,
                        strip_tracking: bool = False,
                        exclude_patterns: list[str] | None = None,
                        path_prefix: str | None = None,
                        include_patterns: list[str] | None = None) -> set[str]:
    """Extract links using lxml (5-20x faster than BeautifulSoup).

    *exclude_patterns*/*include_patterns*: lists of regex **strings** (not
    compiled) — we compile them here because compiled patterns are not
    picklable across the process-pool boundary.
    """
    compiled = [re.compile(p) for p in (exclude_patterns or [])]
    compiled_include = [re.compile(p) for p in (include_patterns or [])]
    links = set()
    try:
        doc = lxml.html.fromstring(html_content)
        doc.make_links_absolute(base_url, resolve_base_href=True)

        for element, attribute, link, pos in doc.iterlinks():
            if not link or not link.startswith('http'):
                continue
            normalized = _normalize_url(link, strip_tracking=strip_tracking)
            parsed = urlparse(normalized)
            tag = element.tag

            if tag == 'a':
                # Follow all same-domain <a> links
                if parsed.netloc == base_domain:
                    if path_prefix and not _url_within_path_prefix(parsed.path, path_prefix):
                        path_lower = parsed.path.lower()
                        if not any(path_lower.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
                            continue
                    if compiled_include and not any(p.search(normalized) for p in compiled_include):
                        continue
                    if not _url_excluded(normalized, compiled):
                        links.add(normalized)
            elif tag in ('link', 'script', 'img'):
                # Only follow non-<a> tags if they point to downloadable files
                path_lower = parsed.path.lower()
                if any(path_lower.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
                    links.add(normalized)
    except Exception:
        pass
    return links


_METADATA_FIELDS = (
    "title", "author", "url", "hostname", "description", "sitename",
    "date", "categories", "tags", "fingerprint", "id", "license",
)


def _build_frontmatter(meta, fallback_url: str, http_status: int | None = None) -> str:
    # Seed url from fallback if metadata didn't capture it
    if meta and not meta.url:
        meta.url = fallback_url
    lines = ["---"]
    for attr in _METADATA_FIELDS:
        value = getattr(meta, attr, None) if meta else None
        if attr == "url" and not value:
            value = fallback_url
        if value:
            # json.dumps produces a valid YAML double-quoted scalar — handles
            # colons, quotes, special chars without adding a yaml dependency.
            lines.append(f"{attr}: {json.dumps(str(value), ensure_ascii=False)}")
    if http_status is not None:
        lines.append(f"http_status: {int(http_status)}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def _extract_text_trafilatura(html_content: str, url: str, http_status: int | None = None) -> str | None:
    """Extract clean Markdown (with metadata front matter) for LLM consumption."""
    try:
        # Reset trafilatura's process-global dedup cache before every page so
        # deduplication is strictly intra-page. Without this, the LRU_TEST
        # cache accumulates across all pages handled by a long-lived
        # ProcessPoolExecutor worker, silently stripping content that legitimately
        # repeats across pages (e.g. an FAQ answer on both the FAQ page and its
        # own page) — and producing no file at all when a page is only such text.
        LRU_TEST.clear()
        body = trafilatura.extract(
            html_content,
            url=url,
            include_comments=False,
            include_tables=True,
            include_links=True,
            include_images=False,
            favor_recall=True,       # maximize content extraction
            deduplicate=True,        # intra-page only (cache cleared above)
            with_metadata=False,
            output_format='markdown',
        )
        if body is None:
            return None
        meta = trafilatura.extract_metadata(html_content, default_url=url)
        return _build_frontmatter(meta, url, http_status=http_status) + body
    except Exception:
        return None


def _parse_and_extract(html_content: str, url: str, base_domain: str,
                       strip_tracking: bool = False,
                       exclude_patterns: list[str] | None = None,
                       http_status: int | None = None,
                       path_prefix: str | None = None,
                       include_patterns: list[str] | None = None) -> tuple[set[str], str | None]:
    """Combined link extraction + text extraction in one process pool call."""
    links = _extract_links_lxml(html_content, url, base_domain,
                                strip_tracking=strip_tracking,
                                exclude_patterns=exclude_patterns,
                                path_prefix=path_prefix,
                                include_patterns=include_patterns)
    text = _extract_text_trafilatura(html_content, url, http_status=http_status)
    return links, text


# ---------------------------------------------------------------------------
# SQLite-backed URL store
# ---------------------------------------------------------------------------

# --- Crawl generations & fetch pathways -------------------------------------
# state.db tracks a per-URL `crawl_gen` (integer) and `last_fetched_at` (UTC
# ISO-8601). A "generation" is one scoped, monotonic crawl pass over the site.
#
#   crawl_gen (control)  — which generation last fetched this row.
#   last_fetched_at (data) — when that fetch happened (freshness/debugging).
#
# Three fetch pathways, selected by --fresh and the queue (NOT by crawl_gen):
#   * fresh   (--fresh)              → clear state, crawl_gen = 1, re-fetch all.
#   * resume  (no flag, queue full)  → an interrupted pass; continue the SAME
#                                       generation (max(baseline, 1)) on the
#                                       leftover queue.
#   * update  (no flag, queue empty) → the last pass completed; start a new
#                                       generation (baseline + 1), discover new
#                                       pages, skip existing ones. This is the
#                                       "run again without wiping" path — it has
#                                       no dedicated flag.
#
# The current generation is DERIVED (see _decide_crawl_gen) from
# COALESCE(MAX(crawl_gen), 0); nothing is stored in the `stats` table. Two
# independent axes: the `queue` table owns resume-vs-new-pass; `crawl_gen` owns
# re-fetch-vs-skip (see _should_fetch). Today `_should_fetch` skips any
# already-visited URL, so `update` only picks up NEW pages. The deferred
# `--update` flag will re-fetch pages whose sitemap <lastmod> changed by making
# `_should_fetch` re-fetch rows with crawl_gen < current — this foundation lays
# that seam WITHOUT changing behavior.
# ----------------------------------------------------------------------------

class URLStore:
    """SQLite-backed visited URL tracking with in-memory LRU cache."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), isolation_level=None)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("CREATE TABLE IF NOT EXISTS visited (url TEXT PRIMARY KEY)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS downloaded_files (hash TEXT PRIMARY KEY)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS queue (url TEXT PRIMARY KEY, found_on TEXT)")
        self.conn.execute("CREATE TABLE IF NOT EXISTS stats (key TEXT PRIMARY KEY, value TEXT)")
        # Migrate existing tables from pre-manifest schema
        for col, col_type in [
            ("filename", "TEXT"), ("hostname", "TEXT"), ("title", "TEXT"),
            ("found_on", "TEXT"), ("file_type", "TEXT"),
            ("content_hash", "TEXT"), ("file_size", "INTEGER"),
            # Crawl-generation foundation (see comment block above class URLStore):
            ("crawl_gen", "INTEGER"),      # which crawl generation last fetched this row
            ("last_fetched_at", "TEXT"),   # UTC ISO-8601 of the most recent successful fetch
        ]:
            try:
                self.conn.execute(f"ALTER TABLE visited ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
        try:
            self.conn.execute("ALTER TABLE queue ADD COLUMN found_on TEXT")
        except sqlite3.OperationalError:
            pass
        # In-memory cache for fast lookups
        self._cache: set[str] = set()
        self._cache_limit = 100_000
        self._count = self.conn.execute("SELECT COUNT(*) FROM visited").fetchone()[0]

    def contains(self, url: str) -> bool:
        if url in self._cache:
            return True
        row = self.conn.execute("SELECT 1 FROM visited WHERE url=?", (url,)).fetchone()
        if row:
            self._add_to_cache(url)
            return True
        return False

    def add(self, url: str):
        try:
            self.conn.execute("INSERT INTO visited (url) VALUES (?)", (url,))
            self._add_to_cache(url)
            self._count += 1
        except sqlite3.IntegrityError:
            pass

    def _add_to_cache(self, url: str):
        if len(self._cache) >= self._cache_limit:
            # Evict ~20% of cache
            to_remove = list(self._cache)[:self._cache_limit // 5]
            for item in to_remove:
                self._cache.discard(item)
        self._cache.add(url)

    @property
    def count(self) -> int:
        return self._count

    def max_crawl_gen(self) -> int:
        """Highest crawl generation recorded, or 0 if none.

        COALESCE guards both an empty table and the one-time post-migration
        state where existing rows have NULL crawl_gen.
        """
        row = self.conn.execute(
            "SELECT COALESCE(MAX(crawl_gen), 0) FROM visited"
        ).fetchone()
        return row[0]

    def has_file_hash(self, file_hash: str) -> bool:
        row = self.conn.execute("SELECT 1 FROM downloaded_files WHERE hash=?", (file_hash,)).fetchone()
        return row is not None

    def add_file_hash(self, file_hash: str):
        try:
            self.conn.execute("INSERT INTO downloaded_files (hash) VALUES (?)", (file_hash,))
        except sqlite3.IntegrityError:
            pass

    def upsert_metadata(self, url: str, *, filename: str, hostname: str,
                        title: str | None = None, found_on: str | None = None,
                        file_type: str = "web", content_hash: str | None = None,
                        file_size: int | None = None, crawl_gen: int | None = None):
        # last_fetched_at stamps the UTC instant of this successful save (freshness);
        # crawl_gen records which crawl generation last fetched the row (control).
        # Only stamp them on a real fetch save (crawl_gen provided); a save without a
        # generation keeps any existing stamp (COALESCE) instead of erasing it.
        fetched_at = (
            datetime.now(timezone.utc).isoformat() if crawl_gen is not None else None
        )
        self.conn.execute("""
            UPDATE visited SET filename=?, hostname=?, title=?, found_on=?,
                file_type=?, content_hash=?, file_size=?,
                crawl_gen=COALESCE(?, crawl_gen), last_fetched_at=COALESCE(?, last_fetched_at)
            WHERE url=?
        """, (filename, hostname, title, found_on, file_type, content_hash,
              file_size, crawl_gen, fetched_at, url))

    def export_manifest(self, base_hostname: str) -> dict:
        rows = self.conn.execute("""
            SELECT filename, url, hostname, title, found_on, file_type, content_hash
            FROM visited WHERE filename IS NOT NULL
        """).fetchall()
        files = {}
        for filename, url, hostname, title, found_on, file_type, content_hash in rows:
            content_type = "webpage" if file_type == "web" else "document"
            entry = {
                "source_url": url,
                "hostname": hostname or base_hostname,
                "title": title or "Unknown",
                "content_type": content_type,
            }
            if file_type != "web":
                ext = os.path.splitext(filename)[1]
                if ext:
                    entry["file_type"] = ext.lstrip(".")
            if found_on:
                entry["found_on"] = found_on
            if content_hash:
                entry["content_hash"] = content_hash
            files[filename] = entry
        return files

    def save_queue(self, urls):
        self.conn.execute("DELETE FROM queue")
        self.conn.executemany(
            "INSERT OR IGNORE INTO queue (url, found_on) VALUES (?, ?)",
            [(u, f) for u, f in urls]
        )

    def load_queue(self):
        rows = self.conn.execute("SELECT url, found_on FROM queue").fetchall()
        return deque((row[0], row[1]) for row in rows)

    def save_stats(self, stats: dict):
        self.conn.execute("INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)",
                          ('stats', json.dumps(stats)))

    def load_stats(self) -> dict | None:
        row = self.conn.execute("SELECT value FROM stats WHERE key='stats'").fetchone()
        if row:
            return json.loads(row[0])
        return None

    def clear(self):
        self.conn.execute("DELETE FROM visited")
        self.conn.execute("DELETE FROM downloaded_files")
        self.conn.execute("DELETE FROM queue")
        self.conn.execute("DELETE FROM stats")
        self._cache.clear()
        self._count = 0

    def close(self):
        self.conn.close()


# ---------------------------------------------------------------------------
# Main scraper
# ---------------------------------------------------------------------------

class WebsiteScraper:
    def __init__(self, start_url: str, fresh: bool = False,
                 exclude_patterns: list[str] | None = None,
                 include_patterns: list[str] | None = None,
                 strip_tracking_params: bool = True,
                 use_sitemap: bool = True,
                 concurrency: int | None = None,
                 timeout: int | None = None,
                 delay: float | None = None,
                 output_dir: str | Path | None = None,
                 scope_to_path: bool | None = None,
                 s3_bucket: str | None = None,
                 playwright_enabled: bool = True,
                 event_keep_since: str | None = None):
        self.start_url = start_url
        # ISO date (YYYY-MM-DD). When set, a sitemap-seeded event page whose lastmod is on or
        # after this date is crawled even though R7 would exclude it. None keeps R7 strict.
        self.event_keep_since = event_keep_since
        self.s3_bucket = s3_bucket
        self.base_domain = self.extract_domain(start_url)

        _start_path = urlparse(start_url).path
        if scope_to_path is None:
            scope_to_path = bool(_start_path and _start_path != '/')
        self.path_prefix: str | None = _start_path if scope_to_path else None

        # Per-instance config values (fall back to module-level defaults)
        self.max_concurrent = concurrency if concurrency is not None else CONFIG['max_concurrent']
        self.timeout = timeout if timeout is not None else CONFIG['timeout']
        self.delay = delay if delay is not None else CONFIG['delay_between_requests']
        self.max_retries = CONFIG['max_retries']
        self.user_agent = CONFIG['user_agent']
        self.max_file_size = CONFIG['max_file_size']
        self.checkpoint_interval = CONFIG['checkpoint_interval']
        self.progress_interval = CONFIG['progress_interval']

        # Crawl-quality knobs
        self.strip_tracking_params = strip_tracking_params
        self.use_sitemap = use_sitemap
        # Kill switch for Tier 3: set False (or --no-playwright CLI) to cap escalation
        # at curl_cffi. Useful if Playwright causes issues on specific sites.
        self.playwright_enabled = playwright_enabled
        # Store patterns as strings (for pickling to process pool)
        # NOTE(review): passing exclude_patterns here REPLACES the defaults, while the CLI and the update rules
        # (rules.evaluate) ADD to them. See review/REVIEW_FINDINGS.md (O5).
        self._exclude_pattern_strings: list[str] = (
            exclude_patterns if exclude_patterns is not None
            else list(_DEFAULT_EXCLUDE_PATTERNS)
        )
        # Pre-compile for in-process filtering (e.g. sitemap seed)
        self._compiled_exclude_patterns: list[re.Pattern] = [
            re.compile(p) for p in self._exclude_pattern_strings
        ]
        self._event_pattern = re.compile(_R7_EVENT_PATTERN)
        self._compiled_non_event_excludes: list[re.Pattern] = [
            p for p in self._compiled_exclude_patterns if p.pattern != _R7_EVENT_PATTERN
        ]
        self._include_pattern_strings: list[str] = include_patterns or []
        self._compiled_include_patterns: list[re.Pattern] = [
            re.compile(p) for p in self._include_pattern_strings
        ]
        self.session = None
        self.semaphore = asyncio.Semaphore(self.max_concurrent)
        # Sticky Tier 2 state (see _TIER1_SKIP_AFTER)
        self._tier1_blocks_in_a_row = 0
        self._skip_tier1 = False
        self.denied_urls: list[str] = []
        self.failed_urls: list[str] = []

        # Browser state (Tier 3: Playwright headed browser under xvfb).
        # Lazy-initialized on first 403 that Tier 2 can't handle.
        # Lock prevents multiple concurrent pages from each launching a browser.
        # _browser_slot_fd holds the flock fd for cross-process slot limiting.
        # _browser_unavailable is set True after a failed attempt (slot denied or
        # import error) so we don't retry on every subsequent 403.
        self._browser = None
        self._playwright = None
        self._browser_lock = asyncio.Lock()
        self._browser_slot_fd: int | None = None
        self._browser_unavailable = False

        # Stats
        self.stats = {
            'pages_downloaded': 0,
            'files_downloaded': 0,
            'text_extracted': 0,
            'errors': 0,
            'denied': 0,
            'not_found': 0,   # 4xx/5xx responses: not saved, links not followed
            'offsite': 0,     # redirect chain left the host: not saved, links not followed
            'total_bytes': 0,
        }

        # Setup directories
        self.base_dir = Path(output_dir) / self.base_domain if output_dir else Path('data') / self.base_domain
        self.pages_dir = self.base_dir / 'pages'
        self.text_dir = self.base_dir / 'text'
        self.files_dir = self.base_dir / 'files'
        self.logs_dir = self.base_dir / 'logs'
        for d in (self.pages_dir, self.text_dir, self.files_dir, self.logs_dir):
            d.mkdir(parents=True, exist_ok=True)

        # Logging
        self.logger = logging.getLogger(f"scraper.{self.base_domain}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        # File handler
        fh = logging.FileHandler(self.logs_dir / 'scrape.log')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
        self.logger.addHandler(fh)
        # Console handler (INFO only)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        self.logger.addHandler(ch)

        if self.path_prefix:
            self.logger.info(f"Path scope: crawl restricted to {self.path_prefix}*")
        if self._include_pattern_strings:
            self.logger.info(f"Include filter: {len(self._include_pattern_strings)} pattern(s) — only matching URLs queued")

        # SQLite-backed URL store
        self.url_store = URLStore(self.logs_dir / 'state.db')

        # Handle fresh start vs resume
        resuming = False
        if fresh:
            self.url_store.clear()
            self.urls_to_visit: Deque[tuple[str, str | None]] = deque([(start_url, None)])
            self.logger.info("Fresh start (--fresh): cleared previous state")
        else:
            # Try to resume from checkpoint
            saved_queue = self.url_store.load_queue()
            saved_stats = self.url_store.load_stats()
            if saved_queue and self.url_store.count > 0:
                self.urls_to_visit = saved_queue
                if saved_stats:
                    self.stats.update(saved_stats)
                resuming = True
                self.logger.info(f"Resuming: {self.url_store.count} URLs visited, {len(saved_queue)} in queue")
            else:
                self.urls_to_visit = deque([(start_url, None)])

        # Crawl-generation state. The queue above (not this value) decides
        # fresh/resume/new-pass; crawl_gen only marks which rows this pass fetched.
        self.crawl_gen = _decide_crawl_gen(
            self.url_store.max_crawl_gen(), fresh=fresh, resuming=resuming
        )
        self.seen_this_run: set[str] = set()   # in-run loop prevention (see _should_fetch)
        self.capped = False                    # --max-pages sets this (deferred stream)
        self.crawl_complete = False            # set True only on normal crawl() completion
        self.logger.info(f"Crawl generation: {self.crawl_gen}")

        # ProcessPoolExecutor for CPU-bound parsing
        self.executor = ProcessPoolExecutor(max_workers=os.cpu_count())

        self.logger.info(f"Output directory: {self.base_dir}")
        self.logger.info(f"Starting domain: {self.base_domain}")
        self.logger.info(f"Max concurrent requests: {self.max_concurrent}")

    @staticmethod
    def extract_domain(url: str) -> str:
        parsed = urlparse(url)
        return parsed.netloc

    def normalize_url(self, url: str) -> str:
        return _normalize_url(url, strip_tracking=self.strip_tracking_params)

    def is_same_domain(self, url: str) -> bool:
        return self.extract_domain(url) == self.base_domain

    def _left_host(self, final_url: str) -> bool:
        """True when a redirect chain ended on another host (www. prefix ignored).

        Such a response is not this site's page: saving it would file outside
        content under this hostname, and resolving its relative links against
        the original URL manufactures phantom URLs on this host (classics'
        /links/<slug> redirects produced 1,898 "Page not found" fetches).
        """
        final_host = self.extract_domain(str(final_url)).lower()
        if not final_host:
            return False
        strip = lambda h: h[4:] if h.startswith('www.') else h
        return strip(final_host) != strip(self.base_domain.lower())

    def should_download_file(self, url: str, content_type: str = None) -> bool:
        path = urlparse(url).path.lower()
        if any(path.endswith(ext) for ext in DOWNLOADABLE_EXTENSIONS):
            return True
        if content_type:
            content_type = content_type.lower().split(';')[0].strip()
            if content_type in DOWNLOADABLE_MIMES:
                return True
        return False

    def get_file_extension(self, url: str, content_type: str = None) -> str:
        path = urlparse(url).path
        if '.' in path:
            ext = path.split('.')[-1].lower()
            if f'.{ext}' in DOWNLOADABLE_EXTENSIONS:
                return f'.{ext}'
        if content_type:
            content_type = content_type.lower().split(';')[0].strip()
            ext = mimetypes.guess_extension(content_type)
            if ext:
                return ext
        return '.bin'

    def generate_filename(self, url: str, content_type: str = None) -> str:
        return generate_filename_binary(url, content_type)

    def generate_html_filename(self, url: str) -> str:
        return generate_filename_web(url)

    async def init_session(self):
        connector = aiohttp.TCPConnector(
            limit=self.max_concurrent,
            limit_per_host=self.max_concurrent,
            resolver=aiohttp.AsyncResolver(),
            ttl_dns_cache=300,
            enable_cleanup_closed=True,
        )
        timeout = aiohttp.ClientTimeout(total=self.timeout, connect=10, sock_connect=10, sock_read=self.timeout)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate',
                'Accept-Language': 'en-US,en;q=0.5',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
            },
            max_field_size=32768,
        )

    async def close_session(self):
        if self.session:
            await self.session.close()

    # --- TIER 3: BROWSER LIFECYCLE ---
    # Browser startup is expensive (~500ms + 100MB memory). We share one browser
    # instance across all pages in a crawl, launching it only on the first 403 that
    # Tier 2 can't handle. The async lock prevents a race where multiple concurrent
    # fetches each try to launch their own browser.

    async def _ensure_browser(self):
        """Lazy-init Playwright browser (headed Chromium). Thread-safe via double-check lock.

        Acquires a cross-process browser slot (flock) before launching. If all
        slots are taken (default: 3 concurrent browsers across all workers),
        sets _browser_unavailable so we don't retry on every subsequent 403.
        """
        if self._browser is not None:
            return
        if self._browser_unavailable:
            return

        async with self._browser_lock:
            if self._browser is not None:
                return
            if self._browser_unavailable:
                return

            # Acquire a cross-process slot before launching the browser.
            # This caps total Chromium instances across all parallel workers.
            self._browser_slot_fd = _acquire_browser_slot(self.logger)
            if self._browser_slot_fd is None:
                self._browser_unavailable = True
                return

            try:
                from playwright.async_api import async_playwright
            except ImportError:
                self.logger.warning(
                    "Playwright not installed; cannot use Tier 3 (headed browser). "
                    "Install with: uv add playwright && uv run playwright install chromium"
                )
                _release_browser_slot(self._browser_slot_fd, self.logger)
                self._browser_slot_fd = None
                self._browser_unavailable = True
                return

            self._playwright = await async_playwright().start()
            # headless=False is required — headless Chromium leaks "HeadlessChrome" in
            # the UA string and gets 403'd by Akamai. Headed mode under xvfb (DISPLAY=:99)
            # passes Bot Manager's automation detection.
            self._browser = await self._playwright.chromium.launch(headless=False)
            self.logger.info("Playwright browser launched (headed mode under xvfb)")

    async def _close_browser(self):
        """Clean shutdown of browser resources. Called in crawl() finally block
        to prevent zombie Chromium processes in ECS tasks. Releases the
        cross-process browser slot so another worker can use it."""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        _release_browser_slot(self._browser_slot_fd, self.logger)
        self._browser_slot_fd = None

    def _backoff(self, attempt: int) -> float:
        """Exponential backoff with full jitter. Caps at 8s to avoid excessive waits.
        Full jitter (uniform 0..max) prevents thundering herd when multiple
        scrapers hit rate limits simultaneously."""
        return random.uniform(0, min(8.0, 1.0 * (2 ** attempt)))

    def _parse_retry_after(self, header: str | None, attempt: int) -> float:
        """Parse Retry-After header (seconds or HTTP-date), fall back to backoff."""
        if not header:
            return self._backoff(attempt)
        try:
            return float(header)
        except ValueError:
            pass
        # HTTP-date format: "Thu, 01 Jan 2026 00:00:00 GMT"
        from email.utils import parsedate_to_datetime
        try:
            target = parsedate_to_datetime(header)
            delta = (target - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, delta)
        except (ValueError, TypeError):
            return self._backoff(attempt)

    # --- TIER 2: curl_cffi (Chrome TLS fingerprint) ---
    # curl_cffi impersonates Chrome's TLS handshake (JA3 fingerprint) and HTTP/2
    # settings. This beats WAFs that inspect TLS fingerprints but don't require
    # full JS execution. Much faster than a real browser (~0.5s vs ~2s per page).

    async def _fetch_via_curl_cffi(self, url: str) -> tuple | None:
        """Tier 2: Fetch with Chrome TLS/HTTP2 fingerprint via curl_cffi.

        Returns same 4-tuple as aiohttp path, or None if still blocked/unavailable.
        None signals the caller to escalate to Tier 3.
        """
        try:
            from curl_cffi.requests import AsyncSession
        except ImportError:
            self.logger.debug("curl_cffi not available, skipping Tier 2")
            return None

        try:
            async with AsyncSession() as session:
                resp = await session.get(
                    url,
                    impersonate='chrome',  # Chrome 124+ TLS fingerprint
                    allow_redirects=True,
                    timeout=self.timeout,
                )
                status = resp.status_code
                content_type = resp.headers.get('Content-Type', '')

                # Still blocked by WAF or rate-limited
                if status in (403, 429):
                    self.logger.debug(f"curl_cffi still blocked ({status}): {url}")
                    return None

                # Return server errors to caller for retry handling
                if status >= 500:
                    self.logger.debug(f"curl_cffi server error ({status}): {url}")
                    return None

                # Determine file vs HTML
                is_file = self.should_download_file(url, content_type)
                if not is_file and self._left_host(resp.url):
                    self.logger.info(f"Redirected off-host, not saved: {url} -> {resp.url}")
                    return '', content_type, 'offsite', status
                if is_file:
                    self.logger.info(f"Fetched via curl_cffi (Tier 2, file): {url}")
                    return resp.content, content_type, 'file', status

                # Charset-safe decode (reuse same logic as aiohttp)
                raw = resp.content
                declared = (resp.encoding or '').lower()
                encoding = declared if declared and declared not in ('iso-8859-1', 'windows-1252') else 'utf-8'
                try:
                    content = raw.decode(encoding)
                except (UnicodeDecodeError, LookupError):
                    content = raw.decode('utf-8', errors='replace')

                self.logger.info(f"Fetched via curl_cffi (Tier 2, HTML): {url}")
                return content, content_type, 'html', status

        except Exception as e:
            self.logger.debug(f"curl_cffi failed for {url}: {e}")
            return None

    # --- TIER 3: Playwright headed browser ---
    # Last resort when curl_cffi's TLS fingerprint isn't enough. A real headed
    # browser passes Akamai Bot Manager's automation detection because it has a
    # full JS engine, DOM, and doesn't leak headless signals.
    # Each page gets its own browser context (isolated cookies/state) but shares
    # the single browser instance launched by _ensure_browser().

    async def _fetch_via_playwright(self, url: str) -> tuple | None:
        """Tier 3: Fetch via headed browser (proven to beat Akamai from AWS).

        Uses page.goto() for both HTML and files — FAS PDFs require real navigation
        (direct HTTP download of PDF URLs gets 403'd by Akamai too).
        Returns same 4-tuple as aiohttp path, or None on failure.
        """
        await self._ensure_browser()
        if self._browser is None:
            return None

        page = None
        context = None
        try:
            # Isolated context per page — no cookie bleed between URLs
            context = await self._browser.new_context(
                user_agent=self.user_agent
            )
            page = await context.new_page()

            # Block images/fonts/stylesheets — we only need HTML/file content,
            # not visual rendering. Cuts ~40% of network time.
            # Optional request param: Playwright may call with (route) or (route, request)
            # depending on version — omitting it raises TypeError at runtime.
            async def _route_handler(route, request=None):
                if route.request.resource_type in {'image', 'font', 'stylesheet'}:
                    await route.abort()
                else:
                    await route.continue_()
            await page.route('**/*', _route_handler)

            # 25s timeout (separate from aiohttp's --timeout setting) —
            # headed browsers need more time for page load + networkidle
            response = await page.goto(url, wait_until='networkidle', timeout=25000)
            if response is None:
                self.logger.warning(f"Playwright navigation returned None: {url}")
                return None

            status = response.status
            content_type = response.headers.get('content-type', '')

            is_file = self.should_download_file(url, content_type)
            if not is_file and self._left_host(page.url):
                self.logger.info(f"Redirected off-host, not saved: {url} -> {page.url}")
                return '', content_type, 'offsite', status

            if is_file:
                # PDFs/docs: get raw response body (not rendered DOM)
                body = await response.body()
                self.logger.info(f"Fetched via Playwright (Tier 3, file): {url}")
                return body, content_type, 'file', status
            else:
                # HTML: get fully rendered DOM (after JS execution)
                html = await page.content()
                self.logger.info(f"Fetched via Playwright (Tier 3, HTML): {url}")
                return html, content_type, 'html', status

        except Exception as e:
            self.logger.warning(f"Playwright fetch failed for {url}: {e}")
            return None
        finally:
            if page:
                await page.close()
            if context:
                await context.close()

    async def _sitemap_fetch(self, url: str) -> bytes | None:
        """Fetch a discovery URL (robots.txt / sitemap) as bytes via the
        tier-escalating fetcher, so Akamai-gated hosts resolve at Tier 2.

        Returns the body as bytes on HTTP 200, else None (non-200 or error) —
        the best-effort contract _fetch_sitemap_urls expects. .xml comes back
        as 'html' (str); robots.txt (.txt) comes back as 'file' (bytes).
        """
        try:
            content, _content_type, _kind, status = await self.fetch_with_retry(url)
        except Exception:
            return None
        if status != 200 or content is None:
            return None
        if isinstance(content, bytes):
            return content
        return content.encode("utf-8", errors="replace")

    # --- FETCH WITH TIER ESCALATION ---
    # Tier 1 (aiohttp) handles most sites. On 403 or 429 (after retries exhausted),
    # escalates to Tier 2 (curl_cffi), then Tier 3 (Playwright) if still blocked.
    # Non-escalatable errors use exponential backoff with jitter and Retry-After
    # header support.

    async def fetch_with_retry(self, url: str, method: str = 'GET') -> tuple:
        """Fetch a URL, escalating through tiers on 403 or 429.

        Flow: aiohttp → (on 403/429) → curl_cffi → (on fail) → Playwright → (on fail) → return status
        Returns (content, content_type, kind, status) for all paths.
        """
        last_error = None
        if self._skip_tier1:
            tier2_result = await self._fetch_via_curl_cffi(url)
            if tier2_result is not None:
                return tier2_result
            if self.playwright_enabled:
                tier3_result = await self._fetch_via_playwright(url)
                if tier3_result is not None:
                    return tier3_result
            # Tier 2/3 could not serve it either: fall through to the normal Tier 1 path
        for attempt in range(self.max_retries):
            try:
                async with self.session.request(method, url, allow_redirects=True) as response:
                    content_type = response.headers.get('Content-Type', '')
                    status = response.status

                    # Retry transient server errors with backoff
                    if status in RETRYABLE_STATUS and attempt < self.max_retries - 1:
                        # Must read response body before continuing to avoid unclosed response warnings
                        await response.read()
                        retry_after = response.headers.get('Retry-After')
                        wait = self._parse_retry_after(retry_after, attempt)
                        self.logger.debug(f"Status {status}, retrying after {wait:.1f}s: {url}")
                        await asyncio.sleep(min(wait, 30.0))
                        continue

                    # Escalate 403/429 to Tier 2 (curl_cffi Chrome fingerprint)
                    if status in (403, 429):
                        self._tier1_blocks_in_a_row += 1
                        if not self._skip_tier1 and self._tier1_blocks_in_a_row >= _TIER1_SKIP_AFTER:
                            self._skip_tier1 = True
                            self.logger.info(
                                f"Tier 1 blocked {self._tier1_blocks_in_a_row} times in a row on "
                                f"{self.base_domain}; starting at Tier 2 for the rest of this crawl"
                            )
                        # Release the aiohttp connection before slow Tier 2/3 work.
                        # Without this, the connection pool slot stays occupied during
                        # potentially multi-second browser fetches.
                        await response.read()

                        self.logger.debug(f"{status} from aiohttp, escalating to Tier 2: {url}")
                        tier2_result = await self._fetch_via_curl_cffi(url)
                        if tier2_result is not None:
                            return tier2_result

                        # Tier 2 failed, escalate to Tier 3 (Playwright headed)
                        if self.playwright_enabled:
                            self.logger.debug(f"Tier 2 failed, escalating to Tier 3: {url}")
                            tier3_result = await self._fetch_via_playwright(url)
                            if tier3_result is not None:
                                return tier3_result

                        # All tiers failed, will return original status below
                    else:
                        self._tier1_blocks_in_a_row = 0

                    # Determine if this is a downloadable file or HTML
                    is_file = self.should_download_file(url, content_type)
                    if not is_file and self._left_host(response.url):
                        await response.read()
                        self.logger.info(f"Redirected off-host, not saved: {url} -> {response.url}")
                        return '', content_type, 'offsite', status
                    if is_file:
                        content = await response.read()
                        self.logger.info(f"Fetched via aiohttp (Tier 1, file): {url}")
                        return content, content_type, 'file', status
                    else:
                        # Charset-safe decode: aiohttp's resp.text() falls back to
                        # chardet when Content-Type lacks a charset, and chardet
                        # frequently mis-guesses UTF-8 as Windows-1252 — producing
                        # mojibake like `—` → `â€"`. Prefer the declared charset
                        # unless it's one of the legacy HTTP defaults that servers
                        # send incorrectly; otherwise force UTF-8 with replacement.
                        raw = await response.read()
                        declared = (response.charset or '').lower()
                        encoding = declared if declared and declared not in ('iso-8859-1', 'windows-1252') else 'utf-8'
                        try:
                            content = raw.decode(encoding)
                        except (UnicodeDecodeError, LookupError):
                            content = raw.decode('utf-8', errors='replace')
                        self.logger.info(f"Fetched via aiohttp (Tier 1, HTML): {url}")
                        return content, content_type, 'html', status
            except asyncio.TimeoutError:
                last_error = "Timeout"
                if attempt < self.max_retries - 1:
                    wait = self._backoff(attempt)
                    self.logger.debug(f"Timeout, retrying after {wait:.1f}s: {url}")
                    await asyncio.sleep(wait)
            except Exception as e:
                last_error = str(e)
                if attempt < self.max_retries - 1:
                    wait = self._backoff(attempt)
                    self.logger.debug(f"Error ({e}), retrying after {wait:.1f}s: {url}")
                    await asyncio.sleep(wait)
        raise Exception(f"Failed after {self.max_retries} attempts: {last_error}")

    async def download_file(self, url: str, content: bytes, content_type: str,
                            found_on: str | None = None):
        file_hash = compute_hash(content)
        if self.url_store.has_file_hash(file_hash):
            return

        filename = generate_filename_binary(url, content_type)
        filepath = self.files_dir / filename

        # Handle filename collisions (rare but possible with 8-char hash).
        # Preserve original stem/ext outside the loop to avoid compounding suffixes.
        orig_stem = Path(filename).stem
        orig_ext = Path(filename).suffix
        counter = 1
        while filepath.exists():
            filename = f"{orig_stem}_{counter}{orig_ext}"
            filepath = self.files_dir / filename
            counter += 1

        async with aiofiles.open(filepath, 'wb') as f:
            await f.write(content)
        self.url_store.add_file_hash(file_hash)
        self.stats['files_downloaded'] += 1
        self.stats['total_bytes'] += len(content)

        name_part = Path(filename).stem.split('__')[-1].rsplit('_', 1)[0]
        title = name_part.replace('-', ' ').replace('_', ' ').title()
        self.url_store.upsert_metadata(
            url, filename=filename, hostname=self.base_domain,
            title=title, found_on=found_on, file_type="binary",
            content_hash=file_hash, file_size=len(content),
            crawl_gen=self.crawl_gen,
        )

        size_mb = len(content) / (1024 * 1024)
        self.logger.debug(f"Downloaded file: {filepath.name} ({size_mb:.2f} MB)")

    async def save_html(self, url: str, content: str):
        filename = generate_filename_web(url)
        html_filename = Path(filename).with_suffix('.html').name
        filepath = self.pages_dir / html_filename

        # Handle filename collisions.
        # Preserve original stem outside the loop to avoid compounding suffixes.
        orig_stem = Path(html_filename).stem
        counter = 1
        while filepath.exists():
            html_filename = f"{orig_stem}_{counter}.html"
            filepath = self.pages_dir / html_filename
            counter += 1

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(content)
        self.stats['pages_downloaded'] += 1
        self.stats['total_bytes'] += len(content.encode('utf-8'))
        self.logger.debug(f"Saved page: {filepath.name}")

    async def save_text(self, url: str, text: str):
        """Save extracted markdown and record metadata."""
        filename = generate_filename_web(url)
        filepath = self.text_dir / filename

        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(text)

        title = None
        if text.startswith('---'):
            for line in text.split('\n')[1:20]:
                if line.startswith('title:'):
                    title = line[6:].strip().strip('"').strip("'")
                    break
                if line.strip() == '---':
                    break

        self.url_store.upsert_metadata(
            url, filename=filename, hostname=self.base_domain,
            title=title, file_type="web",
            content_hash=compute_hash(text),
            file_size=len(text.encode()),
            crawl_gen=self.crawl_gen,
        )
        self.stats['text_extracted'] += 1
        self.logger.debug(f"Saved text: {filepath.name}")

    def is_access_denied(self, content: str, status: int) -> bool:
        if status in (401, 403, 429):
            return True
        if len(content) < 2000 and 'Access Denied' in content:
            return True
        return False

    async def process_url(self, url: str, found_on: str | None = None):
        """Fetch one URL, persist its content, and queue its outbound links.

        Files are downloaded as-is; HTML is parsed off-thread, saved, its
        extracted text stamped at the current crawl generation, and any new
        (not-yet-visited) links appended to the queue. All errors are caught and
        recorded so one bad page never aborts the crawl."""
        async with self.semaphore:
            try:
                await asyncio.sleep(self.delay)

                content, content_type, content_kind, status = await self.fetch_with_retry(url)

                if content_kind == 'offsite':
                    self.stats['offsite'] += 1
                    return

                if content_kind == 'file':
                    if len(content) > self.max_file_size:
                        self.logger.debug(f"Skipping large file: {url} ({len(content) / (1024*1024):.2f} MB)")
                        return
                    await self.download_file(url, content, content_type, found_on=found_on)
                else:
                    if self.is_access_denied(content, status):
                        self.stats['denied'] += 1
                        self.denied_urls.append(url)
                        self.logger.debug(f"Access denied ({status}): {url}")
                        return

                    if status >= 400:
                        # Error pages ("Page not found") are not content and their
                        # links are the site chrome, not new pages.
                        self.stats['not_found'] += 1
                        self.logger.debug(f"Error page ({status}), not saved: {url}")
                        return

                    # Offload parsing + text extraction to process pool
                    loop = asyncio.get_running_loop()
                    links, extracted_text = await loop.run_in_executor(
                        self.executor, _parse_and_extract, content, url,
                        self.base_domain, self.strip_tracking_params,
                        self._exclude_pattern_strings, status,
                        self.path_prefix, self._include_pattern_strings or None,
                    )

                    # Save HTML
                    await self.save_html(url, content)

                    # Save extracted text if we got any
                    if extracted_text and extracted_text.strip():
                        await self.save_text(url, extracted_text)

                    # Queue new links (with current url as found_on)
                    for link in links:
                        if not self.url_store.contains(link):
                            self.urls_to_visit.append((link, url))

            except Exception as e:
                self.stats['errors'] += 1
                self.failed_urls.append(url)
                self.logger.debug(f"Error processing {url}: {e}")

    async def _progress_reporter(self):
        """Periodically log progress summary."""
        while True:
            await asyncio.sleep(self.progress_interval)
            self.logger.info(
                f"Progress: {self.url_store.count} visited | "
                f"{self.stats['pages_downloaded']} pages | "
                f"{self.stats['text_extracted']} text | "
                f"{self.stats['files_downloaded']} files | "
                f"{self.stats['denied']} denied | "
                f"{self.stats['not_found']} not found | "
                f"{self.stats['offsite']} off-host | "
                f"{self.stats['errors']} errors | "
                f"{self.stats['total_bytes'] / (1024*1024):.1f} MB | "
                f"{len(self.urls_to_visit)} queued"
            )

    async def _checkpoint_saver(self):
        """Periodically checkpoint queue + stats to SQLite for crash recovery."""
        while True:
            await asyncio.sleep(self.checkpoint_interval)
            self.url_store.save_queue(self.urls_to_visit)
            self.url_store.save_stats(self.stats)
            self.logger.debug(f"Checkpoint saved: {len(self.urls_to_visit)} URLs in queue")

    async def crawl(self):
        """Run the breadth-first crawl loop until the queue and in-flight tasks drain.

        Optionally seeds new URLs from the sitemap, then fetches each queued URL
        through the `_should_fetch` gate (skips already-visited and this-run
        duplicates). `crawl_complete` is set True ONLY on a clean loop exit — a
        crash propagates out with it still False, which keeps the last complete
        manifest intact (see run()). The finally block always checkpoints the
        queue and tears down the session/browser."""
        await self.init_session()

        # Seed from sitemap if enabled (best-effort, non-blocking).
        # Routes through _sitemap_fetch so Akamai-gated hosts resolve at Tier 2;
        # a naive Tier-1 client 403s and returns [] (silent no-op in prod).
        if self.use_sitemap:
            parsed_start = urlparse(self.start_url)
            try:
                sitemap_entries = await asyncio.wait_for(
                    _fetch_sitemap_entries(
                        self._sitemap_fetch,
                        self.base_domain,
                        parsed_start.scheme or "https",
                    ),
                    timeout=60,
                )
            except Exception as e:
                # Best-effort, but never silent: with seeding on for every host, a quiet
                # failure would be indistinguishable from a site that has no sitemap.
                self.logger.warning(f"Sitemap discovery failed for {self.base_domain}; crawling from links only: {e!r}")
                sitemap_entries = []
            if sitemap_entries:
                added = 0
                kept_by_date = 0
                dropped = {"off-host": 0, "out of scope": 0, "not included": 0, "excluded": 0, "already known": 0}
                for surl, lastmod in sitemap_entries:
                    normalized = _normalize_url(surl, strip_tracking=self.strip_tracking_params)
                    nparsed = urlparse(normalized)
                    if nparsed.netloc != self.base_domain:
                        dropped["off-host"] += 1
                        continue
                    if self.path_prefix and not _url_within_path_prefix(nparsed.path, self.path_prefix):
                        dropped["out of scope"] += 1
                        continue
                    if self._compiled_include_patterns and not any(
                        p.search(normalized) for p in self._compiled_include_patterns
                    ):
                        dropped["not included"] += 1
                        continue
                    if _url_excluded(normalized, self._compiled_exclude_patterns):
                        current_event = (
                            self.event_keep_since is not None and lastmod is not None
                            and lastmod[:10] >= self.event_keep_since
                            and self._event_pattern.search(normalized) is not None
                            and not _url_excluded(normalized, self._compiled_non_event_excludes)
                        )
                        if not current_event:
                            dropped["excluded"] += 1
                            continue
                        kept_by_date += 1
                    if self.url_store.contains(normalized):
                        dropped["already known"] += 1
                        continue
                    self.urls_to_visit.append((normalized, None))
                    added += 1
                drops = ", ".join(f"{k} {v}" for k, v in dropped.items() if v)
                self.logger.info(
                    f"Sitemap: {len(sitemap_entries)} entries found; seeded {added}"
                    + (f"; events kept by date {kept_by_date}" if kept_by_date else "")
                    + (f"; dropped {drops}" if drops else "")
                )
            else:
                self.logger.info(f"Sitemap: none found for {self.base_domain}; crawling from links only")

        # Start background tasks
        progress_task = asyncio.create_task(self._progress_reporter())
        checkpoint_task = asyncio.create_task(self._checkpoint_saver())

        try:
            tasks = []

            while self.urls_to_visit or tasks:
                while self.urls_to_visit and len(tasks) < self.max_concurrent:
                    url, found_on = self.urls_to_visit.popleft()

                    if _should_fetch(url, self.seen_this_run, self.url_store):
                        self.seen_this_run.add(url)
                        self.url_store.add(url)
                        task = asyncio.create_task(self.process_url(url, found_on=found_on))
                        tasks.append(task)

                if tasks:
                    done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = list(tasks)

            # Loop exited normally (queue drained, no in-flight tasks) → complete pass.
            self.crawl_complete = True

        finally:
            progress_task.cancel()
            checkpoint_task.cancel()
            # Final checkpoint
            self.url_store.save_queue(self.urls_to_visit)
            self.url_store.save_stats(self.stats)
            await self.close_session()
            await self._close_browser()

    async def run(self):
        """Drive a full crawl, then regenerate the manifest and upload — atomically.

        The manifest is rewritten only after a complete, non-capped pass
        (`_should_write_manifest`), so a partial or crashed run leaves the last
        complete manifest.json — and any S3 copy — untouched. The S3 upload runs
        only if the crawl returned normally; a crash short-circuits both."""
        start_time = datetime.now()
        self.logger.info(f"Starting scraper at {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

        await self.crawl()

        # Generate manifest.json — only after a complete, non-capped pass, so a
        # partial/crashed/capped run leaves the last complete manifest intact.
        manifest_files = self.url_store.export_manifest(self.base_domain)
        if _should_write_manifest(
            crawl_complete=self.crawl_complete,
            capped=self.capped,
            has_entries=bool(manifest_files),
        ):
            manifest = build_manifest(manifest_files, self.base_domain)
            manifest_path = self.base_dir / "manifest.json"
            write_manifest(manifest, manifest_path)
            self.logger.info(f"Generated manifest.json: {len(manifest_files)} entries")
        elif manifest_files:
            self.logger.info(
                "Skipped manifest regeneration (incomplete or capped pass); "
                "kept last complete manifest.json"
            )

        # Upload to S3 if configured
        if self.s3_bucket:
            from scrape_website.s3 import upload_to_s3
            upload_to_s3(self.base_dir, self.s3_bucket)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Write denied URLs to file
        if self.denied_urls:
            denied_file = self.logs_dir / 'access_denied.txt'
            async with aiofiles.open(denied_file, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(self.denied_urls) + '\n')

        # Write failed URLs to file for retry
        if self.failed_urls:
            failed_file = self.logs_dir / 'failed_urls.txt'
            async with aiofiles.open(failed_file, 'w', encoding='utf-8') as f:
                await f.write('\n'.join(self.failed_urls) + '\n')

        self.logger.info("")
        self.logger.info("=" * 80)
        self.logger.info("SCRAPING COMPLETED")
        self.logger.info("=" * 80)
        self.logger.info(f"Duration: {duration:.2f} seconds")
        self.logger.info(f"URLs visited: {self.url_store.count}")
        self.logger.info(f"Pages downloaded: {self.stats['pages_downloaded']}")
        self.logger.info(f"Text extracted: {self.stats['text_extracted']}")
        self.logger.info(f"Files downloaded: {self.stats['files_downloaded']}")
        self.logger.info(f"Access denied: {self.stats['denied']}")
        self.logger.info(f"Error pages skipped (4xx/5xx): {self.stats['not_found']}")
        self.logger.info(f"Off-host redirects skipped: {self.stats['offsite']}")
        self.logger.info(f"Total data: {self.stats['total_bytes'] / (1024*1024):.2f} MB")
        self.logger.info(f"Errors: {self.stats['errors']}")
        self.logger.info(f"Output location: {self.base_dir}")
        if self.denied_urls:
            self.logger.info(f"Denied URLs logged to: {self.logs_dir / 'access_denied.txt'}")
        if self.failed_urls:
            self.logger.info(f"Failed URLs logged to: {self.logs_dir / 'failed_urls.txt'}")
            self.logger.info(f"  Retry with: scrape-website --retry {self.logs_dir / 'failed_urls.txt'}")
        self.logger.info("=" * 80)

        # Cleanup
        self.executor.shutdown(wait=False)
        self.url_store.close()


def collect_urls(args) -> list[str]:
    """Collect URLs from CLI arg and/or file."""
    urls = []
    if args.url:
        urls.append(args.url)
    if args.file:
        path = Path(args.file)
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    if args.retry:
        path = Path(args.retry)
        for line in path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith('#'):
                urls.append(line)
    return urls


def parse_args():
    parser = argparse.ArgumentParser(description='Scrape an entire website (pages + documents + clean text)')
    parser.add_argument('url', nargs='?', help='Starting URL to scrape (e.g. https://example.com/)')
    parser.add_argument('--file', '-f', help='File with URLs to scrape (one per line)')
    parser.add_argument('--retry', '-r', help='File with failed URLs to retry (e.g. data/example.com/logs/failed_urls.txt)')
    parser.add_argument('--concurrency', type=int, default=CONFIG['max_concurrent'],
                        help=f"Max concurrent requests (default: {CONFIG['max_concurrent']})")
    parser.add_argument('--timeout', type=int, default=CONFIG['timeout'],
                        help=f"Request timeout in seconds (default: {CONFIG['timeout']})")
    parser.add_argument('--delay', type=float, default=CONFIG['delay_between_requests'],
                        help=f"Delay between requests in seconds (default: {CONFIG['delay_between_requests']})")
    parser.add_argument('--output-dir', '-o', default=None,
                        help='Root directory for output (default: data/). Output goes to <output-dir>/<domain>/.')
    parser.add_argument('--s3-bucket', default=None,
                        help='S3 bucket to upload results to after scrape completes (optional)')
    parser.add_argument('--fresh', action='store_true',
                        help='Ignore any saved checkpoint and start fresh')
    parser.add_argument('--exclude-pattern', action='append', default=None,
                        metavar='PATTERN',
                        help='Regex pattern to exclude URLs (repeatable; appends to defaults)')
    parser.add_argument('--no-default-excludes', action='store_true',
                        help='Clear the default exclude patterns (use only --exclude-pattern values)')
    parser.add_argument('--include-pattern', action='append', default=None,
                        metavar='PATTERN',
                        help='Regex pattern — only URLs matching at least one are crawled (repeatable)')
    tracking_group = parser.add_mutually_exclusive_group()
    tracking_group.add_argument('--strip-tracking-params', action='store_true', default=True,
                                dest='strip_tracking_params',
                                help='Strip tracking query params like utm_* (default)')
    tracking_group.add_argument('--no-strip-tracking-params', action='store_false',
                                dest='strip_tracking_params',
                                help='Keep tracking query params in URLs')
    sitemap_group = parser.add_mutually_exclusive_group()
    sitemap_group.add_argument('--use-sitemap', action='store_true', default=True,
                               dest='use_sitemap',
                               help='Seed crawl queue from sitemap.xml (default)')
    sitemap_group.add_argument('--no-use-sitemap', action='store_false',
                               dest='use_sitemap',
                               help='Do not fetch sitemap.xml for seed URLs')
    path_group = parser.add_mutually_exclusive_group()
    path_group.add_argument('--scope-to-path', dest='scope_to_path',
                            action='store_true',
                            help='Restrict crawl to URLs under the starting URL path (default: auto)')
    path_group.add_argument('--no-scope-to-path', dest='scope_to_path',
                            action='store_false',
                            help='Crawl the entire domain regardless of starting URL path')
    parser.set_defaults(scope_to_path=None)
    parser.add_argument('--event-keep-since', default=None, metavar='YYYY-MM-DD',
                        help='Also crawl sitemap-listed event pages whose lastmod is on or after this date '
                             '(R7 excludes event pages otherwise)')
    parser.add_argument('--no-playwright', action='store_true', default=False,
                        help="Disable Tier 3 Playwright escalation (stop at curl_cffi)")
    return parser.parse_args()


async def main():
    args = parse_args()
    urls = collect_urls(args)

    if not urls:
        print("Error: provide a URL, --file, or --retry")
        raise SystemExit(1)

    # Build exclude patterns list
    if args.no_default_excludes:
        exclude_patterns = list(args.exclude_pattern or [])
    elif args.exclude_pattern:
        exclude_patterns = list(_DEFAULT_EXCLUDE_PATTERNS) + args.exclude_pattern
    else:
        exclude_patterns = None  # use defaults inside WebsiteScraper

    # Group URLs by domain so each domain gets one scraper
    by_domain: dict[str, list[str]] = {}
    for url in urls:
        domain = urlparse(url).netloc
        by_domain.setdefault(domain, []).append(url)

    # Run all domains concurrently
    async with asyncio.TaskGroup() as tg:
        for domain, domain_urls in by_domain.items():
            scraper = WebsiteScraper(
                domain_urls[0], fresh=args.fresh,
                exclude_patterns=exclude_patterns,
                include_patterns=args.include_pattern,
                strip_tracking_params=args.strip_tracking_params,
                use_sitemap=args.use_sitemap,
                concurrency=args.concurrency,
                timeout=args.timeout,
                delay=args.delay,
                output_dir=args.output_dir,
                scope_to_path=args.scope_to_path,
                s3_bucket=args.s3_bucket,
                playwright_enabled=not args.no_playwright,
                event_keep_since=args.event_keep_since,
            )
            # Seed any additional URLs for this domain
            for extra in domain_urls[1:]:
                normalized = scraper.normalize_url(extra)
                if not scraper.url_store.contains(normalized):
                    scraper.urls_to_visit.append((normalized, None))
            tg.create_task(scraper.run())
