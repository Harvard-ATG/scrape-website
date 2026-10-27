"""Pure delta between the live sitemap and QA's last-scraped manifest. URLs are
compared at BASE identity (query/slash/scheme normalized). `changed_since_scrape`
uses each sitemap entry's <lastmod> against the manifest's generated_at date —
the only removal/change-aware signal an incremental 'new-URLs-only' pass misses."""
from datetime import date

from dateparse import parse_iso_date
from normalize import norm_base


def diff_urls(sitemap_entries: list, manifest_urls: list,
              generated_at: str | None, today: date, sample: int = 15) -> dict:
    sm_base = {b for b in (norm_base(e.get("loc")) for e in sitemap_entries) if b}
    man_base = {b for b in (norm_base(u) for u in manifest_urls) if b}

    new = sorted(sm_base - man_base)
    gone = sorted(man_base - sm_base)
    crossover = sm_base & man_base

    baseline = parse_iso_date(generated_at)
    baseline_known = baseline is not None
    changed = []
    if baseline_known:
        for e in sitemap_entries:
            lm = parse_iso_date(e.get("lastmod"))
            b = norm_base(e.get("loc"))
            if b and lm is not None and lm > baseline:
                changed.append(b)
    changed = sorted(set(changed))

    return {
        "sitemap_base_count": len(sm_base),
        "manifest_base_count": len(man_base),
        "crossover": len(crossover),
        "new_since_scrape": len(new),
        "gone_from_manifest": len(gone),
        "changed_since_scrape": len(changed),
        "baseline_date": baseline.isoformat() if baseline else None,
        "baseline_known": baseline_known,
        "new_sample": new[:sample],
        "gone_sample": gone[:sample],
        "changed_sample": changed[:sample],
    }
