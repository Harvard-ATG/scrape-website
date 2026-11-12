"""A 429 is "slow down", not "access denied".

2026-10-28: the College WordPress platform (openresty) rate-limits per client
address. advising, gened and oue answered 429 to 10-45% of requests at
concurrency 1-5; every 429 went through all three tiers and was then counted as
denied, and a denied page is a page retired from prod. Now a 429 pauses every
fetch on the host for a backoff and the page is retried before it is given up.
"""

import asyncio

import pytest

import scrape_website.scraper as scraper_mod
from scrape_website.scraper import _RATE_LIMIT_BACKOFF, WebsiteScraper

URL = "https://example.com/page"
OK = ("<html>ok</html>", "text/html", "html", 200)
LIMITED = ("<html>slow down</html>", "text/html", "html", 429)


def _scraper(tmp_path, monkeypatch, answers):
    scraper = WebsiteScraper("https://example.com/", output_dir=tmp_path, use_sitemap=False,
                             playwright_enabled=False, delay=0)
    calls = []

    async def fake_tiered(url, method="GET"):
        calls.append(url)
        return answers.pop(0)

    scraper._fetch_tiered = fake_tiered
    slept = []

    async def fake_sleep(seconds):
        slept.append(seconds)

    monkeypatch.setattr(scraper_mod.asyncio, "sleep", fake_sleep)
    return scraper, calls, slept


async def _a_429_is_retried_after_a_backoff(tmp_path, monkeypatch):
    scraper, calls, slept = _scraper(tmp_path, monkeypatch, [LIMITED, OK])
    result = await scraper.fetch_with_retry(URL)
    assert result == OK
    assert calls == [URL, URL]
    assert slept == [_RATE_LIMIT_BACKOFF[0]]


async def _backoff_grows_and_the_last_429_is_returned(tmp_path, monkeypatch):
    scraper, calls, slept = _scraper(tmp_path, monkeypatch, [LIMITED] * (len(_RATE_LIMIT_BACKOFF) + 1))
    result = await scraper.fetch_with_retry(URL)
    assert result == LIMITED                                   # still counted denied, as before
    assert len(calls) == len(_RATE_LIMIT_BACKOFF) + 1
    assert slept == list(_RATE_LIMIT_BACKOFF)


async def _a_429_pauses_the_whole_host_not_just_one_slot(tmp_path, monkeypatch):
    scraper, calls, slept = _scraper(tmp_path, monkeypatch, [LIMITED, OK, OK])
    await scraper.fetch_with_retry(URL)                        # 429 then OK: host is now paused
    scraper._rate_limited_until = scraper_mod.time.monotonic() + 5   # as the 429 would have set it
    await scraper.fetch_with_retry("https://example.com/other")
    assert slept[-1] == pytest.approx(5, abs=1)                # the other slot waited out the pause


def test_a_429_is_retried_after_a_backoff(tmp_path, monkeypatch):
    asyncio.run(_a_429_is_retried_after_a_backoff(tmp_path, monkeypatch))


def test_backoff_grows_and_the_last_429_is_returned(tmp_path, monkeypatch):
    asyncio.run(_backoff_grows_and_the_last_429_is_returned(tmp_path, monkeypatch))


def test_a_429_pauses_the_whole_host_not_just_one_slot(tmp_path, monkeypatch):
    asyncio.run(_a_429_pauses_the_whole_host_not_just_one_slot(tmp_path, monkeypatch))
