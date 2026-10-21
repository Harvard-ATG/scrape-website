import re

from scrape_website.scraper import _DEFAULT_EXCLUDE_PATTERNS, _url_excluded

COMPILED = [re.compile(p) for p in _DEFAULT_EXCLUDE_PATTERNS]


def test_bibcite_exports_are_excluded_in_every_format():
    base = "https://heb.fas.harvard.edu/bibcite/export?content_filter%5B0%5D=1&format="
    for fmt in ("endnote8", "endnote7", "ris", "bibtex", "marc", "tagged", "pubmed_id"):
        assert _url_excluded(base + fmt, COMPILED), fmt


def test_bibcite_export_with_filters_and_sort_is_excluded():
    url = ("https://astronomy.fas.harvard.edu/bibcite/export?pager_style=no_pager&number_of_items=12"
           "&sort_field=bibcite_year--desc&content_filter%5B0%5D=1484868&format=ris")
    assert _url_excluded(url, COMPILED)


def test_the_publication_pages_themselves_are_not_excluded():
    for url in (
        "https://classics.fas.harvard.edu/publication/persuasion-rhetoric-and-roman-poetry",
        "https://sociology.fas.harvard.edu/publications/cultural-matrix-understanding-black-youth",
        "https://slavic.fas.harvard.edu/publications",
    ):
        assert not _url_excluded(url, COMPILED), url
