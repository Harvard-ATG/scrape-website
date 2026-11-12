"""Sticky Tier 2: once Tier 1 (aiohttp) has been blocked enough times in a row on a
host, later fetches start at Tier 2 (curl_cffi) instead of paying one rejected
round trip per page and feeding the bot wall a stream of bot-fingerprint hits.
"""

import asyncio

from scrape_website.scraper import _TIER1_SKIP_AFTER, WebsiteScraper

URL = "https://example.com/page"


class _Response:
    def __init__(self, status):
        self.status = status
        self.url = URL
        self.headers = {"Content-Type": "text/html"}
        self.charset = "utf-8"

    async def read(self):
        return b"<html>tier1</html>"


class _Request:
    def __init__(self, status):
        self._status = status

    async def __aenter__(self):
        return _Response(self._status)

    async def __aexit__(self, *exc):
        return False


class _Session:
    """Fake aiohttp session: answers with the given status, counts calls."""

    def __init__(self, status=403):
        self.status = status
        self.calls = 0

    def request(self, method, url, allow_redirects=True):
        self.calls += 1
        return _Request(self.status)


def _scraper(tmp_path, tier2_result=("<html>tier2</html>", "text/html", "html", 200)):
    scraper = WebsiteScraper(
        "https://example.com/", output_dir=tmp_path, use_sitemap=False,
        playwright_enabled=False, delay=0,
    )
    scraper.session = _Session()
    scraper.tier2_calls = 0

    async def fake_tier2(url):
        scraper.tier2_calls += 1
        return tier2_result

    scraper._fetch_via_curl_cffi = fake_tier2
    return scraper


async def _tier1_is_skipped_after_consecutive_blocks(tmp_path):
    scraper = _scraper(tmp_path)
    for _ in range(_TIER1_SKIP_AFTER):
        content, _, _, status = await scraper.fetch_with_retry(URL)
        assert (content, status) == ("<html>tier2</html>", 200)
    assert scraper.session.calls == _TIER1_SKIP_AFTER

    content, _, _, status = await scraper.fetch_with_retry(URL)
    assert (content, status) == ("<html>tier2</html>", 200)
    assert scraper.session.calls == _TIER1_SKIP_AFTER          # Tier 1 not tried again
    assert scraper.tier2_calls == _TIER1_SKIP_AFTER + 1


async def _a_tier1_success_resets_the_block_count(tmp_path):
    scraper = _scraper(tmp_path)
    for _ in range(_TIER1_SKIP_AFTER - 1):
        await scraper.fetch_with_retry(URL)
    scraper.session.status = 200
    content, _, _, status = await scraper.fetch_with_retry(URL)
    assert (content, status) == ("<html>tier1</html>", 200)

    scraper.session.status = 403
    for _ in range(_TIER1_SKIP_AFTER - 1):
        await scraper.fetch_with_retry(URL)
    calls_before = scraper.session.calls
    await scraper.fetch_with_retry(URL)
    assert scraper.session.calls == calls_before + 1           # still trying Tier 1


async def _skipping_tier1_still_falls_back_to_it_when_tier2_fails(tmp_path):
    scraper = _scraper(tmp_path, tier2_result=None)
    for _ in range(_TIER1_SKIP_AFTER):
        await scraper.fetch_with_retry(URL)
    calls_before = scraper.session.calls

    content, _, _, status = await scraper.fetch_with_retry(URL)
    assert status == 403                                        # same answer as before the change
    assert content == "<html>tier1</html>"
    assert scraper.session.calls == calls_before + 1            # Tier 1 used as the last resort


def test_tier1_is_skipped_after_consecutive_blocks(tmp_path):
    asyncio.run(_tier1_is_skipped_after_consecutive_blocks(tmp_path))


def test_a_tier1_success_resets_the_block_count(tmp_path):
    asyncio.run(_a_tier1_success_resets_the_block_count(tmp_path))


def test_skipping_tier1_still_falls_back_to_it_when_tier2_fails(tmp_path):
    asyncio.run(_skipping_tier1_still_falls_back_to_it_when_tier2_fails(tmp_path))
