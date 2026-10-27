# analyze_cadence.py
"""Orchestrator for the scrape-cadence analysis. Five cached stages
(discover -> fetch -> cadence -> diff -> recommend); each reads the prior
stage's JSON and writes its own, so any stage re-runs in isolation. All
decision logic lives in the pure modules; this file is wiring + I/O only.

Usage:
    python analyze_cadence.py --all
    python analyze_cadence.py --stage fetch
    python analyze_cadence.py --stage recommend
"""
import argparse
import asyncio
import json
import os
from datetime import date

import fetch as fetch_mod
import s3_manifest
from cadence import cadence_stats
from diff import diff_urls
from recommend import recommend
from report import render_report

HERE = os.path.dirname(os.path.abspath(__file__))
# aws-reachability is a sibling evidence dir under scraper-update-mode/evidence/
DEFAULT_SEED = os.path.join(HERE, "..", "aws-reachability", "result.json")
MANIFEST_CACHE = os.path.join(HERE, "manifest-cache")

DISCOVERED = os.path.join(HERE, "sitemaps_discovered.json")
SITEMAP_URLS = os.path.join(HERE, "sitemap_urls.json")
CADENCE = os.path.join(HERE, "cadence.json")
DIFF = os.path.join(HERE, "diff.json")
RECS_JSON = os.path.join(HERE, "recommendations.json")
RECS_MD = os.path.join(HERE, "RECOMMENDATIONS.md")


def _load(path):
    with open(path) as f:
        return json.load(f)


def _dump(path, obj):
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    print(f"wrote {os.path.relpath(path, HERE)}")


# --- STAGE 1: DISCOVER ---
def stage_discover(seed_path):
    seed = _load(seed_path)
    discovered = [
        {"host": r["host"], "sitemap_url": r.get("sitemap_url"),
         "is_index": r.get("is_index", False), "reachable": r.get("reachable", False)}
        for r in seed["results"]
    ]
    _dump(DISCOVERED, discovered)
    return discovered


# --- STAGE 2: FETCH ---
def stage_fetch():
    discovered = _load(DISCOVERED)
    seeds = [{"host": d["host"], "sitemap_url": d.get("sitemap_url")} for d in discovered]
    results = asyncio.run(fetch_mod.fetch_all(seeds))
    _dump(SITEMAP_URLS, results)
    return results


# --- STAGE 3: CADENCE ---
def stage_cadence(today):
    fetched = _load(SITEMAP_URLS)
    out = {}
    for host, r in fetched.items():
        if r.get("status") != "ok":
            continue
        lastmods = [e.get("lastmod") for e in r["entries"]]
        out[host] = cadence_stats(lastmods, today)
    _dump(CADENCE, out)
    return out


# --- STAGE 4: DIFF ---
def stage_diff(today):
    fetched = _load(SITEMAP_URLS)
    out = {}
    for host, r in fetched.items():
        if r.get("status") != "ok":
            out[host] = None
            continue
        manifest = s3_manifest.pull_manifest(host, MANIFEST_CACHE)
        if manifest is None:
            out[host] = None
            print(f"  {host}: manifest unavailable — diff skipped")
            continue
        out[host] = diff_urls(
            r["entries"],
            s3_manifest.manifest_source_urls(manifest),
            s3_manifest.manifest_generated_at(manifest),
            today,
        )
    _dump(DIFF, out)
    return out


# --- STAGE 5: RECOMMEND ---
def stage_recommend(today):
    discovered = _load(DISCOVERED)
    fetched = _load(SITEMAP_URLS)
    cadence = _load(CADENCE)
    diffs = _load(DIFF)
    records = []
    for d in discovered:
        host = d["host"]
        status = fetched.get(host, {}).get("status", "error")
        cad = cadence.get(host)
        dif = diffs.get(host)
        records.append({
            "host": host,
            "sitemap_url": fetched.get(host, {}).get("sitemap_url"),
            "status": status,
            "cadence": cad,
            "diff": dif,
            "recommendation": recommend(cad, dif),
        })
    _dump(RECS_JSON, records)
    with open(RECS_MD, "w") as f:
        f.write(render_report(records, today.isoformat()))
    print(f"wrote {os.path.relpath(RECS_MD, HERE)}")
    return records


def main():
    ap = argparse.ArgumentParser(description="Per-site scrape cadence analysis")
    ap.add_argument("--stage", choices=["discover", "fetch", "cadence", "diff", "recommend"])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--seed", default=DEFAULT_SEED)
    args = ap.parse_args()
    today = date.today()

    if args.all:
        stage_discover(args.seed)
        stage_fetch()
        stage_cadence(today)
        stage_diff(today)
        stage_recommend(today)
    elif args.stage == "discover":
        stage_discover(args.seed)
    elif args.stage == "fetch":
        stage_fetch()
    elif args.stage == "cadence":
        stage_cadence(today)
    elif args.stage == "diff":
        stage_diff(today)
    elif args.stage == "recommend":
        stage_recommend(today)
    else:
        ap.error("pass --all or --stage <name>")


if __name__ == "__main__":
    main()
