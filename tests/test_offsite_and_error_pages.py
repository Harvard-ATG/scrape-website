"""Two global defaults learned from the 2026-10-27 dev run of classics.fas.harvard.edu.

1. A page whose redirect chain ends on another host is not this site's page: its
   content is not saved and its links are not followed. Classics' /links/<slug>
   pages redirect to outside sites; resolving those pages' relative links against
   the classics hostname produced 1,898 phantom URLs (77% of the crawl).
2. A 4xx/5xx response is not saved and its links are not followed. Those phantom
   URLs were each fetched and saved as a Drupal "Page not found" page.
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor

from scrape_website.scraper import WebsiteScraper

URL = "https://example.com/links/outside"
HTML_WITH_LINK = '<html><body><a href="/core/services">x</a></body></html>'


class _Response:
    def __init__(self, status, final_url):
        self.status = status
        self.url = final_url
        self.headers = {"Content-Type": "text/html"}
        self.charset = "utf-8"

    async def read(self):
        return HTML_WITH_LINK.encode()


class _Request:
    def __init__(self, response):
        self._response = response

    async def __aenter__(self):
        return self._response

    async def __aexit__(self, *exc):
        return False


class _Session:
    def __init__(self, status, final_url):
        self._response = _Response(status, final_url)

    def request(self, method, url, allow_redirects=True):
        return _Request(self._response)


def _scraper(tmp_path):
    scraper = WebsiteScraper(
        "https://example.com/", output_dir=tmp_path, use_sitemap=False,
        playwright_enabled=False, delay=0,
    )
    scraper.executor.shutdown(wait=False)
    scraper.executor = ThreadPoolExecutor(max_workers=2)
    return scraper


def _saved_pages(tmp_path):
    return list((tmp_path / "example.com" / "pages").glob("*"))


async def _tier1_reports_an_offsite_redirect(tmp_path):
    scraper = _scraper(tmp_path)
    scraper.session = _Session(200, "https://outside.org/home")
    _, _, kind, status = await scraper.fetch_with_retry(URL)
    assert (kind, status) == ("offsite", 200)


async def _tier1_keeps_a_same_host_redirect(tmp_path):
    scraper = _scraper(tmp_path)
    scraper.session = _Session(200, "https://example.com/links/outside/")
    content, _, kind, _ = await scraper.fetch_with_retry(URL)
    assert kind == "html"
    assert content == HTML_WITH_LINK


async def _tier1_treats_www_as_the_same_host(tmp_path):
    scraper = _scraper(tmp_path)
    scraper.session = _Session(200, "https://www.example.com/links/outside")
    _, _, kind, _ = await scraper.fetch_with_retry(URL)
    assert kind == "html"


async def _offsite_page_is_neither_saved_nor_expanded(tmp_path):
    scraper = _scraper(tmp_path)

    async def fake_fetch(url, method="GET"):
        return HTML_WITH_LINK, "text/html", "offsite", 200

    scraper.fetch_with_retry = fake_fetch
    queue_before = list(scraper.urls_to_visit)
    await scraper.process_url(URL)
    assert _saved_pages(tmp_path) == []
    assert list(scraper.urls_to_visit) == queue_before
    assert scraper.stats["offsite"] == 1
    assert scraper.stats["pages_downloaded"] == 0


async def _not_found_page_is_neither_saved_nor_expanded(tmp_path):
    scraper = _scraper(tmp_path)

    async def fake_fetch(url, method="GET"):
        return HTML_WITH_LINK, "text/html", "html", 404

    scraper.fetch_with_retry = fake_fetch
    queue_before = list(scraper.urls_to_visit)
    await scraper.process_url(URL)
    assert _saved_pages(tmp_path) == []
    assert list(scraper.urls_to_visit) == queue_before
    assert scraper.stats["not_found"] == 1
    assert scraper.stats["pages_downloaded"] == 0


async def _ok_page_is_still_saved_and_expanded(tmp_path):
    scraper = _scraper(tmp_path)

    async def fake_fetch(url, method="GET"):
        return HTML_WITH_LINK, "text/html", "html", 200

    scraper.fetch_with_retry = fake_fetch
    await scraper.process_url(URL)
    assert len(_saved_pages(tmp_path)) == 1
    assert ("https://example.com/core/services", URL) in scraper.urls_to_visit


def test_tier1_reports_an_offsite_redirect(tmp_path):
    asyncio.run(_tier1_reports_an_offsite_redirect(tmp_path))


def test_tier1_keeps_a_same_host_redirect(tmp_path):
    asyncio.run(_tier1_keeps_a_same_host_redirect(tmp_path))


def test_tier1_treats_www_as_the_same_host(tmp_path):
    asyncio.run(_tier1_treats_www_as_the_same_host(tmp_path))


def test_offsite_page_is_neither_saved_nor_expanded(tmp_path):
    asyncio.run(_offsite_page_is_neither_saved_nor_expanded(tmp_path))


def test_not_found_page_is_neither_saved_nor_expanded(tmp_path):
    asyncio.run(_not_found_page_is_neither_saved_nor_expanded(tmp_path))


def test_ok_page_is_still_saved_and_expanded(tmp_path):
    asyncio.run(_ok_page_is_still_saved_and_expanded(tmp_path))
