# Scraper refinements: review and code walkthrough pack

What changed in the scraper and its run settings for the Oct 27–28 registration refresh, set up so a reviewer can
orient in 15, 25 or 40 minutes.

| Piece | Where | Status |
|---|---|---|
| Deck, 19 slides | https://claude.ai/artifact/QVZER3WsXLeHekUocHNrLN | private; share from its Share menu |
| Scraper tour, 37 steps | `.tours/scraper-refinements.tour` (ref `ffe35d6`) | local only |
| Orchestration tour, 11 steps | `apo-mcp-server/.tours/refresh-orchestration.tour` (ref `c833135`) | local only |
| Rehearsal, three lengths | `REHEARSAL.md` | local only |
| Decisions needed | `OPEN_QUESTIONS.md` | local only |
| Tests run | `TEST_RESULTS.md` | local only |
| Narration script | `script.yaml`, `descriptions.yaml` | local only |

## One numbering

Slide N, tour step N (or Na, Nb...) and the rehearsal row N are the same code. Steps 13 and 14 and the apo-mcp-server
parts of 4, 9 and 12 are in the orchestration tour.

## Code under review

- scrape-website `37bce63` → `ffe35d6`: 47 commits, `scraper.py` plus 10 test files. `ffe35d6` is the head of PR #10 (draft).
- apo-mcp-server `v1.0.1` → `v1.1.0-rc14` (`c833135`, branch `fix/scrape-and-ingest-ordering`): the pin, run flags, fast retirement.

## Narrated video, later

The deck follows the slides-to-video pipeline's rules: the speaker notes are the narration, and `script.yaml` is
generated from them (`make_script.py` here: `python3 make_script.py <deck folder>/project script.yaml`; regenerate after editing notes). Cues name targets, and
each target is visible slide text, never a pixel position. `pronunciations` respell for the voice only. To render, adapt
`readout/video/` from the ai-hackathon-2026 workspace: point `capture.mjs` at a local HTML export of the deck and map
each `targets` entry to `text()`. Full narration is about 16 minutes; Core frames alone about 10.

## The existing update-mode material

The weekly sitemap update (not built) has its own pack in `aidocs/feature/scraper-update-mode/review/` and tours
`scrape-update-mode.tour` and `scrape-traces.tour`.
