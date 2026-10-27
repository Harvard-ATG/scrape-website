"""Cross-host validation over every host, offline, from the saved snapshots, sites.toml and cached manifests.
Expected exceptions are written out as constants so any new deviation fails loudly."""
import pytest

from loaders import (MOVED_HOSTS, SNAP_JUL, SNAP_OCT, SITES_TOML, load_manifest, load_sites, load_snapshot,
                     manifest_hosts, sitemap_dict)
from rules import evaluate, normalize_key, plan_update, url_kind

pytestmark = pytest.mark.skipif(not (SITES_TOML.exists() and SNAP_OCT.exists()), reason="inputs missing")

OCT = load_snapshot(SNAP_OCT) if SNAP_OCT.exists() else {}
JUL = load_snapshot(SNAP_JUL) if SNAP_JUL.exists() else {}
SITES = load_sites() if SITES_TOML.exists() else {}
OLD_ENTRIES = {old: [{"url": f"https://{old}/"}] for old in MOVED_HOSTS}
ALL = {**SITES, **OLD_ENTRIES}                                   # old hostnames still appear in the snapshots

# Known, documented exceptions (RULES.md). A new deviation must be investigated, not added here silently.
NO_SITEMAP = {"courses.my.harvard.edu", "ces.fas.harvard.edu", "daviscenter.fas.harvard.edu", "careerservices.fas.harvard.edu"}
UNREADABLE_NOW = {"astronomy.fas.harvard.edu", "scienceeducation.fas.harvard.edu", "statistics.fas.harvard.edu",  # 503 on 2026-10-15
                  "www.math.harvard.edu"}      # readable in an earlier 2026-10-15 fetch, failed in this one: flaky
RELATIVE_LOCS = {"csadvising.seas.harvard.edu"}
# hosts with lastmod on under 90% of URLs, with (coverage, URLs without lastmod); those URLs are refetched every run
LOW_LASTMOD = {"emr.fas.harvard.edu": (0.778, 39), "engagedscholarship.fas.harvard.edu": (0.816, 16),
               "complit.fas.harvard.edu": (0.869, 113), "csadvising.seas.harvard.edu": (0.0, 38)}
LOW_LASTMOD_OK = 0.90


def readable(host):
    return sitemap_dict(OCT.get(host))


def test_every_snapshot_host_is_accounted_for():
    for h in OCT:
        assert h in ALL, f"{h} has a snapshot but is not in sites.toml or the moved-host list"


def test_sitemap_availability_matches_the_documented_exceptions():
    unreadable = {h for h in OCT if h in ALL and readable(h) is None}
    assert unreadable == NO_SITEMAP | UNREADABLE_NOW


def test_moved_hosts_are_detected_as_foreign_host_sitemaps():
    for old in MOVED_HOSTS:
        plan = plan_update(readable(old), {}, old, OLD_ENTRIES[old], prev_sitemap=readable(old))
        assert plan.blocked == "sitemap_foreign_host", old
        assert plan.departures == [] and plan.fetch == {}


def test_no_other_host_has_a_foreign_host_sitemap():
    for h, entries in SITES.items():
        sm = readable(h)
        if sm:
            assert plan_update(sm, {}, h, entries).blocked != "sitemap_foreign_host", h


def test_relative_locs_only_on_the_documented_host():
    rel = {h for h, v in OCT.items() if any(loc.startswith("/") for loc, _ in v.get("entries", []))}
    assert rel == RELATIVE_LOCS


def test_lastmod_coverage_is_high_except_documented_hosts():
    bad = {}
    for h, entries in SITES.items():
        sm = readable(h)
        if not sm:
            continue
        cov = sum(1 for v in sm.values() if v) / len(sm)
        if cov < LOW_LASTMOD_OK:
            bad[h] = round(cov, 2)
    assert set(bad) == set(LOW_LASTMOD), bad
    for h, cov in bad.items():
        assert abs(cov - LOW_LASTMOD[h][0]) < 0.02, (h, cov)


def test_urls_refetched_every_run_for_lack_of_lastmod_is_small():
    total = sum(n for _, n in LOW_LASTMOD.values())
    assert total == 206                                  # per-run cost of decision 'missing lastmod => always refetch'
    seen = 0
    for h in LOW_LASTMOD:
        sm = readable(h)
        plan = plan_update(sm, {normalize_key(u if "://" in u else f"https://{h}{u}"): {"lastmod": "2026-01-01"} for u in sm}, h, SITES[h])
        seen += sum(1 for r in plan.fetch.values() if r == "no_lastmod")
    assert 0 < seen <= total, (seen, total)


def test_seeds_are_always_in_scope_even_with_every_proposed_rule_on():
    for h, entries in SITES.items():
        for e in entries:
            assert evaluate(e["url"], h, entries, adopt_proposed=True, exclude_events=True).in_scope, e["url"]


# Hosts whose rules changed after the QA crawl, so ingested pages are now out of scope and need an explicit prune
# (decision 26). Value = distinct non-query manifest pages now out of scope. A change in the count fails the test.
PENDING_PRUNE = {"www.mcb.harvard.edu": 640}      # scope_to_path added 2026-10-15; /directory and /department pages


@pytest.mark.parametrize("host", manifest_hosts())
def test_nothing_in_the_qa_manifest_violates_todays_rules(host):
    """Every non-query page the QA crawl saved must be in scope under today's rules (default excludes, path, include),
    except the documented PENDING_PRUNE hosts, whose out-of-scope count must match exactly."""
    if host not in SITES:
        pytest.skip("host not in sites.toml (moved)")
    ents, _ = load_manifest(host)
    entries = SITES[host]
    bad = set()
    for e in ents:
        if e.get("content_type") != "webpage" or "?" in e["source_url"]:
            continue
        d = evaluate(e["source_url"], host, entries)
        if not d.in_scope and d.reason in ("outside_path", "include_miss", "excluded"):
            if url_kind(e["source_url"]) == "event_feed":
                continue                       # counted separately: test_event_feeds_pending_prune
            bad.add(normalize_key(e["source_url"]))
    assert len(bad) == PENDING_PRUNE.get(host, 0), sorted(bad)[:5]


def test_event_feeds_pending_prune():
    """The QA manifests hold 10,012 .ics feed pages. They are out of scope only once the scraper excludes \\.ics$
    by default (PR #4); before that they are in scope, after it they are a counted pending prune (decision 26)."""
    import re
    from scrape_website.scraper import _DEFAULT_EXCLUDE_PATTERNS
    if not manifest_hosts():
        pytest.skip("no cached QA manifests")
    feeds = set()
    for host in manifest_hosts():
        ents, _ = load_manifest(host)
        for e in ents:
            if e.get("content_type") == "webpage" and "?" not in e["source_url"] and url_kind(e["source_url"]) == "event_feed":
                feeds.add(normalize_key(e["source_url"]))
    assert len(feeds) == 10012
    excluded_by_default = any(re.search(p, "https://x.harvard.edu/node/1/event-feed.ics") for p in _DEFAULT_EXCLUDE_PATTERNS)
    out_of_scope = 0
    for u in feeds:
        host = u.split("/")[2]
        if host in SITES and not evaluate(u, host, SITES[host]).in_scope:
            out_of_scope += 1
    assert excluded_by_default, "the scraper's default excludes must catch .ics feeds (PR #4)"
    assert out_of_scope == len(feeds) - sum(1 for u in feeds if u.split("/")[2] not in SITES)


def test_proposed_event_feed_exclude_removes_only_feeds():
    """Decision 6: the .ics exclude must remove feeds and nothing that is a content page."""
    for h, entries in SITES.items():
        sm = readable(h)
        if not sm:
            continue
        for u in sm:
            full = u if "://" in u else f"https://{h}{u}"
            d = evaluate(full, h, entries, adopt_proposed=True)
            if d.reason == "proposed:event_feed":
                assert url_kind(full) == "event_feed", full


def test_ofa_restructure_trips_the_departure_cap_and_blocks_removals():
    h = "ofa.fas.harvard.edu"
    plan = plan_update(readable(h), {}, h, SITES[h], prev_sitemap=sitemap_dict(JUL[h]))
    assert plan.removal_blocked and plan.departures == []


def test_departures_do_not_include_the_moved_hosts_urls():
    for old in MOVED_HOSTS:
        plan = plan_update(readable(old), {}, old, OLD_ENTRIES[old], prev_sitemap=sitemap_dict(JUL.get(old)))
        assert plan.departures == []


def test_first_run_is_bounded_by_in_scope_sitemap_pages():
    for h, entries in SITES.items():
        sm = readable(h)
        if not sm:
            continue
        plan = plan_update(sm, {}, h, entries)
        if plan.blocked:
            continue
        seeds = {normalize_key(e["url"]) for e in entries}
        for key in plan.fetch:                               # every planned fetch is a seed or an in-scope URL
            assert key in seeds or evaluate(key, h, entries).in_scope, (h, key)


def test_out_of_scope_count_matches_an_independent_count_on_every_planned_host():
    """Guards the validation report: plan.out_of_scope must equal the sitemap URLs that fail evaluate(), including on
    path-scoped hosts that take the seeds-only shortcut (the report once counted their whole sitemap as in scope)."""
    checked = 0
    for h, entries in SITES.items():
        sm = readable(h)
        if not sm:
            continue
        plan = plan_update(sm, {}, h, entries)
        if plan.blocked:
            continue
        independent = sum(1 for u in sm if not evaluate(u if "://" in u else f"https://{h}{u}", h, entries).in_scope)
        assert plan.out_of_scope == independent, (h, plan.out_of_scope, independent)
        checked += 1
    assert checked >= 70
