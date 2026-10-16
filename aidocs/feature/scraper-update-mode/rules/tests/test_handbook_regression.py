"""Regression for the handbook include-pattern bug: the 2026-08 Fields of Concentration PDF is not followed.

The fixture holds the links of the live handbook homepage as of 2026-10-15. These tests run the scraper's own
link extractor with the include patterns from sites.toml.
"""
import re

import pytest

from loaders import FIXTURES, SITES_TOML, load_sites

pytestmark = pytest.mark.skipif(not SITES_TOML.exists(), reason="sites.toml not found")

HOST = "handbook.college.harvard.edu"
FIXED_PATTERN = r"(?i)fields(?:%20|[_\-\s])of(?:%20|[_\-\s])concentration"   # proposed addition (decision 4)
STUDENT = "2026-2027%20Harvard%20College%20Student%20Handbook.pdf"
FIELDS = "Fields_of_Concentration_2026-27.pdf"


def followed(patterns):
    from scrape_website.scraper import _DEFAULT_EXCLUDE_PATTERNS, _extract_links_lxml
    html = (FIXTURES / "handbook_homepage_links.html").read_text()
    links = _extract_links_lxml(html, f"https://{HOST}/", HOST, exclude_patterns=list(_DEFAULT_EXCLUDE_PATTERNS),
                                include_patterns=patterns)
    return {l.rsplit("/", 1)[1] for l in links}


def current_patterns():
    return load_sites()[HOST][0].get("include_patterns", [])


def test_student_handbook_pdf_is_followed_today():
    assert STUDENT in followed(current_patterns())


def test_fields_pdf_is_followed_with_current_patterns():
    """Fixed in sites.toml on 2026-10-15 (decision 4)."""
    assert FIELDS in followed(current_patterns())


def test_fixed_patterns_follow_both_pdfs_and_nothing_else_external():
    fixed = list(current_patterns()) + [FIXED_PATTERN]
    got = followed(fixed)
    assert STUDENT in got and FIELDS in got
    assert "fas_free_speech_guidelines.pdf" not in got          # different host, still skipped (R2)


def test_proposed_pattern_matches_every_naming_and_nothing_unrelated():
    p = re.compile(FIXED_PATTERN)
    for name in ("Fields%20of%20Concentration_0.pdf", "Fields_of_Concentration_2026-27.pdf",
                 "fields-of-concentration.pdf", "FIELDS OF CONCENTRATION.pdf"):
        assert p.search(name), name
    assert not p.search("https://handbook.college.harvard.edu/files/campus-use-rules.pdf")
    assert not p.search("https://handbook.college.harvard.edu/files/field-of-study.pdf")


def test_a_looser_dot_pattern_would_have_missed_the_percent20_naming():
    """Why the pattern spells out %20: a plain Fields.?of.?Concentration cannot match the 3-character %20."""
    assert not re.search(r"(?i)Fields.?of.?Concentration", "Fields%20of%20Concentration_0.pdf")
