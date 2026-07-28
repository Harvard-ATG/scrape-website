import datetime

from diff import diff_urls

TODAY = datetime.date(2024, 6, 1)


def _entry(loc, lastmod=None):
    return {"loc": loc, "lastmod": lastmod}


def test_new_gone_and_crossover():
    sm = [_entry("https://x.edu/a"), _entry("https://x.edu/b"), _entry("https://x.edu/c/")]
    man = ["https://x.edu/a", "https://x.edu/b?page=1", "https://x.edu/old"]
    d = diff_urls(sm, man, "2024-05-01", TODAY)
    # base normalization: b?page=1 -> b, c/ -> c
    assert d["sitemap_base_count"] == 3
    assert d["manifest_base_count"] == 3
    assert d["crossover"] == 2                 # a, b
    assert d["new_since_scrape"] == 1          # c
    assert d["gone_from_manifest"] == 1        # old
    assert "https://x.edu/c" in d["new_sample"]
    assert "https://x.edu/old" in d["gone_sample"]


def test_changed_since_scrape_uses_lastmod_vs_baseline():
    sm = [_entry("https://x.edu/a", "2024-05-15"),   # after baseline -> changed
          _entry("https://x.edu/b", "2024-04-01"),   # before baseline
          _entry("https://x.edu/c", None)]           # no lastmod -> not changed
    man = ["https://x.edu/a", "https://x.edu/b", "https://x.edu/c"]
    d = diff_urls(sm, man, "2024-05-01", TODAY)
    assert d["baseline_known"] is True
    assert d["baseline_date"] == "2024-05-01"
    assert d["changed_since_scrape"] == 1
    assert d["changed_sample"] == ["https://x.edu/a"]


def test_missing_baseline_marks_unknown():
    sm = [_entry("https://x.edu/a", "2024-05-15")]
    d = diff_urls(sm, ["https://x.edu/a"], None, TODAY)
    assert d["baseline_known"] is False
    assert d["changed_since_scrape"] == 0
