# Open questions

Collected 2026-10-16 from the review pack. Owner column is a suggestion, not an assignment.

| # | Question | Why it matters | Needs |
| --- | --- | --- | --- |
| 1 | The manifest is the hand-off: a retired URL is absent from it. Does ingest iterate manifest entries (preferred) or does the scraper delete the file? | `ingest.py` reads files on disk, so manifest absence alone retires nothing | design decision (O8) |
| 2 | Departure cap as a Sentry alert with review links. Empty-set and non-removal-status guards are done locally (F9, F10); the cap is not | Today a partial crawl can retire pages | build (O9) |
| 3 | Monthly full run is 17 to 27 hours. One task, sharded by host group, or longer timeouts? | Overlaps weekly and daily runs; the ingest lock is same-machine only | ops decision |
| 4 | Who prevents overlap between daily, weekly and monthly tasks? | Separate Fargate tasks share no lock | ops decision |
| 5 | Where does `_should_fetch` call the planner, and where do per-URL `lastmod` and `fetched` live in `state.db`? | R13 reads a `state` dict today | scraper change |
| 6 | Backfill: run once by hand per host (decided: no schedule, no weekly cap); the monthly full run covers the rest | 18,205 never-captured pages | confirmed 2026-10-18 |
| 7 | Retire never-captured or out-of-scope pages (mcb: 640 pages pending prune)? | Pending prune changes what is in the store | decision 26 |
| 8 | R6 and R7 (extra excludes, event pages): adopt in the scraper? | Off in code; 15,046 event pages in scope | decision |
| 9 | Hosts with no or unreadable sitemap (courses.my, ces, daviscenter, careerservices, astronomy, scienceeducation, statistics, math) | Update mode cannot see changes there | fall back to seeds plus monthly full |
| 10 | Is the `sites.toml` move for the four Harvard-reorganization hosts committed and deployed? | Memory notes it as uncommitted on 2026-10-15 | apo-mcp-server commit |
| 11 | Push `a523244` to PR #10 and refresh its description? | Origin has `a70def7`; the tour line numbers match `a523244` | go-ahead |
| 12 | Which channel should this pack go to? | The request said "that channel"; no channel was named | name it |
| 13 | CodeTour images inside the VS Code panel | Not opened in VS Code; checked by script only | someone with VS Code |
| 14 | Review findings still open: see [REVIEW_FINDINGS.md](REVIEW_FINDINGS.md) O1 to O15 | Failed pages and the manifest (O1, O2) are the main data-loss risks left | decisions |
