"""Pure mapping from (cadence, diff) to a scrape recommendation. 'Balanced'
objective: pick the longest interval that keeps content acceptably fresh, and
prefer cheap incremental passes unless the diff shows removals/changes that an
incremental 'new-URLs-only' pass cannot catch (then force a fresh re-scrape)."""

FREQ_BY_CLASS = {
    "high": "weekly", "moderate": "monthly", "low": "quarterly",
    "dormant": "semiannual", "unknown": "monthly",
}

# mode thresholds
GONE_ABS = 5          # >5 removed pages
GONE_FRAC = 0.05      # or >5% of the manifest removed
CHANGED_FRAC = 0.10   # or >10% of sitemap changed since last scrape


def _choose_mode(diff) -> tuple[str, str]:
    if diff is None or not diff.get("baseline_known"):
        return "fresh", "no reliable baseline — full re-scrape to establish state"
    man = diff["manifest_base_count"]
    if man == 0:
        return "fresh", "host not present in QA corpus — bootstrap with a full scrape"
    gone = diff["gone_from_manifest"]
    changed = diff["changed_since_scrape"]
    sm = diff["sitemap_base_count"]
    if gone > max(GONE_ABS, GONE_FRAC * man):
        return "fresh", f"{gone} pages gone from sitemap — incremental cannot retire removals"
    if sm > 0 and changed > CHANGED_FRAC * sm:
        return "fresh", f"{changed} pages changed since last scrape — incremental misses edits"
    new = diff.get("new_since_scrape", sm - gone)
    return "incremental", f"mostly additive ({new} new, {gone} gone, {changed} changed)"


def recommend(cadence: dict | None, diff: dict | None) -> dict:
    cls = cadence.get("cadence_class", "unknown") if cadence else "unknown"
    frequency = FREQ_BY_CLASS.get(cls, "monthly")
    if cls == "unknown":
        return {"frequency": "monthly", "mode": "fresh",
                "rationale": "no sitemap / no lastmod signal — conservative monthly full scrape"}
    mode, mode_why = _choose_mode(diff)
    interval = cadence.get("est_update_interval_days")
    rationale = (f"cadence={cls}"
                 + (f" (~{interval}d interval)" if interval is not None else "")
                 + f"; {mode_why}")
    return {"frequency": frequency, "mode": mode, "rationale": rationale}
