# Rehearsal: scraper refinements code walkthrough

Deck: https://claude.ai/artifact/QVZER3WsXLeHekUocHNrLN (private until shared from its Share menu)
Tours: `.tours/scraper-refinements.tour` (this checkout, ref `ffe35d6`) and
`apo-mcp-server/.tours/refresh-orchestration.tour` (ref `c833135`, tag v1.1.0-rc14). Both are local and uncommitted.

Step N in the tours is slide N. Slides carry a tag: **Core** (red), **25 min** (blue), **40 min** (outlined).

## Setup (5 minutes before)

- [ ] `git -C ~/codebase/harvard-atg/scrape-website-pr10 rev-parse --short HEAD` prints `ffe35d6`
- [ ] `uv run --extra dev pytest -q tests` prints `80 passed`
- [ ] VS Code open on scrape-website-pr10, CodeTour extension installed, "Scraper refinements" listed
- [ ] apo-mcp-server open in a second window; "Refresh orchestration" listed (the tour reads `c833135` from git, so the branch checked out does not matter)
- [ ] Deck open in Present mode; check the link opens for the audience (Share menu) if they will follow along

## Timing by length

Narration per slide is the speaker note read at 150 words a minute. Discussion is the time left for the "Ask the room" box.

| # | Slide | Track | Narration | 15 min | 25 min | 40 min | Tour steps | Ask |
|---|---|---|---|---|---|---|---|---|
| 1 | Cover | Core | 0:34 | 0:30 | 0:30 | 0:30 | 1 | |
| 2 | Three tools, one numbering | Core | 0:39 | 0:30 | 0:40 | 0:40 | 2 | |
| 3 | Where each change lives | Core | 0:39 | 0:45 | 0:45 | 1:20 | 3 | |
| 4 | Fourteen release candidates | Core | 0:42 | 1:00 | 1:30 | 2:00 | 4, orch. 4 | Q1 |
| 5 | Three tiers | Core | 0:53 | 1:00 | 1:15 | 2:30 | 5a, 5b | browser slots full |
| 6 | Sticky Tier 2 | 25 min | 0:50 | | 1:00 | 1:30 | 6a, 6b | re-probe Tier 1? |
| 7 | 429 means slow down | Core | 0:59 | 2:00 | 3:00 | 4:00 | 7a–7c | Q2, Q3 |
| 8 | Default excludes | Core | 0:50 | 1:00 | 1:15 | 2:00 | 8a, 8b | who reads "excluded" |
| 9 | R7 events | 25 min | 0:54 | | 1:15 | 2:00 | 9a, 9b, orch. 9 | Q5 |
| 10 | Sitemap seeding | 25 min | 0:57 | | 1:15 | 2:00 | 10a–10c | Q6 |
| 11 | Not pages | Core | 0:56 | 1:15 | 1:30 | 2:30 | 11a, 11b | sister-site redirects |
| 12 | Concurrency flag | Core | 0:52 | 1:45 | 3:00 | 3:30 | 12a–12d, orch. 12a–12d | Q4 |
| 13 | Scrape sets | Core | 1:02 | 1:30 | 1:30 | 2:30 | orch. 13a, 13b | Q8 |
| 14 | One-call retirement | 25 min | 1:00 | | 1:15 | 2:30 | orch. 14a–14c | Q7 |
| 15 | One page end to end | 40 min | 1:04 | | | 3:30 | 15a–15g | |
| 16 | Tests | 40 min | 0:54 | | | 1:30 | 16 | |
| 17 | Decisions we need | Core | 0:57 | 3:15 | 3:50 | 4:00 | 17 | all |
| 18 | Not built yet | 25 min | 0:52 | | 1:00 | 1:00 | 18 | |
| 19 | Read it yourself | Core | 0:35 | 0:30 | 0:30 | 0:30 | 19 | |
| | **Total** | | 16:13 | **15:00** | **25:00** | **40:00** | | |

- **15 min:** deck only. Read the Ask boxes aloud on 7 and 12, and save the rest for slide 17.
- **25 min:** open the tour on slide 7 (step 7b, `fetch_with_retry`) and slide 12 (12b and orchestration 12a). Close the editor after each one.
- **40 min:** deck on one screen, editor on the other; play every step. Slide 15 is the tour's trace, 15a to 15g.

## One sentence per slide, if time runs short

| # | Say |
|---|---|
| 4 | Every scraper pin change answers something prod showed us; read the commits oldest first. |
| 5 | Three tiers, same return shape, used only when blocked. |
| 7 | A 429 from every tier means the request rate, so the host pauses 15, 30 and 60 seconds before giving up. |
| 8 | Each default exclude carries its measurement in a comment. |
| 11 | Off-host redirects, media and error pages are not saved or expanded. |
| 12 | Concurrency is a flag now, not a rebuild. |
| 13 | Hosts run in disjoint sets by platform; upload workers stay near 60. |
| 17 | Eight decisions; Q1, the draft PR that prod pins, comes first. |

## Fallbacks

- **CodeTour won't open a step** (ref not found): run `git fetch origin` in that repo; the tours read `ffe35d6` and `c833135` from git.
- **No editor:** every slide footer links the exact lines on GitHub at the pinned commit.
- **Deck link fails for someone:** it is private until shared. Present from your screen.
- **Asked for live numbers:** the throughput and denial figures come from the Oct 27–28 prod runs (apo-mcp-server `aidocs/fix/scrape-and-ingest-ordering/STATUS.md`, `RUN_ORDER.md`). Nothing was re-measured for this review.

## Do not claim

- That the weekly sitemap update runs. `plan_update` is reference code; nothing calls it.
- That schedules exist. `SCHEDULES.md` is a sketch; nothing is applied.
- That PR #10 is reviewed or merged. It is a draft; prod pins its head.
- That Terraform records rc14. The prod and QA task definitions were registered by hand (prod revision 16, QA revision 20).
- That tests cover throughput or rate limits on live sites. They use fake fetches.
- That the "about 6 hours" full-refresh figure was measured. It is a projection from the Oct 27–28 rates.
