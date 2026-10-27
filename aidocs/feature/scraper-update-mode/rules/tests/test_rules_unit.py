"""Unit tests for normalization, URL taxonomy and scope rules. Every example URL is real, taken from the
sitemaps and manifests examined while writing RULES.md."""
import pytest

from rules import (Decision, evaluate, is_path_scoped, normalize_key, parse_lastmod, url_kind)


# --- R1 normalization -------------------------------------------------------------------------------
@pytest.mark.parametrize("raw,key", [
    ("https://www.economics.harvard.edu/about/", "https://www.economics.harvard.edu/about"),
    ("http://www.economics.harvard.edu/about", "https://www.economics.harvard.edu/about"),   # http twin (PR #9)
    ("https://WWW.Economics.Harvard.edu/about#top", "https://www.economics.harvard.edu/about"),
    ("https://handbook.college.harvard.edu/", "https://handbook.college.harvard.edu"),
    ("https://x.harvard.edu/search?page=2", "https://x.harvard.edu/search?page=2"),          # query kept
])
def test_normalize_key(raw, key):
    assert normalize_key(raw) == key


def test_http_and_https_collapse_to_one_key():
    assert normalize_key("http://folkmyth.fas.harvard.edu/x/") == normalize_key("https://folkmyth.fas.harvard.edu/x")


# --- R14 timestamps ---------------------------------------------------------------------------------
def test_parse_lastmod_same_instant_different_offsets_are_equal():
    assert parse_lastmod("2026-08-29T12:56:08+00:00") == parse_lastmod("2026-08-29T08:56:08-04:00")


def test_parse_lastmod_variants():
    assert parse_lastmod("2026-08-29T12:56:08Z").tzinfo is not None
    assert parse_lastmod("2026-08-29").year == 2026
    assert parse_lastmod("") is None and parse_lastmod(None) is None
    assert parse_lastmod("not a date") is None


def test_parse_lastmod_rejects_trailing_text_and_reads_bare_dates_as_end_of_day():
    assert parse_lastmod("2026-10-15 garbage") is None
    assert parse_lastmod("2026-13-45") is None
    d = parse_lastmod("2026-10-15")
    assert (d.hour, d.minute, d.second) == (23, 59, 59) and d == parse_lastmod("2026-10-15Z")
    assert parse_lastmod("2026-10-15T10:00:00").hour == 10      # naive is read as UTC


@pytest.mark.parametrize("url", ["https://Example.edu/", "https://example.edu/a/?x=1", "http://example.edu/a/", "https://example.edu/a#frag"])
def test_scraper_keys_agree_with_rule_keys_after_normalize_key(url):
    """The planner's state is keyed by normalize_key; keys the scraper stores must map to the same key."""
    from scrape_website.scraper import _normalize_url
    assert normalize_key(_normalize_url(url)) == normalize_key(url)


# --- taxonomy: url_kind -----------------------------------------------------------------------------
@pytest.mark.parametrize("url,kind", [
    ("https://www.economics.harvard.edu/node/1397253/event-feed.ics", "event_feed"),
    ("https://haa.fas.harvard.edu/resource/historyofartsandarchitecture-pages-tablexlsx", "resource_page"),
    ("https://www.mcb.harvard.edu/department/news/tag/2014-double-helix-medal/", "tag_archive"),
    ("https://hscrb.harvard.edu/author/krush/", "tag_archive"),
    ("https://example.harvard.edu/news/page/2", "archive_listing"),
    ("https://oue.fas.harvard.edu/2024/11", "archive_listing"),                               # WordPress date archive
    ("https://example.harvard.edu/search?page=3", "query_variant"),
    ("https://www.economics.harvard.edu/event/seminar-macroeconomics-58", "event_page"),
    ("https://iop.harvard.edu/events/conversation-jack-lew-former-us-treasury-secretary-2013-2017", "event_page"),
    ("https://writingprogram.college.harvard.edu/calendar_event/course-registration", "event_page"),
    ("https://www.economics.harvard.edu/events", "page"),                                      # listing, not an event
    ("https://handbook.college.harvard.edu/sites/g/files/omnuum5551/files/2026-08/Fields_of_Concentration_2026-27.pdf", "file_binary"),
    ("https://folkmyth.fas.harvard.edu/wp-admin/admin-ajax.php", "admin"),
    ("https://oue.fas.harvard.edu/wp-sitemap-taxonomies-post_tag-1.xml", "admin"),
    ("https://celtic.fas.harvard.edu/undergraduate-program", "page"),
])
def test_url_kind(url, kind):
    assert url_kind(url) == kind


# --- R2-R5 scope ------------------------------------------------------------------------------------
ROOT = [{"url": "https://english.fas.harvard.edu/", "hostname": "english.fas.harvard.edu"}]
SCOPED = [{"url": "https://haa.fas.harvard.edu/undergraduate-program", "scope_to_path": True}]
HANDBOOK = [{"url": "https://handbook.college.harvard.edu/",
             "include_patterns": ["Student%20Handbook", "Fields%20of%20Concentration", "fields"]}]


def test_seed_is_always_in_scope_even_if_pattern_would_exclude():
    e = [{"url": "https://x.harvard.edu/tag/seed", "exclude_patterns": ["/tag/"]}]
    assert evaluate("https://x.harvard.edu/tag/seed", "x.harvard.edu", e) == Decision(True, "seed", "tag_archive")


def test_foreign_host_is_out_of_scope():
    d = evaluate("https://studyabroad.college.harvard.edu/faq", "oie.fas.harvard.edu", ROOT)
    assert (d.in_scope, d.reason) == (False, "foreign_host")


@pytest.mark.parametrize("path,ok", [
    ("/undergraduate-program", True),
    ("/undergraduate-program/requirements", True),
    ("/undergraduate-program-faq", False),        # prefix must end at a path boundary
    ("/graduate-program", False),
    ("/", False),
])
def test_path_scope_boundary(path, ok):
    assert evaluate(f"https://haa.fas.harvard.edu{path}", "haa.fas.harvard.edu", SCOPED).in_scope is ok


def test_default_excludes_apply_everywhere():
    for u in ("https://english.fas.harvard.edu/tag/x", "https://english.fas.harvard.edu/author/y",
              "https://english.fas.harvard.edu/news/page/3", "https://english.fas.harvard.edu/feed/"):
        d = evaluate(u, "english.fas.harvard.edu", ROOT)
        assert (d.in_scope, d.reason) == (False, "excluded"), u


def test_include_patterns_require_a_match():
    h = "handbook.college.harvard.edu"
    assert evaluate("https://handbook.college.harvard.edu/files/2026-08/2026-2027%20Harvard%20College%20Student%20Handbook.pdf", h, HANDBOOK).in_scope
    assert not evaluate("https://handbook.college.harvard.edu/campus-use-rules-faqs", h, HANDBOOK).in_scope


def test_site_exclude_patterns():
    e = [{"url": "https://writingprogram.college.harvard.edu/", "exclude_patterns": ["/calendar_event/"]}]
    assert not evaluate("https://writingprogram.college.harvard.edu/calendar_event/x", "writingprogram.college.harvard.edu", e).in_scope
    assert evaluate("https://writingprogram.college.harvard.edu/about", "writingprogram.college.harvard.edu", e).in_scope


def test_multiple_entries_take_the_union():
    reg = [{"url": "https://registrar.fas.harvard.edu/cross-registration", "scope_to_path": True},
           {"url": "https://registrar.fas.harvard.edu/"}]
    assert evaluate("https://registrar.fas.harvard.edu/handbooks", "registrar.fas.harvard.edu", reg).in_scope
    assert not is_path_scoped(reg)


def test_path_scoped_requires_every_entry_scoped():
    assert is_path_scoped(SCOPED) and not is_path_scoped(ROOT) and not is_path_scoped([])


# --- PROPOSED rules are inert until adopted ---------------------------------------------------------
@pytest.mark.parametrize("url,name", [
    ("https://www.economics.harvard.edu/node/1397253/event-feed.ics", "event_feed"),
    ("http://folkmyth.fas.harvard.edu/people/x", "http_dup"),
    ("https://folkmyth.fas.harvard.edu/search?page=2", "search"),
    ("https://www.example.harvard.edu/wp-admin/options.php", "wp_admin"),
])
def test_proposed_excludes_only_when_adopted(url, name, monkeypatch):
    """Each proposed pattern is tested on its own: the scraper's default excludes already catch .ics and /search?,
    so they are emptied here. Otherwise the default exclude would answer first and this test could not fail."""
    import rules
    monkeypatch.setattr(rules, "_DEFAULT_EXCLUDE_PATTERNS", [])
    host = url.split("/")[2]
    entries = [{"url": f"https://{host}/"}]
    assert evaluate(url, host, entries).in_scope                  # inert until adopted
    d = evaluate(url, host, entries, adopt_proposed=True)
    assert (d.in_scope, d.reason) == (False, f"proposed:{name}")


def test_proposed_excludes_leave_ordinary_pages_alone():
    host = "www.example.harvard.edu"
    for path in ("/about", "/people/jane-doe", "/news/search-for-truth", "/wp-content/uploads/x.pdf"):
        assert evaluate(f"https://{host}{path}", host, [{"url": f"https://{host}/"}], adopt_proposed=True).in_scope, path


def test_event_policy_is_off_by_default_and_spares_listings():
    e = [{"url": "https://www.economics.harvard.edu/"}]
    h = "www.economics.harvard.edu"
    assert evaluate("https://www.economics.harvard.edu/event/seminar-1", h, e).in_scope
    assert not evaluate("https://www.economics.harvard.edu/event/seminar-1", h, e, exclude_events=True).in_scope
    assert evaluate("https://www.economics.harvard.edu/events", h, e, exclude_events=True).in_scope
