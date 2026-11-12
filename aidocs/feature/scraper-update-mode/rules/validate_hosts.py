"""Cross-host validation report (offline). Runs the reference rules over every host and writes
report/hosts.csv and report/summary.json.

    cd aidocs/feature/scraper-update-mode/rules
    ../../../../.venv/bin/python validate_hosts.py

Inputs: fixtures/sitemaps_*.json.gz, sites.toml (SITES_TOML), cached QA manifests (MANIFEST_CACHE).
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parents[3])]

from loaders import (MOVED_HOSTS, SNAP_JUL, SNAP_OCT, load_manifest, load_sites, load_snapshot,  # noqa: E402
                     sitemap_dict)
from rules import evaluate, is_path_scoped, normalize_key, parse_lastmod, plan_update, url_kind  # noqa: E402

TODAY = datetime(2026, 10, 15, tzinfo=timezone.utc)


def entry_kind(entries):
    if is_path_scoped(entries):
        return "scoped"
    if any(e.get("include_patterns") for e in entries):
        return "include"
    if any(urlsplit(e["url"]).path.strip("/") == "" for e in entries):
        return "root"
    return "subpath"


def main():
    oct_, jul = load_snapshot(SNAP_OCT), load_snapshot(SNAP_JUL)
    sites = load_sites()
    old_entries = {old: [{"url": f"https://{old}/"}] for old in MOVED_HOSTS}
    hosts = {**sites, **old_entries}
    rows = []
    for host, entries in sorted(hosts.items()):
        moved_old = host in MOVED_HOSTS
        sm = sitemap_dict(oct_.get(host))
        r = {"host": host, "kind": "moved(old name)" if moved_old else entry_kind(entries), "sitemap": "ok" if sm else "none/unreadable",
             "sitemap_urls": len(sm) if sm else 0}
        if not sm:
            r["note"] = "no snapshot (new hostname)" if host not in oct_ else "unreadable"
            rows.append(r)
            continue
        r["lastmod_cov"] = round(sum(1 for v in sm.values() if v) / len(sm), 3)
        # --- first run from the QA manifest as baseline (R13b) and from an empty state
        man = load_manifest(host)
        state, baseline = {}, None
        if man:
            ents, baseline = man
            for e in ents:
                if e.get("content_type") == "webpage" and "?" not in e["source_url"]:
                    state[normalize_key(e["source_url"])] = {"lastmod": None}
        prev = sitemap_dict(jul.get(host))
        plan = plan_update(sm, state, host, entries, prev_sitemap=prev, baseline=baseline)
        r["blocked"] = plan.blocked or ""
        if plan.blocked:
            rows.append(r)
            continue
        c = plan.counts()
        r["in_scope"] = len(sm) - plan.out_of_scope
        r["out_of_scope"] = plan.out_of_scope
        new_res = sum(1 for k, rr in plan.fetch.items() if rr == "new" and url_kind(k) == "resource_page")
        r["first_run_new"] = c.get("new", 0) - new_res
        r["first_run_new_resource_pages"] = new_res
        r["first_run_changed"] = c.get("changed", 0)
        r["no_lastmod"] = c.get("no_lastmod", 0)
        r["skip"] = c.get("skip", 0)
        r["backfill"] = c.get("backfill", 0)
        r["departures"] = c.get("departures", 0)
        r["removal_blocked"] = plan.removal_blocked or ""
        r["manifest_baseline"] = baseline.date().isoformat() if baseline else ""
        # --- steady state: in-scope URLs whose lastmod is within the last 7 and 30 days
        for days in (7, 30):
            lim = TODAY - timedelta(days=days)
            n = 0
            for u, lm in sm.items():
                full = u if "://" in u else f"https://{host}{u}"
                d = parse_lastmod(lm)
                if d and d >= lim and evaluate(full, host, entries).in_scope:
                    n += 1
            r[f"changed_{days}d"] = n
        # --- effect of the proposed rules on this host's in-scope pages
        kinds = Counter()
        for u in sm:
            full = u if "://" in u else f"https://{host}{u}"
            if evaluate(full, host, entries).in_scope:
                kinds[url_kind(full)] += 1
        r["in_scope_event_pages"] = kinds["event_page"]
        r["in_scope_event_feeds"] = kinds["event_feed"]
        r["in_scope_resource_pages"] = kinds["resource_page"]
        plan2 = plan_update(sm, state, host, entries, prev_sitemap=prev, baseline=baseline, adopt_proposed=True, exclude_events=True)
        c2 = plan2.counts()
        r["first_run_if_proposed_adopted"] = c2.get("new", 0) + c2.get("changed", 0)
        rows.append(r)

    out = HERE / "report"
    out.mkdir(exist_ok=True)
    cols = sorted({k for r in rows for k in r}, key=lambda k: ["host", "kind", "sitemap", "sitemap_urls", "note", "blocked"].index(k)
                  if k in ["host", "kind", "sitemap", "sitemap_urls", "note", "blocked"] else 99)
    with open(out / "hosts.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    ok = [r for r in rows if "in_scope" in r]
    S = lambda k, rs=ok: sum(r.get(k, 0) for r in rs)
    by_kind = Counter(r["kind"] for r in rows)
    summary = {
        "hosts": len(rows), "by_kind": dict(by_kind),
        "sitemap_ok": sum(1 for r in rows if r["sitemap"] == "ok"),
        "blocked": {r["host"]: r["blocked"] for r in rows if r.get("blocked")},
        "unreadable_or_missing": [r["host"] for r in rows if r["sitemap"] != "ok"],
        "hosts_planned": len(ok),
        "in_scope_pages": S("in_scope"), "out_of_scope_pages": S("out_of_scope"),
        "first_run_new_pages": S("first_run_new"), "first_run_new_resource_pages": S("first_run_new_resource_pages"),
        "first_run_changed": S("first_run_changed"),
        "first_run_no_lastmod": S("no_lastmod"),
        "backfill_never_captured": S("backfill"),
        "first_run_total_excluding_resource_pages": S("first_run_new") + S("first_run_changed") + S("no_lastmod"),
        "first_run_total_including_resource_pages": S("first_run_new") + S("first_run_new_resource_pages") + S("first_run_changed") + S("no_lastmod"),
        "first_run_if_proposed_adopted": S("first_run_if_proposed_adopted"),
        "changed_7d": S("changed_7d"), "changed_30d": S("changed_30d"),
        "departures": S("departures"),
        "removal_blocked": {r["host"]: r["removal_blocked"] for r in ok if r.get("removal_blocked")},
        "event_pages_in_scope": S("in_scope_event_pages"), "event_feeds_in_scope": S("in_scope_event_feeds"),
        "resource_pages_in_scope": S("in_scope_resource_pages"),
    }
    json.dump(summary, open(out / "summary.json", "w"), indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
