# Prompt for the code walk

Paste everything below the line into the code-walk tool and point the tool at this folder:

    /Users/kevingray/codebase/harvard-atg/scrape-website-pr10

It is a separate checkout of PR #10's branch (`feature/scraper-update-mode-consolidated`, base `feature/python-package`).
Do not point the tool at `scrape-website`: that folder is on a different branch and has none of the PR #7 code. Line
numbers below are for local commit `a523244`, which is the PR's last pushed commit `a70def7` plus one unpushed fix.

---

Build a guided code walkthrough of this pull request.

Before anything else, run `git rev-parse --short HEAD` in the checkout. It must print `a523244`. If it prints anything else,
stop and say which commit you found; do not guess line numbers.

## Context

- The scraper crawls about 83 Harvard websites. A separate repo, `apo-mcp-server`, runs it and ingests the results into a vector store.
- This PR stacks earlier scraper work (429 escalation, PR #4 URL canonicalization and excludes, PR #7 crawl-generation state, PR #8 tiered sitemap discovery and cadence tooling) and adds a taxonomy, 20 rules (R1 to R20), a tested reference implementation of them, tests, and a validation script, all under `aidocs/feature/scraper-update-mode/rules/`.
- Important: the reference implementation is not wired into the scraper. There is no `--update` flag yet. Label anything proposed as "proposed".
- Audience: engineers who will review the PR and later build update mode. They know Python, async and SQLite. They do not know this codebase.
- Goal: after the walk a reader can (1) explain how a scrape and a refresh work today, (2) explain what an update run would do differently and why, (3) find each rule in the code and the test that covers it, and (4) say what exists and what is not built.

## Framing

The walk answers one question: how should scraping, and keeping pages up to date, get better? Make the steps support these
five points, in this order, and say in each step which point it supports:

1. A full re-scrape is still needed, and it gets cleaner (steps 1 to 3: the exclude patterns and the https canonicalization; in the July manifests they remove or merge 73,101 of 143,477 saved pages).
2. The sitemap files give a map, and only the XML one has dates (step 5, and the taxonomy in `RULES.md`).
3. Intermediate updates fetch only what changed (steps 12 to 15).
4. Sites that moved in the Harvard reorganization are recognized, not mistaken for deletions (step 15: the foreign-host check in `plan_update` and `host_moved`; the `sites.toml` change).
5. Deleting needs a fetch to agree (step 15: `classify_confirmation`).

## Format

- About 16 steps, in the order given below.
- Each step has: a title; the file and line range; a 2 to 4 sentence plain-language explanation; one sentence on why it matters; one concrete thing to notice (a constant, a line, a test name); and a status tag: IN SCRAPER TODAY, REFERENCE CODE ONLY, TEST, or OUTSIDE THIS PR.
- Open with a one-paragraph overview and two small flow diagrams: today (sites.toml entry, crawl, fetch, save, manifest and S3, ingest) and proposed update (entry, scope, read sitemap, plan, fetch only the plan, save, record state, ingest). Mark proposed steps as dashed.
- Quote short snippets only (10 lines or fewer). Never describe behavior you have not seen in the code.
- Explain each rule id (R1, R2, ...) the first time it appears, and tie it to its code and its test.
- Close with: a table mapping PR pieces to stages of the flow, a list of what is not built yet, and the commands to run the tests and the validation script.
- Tone: concrete and plain, no hype.
- Output: return exactly the structured format this tool asks for, as valid JSON with no text outside it. If you cannot complete the walk, return that same structure with the problem described in its error or summary field, never plain prose.

## The walk

### Part A: how a scrape works today (`scrape_website/scraper.py`)

1. `_DEFAULT_EXCLUDE_PATTERNS`, line 84. The default excludes; PR #4 added `/search\?` and `\.ics$`.
2. `_url_excluded` (192) and `_url_within_path_prefix` (203). The scope helpers that the new rules reuse unchanged.
3. `_normalize_url`, line 321. PR #4 rewrites `http` to `https` so one page is not crawled twice.
4. `_extract_links_lxml`, line 387. Returns a set, so crawl order is random; this is why the same settings once saved 45 to 136 pages on one site.
5. `_fetch_sitemap_urls`, line 228. Tiered sitemap discovery from PR #8. It returns URLs only, with no last-modified dates, which is the gap update mode fills.
6. `URLStore` (536), `max_crawl_gen` (600), `upsert_metadata` (621), `export_manifest` (638). The state database and manifest, with PR #7's `crawl_gen` and `last_fetched_at` columns.
7. `_decide_crawl_gen` (342), `_should_fetch` (360), `_should_write_manifest` (376). PR #7's seams. `_should_fetch` is where update mode would plug in.
8. `WebsiteScraper.crawl` (1397), `process_url` (1323), `run` (1478). The crawl loop. Sitemap seeding only happens when `use_sitemap` is on.

### Part B: context outside this PR (`apo-mcp-server`, show briefly)

If the tool cannot read the `apo-mcp-server` repository, skip Part B and say so in the walk instead of describing it from memory.

9. `scrape.py`: passes `scope_to_path` and `use_sitemap` from `sites.toml`; both default to False, so production crawls by following links only.
10. `scrape_and_ingest.py`, the fresh versus normal logic (about lines 258 to 330): fresh clears local data and re-crawls; normal pulls the last run from S3 and skips visited URLs.
11. `ingest.py`: `_ingest_hostname_locked` (290) builds the active set from files on disk; `deprecate_removed_urls` (71) retires every record for the host that is not in it, softly unless the hard-delete flag is on.

### Part C: the rules (`aidocs/feature/scraper-update-mode/rules/`)

12. `RULES.md`: the taxonomy (URL kinds, host classes, page states) and rules R1 to R20.
13. `rules.py`: `normalize_key` (40), `parse_lastmod` (47), `url_kind` (63). Normalization, UTC timestamps and the URL taxonomy.
14. `rules.py`: `evaluate` (119) with `_entry_decision` (94) and the `Decision` class (88). Scope rules R2 to R9. Note that proposed excludes are inert unless `adopt_proposed` or `exclude_events` is set.
15. `rules.py`: `plan_update` (167) with `Plan` (148). Walk the order of checks: path-scoped tiny section (R10), unreadable sitemap (R11), sitemap lists another host (R12), per-URL evaluation, the date comparison (R13, R13b), never-captured pages kept for backfill (R20), then departures with the 30% cap (R15). Also `classify_confirmation` (263) and `host_moved` (276).

### Part D: tests and tooling

16. `tests/`: `test_rules_unit.py` and `test_plan.py` (one test per rule, with real URLs), `test_handbook_regression.py` (a real bug found with the scraper's own link extractor), `test_all_hosts.py` (documented per-host exceptions such as NO_SITEMAP, UNREADABLE_NOW, LOW_LASTMOD and PENDING_PRUNE), `test_sites_toml.py`. Then `loaders.py`, `validate_hosts.py`, `fixtures/` and `report/`.

## Facts to get right

- 83 hosts; 56,992 in-scope sitemap pages (across the 71 hosts the report can plan); a first update run from the July manifests is about 4,339 pages, with 18,205 never-captured pages kept for a separate backfill; about 341 pages change per week; 821 departure candidates.
- 257 tests pass with the real `sites.toml` and cached manifests; 183 pass and 2 skip with `sites.toml` but no manifests; 76 pass and 26 skip with neither.
- Run over the 143,477 pages saved in the July manifests, PR #10's own code drops or merges 73,101 (50.9%): 23,896 `/search?` pages, 10,012 `.ics` feeds and 39,193 twin URLs (http versus https, trailing slash). 19,823 query-string pages remain pending a rule.
- Times quoted anywhere (for example 1.1 to 1.7 seconds per page) come from local scrape logs, not from AWS.

## Do not claim

- That update mode runs, or that any of `rules.py` is called by the scraper.
- That any AI or human review of this PR has happened.
- Anything about pages the sitemaps do not list, beyond saying they rely on a monthly full refresh (R19).
