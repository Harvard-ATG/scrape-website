# Open questions: scraper refinements

Code under review: scrape-website `4b7befc` (PR #10 head), apo-mcp-server `c833135` (v1.1.0-rc14).
Each item is shown on deck slide 17 and in the tour step named. Owner and decision are blank until the review.

| # | Question | Why it matters | Where | Needed | Owner | Decision |
|---|---|---|---|---|---|---|
| Q1 | Merge PR #10, or move the apo-mcp-server pin to a commit on `main`? | Prod and QA pin `ffe35d6`, the head of a draft PR whose base is `feature/python-package`. The code in prod is not on any reviewed branch. | slide 4; apo `pyproject.toml:27` | review of PR #10, merge path to `main` | | |
| Q2 | Share the 429 pause across hosts on one platform? | `_rate_limited_until` is per `WebsiteScraper`, so per host. The College WordPress platform limits per client address, so hosts in one task do not share the pause. The run settings (concurrency 1, 3 sites in flight) cover it today. | slide 7; `scraper.py:1281` | decide code versus run settings | | |
| Q3 | Keep the old row when a page is still rate-limited after the last backoff? | After 15 + 30 + 60 s the 429 is counted denied; a `--fresh` ingest then retires the row because the page is not in the manifest. | slide 7; `scraper.py:1288`, apo `ingest.py:122` | decide; would need ingest to know about denied URLs | | |
| Q4 | Lower the scraper CLI's default concurrency? | `scrape-website <url>` defaults to 100 requests in flight with a 0.1 s delay (`CONFIG`). apo-mcp-server always passes its own values (1 and 0.75 s). | slide 12; `scraper.py:41`, `:1796` | decide a default | | |
| Q5 | Who advances `EVENT_KEEP_SINCE` and re-checks the event keep hosts each summer? | The date (2026-06-01) and four keep hosts were checked against sitemap lastmod on Oct 27. Without a review, next year's events are kept only by the stale date and old calendars come back. | slide 9; apo `scrape.py:34`, `scraper.py:107` | owner and a calendar reminder | | |
| Q6 | Return a "list was cut off" flag from sitemap discovery? | TODO at `scraper.py:393`. The weekly update planner (R11, R15) cannot tell a truncated sitemap from removed pages. | slide 10 | needed before the weekly update is wired | | |
| Q7 | One builder for vector-store attributes? | The attribute set is written in `_upload_to_vector_store` and again in `_retire_file_fast`. An update replaces the whole set, so an attribute added only to the upload is lost on retirement. | slide 14; apo `ingest.py:87` | small refactor plus a test | | |
| Q8 | Scrape sets and task definitions in Terraform or a script? | The sets live in `RUN_ORDER.md`; platform groups come from a header probe that goes stale; prod and QA task definitions were registered by hand. | slide 13 | decide; Terraform change in atg-ops-appserver | | |

Smaller points raised on slides, not on slide 17:

- Tier 3 is skipped and the page counted denied when all browser slots are taken (slide 5, `scraper.py:186`).
- Sticky Tier 2 is never cleared within a crawl (slide 6, `scraper.py:1331`).
- Only sitemap-seeded event pages get the date check; a current event reached by a link stays excluded (slide 9, `scraper.py:1635`).
- Off-host redirects to a sister site we do not crawl are retired on `--fresh` (slide 11).
- The fresh retirement loop is serial, about 90 rows a minute (slide 14).
