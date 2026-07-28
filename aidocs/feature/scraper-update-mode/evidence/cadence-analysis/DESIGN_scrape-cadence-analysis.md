# Design: Per-Site Scrape Cadence Analysis

**Date**: 2026-07-28 | **Status**: Approved for planning
**Repo/branch**: `Harvard-ATG/scrape-website` `fix/sitemap-discovery-tiered`
**Foundation**: [DESIGN_update-mode-scoping.md](../scraper-update-mode/DESIGN_update-mode-scoping.md),
`evidence/aws-reachability/`, `evidence/crossover/corpus_crossover.py`

## 1. Goal

For each of the 83 sites in `sites.toml`, produce a **recommendation of scrape
frequency + mode (fresh vs. incremental)**, grounded in two evidence sources:

1. **Cadence** — the live sitemap's `<lastmod>` distribution (how often the site
   actually changes).
2. **Diff** — the delta between the live sitemap and QA's last-scraped
   `state.db` (what has drifted since we last scraped).

The output informs how often each site should be re-scraped and whether a full
fresh re-scrape or an incremental pass is appropriate.

## 2. Motivating evidence (why this matters)

Live example found 2026-07-28: `aaas.fas.harvard.edu/file_url/1251` is the
**2024–2025** Harvard College *Fields of Concentration* PDF (4.73 MB). In the
prod vector store it is `deleted=false`, `source_status=current` (DB id 15514,
`file-2M3eskXruDX4Xyp6H8aEHs`, ingested 2026-06-29) — i.e. **live and
searchable**, a full academic year out of date. It persists because the live
site still links `/file_url/1251` (HTTP 200), so every scrape re-ingests it and
nothing retires it. An incremental "new-URLs-only" pass can **never** catch this
— the URL is unchanged; only a content-change / removal-aware signal can. This
is the exact class of staleness the cadence analysis is built to surface. (The
same `/file_url/NNN` pattern hides other stale docs: `1018` = a Boston Globe
article PDF, `833` = a 2021 event flyer.)

## 3. Decisions (locked)

| # | Decision | Choice | Rationale |
|---|----------|--------|-----------|
| D1 | Deliverable form | **Reproducible Python script + committed MD report** (not a notebook) | PR-reviewable, re-runnable headless, no notebook-diff noise |
| D2 | Baseline for the diff | **QA scrape bucket `manifest.json`** `s3://atg-apo-mcp-qa-scrape/data/{host}/manifest.json` — not `state.db` | The `visited` table in `state.db` has **no timestamp column** (confirmed 2026-07-28: `url, filename, hostname, title, found_on, file_type, content_hash, file_size`), so it cannot date the baseline. `manifest.json` carries `generated_at` (ISO 8601 = when the host was last scraped/ingested) **and** `files{}.source_url` (the exact URL set QA holds) in one small top-level file. QA's per-host `generated_at` is surfaced so a stale/Akamai-blocked baseline is visible, not hidden |
| D3 | Recommendation objective | **Balanced** | Longest interval that still keeps content acceptably fresh given each site's observed update rate |
| D4 | Run location | **Local** (Tier 2 curl_cffi `impersonate=chrome`) | The AWS-NAT Akamai 403 problem is irrelevant for *reading* sitemaps from a local IP; S3 pulls use `AWS_PROFILE=tlt-prod` |
| D5 | Code + artifact location | `aidocs/feature/scraper-update-mode/evidence/cadence-analysis/` | Discovery/evidence tooling (not a shipped feature); lives beside the `aws-reachability` seed it consumes, matching the repo's `evidence/`-script pattern |
| D6 | No-sitemap edge set | **Confirmed** (2026-07-28 deep probe, `aidocs/fix/sitemap-discovery-tiered/no-sitemap-deep-probe/`): all 4 flagged hosts (ces, daviscenter, careerservices, www.hio) truly lack a sitemap — 46 candidate paths × apex/www, robots.txt parsed, 0 hits. CMS: careerservices=WordPress (core sitemaps disabled), daviscenter+www.hio=Drupal (no `simple_sitemap`), ces=no CMS fingerprint. These 4 are a permanent no-lastmod edge |

## 4. Architecture — one orchestrator, five single-purpose stages

`analyze_cadence.py` runs all stages end-to-end but **caches each stage's JSON**,
so any stage re-runs independently without repeating expensive network work
(`--stage discover|fetch|cadence|diff|recommend`, or `--all`).

| # | Stage | Reuses | Emits | Purpose |
|---|-------|--------|-------|---------|
| 1 | **Discover** | crossover discovery (robots.txt → `/sitemap.xml` → `/sitemap_index.xml` → `/wp-sitemap.xml`, Tier 2) | `sitemaps_discovered.json` | Authoritative "where each sitemap lives" map |
| 2 | **Fetch** | crossover fetch | `sitemap_urls.json` (host → `[{loc, lastmod}]`) | Pull full sitemap(s), recurse **fully** into indexes, extract every `(loc, lastmod)` |
| 3 | **Cadence** | new (pure math) | `cadence.json` | Per host: #URLs, % with lastmod, newest/oldest, median age, updated-in-last-7/30/90/180d, estimated update interval |
| 4 | **Diff** | crossover URL normalization + S3 pull | `diff.json` | Pull QA `manifest.json`; new-since-scrape, gone-from-manifest (possible removals), and URLs whose `<lastmod>` > `generated_at` (changed) |
| 5 | **Recommend** | new | `recommendations.json` + `RECOMMENDATIONS.md` | Combine cadence + diff → per-site `{frequency, mode, rationale}` + corpus summary |

### Data flow

```
sites.toml ─┐
            ├─► (1) discover ─► sitemaps_discovered.json
            │                        │
            │                        ▼
            │        (2) fetch ─► sitemap_urls.json ──────┐
            │                        │                    │
            │                        ▼                    │
            │      (3) cadence ─► cadence.json ───────────┤
            │                                             │
QA S3 manifest.json ─► (4) diff ─► diff.json ─────────────┤
                                                          ▼
                                       (5) recommend ─► recommendations.json
                                                        RECOMMENDATIONS.md
```

## 5. Stage detail

### Stage 1 — Discover
- For each host, resolve the sitemap URL via the tier-escalating discovery from
  `corpus_crossover.py` (robots.txt `Sitemap:` first, then candidate paths).
- Seed from `evidence/aws-reachability/result.json` where already known, but
  re-verify locally (cheap) so results are self-contained.
- Record: `host, sitemap_url, is_index, tier, status, loc_count_hint`.

### Stage 2 — Fetch
- Pull the full sitemap; **recurse fully** into every child of a `<sitemapindex>`
  (not one level — cadence needs every leaf's lastmods).
- Extract `(loc, lastmod)` per `<url>`; missing `<lastmod>` → `None`.
- Record per-host `lastmod_coverage` (% of URLs carrying a lastmod).

### Stage 3 — Cadence (pure functions, unit-tested)
Per host, from the lastmod set (relative to run date):
- `total_urls`, `with_lastmod`, `lastmod_coverage`
- `newest`, `oldest`, `median_age_days`
- `changed_last_{7,30,90,180}d` counts and fractions
- `est_update_interval_days` — median gap between consecutive sorted distinct
  lastmod dates (falls back to span/among-distinct-days when sparse)
- `cadence_class` ∈ {`high`, `moderate`, `low`, `dormant`, `unknown`}

### Stage 4 — Diff
- `aws s3 cp` each host's `manifest.json` from the QA bucket to a local cache
  (one small top-level file per host; `AWS_PROFILE=tlt-prod`).
- Read `generated_at` (baseline date) and the held-URL set
  `{f["source_url"] for f in manifest["files"].values()}`.
- Normalize URLs with the crossover normalizer (scheme→https, lower host, drop
  fragment, strip trailing slash) at the BASE level (drops query = page id).
- Compute: `qa_last_scrape` = `generated_at` (fall back to the manifest object's
  S3 `LastModified` if the field is absent), `new_since_scrape`
  (sitemap−manifest), `gone_from_manifest` (manifest−sitemap = removal
  candidates), `changed_since_scrape` (sitemap URLs whose `<lastmod>` >
  `qa_last_scrape`).

### Stage 5 — Recommend (balanced)
- **Frequency** from `cadence_class` + `changed_last_Nd`: high churn → weekly;
  moderate → biweekly/monthly; low → quarterly; dormant → on-demand only.
- **Mode**: notable `gone_from_manifest` **or** high `changed_since_scrape` →
  **fresh** (incremental can't catch changes/removals — see §2); mostly additive
  (new pages, few removals/changes) → **incremental** (cheaper, safe).
- Emit machine JSON + a human `RECOMMENDATIONS.md` (per-site table + rationale +
  corpus rollup: how many sites weekly/biweekly/monthly/quarterly, fresh vs incr).

## 6. Edge cases & honesty

- **No-sitemap hosts** (confirmed 4: ces, daviscenter, careerservices, www.hio —
  D6): no lastmod signal is possible → `cadence_class = unknown`. Cadence math
  cannot apply, so the recommendation falls back to a **fixed conservative
  periodic schedule** (e.g. monthly fresh) rather than a data-derived interval,
  and the host is explicitly flagged in the report as "no sitemap — default
  schedule." The v2 probe (2026-07-28, `result_v2.json`) exhausted extra XML
  spellings, HTML sitemap pages, homepage anchor scans, `Link:` headers, and the
  `http://` scheme — none found. It confirmed `homepage=200` + `robots.txt=200`
  on all 4 (real negatives, not Akamai challenges) and found a **partial
  freshness fallback**: `careerservices` exposes `/feed/` and `www.hio` exposes
  `/rss.xml` (RSS `<pubDate>` — recent items only, whole-site coverage NOT
  guaranteed); `ces` + `daviscenter` have no feed → pure fixed-schedule.
- **Low lastmod coverage**: reported per host; weak signal is called out in the
  rationale rather than silently trusted.
- **Stale/blocked QA baseline**: `qa_last_scrape` per host is printed so a QA
  state.db that lost to Akamai (FAS hosts) is visible as a caveat, not masked.
- **Per-host failure isolation**: one host's fetch/parse/S3 failure records a
  status and never aborts the run.

## 7. Testing (proportional — analysis tooling, not prod)

Unit tests on the **pure** functions only, over small fixtures:
- cadence stats (known lastmod sets → expected buckets/intervals),
- URL normalization (http/https, `?page=`, trailing slash, fragment),
- recommendation mapping (cadence_class × diff → frequency/mode).

Network stages are validated by inspecting the emitted `RECOMMENDATIONS.md`.

## 8. Artifacts (all under `aidocs/feature/scraper-update-mode/evidence/cadence-analysis/`)

```
analyze_cadence.py            # orchestrator + 5 stages
lib/                          # normalize.py, cadence.py, recommend.py (pure, tested)
tests/                        # unit tests for the pure functions
sitemaps_discovered.json      # stage 1
sitemap_urls.json             # stage 2
cadence.json                  # stage 3
diff.json                     # stage 4
recommendations.json          # stage 5 (machine)
RECOMMENDATIONS.md            # stage 5 (human report — the deliverable)
```

## 9. Open items feeding this design

- **Deep no-sitemap probe** (D6) — ✅ done 2026-07-28; confirmed 4 no-sitemap
  hosts, folded into §6. Evidence: `aidocs/fix/sitemap-discovery-tiered/no-sitemap-deep-probe/result.json`.
- **QA baseline recency** — Stage 4 surfaces per-host `qa_last_scrape`; if broadly
  stale we note it as a confidence caveat on the diff signal.
