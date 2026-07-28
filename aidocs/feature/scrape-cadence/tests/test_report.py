from report import render_report

RECORDS = [
    {"host": "a.edu", "status": "ok", "sitemap_url": "https://a.edu/sitemap.xml",
     "cadence": {"cadence_class": "high", "est_update_interval_days": 7.0,
                 "with_lastmod": 50, "lastmod_coverage": 1.0},
     "diff": {"new_since_scrape": 2, "gone_from_manifest": 0,
              "changed_since_scrape": 1, "baseline_date": "2024-05-01",
              "baseline_known": True},
     "recommendation": {"frequency": "weekly", "mode": "incremental",
                        "rationale": "cadence=high (~7.0d interval); mostly additive"}},
    {"host": "b.edu", "status": "no_sitemap", "sitemap_url": None,
     "cadence": None, "diff": None,
     "recommendation": {"frequency": "monthly", "mode": "fresh",
                        "rationale": "no sitemap / no lastmod signal — conservative monthly full scrape"}},
    {"host": "c.edu", "status": "ok", "sitemap_url": "https://c.edu/sitemap.xml",
     "cadence": {"cadence_class": "low", "est_update_interval_days": 120.0,
                 "with_lastmod": 30, "lastmod_coverage": 0.9},
     "diff": {"new_since_scrape": 0, "gone_from_manifest": 0,
              "changed_since_scrape": 0, "baseline_date": "2020-01-01",
              "baseline_known": True},
     "recommendation": {"frequency": "quarterly", "mode": "incremental",
                        "rationale": "cadence=low (~120.0d interval); mostly additive"}},
]


def test_report_has_sections_and_rows():
    md = render_report(RECORDS, "2024-06-01")
    assert md.startswith("# Scrape Cadence Recommendations")
    assert "2024-06-01" in md
    assert "| a.edu |" in md
    assert "weekly" in md and "incremental" in md
    # corpus rollup counts
    assert "weekly" in md and "monthly" in md
    # no-sitemap host is called out
    assert "b.edu" in md
    assert "No sitemap" in md
    # baseline recency is surfaced (design §6 honesty requirement)
    assert "Baseline" in md            # new column header
    assert "2024-05-01" in md          # a.edu fresh baseline date shown
    assert "stale" in md               # c.edu's 2020 baseline flagged stale


def test_report_is_deterministic():
    assert render_report(RECORDS, "2024-06-01") == render_report(RECORDS, "2024-06-01")
