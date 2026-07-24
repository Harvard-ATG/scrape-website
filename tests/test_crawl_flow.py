"""End-to-end crawl-loop flow tests over a mocked website.

These drive the REAL crawl()/run() loop against a small in-memory fake site so
the three fetch pathways are visible as they play out across pages. The network
tier (fetch_with_retry) and the CPU-bound parser (_parse_and_extract) are
stubbed, so no sockets or subprocesses are involved:

  - fresh:  --fresh clears state → generation 1 → every page fetched, manifest
            written once at completion.
  - resume: no flag + non-empty queue → SAME generation; already-visited URLs
            are skipped, only the queued remainder is fetched.
  - update: no flag + empty queue → generation ADVANCES; a new page discovered
            via the sitemap is fetched at the new generation, while existing
            pages keep their old generation and are skipped.

They also pin the manifest-atomicity invariant: a crash mid-crawl leaves the
prior manifest.json byte-for-byte intact and performs NO S3 upload, because
`crawl_complete` is only set on a clean loop exit.

NOTE — the deferred `--update` flag: today `_should_fetch` always skips any
already-visited URL, so an "update" pass discovers new pages (via the sitemap)
but never RE-fetches changed ones. The future `--update` flag will flip exactly
one line — the `_should_fetch` gate at scraper.py — to re-fetch rows whose
crawl_gen is older than the current pass. That behavior does not exist yet and
is intentionally not asserted here.
"""
import asyncio
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

import scrape_website.scraper as scraper_mod
from scrape_website.scraper import URLStore, WebsiteScraper

HOME = "https://example.com/"
PAGE_A = "https://example.com/a"
PAGE_B = "https://example.com/b"
PAGE_C = "https://example.com/c"


def _install_fake_site(monkeypatch, scraper, site, fetched=None):
    """Wire a scraper to serve `site` (url -> (links, text)) without I/O.

    Replaces the fetch tier and the parser with table lookups, swaps the
    process pool for a thread pool (so the patched module-level parser is
    actually used — a ProcessPoolExecutor would re-import the original in its
    child), and no-ops the session/browser lifecycle. If `fetched` is given,
    every URL that reaches the fetch tier is appended to it, so a test can
    assert exactly which pages were hit vs. skipped.
    """
    async def fake_fetch(url, method="GET"):
        if fetched is not None:
            fetched.append(url)
        return f"<html>{url}</html>", "text/html", "html", 200

    monkeypatch.setattr(scraper, "fetch_with_retry", fake_fetch)

    def fake_parse(html_content, url, *args, **kwargs):
        links, text = site[url]
        return list(links), text

    monkeypatch.setattr(scraper_mod, "_parse_and_extract", fake_parse)

    scraper.executor.shutdown(wait=False)
    scraper.executor = ThreadPoolExecutor(max_workers=2)

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(scraper, "init_session", _noop)
    monkeypatch.setattr(scraper, "close_session", _noop)
    monkeypatch.setattr(scraper, "_close_browser", _noop)


def _db_path(tmp_path):
    return tmp_path / "example.com" / "logs" / "state.db"


def _gen(tmp_path, url):
    # run() closes the scraper's own store, so read final state from a fresh
    # connection to the on-disk state.db.
    conn = sqlite3.connect(str(_db_path(tmp_path)))
    try:
        row = conn.execute(
            "SELECT crawl_gen FROM visited WHERE url=?", (url,)
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def _make(tmp_path, **kw):
    return WebsiteScraper(
        HOME, output_dir=tmp_path, concurrency=2, delay=0,
        playwright_enabled=False, **kw,
    )


def test_fresh_crawl_fetches_all_pages_at_gen_one(tmp_path, monkeypatch):
    site = {
        HOME: ([PAGE_A, PAGE_B], "# Home"),
        PAGE_A: ([], "# A"),
        PAGE_B: ([], "# B"),
    }
    fetched = []
    scraper = _make(tmp_path, fresh=True, use_sitemap=False)
    _install_fake_site(monkeypatch, scraper, site, fetched)
    try:
        asyncio.run(scraper.run())

        assert scraper.crawl_complete is True
        assert set(fetched) == {HOME, PAGE_A, PAGE_B}   # every page fetched once
        assert scraper.crawl_gen == 1
        assert _gen(tmp_path, HOME) == 1
        assert _gen(tmp_path, PAGE_A) == 1
        assert _gen(tmp_path, PAGE_B) == 1

        # Manifest written at completion, one entry per saved text page.
        store = URLStore(_db_path(tmp_path))
        assert len(store.export_manifest("example.com")) == 3
        store.close()
        manifest_path = tmp_path / "example.com" / "manifest.json"
        assert manifest_path.exists()
        assert PAGE_A in manifest_path.read_text()
    finally:
        scraper.executor.shutdown(wait=False)
        scraper.url_store.close()


def test_resume_skips_visited_and_keeps_generation(tmp_path, monkeypatch):
    # Prior interrupted pass at gen 1: /a already visited; the checkpointed
    # queue still holds /a (done) and /b (not yet reached).
    seed = _make(tmp_path, fresh=True, use_sitemap=False)
    seed.url_store.add(PAGE_A)
    seed.url_store.upsert_metadata(PAGE_A, filename="a.md", hostname="example.com", crawl_gen=1)
    seed.url_store.save_queue([(PAGE_A, None), (PAGE_B, None)])
    seed.executor.shutdown(wait=False)
    seed.url_store.close()

    site = {PAGE_A: ([], "# A v2"), PAGE_B: ([], "# B")}
    fetched = []
    scraper = _make(tmp_path, fresh=False, use_sitemap=False)
    _install_fake_site(monkeypatch, scraper, site, fetched)
    try:
        assert scraper.crawl_gen == 1                    # resume → SAME generation
        asyncio.run(scraper.run())

        assert fetched == [PAGE_B]                        # /a skipped (already visited)
        assert _gen(tmp_path, PAGE_B) == 1                # remainder stamped at same gen
        assert _gen(tmp_path, PAGE_A) == 1                # untouched
    finally:
        scraper.executor.shutdown(wait=False)
        scraper.url_store.close()


def test_update_pass_discovers_new_page_via_sitemap_at_next_gen(tmp_path, monkeypatch):
    # Prior COMPLETE pass at gen 1: home + /a + /b visited, queue drained.
    seed = _make(tmp_path, fresh=True, use_sitemap=False)
    for i, url in enumerate((HOME, PAGE_A, PAGE_B)):
        seed.url_store.add(url)
        seed.url_store.upsert_metadata(url, filename=f"p{i}.md", hostname="example.com", crawl_gen=1)
    seed.url_store.save_queue([])
    seed.executor.shutdown(wait=False)
    seed.url_store.close()

    # The site now advertises a fourth page in its sitemap.
    async def fake_sitemap(fetch, host, scheme):
        return [HOME, PAGE_A, PAGE_B, PAGE_C]

    monkeypatch.setattr(scraper_mod, "_fetch_sitemap_urls", fake_sitemap)

    site = {HOME: ([], "# Home"), PAGE_C: ([], "# C (new)")}
    fetched = []
    scraper = _make(tmp_path, fresh=False, use_sitemap=True)
    _install_fake_site(monkeypatch, scraper, site, fetched)
    try:
        assert scraper.crawl_gen == 2                    # empty queue + prior gen 1 → new pass
        asyncio.run(scraper.run())

        assert fetched == [PAGE_C]                        # only the newly-advertised page
        assert _gen(tmp_path, PAGE_C) == 2                # stamped at the update generation
        assert _gen(tmp_path, HOME) == 1                  # existing pages untouched
        assert _gen(tmp_path, PAGE_A) == 1
        assert _gen(tmp_path, PAGE_B) == 1
    finally:
        scraper.executor.shutdown(wait=False)
        scraper.url_store.close()


def test_crash_midcrawl_preserves_manifest_and_skips_upload(tmp_path, monkeypatch):
    # A prior complete manifest sits on disk (as if just pulled from S3).
    base = tmp_path / "example.com"
    base.mkdir(parents=True, exist_ok=True)
    manifest_path = base / "manifest.json"
    sentinel = '{"prior": "manifest"}'
    manifest_path.write_text(sentinel)

    upload_calls = []
    monkeypatch.setattr(
        "scrape_website.s3.upload_to_s3", lambda *a, **k: upload_calls.append(a)
    )

    site = {HOME: ([], "# Home")}
    scraper = _make(tmp_path, fresh=True, use_sitemap=False, s3_bucket="fake-bucket")
    _install_fake_site(monkeypatch, scraper, site)

    # Inject a crash the moment the loop records its first popped URL — before
    # crawl_complete can be set on a clean exit.
    def boom(url):
        raise RuntimeError("simulated crash")

    monkeypatch.setattr(scraper.url_store, "add", boom)
    try:
        with pytest.raises(RuntimeError, match="simulated crash"):
            asyncio.run(scraper.run())

        assert scraper.crawl_complete is False
        assert manifest_path.read_text() == sentinel      # prior manifest untouched
        assert upload_calls == []                          # nothing pushed to S3
    finally:
        scraper.executor.shutdown(wait=False)
        scraper.url_store.close()
