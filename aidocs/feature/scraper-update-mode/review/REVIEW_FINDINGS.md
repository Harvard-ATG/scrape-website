# Review findings: fixed and open

From two reviews of PR #10 (one read-only, one that ran code) on 2026-10-16 to 2026-10-18. Fixes are local and
uncommitted on `fix/update-mode-review-fixes` (scrape-website-pr10) and `fix/ingest-empty-active-urls`
(apo-mcp-server-fix, off origin/main). Each new test was checked to fail on the old code, except the guards marked (guard).

## Fixed

| Id | Finding | Where | Fix |
| --- | --- | --- | --- |
| F1 | `backfill=True` skipped a recorded-unfetched page with unchanged date | `rules.py` plan_update | fetched with reason `backfill`; changed date still gives `changed` |
| F2 | `Plan.counts()` overwrote the backfill count | `rules.py` | adds fetched and held |
| F3 | A seed missing from the sitemap was listed as a departure | `rules.py` R15 | seeds are subtracted |
| F4 | An unparseable `lastmod` was skipped | `rules.py` R13 | refetched as `no_lastmod` |
| F5 | `parse_lastmod` accepted trailing text; a bare date read as midnight missed same-day edits | `rules.py` R14 | trailing text rejected; bare date = end of that day |
| F6 | `upsert_metadata` erased `crawl_gen` and `last_fetched_at` when called without them | `scraper.py` | `COALESCE` keeps the stamp |
| F7 | Sitemap discovery probed `/sitemap.xml`, `/sitemap_index.xml`, `/wp-sitemap.xml` even when robots.txt advertised a working sitemap (each 403 can escalate to Tier 2/3) | `scraper.py` `_fetch_sitemap_urls` | fallbacks only when robots gave no URLs |
| F8 | Truncation at `max_urls` was silent | `scraper.py` | warning logged; flag still open (O4) |
| F9 | Empty `active_urls` retired every current row of the host | `apo-mcp-server/ingest.py` | no retirement, warning and Sentry message |
| F10 | Any non-200 page was treated as removed | `apo-mcp-server/ingest.py` | only 404 and 410 retire; 403, 429, 5xx, timeouts, 400 and unknown keep the page active (not re-ingested) |
| F11 | Tests that could not fail (proposed excludes, `.ics` loop, tautological asserts) | `rules/tests/` | proposed excludes tested with the defaults emptied; assertions tightened; R10 boundary (5 vs 6) and R12 mixed-host tests added |
| F12 | RULES.md out of step with code | `RULES.md` | R13, R14, R15 updated |
| F13 | 2,369 citation export files (26% of documents) were crawled and listed though ingest never reads them | `scraper.py` `_DEFAULT_EXCLUDE_PATTERNS` | `/bibcite/export` excluded; decision D1 in `DECISIONS.md`; `tests/test_default_excludes.py` |

Added guards (guard): scraper and rule keys agree after `normalize_key`; proposed excludes leave ordinary pages alone.
Not covered by a test: the ingest loop that adds non-removal non-200 pages to `active_urls` (only the status helper is tested).

## Open (noted in code as `NOTE(review)` where it applies)

| Id | Issue | Why it is open | Needs |
| --- | --- | --- | --- |
| O1 | `_should_write_manifest` counts a drained queue as complete; failed and denied pages are omitted from the manifest and then retired downstream (`scraper.py`, `process_url`) | A strict rule could stop manifests for most large sites | decision: error ratio threshold, or carry failed pages forward in the manifest |
| O2 | A URL is marked visited before it is fetched, so failed pages are never retried (`_should_fetch`, crawl loop) | Changing it touches resume semantics and the "fetched False" model | design with the planner seam |
| O3 | Planner does not fit the scraper: no per-URL `lastmod`/`fetched` columns; `_fetch_sitemap_urls` returns URLs without dates | The seam is the update flag work | schema and API change |
| O4 | Discovery returns no "complete" flag; nested indexes and `.xml.gz` are not followed | R11 and R15 need to tell a cut-off list from a full one | `SitemapResult(entries, complete)` |
| O5 | `WebsiteScraper(exclude_patterns=...)` replaces the defaults; the CLI and `rules.evaluate` add to them | Behavior change for callers that pass patterns | pick one meaning |
| O6 | Scope logic exists three times (link extraction, sitemap seeding, `_entry_decision`) and differs on host case | Refactor, not a bug today | extract one `_scope_reason` |
| O7 | `_retire_file` does not tolerate an already-gone file; the DB commit follows the OpenAI deletes | Changes failure handling in `apo-mcp-server` | decision on retries and ordering |
| O8 | Manifest as the retire list: ingest reads files on disk, not manifest entries; a normal run keeps old files from S3 | Needs either file deletion in the scraper or ingest iterating the manifest | design decision |
| O9 | Departure cap as a Sentry alert with review links; weekly confirm-and-retire | Not built; weekly backfill schedule dropped | build after O8 |
| O10 | `plan_update` is long and evaluates each URL more than once; `_abs` join repeated five times; `PROPOSED_EXCLUDES` for `.ics` and `/search?` now redundant; `host_moved` unused by the planner | Refactor | cleanup pass |
| O11 | `validate_hosts.py` not re-run after F4 and F5; summary numbers (4,339 first run and so on) may shift | It rewrites `report/` files | re-run and commit the report |
| O12 | Cross-host tests skip silently when `sites.toml` or the manifests are missing | CI has neither | decide whether CI provides them |
| O13 | Hosts with no or unreadable sitemap are seen only by the monthly full run | Policy | decide on a daily link-follow fallback |
| O14 | 4 new hostnames have no sitemap snapshot | Input gap | re-run the cadence fetch |
| O15 | 400 is not a removal status | Chosen to match R16 (404 and 410 only) | confirm |
| O16 | `/sitemap-llm` (52 Drupal 10 hosts, markdown, no dates): useful for **files and per-page `.md` copies**, not for page change detection. Evidence (earlier session, 2026-10-15/16, Claude Doc "Incremental Update via Sitemap lastmod: Findings"): same pages as the XML sitemap within 9 on the five hosts with both; **24% of its entries are files** (8,297 of 34,816), each linking to a metadata card with size, format, date and download path; on `haa` all 276 file entries are also in the XML sitemap (as landing pages with `lastmod`). Compared with what the crawl downloaded (filename match, approximate): economics 555 of 698 files, english 142 of 363, registrar 0 of 228, so link-following misses files the markdown sitemap lists. 26 of 30 sampled HTML pages advertise their own `.md` copy; the `.md` pages do not link to each other. A `<link rel="alternate" type="text/markdown">` tag on the homepage predicts the 52 hosts exactly. | SCOPE CAVEAT: the file comparison above was host-wide (whole `/sitemap-llm` against the whole manifest, matched by title or filename); it did not apply `sites.toml` scope, include or exclude rules. Run offline through `rules.evaluate`, the XML `/resource/` landing pages (a proxy for the file entries) are 9,964 across 45 hosts, of which 9,213 are in scope and 751 are not; all of `haa` (276), `mbb` (177), `histsci` (97), `medieval` (84), `archaeology` (43), `msi` (32), `celtic` (20) and `ghhp` (10) are out of scope because those hosts are path-scoped, and `music` (12) is dropped by its include patterns. Any file inventory must pass through the scope rules. An earlier answer in this review said it adds little; that was wrong about files. Limits: no dates; no new pages beyond XML; one known join bug (homepage slug differs from XML); the file overlap numbers are filename-based; whether served `.md` beats trafilatura output was never measured | decide: use it as a file inventory (find files the crawl missed, with the XML `/resource/` `lastmod` for change detection), and optionally run the small page-quality comparison |

### O16 result: `/sitemap-llm` through the scope rules, against the QA manifests (2026-10-19)

One GET per host (47 hosts read; economics timed out; three old moved names are not in `sites.toml`). Script: `llm_scope_check.py`; data: `llm_scope_2026-10-19.json`. Manifests are from 2026-07-22 and the sitemaps are live, so pages created since July count as missing.

| Measure | Value | Reliability |
| --- | --- | --- |
| Pages listed | 37,632 | |
| Pages in scope (`rules.evaluate`) | 30,708 (82%) | solid |
| In-scope pages found in the manifest (URL match) | 24,346 (79% of in-scope) | solid, July baseline |
| File entries listed | 10,375 | |
| File entries in scope | 9,624 | solid |
| File entries out of scope | 751 (same 751 as the XML `/resource/` proxy: haa, mbb, histsci, medieval, archaeology, msi, celtic, music, ghhp) | solid |
| In-scope file entries matched to a manifest document by name | 116 | **not usable** |
| In-scope file cards present in the manifest as pages | 571 | solid but narrow |

The file-gap question is **not answered**. Manifest documents are stored as `/file_url/NNN` or by PDF path, with names unrelated to the `/resource/` card slug, so name matching undercounts (the earlier "registrar 0 of 228" and "economics 555 of 698" were name-based and should not be relied on). A real measure needs each card resolved to its download path: a sample of about 100 cards would bound it. Page coverage is the usable result: 6,362 in-scope pages listed by sitemap-llm are not in the July manifest.
| O17 | Date handling: XML `lastmod` is the only fine-grained change date (99.0% timestamps; date-only on `www.gov` and `lpce`); no better date exists on the sampled pages (page `.md` copies show a written date on news, events and blog pages only, the publication or event date; file cards carry a date-only `Date` that equals the XML `lastmod` date on 14 of 19 cards; the other 5 are older because the XML moved on a bulk re-save). Store the exact value and refetch on any difference; for date-only hosts refetch when the stored date equals the last scrape date. The cadence tool's `parse_iso_date` floors to a date and must not be reused for planning | Full analysis in `SITEMAP_LLM_VS_XML.md` | build with the planner seam (O3) |
| O18 | Our extraction returned the site navigation menu as the page on 4 of 20 sampled pages (english Contact, two physics people pages, physics News and Events); the served `.md` was empty on two of them. Served `.md` keeps taxonomy and contact fields that our extraction drops | Navigation-only pages would be ingested as content | add a navigation-only guard; diagnose with `favor_recall`; larger sample |
| O19 | 16,434 in-scope pages in the QA crawl are not in the XML sitemap (listing, category and legacy pages); a sitemap-as-source design would lose them | Covered only by link-following and the monthly full run | decide whether the monthly run stays link-following |
| O20 | The `.md` copies and `/sitemap-llm` are documented HarvardSites platform features (HarvardSites guidance, read 2026-10-21), so they are a supported interface on the 52 hosts; `/resource/` entries can be articles, not only files, so earlier "file entry" counts may be too high | Affects the file-inventory idea (O16) and the 751 out-of-scope count | measure how many resources are articles |
| O21 | Date hunt on `haa` (sitemap-llm, one page, headers, 5 standard Drupal endpoints): the XML `<lastmod>` is the only modification date. `/rss.xml` gives authored timestamps for promoted nodes only; HTTP validators are cache times; sitemap-llm has none. Details in `SITEMAP_LLM_VS_XML.md` 4d | Confirms XML `lastmod` as the sole change signal; other hosts and custom feeds not checked | none unless a custom feed is found |
| O22 | trafilatura 2.0.0 returns the displayed publication date at day precision (13 of 13 where a date is shown) and a year-only guess `YYYY-01-01` where none is (20 of 38); `sitemap_search` returns links only (no `lastmod`) and fetches with its own downloader | Our front matter `date` is not a change date; `sitemap_search` cannot replace XML `lastmod` | `SITEMAP_LLM_VS_XML.md` 8c and 8d; do not use front matter `date` for planning |
| O23 | **NOT CHECKED:** whether any `/bibcite/export` file was ever ingested or returned by the bot is unverified: the database check was not run and the bot test was not reported | D1 rests on the code (ingest reads only four document types), Splunk (crawler fetches only) and a 6-file sample | run the two `web_content_files` queries and the three bot questions; reverse D1 if the exports were used |
