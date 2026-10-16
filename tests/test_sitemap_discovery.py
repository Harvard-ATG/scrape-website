"""Unit tests for tiered sitemap discovery (Task 16).

Pure tests over the discovery helpers — no scraper, no sockets. `fetch` is a
plain dict-backed async callable so we exercise robots.txt parsing, the
/wp-sitemap.xml fallback, sitemap-index recursion, and the max_urls cap
without any network tier.
"""
import asyncio

from scrape_website.scraper import _fetch_sitemap_urls, _parse_robots_sitemaps


def test_parse_robots_sitemaps_extracts_all_directives():
    robots = (
        b"User-agent: *\n"
        b"Disallow: /admin\n"
        b"Sitemap: https://example.com/sitemap.xml\n"
        b"sitemap:   https://example.com/sitemap-news.xml  \n"
    )
    assert _parse_robots_sitemaps(robots) == [
        "https://example.com/sitemap.xml",
        "https://example.com/sitemap-news.xml",
    ]


def test_parse_robots_sitemaps_empty_or_none():
    assert _parse_robots_sitemaps(b"") == []
    assert _parse_robots_sitemaps(None) == []
    assert _parse_robots_sitemaps(b"User-agent: *\nDisallow: /\n") == []


def _fetch_from(pages: dict[str, bytes]):
    """Build an async fetch callable backed by a {url: body} table."""
    async def fetch(url: str) -> bytes | None:
        return pages.get(url)
    return fetch


def test_discovery_uses_robots_advertised_sitemap():
    pages = {
        "https://example.com/robots.txt":
            b"Sitemap: https://example.com/custom-sitemap.xml\n",
        "https://example.com/custom-sitemap.xml":
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<url><loc>https://example.com/from-robots</loc></url></urlset>",
    }
    urls = asyncio.run(_fetch_sitemap_urls(_fetch_from(pages), "example.com"))
    assert urls == ["https://example.com/from-robots"]


def test_discovery_falls_back_to_wp_sitemap_index():
    # No robots.txt sitemap, no /sitemap.xml — only WordPress /wp-sitemap.xml,
    # which is an index pointing at a child sitemap.
    pages = {
        "https://example.com/wp-sitemap.xml":
            b'<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<sitemap><loc>https://example.com/wp-sitemap-posts-post-1.xml</loc>"
            b"</sitemap></sitemapindex>",
        "https://example.com/wp-sitemap-posts-post-1.xml":
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<url><loc>https://example.com/post-1</loc></url>"
            b"<url><loc>https://example.com/post-2</loc></url></urlset>",
    }
    urls = asyncio.run(_fetch_sitemap_urls(_fetch_from(pages), "example.com"))
    assert urls == ["https://example.com/post-1", "https://example.com/post-2"]


def test_discovery_parses_plain_drupal_sitemap():
    pages = {
        "https://example.com/sitemap.xml":
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            b"<url><loc>https://example.com/a</loc></url>"
            b"<url><loc>https://example.com/b</loc></url></urlset>",
    }
    urls = asyncio.run(_fetch_sitemap_urls(_fetch_from(pages), "example.com"))
    assert urls == ["https://example.com/a", "https://example.com/b"]


def test_discovery_returns_empty_when_nothing_reachable():
    urls = asyncio.run(_fetch_sitemap_urls(_fetch_from({}), "example.com"))
    assert urls == []


def test_discovery_caps_at_max_urls():
    locs = b"".join(
        f"<url><loc>https://example.com/p{i}</loc></url>".encode()
        for i in range(10)
    )
    pages = {
        "https://example.com/sitemap.xml":
            b'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
            + locs + b"</urlset>",
    }
    urls = asyncio.run(
        _fetch_sitemap_urls(_fetch_from(pages), "example.com", max_urls=3)
    )
    assert len(urls) == 3
    assert urls[0] == "https://example.com/p0"
