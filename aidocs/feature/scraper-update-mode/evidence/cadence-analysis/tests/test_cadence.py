import datetime

from cadence import cadence_stats, classify

TODAY = datetime.date(2024, 6, 1)


def test_no_lastmod_is_unknown():
    s = cadence_stats([None, None, None], TODAY)
    assert s["total_urls"] == 3
    assert s["with_lastmod"] == 0
    assert s["lastmod_coverage"] == 0.0
    assert s["cadence_class"] == "unknown"
    assert s["newest"] is None
    assert s["est_update_interval_days"] is None


def test_weekly_cadence_is_high():
    # 8 dates, 7 days apart -> interval 7 -> high; newest 7 days before TODAY
    dates = [f"2024-0{m}-{d:02d}" for (m, d) in
             [(4, 6), (4, 13), (4, 20), (4, 27), (5, 4), (5, 11), (5, 18), (5, 25)]]
    s = cadence_stats(dates, TODAY)
    assert s["with_lastmod"] == 8
    assert s["lastmod_coverage"] == 1.0
    assert s["est_update_interval_days"] == 7.0
    assert s["cadence_class"] == "high"
    assert s["changed_last_30d"] == 4   # 05-25(7d),05-18(14d),05-11(21d),05-04(28d) <= 30
    assert s["newest"] == "2024-05-25"
    assert s["oldest"] == "2024-04-06"


def test_old_site_is_dormant():
    s = cadence_stats(["2022-01-01", "2022-02-01"], TODAY)
    assert s["cadence_class"] == "dormant"   # newest_age > 365


def test_single_recent_date_is_moderate():
    s = cadence_stats(["2024-05-20"], TODAY)   # 1 distinct date -> interval None, recent
    assert s["est_update_interval_days"] is None
    assert s["cadence_class"] == "moderate"


def test_classify_thresholds():
    assert classify(None, None, 0) == "unknown"
    assert classify(10.0, 5, 3) == "high"
    assert classify(30.0, 5, 3) == "moderate"
    assert classify(120.0, 40, 3) == "low"
    assert classify(400.0, 40, 3) == "dormant"
    assert classify(10.0, 400, 3) == "dormant"   # stale newest overrides interval
