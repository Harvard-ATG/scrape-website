# Code tour guide

A CodeTour walk of PR #10 with side-by-side code and diagrams. Tour file: `.tours/scrape-update-mode.tour` (35 steps).

## Open it

1. Open the folder `/Users/kevingray/codebase/harvard-atg/scrape-website-pr10` in VS Code. It is a checkout of the PR branch at commit `a523244`; line numbers in the tour match that commit. Do not open `scrape-website`: it is on another branch.
2. Install the CodeTour extension (`vsls-contrib.codetour`).
3. Open the CodeTour panel in the Explorer sidebar, choose "Scrape update mode (PR #10)" and press Start.

The "Part B" step covers `apo-mcp-server` as a content-only step (that repo is outside this workspace); open it separately.

## Step to code to image to doc

| Steps | Code | Image (`overview/tour/`) | Point |
|---|---|---|---|
| Start | whole PR | none | overview |
| 1 | `scraper.py` 84 default excludes | `02-cleaner-full-scrape` | 1 cleaner full scrape |
| 2-4 | `scraper.py` 192, 321, 387 | `01-today-flow` (step 4) | 1 |
| 5 | `scraper.py` 228 sitemap discovery | `03-sitemap-kinds` | 2 sitemap map and dates |
| 6a-8c | URLStore, seams, crawl loop | `04-update-flow` (step 7b) | 3 where update plugs in |
| Part B | apo-mcp-server (content only) | `07-deletion` | deletion today |
| 9-11 | `RULES.md`, `rules.py` 40/47/63 | none | taxonomy and rules |
| 12 | `rules.py` 119 `evaluate` | `05-url-gates` | scope rules |
| 13 | `rules.py` 167 `plan_update` | `11-plan-order` | 3 |
| 14-16 | `rules.py` 184, 199, 215 | `06-moved-host`, `08-savings-one-host` | 3 and 4 moved sites |
| 17 | `validate_hosts.py` | `09-savings-all-hosts` | 3 totals |
| 18-20 | `rules.py` 248, 263, 276 | `07-deletion` | 5 deleting needs a fetch |
| 21-23 | `tests/` | `10-test-modes` | tests |
| 24 | none | none | what is not built |

Other docs: [RULES.md](../RULES.md) (taxonomy, R1 to R20), [OVERVIEW.md](OVERVIEW.md) (Mermaid diagrams for GitHub), [PRESENTATION_NOTES.md](PRESENTATION_NOTES.md) (storyline), `scrape-update-explainer.standalone.html` (open in a browser).

## Images

Each image exists as `.svg` and `.png` (1280 px wide). The tour uses the PNGs because they render reliably in the CodeTour webview; the SVGs are for docs and slides.

Regenerate after editing `build_tour_images.py` (needs Google Chrome for the PNGs):

    python3 aidocs/feature/scraper-update-mode/rules/overview/build_tour_images.py

## Keeping line numbers right

Steps point at fixed lines. If code moves, update the line numbers or switch a step to a `pattern`. CodeTour can also re-anchor steps when you use its "Record" mode in VS Code.

## Caveats

- Rendering of images inside the CodeTour panel was not checked in VS Code; the image paths and every file and line were validated by script.
- The reference code is not wired into the scraper; steps say so.
- The tour and these docs are untracked and unpushed.
