"""Tests for update planning, removal guards and confirmation of departures."""
from datetime import datetime, timezone

import pytest

from rules import classify_confirmation, host_moved, normalize_key, plan_update

H = "english.fas.harvard.edu"
E = [{"url": f"https://{H}/"}]


def sm(*pairs):
    return {f"https://{H}{p}": lm for p, lm in pairs}


def state(*pairs):
    return {normalize_key(f"https://{H}{p}"): {"lastmod": lm} for p, lm in pairs}


def k(p):
    return normalize_key(f"https://{H}{p}")


def test_first_run_everything_in_scope_is_new():
    plan = plan_update(sm(("/a", "2026-01-01"), ("/b", "2026-01-02"), ("/tag/x", "2026-01-03")), {}, H, E)
    assert plan.fetch[k("/a")] == "new" and plan.fetch[k("/b")] == "new"
    assert k("/tag/x") not in plan.fetch and plan.out_of_scope == 1       # default exclude
    assert plan.fetch[normalize_key(E[0]["url"])] == "seed"


def test_unchanged_is_skipped():
    plan = plan_update(sm(("/a", "2026-01-01T10:00:00+00:00")), state(("/a", "2026-01-01T10:00:00+00:00")), H, E)
    assert plan.skip == [k("/a")] and k("/a") not in plan.fetch


def test_same_instant_in_another_offset_is_unchanged():
    plan = plan_update(sm(("/a", "2026-01-01T06:00:00-04:00")), state(("/a", "2026-01-01T10:00:00+00:00")), H, E)
    assert k("/a") in plan.skip


def test_newer_lastmod_is_changed():
    plan = plan_update(sm(("/a", "2026-03-01")), state(("/a", "2026-01-01")), H, E)
    assert plan.fetch[k("/a")] == "changed"


def test_older_lastmod_is_also_changed_inequality_not_just_newer():
    plan = plan_update(sm(("/a", "2025-12-01")), state(("/a", "2026-01-01")), H, E)
    assert plan.fetch[k("/a")] == "changed"


def test_missing_lastmod_always_refetches():
    plan = plan_update(sm(("/a", None)), state(("/a", "2026-01-01")), H, E)
    assert plan.fetch[k("/a")] == "no_lastmod"


def test_baseline_bootstrap_uses_manifest_date_when_no_lastmod_stored():
    base = datetime(2026, 7, 22, tzinfo=timezone.utc)
    plan = plan_update(sm(("/old", "2026-05-01"), ("/new", "2026-09-01")), state(("/old", None), ("/new", None)),
                       H, E, baseline=base)
    assert plan.fetch[k("/new")] == "changed" and k("/old") in plan.skip


def test_out_of_scope_urls_are_counted_not_planned():
    plan = plan_update({f"https://{H}/a": "2026-01-01", "https://other.harvard.edu/z": "2026-01-01"}, {}, H, E)
    assert k("/a") in plan.fetch and plan.out_of_scope == 1


def test_relative_sitemap_locs_are_joined_to_the_host():            # csadvising lists /faq/index.html
    plan = plan_update({"/faq/index.html": "2026-01-01"}, {}, H, E)
    assert k("/faq/index.html") in plan.fetch


# --- R10 path-scoped hosts --------------------------------------------------------------------------
def test_path_scoped_host_refetches_seeds_and_ignores_the_sitemap():
    scoped = [{"url": f"https://{H}/undergraduate", "scope_to_path": True}]
    for sitemap in (None, {}, sm(("/undergraduate", "2020-01-01"))):
        plan = plan_update(sitemap, {}, H, scoped)
        assert plan.blocked is None and list(plan.fetch.values()) == ["seed"]


# --- R11/R12 blocked hosts --------------------------------------------------------------------------
@pytest.mark.parametrize("sitemap", [None, {}])
def test_unreadable_sitemap_blocks_the_host(sitemap):
    assert plan_update(sitemap, {}, H, E).blocked == "sitemap_unreadable"


def test_moved_host_sitemap_blocks_and_never_proposes_departures():
    old = "oie.fas.harvard.edu"
    entries = [{"url": f"https://{old}/"}]
    now = {"https://studyabroad.college.harvard.edu/a": "2026-10-01", "https://studyabroad.college.harvard.edu/b": "2026-10-01"}
    prev = {f"https://{old}/a": "2026-05-01", f"https://{old}/b": "2026-05-01"}
    plan = plan_update(now, {}, old, entries, prev_sitemap=prev)
    assert plan.blocked == "sitemap_foreign_host" and plan.departures == [] and plan.fetch == {}


def test_host_moved_helper():
    assert host_moved(["https://oie.fas.harvard.edu/a"], ["https://studyabroad.college.harvard.edu/a"])
    assert not host_moved(["https://english.fas.harvard.edu/a"], ["https://english.fas.harvard.edu/b"])
    assert not host_moved([], ["https://english.fas.harvard.edu/b"])


# --- R15 departures and the cap ---------------------------------------------------------------------
def test_departures_are_urls_in_the_previous_snapshot_and_absent_now():
    prev = sm(*[(f"/p{i}", "2026-01-01") for i in range(20)])
    now = sm(*[(f"/p{i}", "2026-01-01") for i in range(19)])        # p19 left
    plan = plan_update(now, {}, H, E, prev_sitemap=prev)
    assert plan.departures == [k("/p19")] and plan.removal_blocked is None


def test_departures_ignore_out_of_scope_urls():
    prev = sm(("/a", "2026-01-01"), ("/tag/gone", "2026-01-01"))
    now = sm(("/a", "2026-01-01"))
    assert plan_update(now, {}, H, E, prev_sitemap=prev).departures == []


def test_urls_never_in_the_previous_snapshot_are_never_departures():   # manifest-only pages are not candidates
    prev = sm(("/a", "2026-01-01"))
    now = sm(("/a", "2026-01-01"))
    assert plan_update(now, state(("/crawled-only", "2026-01-01")), H, E, prev_sitemap=prev).departures == []


def test_departure_cap_holds_removals_but_still_fetches():
    prev = sm(*[(f"/p{i}", "2026-01-01") for i in range(10)])
    now = sm(*[(f"/p{i}", "2026-01-01") for i in range(4)], ("/new", "2026-02-01"))   # 6 of 10 gone
    plan = plan_update(now, {}, H, E, prev_sitemap=prev, departure_cap=0.30)
    assert plan.removal_blocked and plan.departures == [] and plan.fetch[k("/new")] == "new"


# --- R16 confirmation fetch -------------------------------------------------------------------------
@pytest.mark.parametrize("status,loc,expected", [
    (404, None, "retire"), (410, None, "retire"),
    (403, None, "hold"),
    (301, "/new-slug", "follow"), (308, "https://x/y", "follow"),
    (200, None, "keep"),
    (500, None, "unknown"), (503, None, "unknown"), (None, None, "unknown"),
    (301, None, "unknown"),                                              # redirect with no target is not trusted
])
def test_classify_confirmation(status, loc, expected):
    assert classify_confirmation(status, loc) == expected


def test_server_errors_never_retire():
    assert all(classify_confirmation(s) != "retire" for s in (500, 502, 503, 504, None))


# --- R20 never-captured pages are a separate backfill ------------------------------------------------
BASE = datetime(2026, 7, 22, tzinfo=timezone.utc)


def test_never_captured_pages_are_listed_not_fetched_by_default():
    sitemap = sm(("/old", "2026-05-01"), ("/fresh", "2026-09-01"))
    plan = plan_update(sitemap, {}, H, E, baseline=BASE)
    assert plan.backfill == {k("/old"): "never_captured"} and plan.fetch[k("/fresh")] == "new"
    assert k("/old") not in plan.fetch


def test_backfill_flag_fetches_them_with_their_own_reason():
    plan = plan_update(sm(("/old", "2026-05-01")), {}, H, E, baseline=BASE, backfill=True)
    assert plan.fetch[k("/old")] == "backfill" and plan.backfill == {}


def test_recorded_unfetched_pages_stay_in_backfill_until_their_lastmod_moves():
    st = {k("/old"): {"lastmod": "2026-05-01", "fetched": False}}
    assert plan_update(sm(("/old", "2026-05-01")), st, H, E).backfill == {k("/old"): "never_captured"}
    assert plan_update(sm(("/old", "2026-09-30")), st, H, E).fetch[k("/old")] == "changed"


def test_without_a_baseline_unknown_pages_are_new_not_backfill():
    plan = plan_update(sm(("/old", "2020-01-01")), {}, H, E)
    assert plan.fetch[k("/old")] == "new" and plan.backfill == {}


# --- R10 refined: a scoped host with a real section uses the sitemap -------------------------------------
def test_scoped_host_with_a_real_section_is_planned_from_the_sitemap():
    scoped = [{"url": f"https://{H}/undergraduate/", "scope_to_path": True}]
    pages = [(f"/undergraduate/concentration/p{i}", "2026-09-01") for i in range(40)] + [("/directory/x", "2026-09-01")]
    plan = plan_update(sm(*pages), {}, H, scoped)
    assert plan.blocked is None
    assert sum(1 for r in plan.fetch.values() if r == "new") == 40          # the section, not the directory
    assert plan.out_of_scope == 1


def test_scoped_host_with_a_real_section_and_unreadable_sitemap_falls_back_to_seeds():
    scoped = [{"url": f"https://{H}/undergraduate/", "scope_to_path": True}]
    assert list(plan_update(None, {}, H, scoped).fetch.values()) == ["seed"]


def test_scoped_host_departures_stay_inside_the_section():
    scoped = [{"url": f"https://{H}/undergraduate/", "scope_to_path": True}]
    prev = sm(*[(f"/undergraduate/p{i}", "2026-01-01") for i in range(20)] + [("/directory/gone", "2026-01-01")])
    now = sm(*[(f"/undergraduate/p{i}", "2026-01-01") for i in range(19)])
    plan = plan_update(now, {}, H, scoped, prev_sitemap=prev)
    assert plan.departures == [normalize_key(f"https://{H}/undergraduate/p19")]


def test_tiny_scoped_host_reports_the_sitemap_pages_outside_its_section_as_out_of_scope():
    scoped = [{"url": f"https://{H}/undergraduate", "scope_to_path": True}]
    pages = [("/undergraduate", "2026-01-01"), ("/undergraduate/a", "2026-01-01")] + [(f"/other/p{i}", "2026-01-01") for i in range(7)]
    plan = plan_update(sm(*pages), {}, H, scoped)
    assert list(plan.fetch.values()) == ["seed"]
    assert plan.out_of_scope == 7                    # the report once counted these as in scope
