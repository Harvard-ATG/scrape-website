# Scraper refinements: review and code walkthrough pack

What changed in the scraper and its run settings for the October registration refresh: what the June crawl produced,
what changed, and what the refresh showed. Set up so a reviewer can orient in 5, 15 or 40 minutes.

| Piece | Where | Status |
|---|---|---|
| Narrated video, full (14 min 3 s, 55 MB) and short (5 min 18 s, 20 MB); files `scraper-changes-june-october-2026-11-10.mp4` and `-short-2026-11-10.mp4` | At the top of PR #10, https://github.com/Harvard-ATG/scrape-website/pull/10 | attached to the PR description |
| Captions and transcript for the full video | `scraper-changes-june-october.vtt`, `.srt` | this folder |
| Deck, 19 slides, "Scraper Changes: June vs October" (the source of both videos) | https://claude.ai/artifact/6cLjdW4u6YqWXNy16Huthv | private; share from its Share menu |
| Before-and-after page, "Less Junk, Faster, Still Complete" | https://claude.ai/artifact/Ju9LDiV5YuhYwYKioMuF7y | private; share from its Share menu |
| Resources page (every link here, the video build order, the message to the team) | https://claude.ai/artifact/LbH1XV64fTd1qyFbtaBzo5 | private; share from its Share menu |
| Code-walkthrough deck, 19 slides (one slide per tour step) | https://claude.ai/artifact/QVZER3WsXLeHekUocHNrLN | private; share from its Share menu |
| Sprint demo deck, slides 4 to 8: moved sites, the rules funnel, "Smarter scraper, smarter tool" (problem we hit / what fixed it, the three request tiers, 1 to 6 concurrency), refresh cadence, sitemap updates | https://claude.ai/artifact/CQ5Mx6BQ66X8nCBZEXCdRU#slide-4 | private; stakeholder-level explanation of the same fixes |
| Update-mode walkthrough (the sitemap-driven update design, not yet wired in) | https://claude.ai/artifact/BzBBvTUTpjikp2f1Lq9bcy | private; reference only |
| Scraper tour, 37 steps | `.tours/scraper-refinements.tour` (ref `4b7befc`) | on this branch |
| Orchestration tour, 11 steps | `apo-mcp-server/.tours/refresh-orchestration.tour` (ref `c833135`) | local only |
| Live tour, 15 minutes | Tuesday, November 10; follows one page end to end through the scraper in VS Code using the scraper tour | scheduled |
| Rehearsal, three lengths | `REHEARSAL.md` | this folder |
| Decisions needed | `OPEN_QUESTIONS.md` | this folder |
| Tests run | `TEST_RESULTS.md` | this folder |
| Narration script | `script.yaml`, `descriptions.yaml`, `make_script.py` | this folder |

## One numbering

Slide N in the code-walkthrough deck, tour step N (or Na, Nb...) and the rehearsal row N are the same code. Steps 13
and 14 and the apo-mcp-server parts of 4, 9 and 12 are in the orchestration tour.

## Code under review

- scrape-website `37bce63` → `4b7befc`: 48 commits, `scraper.py` plus 10 test files. `4b7befc` is the head of PR #10,
  which contains PRs #4, #7, #8 and the 429 fix; merging it closes the others.
- apo-mcp-server `v1.0.1` → `v1.1.0-rc14` (`c833135`, branch `fix/scrape-and-ingest-ordering`): the pin, run flags, fast retirement.
- Review the 10 files under `scrape_website/` and `tests/`. Everything under `aidocs/` is reference material and tooling
  with its own tests; confirm the tests run rather than reading it.

## Narrated video

The June-vs-October deck's speaker notes are the narration; `script.yaml` is generated from them
(`python3 make_script.py <deck folder>/project script.yaml`; regenerate after editing notes). Cues name visible slide
text, never pixel positions. Rendered with Remotion and Amazon Polly (voice Ruth); the resources page has the build
order. The short cut uses eight of the 19 slides with the same numbers.

## The existing update-mode material

The weekly sitemap update (not built) has its own pack in `aidocs/feature/scraper-update-mode/review/` and tours
`scrape-update-mode.tour` and `scrape-traces.tour`.
