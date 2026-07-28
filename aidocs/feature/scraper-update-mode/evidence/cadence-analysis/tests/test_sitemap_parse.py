from sitemap_parse import parse_sitemap

URLSET = b"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://x.edu/a</loc><lastmod>2024-01-15</lastmod></url>
  <url><loc>https://x.edu/b</loc></url>
</urlset>"""

INDEX = b"""<?xml version="1.0" encoding="UTF-8"?>
<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <sitemap><loc>https://x.edu/sitemap-1.xml</loc></sitemap>
  <sitemap><loc>https://x.edu/sitemap-2.xml</loc></sitemap>
</sitemapindex>"""


def test_urlset_extracts_loc_and_lastmod():
    children, entries = parse_sitemap(URLSET)
    assert children == []
    assert entries == [
        {"loc": "https://x.edu/a", "lastmod": "2024-01-15"},
        {"loc": "https://x.edu/b", "lastmod": None},
    ]


def test_index_returns_children_only():
    children, entries = parse_sitemap(INDEX)
    assert children == ["https://x.edu/sitemap-1.xml", "https://x.edu/sitemap-2.xml"]
    assert entries == []


def test_garbage_returns_empty():
    assert parse_sitemap(b"<html>not a sitemap</html>") == ([], [])
    assert parse_sitemap(b"") == ([], [])
