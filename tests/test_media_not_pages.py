"""Images, audio and video are not pages: not fetched when the URL says so, and
not saved or link-expanded when the server says so.

2026-10-28: seas.harvard.edu's crawl followed links to /sites/default/files/*.jpg,
fetched them as HTML, decoded the bytes as text, parsed them for links and wrote the
garbage to the log, which killed the orchestrator's log drain.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor

from scrape_website.scraper import _DEFAULT_EXCLUDE_PATTERNS, WebsiteScraper, _url_excluded

EXCLUDES = [re.compile(p) for p in _DEFAULT_EXCLUDE_PATTERNS]
URL = "https://example.com/sites/default/files/2019-12/Figure2b.jpg"


def test_media_urls_are_excluded_by_default():
    for u in ("https://example.com/a/photo.jpg", "https://example.com/a/photo.JPEG", "https://example.com/x.png?itok=abc",
              "https://example.com/anim.gif", "https://example.com/v.mp4", "https://example.com/talk.mp3",
              "https://example.com/logo.svg", "https://example.com/i.webp"):
        assert _url_excluded(u, EXCLUDES), u
    assert not _url_excluded("https://example.com/academics/requirements", EXCLUDES)
    assert not _url_excluded("https://example.com/files/handbook.pdf", EXCLUDES)


def _scraper(tmp_path):
    scraper = WebsiteScraper("https://example.com/", output_dir=tmp_path, use_sitemap=False,
                             playwright_enabled=False, delay=0)
    scraper.executor.shutdown(wait=False)
    scraper.executor = ThreadPoolExecutor(max_workers=2)
    return scraper


async def _media_response_is_neither_saved_nor_expanded(tmp_path):
    scraper = _scraper(tmp_path)

    async def fake_fetch(url, method="GET"):
        return "\xff\xfe\x00<a href='/phantom'>", "image/jpeg", "html", 200

    scraper.fetch_with_retry = fake_fetch
    queue_before = list(scraper.urls_to_visit)
    await scraper.process_url("https://example.com/no-extension-image")
    assert list((tmp_path / "example.com" / "pages").glob("*")) == []
    assert list(scraper.urls_to_visit) == queue_before
    assert scraper.stats["media"] == 1
    assert scraper.stats["pages_downloaded"] == 0


def test_media_response_is_neither_saved_nor_expanded(tmp_path):
    asyncio.run(_media_response_is_neither_saved_nor_expanded(tmp_path))
