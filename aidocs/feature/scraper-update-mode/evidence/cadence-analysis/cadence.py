"""Pure cadence statistics from a host's sitemap <lastmod> values. All dates
are compared against an injected `today` so results are deterministic and
testable. `classify` maps the observed update interval + recency into a
coarse cadence class that Stage 5 turns into a frequency recommendation."""
from datetime import date
from statistics import median

from dateparse import parse_iso_date

# classification thresholds (days) — "balanced" objective
HIGH_MAX = 14
MODERATE_MAX = 45
LOW_MAX = 180
STALE_MAX = 365   # newest older than this -> dormant regardless of interval


def classify(est_interval_days, newest_age_days, with_lastmod) -> str:
    if with_lastmod == 0:
        return "unknown"
    if newest_age_days is not None and newest_age_days > STALE_MAX:
        return "dormant"
    if est_interval_days is None:
        # <2 distinct dates: judge by recency of the single/newest date
        if newest_age_days is not None and newest_age_days <= 30:
            return "moderate"
        return "low"
    if est_interval_days <= HIGH_MAX:
        return "high"
    if est_interval_days <= MODERATE_MAX:
        return "moderate"
    if est_interval_days <= LOW_MAX:
        return "low"
    return "dormant"


def cadence_stats(lastmods: list, today: date) -> dict:
    total = len(lastmods)
    dts = [d for d in (parse_iso_date(x) for x in lastmods) if d is not None]
    with_lastmod = len(dts)
    coverage = round(with_lastmod / total, 3) if total else 0.0

    if not dts:
        return {
            "total_urls": total, "with_lastmod": 0, "lastmod_coverage": coverage,
            "newest": None, "oldest": None, "median_age_days": None,
            "changed_last_7d": 0, "changed_last_30d": 0,
            "changed_last_90d": 0, "changed_last_180d": 0,
            "frac_last_30d": 0.0, "est_update_interval_days": None,
            "cadence_class": "unknown",
        }

    ages = [(today - d).days for d in dts]
    newest, oldest = max(dts), min(dts)
    newest_age = (today - newest).days

    def within(n):
        return sum(1 for a in ages if 0 <= a <= n)

    changed_30 = within(30)
    distinct = sorted(set(dts))
    if len(distinct) >= 2:
        gaps = [(distinct[i + 1] - distinct[i]).days for i in range(len(distinct) - 1)]
        interval = round(float(median(gaps)), 1)
    else:
        interval = None

    return {
        "total_urls": total, "with_lastmod": with_lastmod, "lastmod_coverage": coverage,
        "newest": newest.isoformat(), "oldest": oldest.isoformat(),
        "median_age_days": int(round(median(ages))),
        "changed_last_7d": within(7), "changed_last_30d": changed_30,
        "changed_last_90d": within(90), "changed_last_180d": within(180),
        "frac_last_30d": round(changed_30 / with_lastmod, 3),
        "est_update_interval_days": interval,
        "cadence_class": classify(interval, newest_age, with_lastmod),
    }
