# Rehearsal guide: PR #10 team code review

About 50 minutes. One presenter drives the CodeTour; one person keeps the open-questions list. Everything shown is in the
PR #10 checkout `scrape-website-pr10` at `a523244` (the tour's line numbers match that commit). Step numbers below are the numbers in the tour step titles, as in [TOUR_GUIDE.md](../rules/overview/TOUR_GUIDE.md).

## Before the session (10 minutes)

1. Open `/Users/kevingray/codebase/harvard-atg/scrape-website-pr10` in VS Code, install `vsls-contrib.codetour`.
2. Run `git rev-parse --short HEAD`; it must print `a523244`.
3. Run the tests once so nobody waits: see [TEST_RESULTS.md](TEST_RESULTS.md). Expect 257 passed, 4 skipped with manifests.
4. Open the hub page `review/index.html` in a browser for the diagrams and links.
5. Open [DELETION_SIDE_BY_SIDE.md](DELETION_SIDE_BY_SIDE.md) in a second pane.

## Run of show

| Min | Segment | Show | Doc to point at | Say | Ask the room |
| --- | --- | --- | --- | --- | --- |
| 0 to 3 | Frame | Tour step 0 | [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#what-problem-this-solves) | "How should scraping, and keeping pages current, get better? Five points." | Who has run a full scrape and seen it drift? |
| 3 to 10 | 1. Cleaner full scrape | Tour steps 1 to 4, image `02-cleaner-full-scrape` | [PRESENTATION_NOTES.md](../rules/overview/PRESENTATION_NOTES.md) section 1 | "The two PR #4 changes remove or merge 73,101 of 143,477 saved pages." | Is `/search?` and `.ics` exclusion safe for every site? |
| 10 to 17 | 2. Sitemaps are a map | Tour step 5, image `03-sitemap-kinds` | [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#sitemap-kinds), [RULES.md](../rules/RULES.md) section 1 | "Only the XML sitemap has dates. 52 hosts also have a markdown sitemap with none." | Do we trust `lastmod` on every platform? (emr, engagedscholarship, complit are partial) |
| 17 to 27 | 3. Fetch only what changed | Tour steps 7b, 12 to 14, 16, 17; image `05-url-gates`, `11-plan-order` | [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#decision-tree-what-happens-to-one-url) | "Walk one URL down the tree. This is `plan_update`; it is not wired in." | Where should `_should_fetch` call the planner? |
| 27 to 32 | 4. Moved hosts | Tour step 15, image `06-moved-host` | [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#decision-tree-what-happens-to-a-host) | "Four hosts moved in the reorganization. The sitemap lists another host, so we block, not delete." | Who owns keeping `sites.toml` aligned with moves? |
| 32 to 40 | 5. Deletion | Tour Part B, steps 18 to 20; image `07-deletion`; open DELETION_SIDE_BY_SIDE | [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#deleting-pages), [DELETION_SIDE_BY_SIDE.md](DELETION_SIDE_BY_SIDE.md) | "Today absence retires a page, with no cap and no check. Proposed: cap at 30%, confirm by fetch." | Where does the retire list cross from scrape-website to apo-mcp-server? |
| 40 to 45 | Tests and numbers | Tour steps 21 to 23; image `10-test-modes`, `08`, `09` | [TEST_RESULTS.md](TEST_RESULTS.md) | "One test per rule, real URLs, per-host exceptions asserted." | Which exception would you not accept? |
| 45 to 50 | Schedules and what is not built | Tour step 24; hub page schedules tab | [SCHEDULES.md](SCHEDULES.md), [UPDATE_MODE.md](../../../../docs/UPDATE_MODE.md#what-is-not-built) | "Daily update, weekly backfill and retire, monthly full. None can be enabled until the flag exists." | Is a 17 to 27 hour monthly run acceptable as one task? |

## Fallbacks

- CodeTour will not render images: open the PNGs in `rules/overview/tour/` or the hub page.
- Line numbers drift: re-check out `a523244`, or use the permalinks in the hub page (`a70def7`).
- Someone asks "does it run?": no. Say it, point at [What is not built](../../../../docs/UPDATE_MODE.md#what-is-not-built).

## Do not claim

- That update mode runs, or that `rules.py` is called by the scraper.
- That any review of the PR has happened.
- Numbers about pages the sitemaps do not list.

## After the session

Copy the answers into [OPEN_QUESTIONS.md](OPEN_QUESTIONS.md) and the decisions into the Scraping Decisions Log.
