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


def test_individual_event_pages_are_excluded():
    for url in (
        "https://www.economics.harvard.edu/event/graduate-student-workshop-macroeconomics",
        "https://history.fas.harvard.edu/events/brown-bag-lunch-talk",
        "https://iop.harvard.edu/events/conversation-jack-lew-former-us-treasury-secretary-2013-2017",
        "https://writingprogram.college.harvard.edu/calendar_event/course-registration",
        "https://x.harvard.edu/calendar-event/open-house",
        "https://x.harvard.edu/Events/Mixed-Case-Slug",
        "https://x.harvard.edu/events/talk/",                       # trailing slash
        "https://x.harvard.edu/event/talk?date=2026-11-01",         # query string
    ):
        assert _url_excluded(url, COMPILED), url


def test_event_listing_pages_are_not_excluded():
    for url in (
        "https://www.economics.harvard.edu/events",
        "https://www.economics.harvard.edu/events/",
        "https://www.economics.harvard.edu/events?page=2",
        "https://www.economics.harvard.edu/calendar",
        "https://www.economics.harvard.edu/event-topic/macroeconomics",
        "https://www.economics.harvard.edu/event-type/seminar",
        "https://x.harvard.edu/events/2026/talk",                   # two segments stay in scope
        "https://x.harvard.edu/news/eventful-year",                 # 'event' inside another word
    ):
        assert not _url_excluded(url, COMPILED), url
