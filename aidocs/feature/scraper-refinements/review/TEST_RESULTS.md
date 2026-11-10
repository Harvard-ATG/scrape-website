# Test results: scraper refinements

Run 2026-11-05, local, no network.

| Suite | Code | Command | Result |
|---|---|---|---|
| scrape-website `tests/` | `ffe35d6` | `uv run --frozen --extra dev pytest -q -rs tests` | 80 passed |
| update-mode rules | `ffe35d6` | `uv run --frozen --extra dev pytest -q -rs aidocs/feature/scraper-update-mode/rules/tests` | 198 passed, 2 skipped |
| apo-mcp-server orchestration | `c833135` (v1.1.0-rc14), detached worktree | `uv run --frozen pytest -q tests/test_scrape_and_ingest_args.py tests/test_scrape_defaults.py tests/test_ingest.py` | 34 passed |

Skips: `test_all_hosts.py:97` (empty host parameter set) and `:123` (no cached QA manifests). Both need QA manifests pulled locally.

## Per file, scrape-website

| File | What it pins | Tests |
|---|---|---|
| test_rate_limit.py | 429 retried after a backoff; 15/30/60 s then denied; pause carries to the next fetch on the host | 3 |
| test_tier1_skip.py | sticky Tier 2 after 5 blocks; reset on success | 3 |
| test_browser_slots.py | Tier 3 browser cap across processes | 14 |
| test_offsite_and_error_pages.py | off-host redirects and 4xx/5xx not saved or expanded | 6 |
| test_media_not_pages.py | media URLs and media content types | 2 |
| test_default_excludes.py | default patterns, event keep hosts | 8 |
| test_sitemap_discovery.py | robots-first discovery, tiers, lastmod, logging | 12 |
| test_crawl_flow.py | fetch paths, manifest atomicity | 10 |
| test_crawl_generation.py | crawl generation decisions | 18 |
| test_scraper_wiring.py | constructor wiring | 4 |

## Not tested

- Live sites, rate limits and WAF behavior: tests use fake fetches. The figures in the deck come from the Oct 27–28 prod runs.
- Throughput at each concurrency, and the gateway's upload limit.
- The scrape sets (a document, not code).
- The weekly update: `plan_update` has rules tests but is not called by the scraper.

Note: running the scraper suite installed the `dev` extra (pytest) into the scrape-website-pr10 `.venv`.
