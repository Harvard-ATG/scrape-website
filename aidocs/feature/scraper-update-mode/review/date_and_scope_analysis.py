"""Offline: date precision of sitemap lastmod, edit times of day, rounding effects, and scope/coverage of the sitemap against
our scraper rules and the cached QA manifests. No network.
  MANIFEST_CACHE=<dir> SITES_TOML=<file> python -I date_and_scope_analysis.py > out.json
"""
import collections, json, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE.parent / "rules")]
from loaders import SNAP_JUL, SNAP_OCT, load_manifest, load_sites, load_snapshot, manifest_hosts  # noqa: E402
from rules import evaluate, normalize_key, parse_lastmod, url_kind  # noqa: E402

ET = ZoneInfo("America/New_York")
TODAY = datetime(2026, 10, 15, tzinfo=timezone.utc)
oct_, jul = load_snapshot(SNAP_OCT), load_snapshot(SNAP_JUL)
sites = load_sites()
R = {}

# 1. precision
prec = collections.Counter()
for h, v in oct_.items():
    for loc, lm in v.get("entries") or []:
        prec["none" if not lm else "date_only" if re.fullmatch(r"\d{4}-\d{2}-\d{2}", lm) else "timestamp"] += 1
R["precision"] = dict(prec)

# 2. hour of day (ET) of lastmod for edits in the 30 days before the snapshot
hours, n30 = collections.Counter(), 0
after5 = 0
for h, v in oct_.items():
    for loc, lm in v.get("entries") or []:
        d = parse_lastmod(lm) if lm and "T" in lm else None
        if d and TODAY - timedelta(days=30) <= d < TODAY:
            e = d.astimezone(ET); hours[e.hour] += 1; n30 += 1
            after5 += e.hour >= 5
R["edits_last_30d_with_time"] = n30
R["edit_hour_ET"] = {str(k): hours[k] for k in sorted(hours)}
R["share_edited_at_or_after_05_ET"] = round(after5 / n30, 3) if n30 else None
R["share_edited_08_to_18_ET"] = round(sum(hours[k] for k in range(8, 18)) / n30, 3) if n30 else None

# 3. rounding to a date (what cadence-analysis/dateparse.py does) versus full timestamps, windows relative to TODAY
def count(days, floor):
    n = 0
    lim = TODAY - timedelta(days=days)
    for v in oct_.values():
        for loc, lm in v.get("entries") or []:
            d = parse_lastmod(lm) if lm else None
            if not d: continue
            x = d.astimezone(timezone.utc)
            if floor: x = datetime(x.year, x.month, x.day, tzinfo=timezone.utc)
            if x >= lim: n += 1
    return n
R["changed_windows"] = {f"{d}d": {"timestamp": count(d, False), "date_floor": count(d, True)} for d in (1, 2, 7, 30)}

# 4. changes between the two snapshots, and same-day collisions with a date-only compare
changed = same_day = total = 0
bulk_by_ts = collections.Counter()
for h in oct_:
    a = {l: m for l, m in (jul.get(h, {}).get("entries") or [])}
    for loc, lm in oct_[h].get("entries") or []:
        if loc in a and lm and a[loc]:
            total += 1
            if lm != a[loc]:
                changed += 1
                da, db = parse_lastmod(a[loc]), parse_lastmod(lm)
                if da and db and da.astimezone(ET).date() == db.astimezone(ET).date(): same_day += 1
                bulk_by_ts[lm] += 1
R["jul_to_oct"] = {"urls_in_both_with_dates": total, "lastmod_changed": changed,
                   "changed_but_same_calendar_day_ET": same_day,
                   "largest_single_timestamp_groups": bulk_by_ts.most_common(5)}

# 5. what the XML sitemap lists that our scope rules exclude (reason counts), and kinds
reasons, kinds_out = collections.Counter(), collections.Counter()
per_host_out = {}
for h, ents in sites.items():
    for loc, lm in (oct_.get(h, {}).get("entries") or []):
        d = evaluate(loc, h, ents)
        if not d.in_scope:
            reasons[d.reason] += 1; kinds_out[d.kind] += 1
            per_host_out.setdefault(h, collections.Counter())[d.reason] += 1
R["xml_listed_but_out_of_scope"] = {"by_reason": dict(reasons), "by_kind": dict(kinds_out),
                                    "top_hosts": sorted(((sum(c.values()), h, dict(c)) for h, c in per_host_out.items()), reverse=True)[:8]}

# 6. what the crawl saved (QA manifests) that the XML sitemap does not list
miss_kind, miss_host = collections.Counter(), {}
tot_pages = tot_missing = 0
for h in manifest_hosts():
    sm = {normalize_key(l) for l, _ in (oct_.get(h, {}).get("entries") or [])}
    if not sm: continue
    ents, _ = load_manifest(h)
    for e in ents:
        if e.get("content_type") != "webpage": continue
        u = normalize_key(e["source_url"]); tot_pages += 1
        if u not in sm:
            tot_missing += 1
            kind = "query_string" if "?" in u else url_kind(u)
            if kind == "page" and re.search(r"/file_url/\d+|/node/\d+", u): kind = "node_or_file_url"
            miss_kind[kind] += 1
            miss_host[h] = miss_host.get(h, 0) + 1
R["manifest_pages_not_in_xml"] = {"manifest_webpages_checked": tot_pages, "not_in_xml": tot_missing,
                                  "by_kind": dict(miss_kind), "top_hosts": sorted(((n, h) for h, n in miss_host.items()), reverse=True)[:8]}
print(json.dumps(R, indent=1))
