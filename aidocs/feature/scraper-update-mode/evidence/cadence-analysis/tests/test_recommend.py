from recommend import recommend


def _cad(cls):
    return {"cadence_class": cls, "changed_last_30d": 0}


def _diff(man=100, sm=100, gone=0, changed=0, known=True):
    return {"manifest_base_count": man, "sitemap_base_count": sm,
            "gone_from_manifest": gone, "changed_since_scrape": changed,
            "baseline_known": known}


def test_frequency_by_class():
    assert recommend(_cad("high"), _diff())["frequency"] == "weekly"
    assert recommend(_cad("moderate"), _diff())["frequency"] == "monthly"
    assert recommend(_cad("low"), _diff())["frequency"] == "quarterly"
    assert recommend(_cad("dormant"), _diff())["frequency"] == "semiannual"


def test_no_sitemap_defaults():
    r = recommend(_cad("unknown"), None)
    assert r["frequency"] == "monthly"
    assert r["mode"] == "fresh"


def test_mode_fresh_when_removals_high():
    r = recommend(_cad("low"), _diff(man=100, gone=20))
    assert r["mode"] == "fresh"


def test_mode_fresh_when_changes_high():
    r = recommend(_cad("low"), _diff(man=100, sm=100, changed=20))
    assert r["mode"] == "fresh"


def test_mode_incremental_when_mostly_additive():
    r = recommend(_cad("low"), _diff(man=100, sm=105, gone=1, changed=2))
    assert r["mode"] == "incremental"


def test_mode_fresh_when_baseline_unknown_or_empty():
    assert recommend(_cad("low"), _diff(known=False))["mode"] == "fresh"
    assert recommend(_cad("low"), _diff(man=0))["mode"] == "fresh"


def test_unknown_rationale_distinguishes_no_sitemap_from_no_lastmod():
    # cadence is None → no sitemap was fetched at all
    r_none = recommend(None, None)
    assert r_none["frequency"] == "monthly" and r_none["mode"] == "fresh"
    assert "no sitemap" in r_none["rationale"]
    # cadence present but class unknown → sitemap exists, just no <lastmod> dates
    r_present = recommend(_cad("unknown"), None)
    assert "no <lastmod>" in r_present["rationale"]
