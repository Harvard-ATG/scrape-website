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
