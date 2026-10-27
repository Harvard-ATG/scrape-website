# Scraping taxonomy and rules

Derived from the sitemap / manifest / scope analysis of 2026-10-15 (see the Claude Docs "Incremental Update via
Sitemap lastmod: Findings" and "Scraping Decisions Log"). Executable version: `rules.py`. Tests: `tests/`.
Rules marked **PROPOSED** (R6, R7) were adopted on 2026-10-15 as policy (decisions 6, 7, 43) but are not yet in the
scraper, so they stay switched off in code unless `adopt_proposed=True` / `exclude_events=True`.

## 1. Taxonomy

### 1.1 URL kinds (`url_kind`)

| Kind | Example | What it is | Default action |
| --- | --- | --- | --- |
| `page` | `/undergraduate-program` | Ordinary content page | Fetch when new or lastmod changed |
| `event_page` | `/event/seminar-macroeconomics-58` | One event (about 35% of sitemap pages; the 80 sampled dated events were all past) | In scope today; PROPOSED exclude (43) |
| `event_feed` | `/node/1397253/event-feed.ics` | iCal feed per event; found by link-following, never listed in a sitemap | PROPOSED exclude (6) |
| `resource_page` | `/resource/slug` | Landing page for a file; in the XML sitemap with the file's date | Fetch card, then the binary |
| `file_binary` | `/sites/g/files/.../x.pdf` | PDF, DOCX and similar; in no sitemap | Reached by link; include patterns can drop it; carry forward |
| `tag_archive` | `/tag/x`, `/author/y`, `/category/z` | Archive listings | Excluded (default) |
| `archive_listing` | `/news/page/2`, `/2024/11` | Pagination and date archives | Excluded (default, `/page/N`) |
| `query_variant` | `/search?page=3` | Query-string variant | Excluded for search (PROPOSED); other queries decision 8 |
| `admin` | `/wp-admin/...`, `wp-sitemap-*.xml` | System paths | PROPOSED exclude (6) |

Duplicate addresses (`http://` twin, trailing slash, `index.html`) are handled by normalization (R1) and the
`^http://` exclude (PROPOSED, 7), not by a kind.

### 1.2 Host classes

| Dimension | Values | Counts (83 hosts) |
| --- | --- | --- |
| Entry kind | `scoped` (every entry has scope_to_path), `include` (include_patterns), `root` (seed is the domain root), `subpath` (seed has a path, not scoped) | 17 / 3 / 29 / 34 (4 old moved names counted separately; mcb became scoped on 2026-10-15) |
| Sitemap state | `ok`, `none` (ces, daviscenter, careerservices, courses.my), `unreadable` (astronomy, scienceeducation, statistics returned 503; math failed in one fetch), `foreign_host` (host moved), `relative_locs` (csadvising) | see report |
| Lastmod coverage | 90% or more of URLs on 72 hosts; partial on emr (78%), engagedscholarship (82%), complit (87%); none on csadvising | 206 URLs refetched every run |
| Platform | Drupal 10 HWP (52, has markdown sitemap), Drupal 11, HU Sites 7, WordPress, Wix, Hugo | |

### 1.3 Page states in an update run

`new` (not stored) | `changed` (stored lastmod differs) | `no_lastmod` (sitemap has none: always refetch) |
`unchanged` (skip) | `never_captured` (in scope, in the sitemap, never stored, lastmod not later than the baseline: listed for a separate backfill, not fetched) | `seed` (always fetched) | `out_of_scope` | `departure` (in last snapshot, not now) |
`blocked` (whole host skipped).

## 2. Rules (in evaluation order)

| Id | Rule | In code |
| --- | --- | --- |
| R1 | Compare URLs by key: https, lowercase host, no fragment, no trailing slash, query kept | `normalize_key` |
| R2 | A URL on another host than the entry's hostname is out of scope | `evaluate` |
| R3 | `scope_to_path`: only the seed path and below, ending at a path boundary (`/a` does not admit `/a-b`) | `evaluate` |
| R4 | `include_patterns`: a URL must match at least one regex | `evaluate` |
| R5 | Default excludes (`/tag/`, `/author/`, `/page/N`, `/feed`, `/print/`, `?print=`, `/comments/`, `/cdn-cgi/`, `/search?`, `.ics`, `/bibcite/export` (decision D1)) plus the site's `exclude_patterns` | `evaluate` |
| R6 | **PROPOSED** (6, 7): also exclude `\.ics`, `^http://`, `/search\?`, `/wp-admin/`. PR #4 delivers the `\.ics` and `/search\?` excludes and replaces `^http://` with http-to-https canonicalization (R1), so `^http://` (PR #9) becomes unnecessary if #4 merges | `PROPOSED_EXCLUDES` |
| R7 | **PROPOSED** (43): exclude individual event pages (listings stay) | `exclude_events` |
| R8 | A host with several entries takes the union of their scopes | `evaluate` |
| R9 | Every entry's seed URL is always in scope | `evaluate` |
| R10 | A host whose entries are all path-scoped with a tiny section (at most 5 sitemap pages besides the seed, true of 16 hosts): re-fetch the seeds each run, ignore the sitemap. A larger section (mcb, 182 pages) is planned from the sitemap like any other host | `plan_update`, `SECTION_PAGE_THRESHOLD` |
| R11 | Sitemap unreadable or empty: block the host (no fetches, no removals) | `plan_update` |
| R12 | Sitemap lists only another host (moved): block the host, never propose removals | `plan_update`, `host_moved` |
| R13 | Fetch a URL when it is not stored (`new`) or its lastmod differs from the stored one (`changed`, any difference, not only newer); fetch always when the sitemap has no lastmod or one that cannot be parsed | `plan_update` |
| R13b | First run, no stored lastmod: `changed` only if lastmod is later than the baseline (manifest `generated_at`) | `plan_update(baseline=)` |
| R14 | Compare full timestamps in UTC. A bare date is read as the end of that day, so a same-day edit is not missed; text after a date is rejected | `parse_lastmod` |
| R20 | Pages never captured (not stored, lastmod not later than the baseline) are listed in `plan.backfill` and are not fetched by a normal update; a separate, capped backfill fetches them (`backfill=True`). Record them in state as unfetched so later runs keep skipping them | `plan_update(backfill=)` |
| R15 | Departures are in-scope URLs in the previous snapshot and absent from the current one (a seed is never a departure, R9). If more than 30% (suggested) depart, hold all removals for review | `plan_update(prev_sitemap=)` |
| R16 | Confirm each departure by fetching it: 404 or 410 retire; 403 hold; 3xx follow (retire once the target is captured); 200 keep; 5xx or timeout unknown, never retire | `classify_confirmation` |
| R17 | Retire only after a complete, uncapped run of the host; never on a failed or partial run (policy, not coded) | |
| R18 | Files: use `/resource/` page lastmod where the sitemap has it; carry known files forward elsewhere (policy, not coded) | |
| R19 | Monthly full refresh as the backstop for silent edits, listing pages and pages in no sitemap (policy, not coded) | |

## 3. Known exceptions (asserted in `tests/test_all_hosts.py`)

- No sitemap: courses.my, ces, daviscenter, careerservices.
- Unreadable on 2026-10-15: astronomy, scienceeducation, statistics (503); www.math (flaky).
- Moved hostnames (sitemap lists the new host): oie.fas, summerfunding, incomingstudents, oaisc.fas.
- Relative sitemap URLs and no lastmod: csadvising.
- Partial lastmod: emr, engagedscholarship, complit.
- Pending prune after a rule change: mcb (scope_to_path added 2026-10-15; 640 manifest pages now out of scope; `PENDING_PRUNE` in `tests/test_all_hosts.py`).
- Departure cap trips: ofa (616 of 1,085 URLs left after a restructure).
- Known bug, expected failure: handbook include patterns drop `Fields_of_Concentration_2026-27.pdf`.
  Proposed pattern: `(?i)fields(?:%20|[_\-\s])of(?:%20|[_\-\s])concentration` (a plain `.?` cannot match `%20`).

## 4. Running

```
cd aidocs/feature/scraper-update-mode/rules
../../../../.venv/bin/python -m pytest tests -q          # unit, scope, plan, cross-host invariants
../../../../.venv/bin/python validate_hosts.py           # writes report/hosts.csv and report/summary.json
```

Inputs: `fixtures/sitemaps_2026-10-15.json.gz`, `fixtures/sitemaps_2026-07-28.json.gz`, `sites.toml` (env
`SITES_TOML`), cached QA manifests (env `MANIFEST_CACHE`). Refresh the snapshots with the cadence tool's fetch stage.
