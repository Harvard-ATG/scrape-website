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
        "https://x.harvard.edu/Events/Mixed-Case-Slug",
        "https://www.chemistry.harvard.edu/event/professor-peng-chen-peking-university?occ_id=0",
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


def test_academic_calendar_event_pages_are_kept():
    """Registrar-style deadlines live under calendar_event (OUE, SAS): the most-cited
    event content in Splunk (Jul-Oct 2026), only ~40 pages across all hosts."""
    for url in (
        "https://oue.fas.harvard.edu/calendar_event/fall-course-registration-opens-for-incoming-students",
        "https://sas.fas.harvard.edu/calendar_event/fall-2026-course-registration-deadline-for-continuing-students",
        "https://x.harvard.edu/calendar-event/open-house",
    ):
        assert not _url_excluded(url, COMPILED), url


def test_advising_hosts_keep_their_event_pages():
    """A few small advising hosts use /event/ for deadlines, placement exams, info sessions
    and advising hours rather than seminars (slugs reviewed against prod manifests and
    Splunk citations, 2026-10-27). Their event pages stay; every other host's go."""
    for url in (
        "https://incomingstudents.college.harvard.edu/event/take-math-placement-exam",
        "https://specialconcentrations.fas.harvard.edu/event/spring-application-deadline-3",
        "https://histlit.fas.harvard.edu/event/plan-concentration-field-worksheet-and-other-end-year-forms-due",
        "https://socialstudies.fas.harvard.edu/event/advising-corner-hours-0",
        "https://espp.fas.harvard.edu/event/course-registration-deadline-1",
        "https://undergrad.psychology.fas.harvard.edu/event/thesis-abstracts-due",
        "https://firstyear.college.harvard.edu/event/take-math-placement-exam",
    ):
        assert not _url_excluded(url, COMPILED), url
    for url in (
        "https://history.fas.harvard.edu/event/take-math-placement-exam",
        "https://registrar.fas.harvard.edu/event/fall-2026-ferpa-workshop",
        "https://www.economics.harvard.edu/event/sophomore-declaration-event",
    ):
        assert _url_excluded(url, COMPILED), url
