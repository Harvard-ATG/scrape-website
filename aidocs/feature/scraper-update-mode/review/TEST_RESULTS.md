# Test results

Run on 2026-10-16. PR #10 head is `a70def7` on origin; the local worktree is `a523244` (one unpushed fix commit).

| Suite | Where | Result | Notes |
| --- | --- | --- | --- |
| Scraper tests | `scrape-website-pr10`, `tests/` | **47 passed** | crawl generation, sitemap discovery, wiring, browser slots |
| Cadence tests | `aidocs/.../evidence/cadence-analysis/tests/` | **31 passed** | sitemap parsing, date parsing, diff, recommend |
| Rules tests, full inputs | `scrape-website` checkout, `aidocs/.../rules/tests/` | **257 passed, 4 skipped** | real `sites.toml` and cached QA manifests; the 4 skips are the moved hosts, which are not in `sites.toml` (`test_all_hosts.py:104`) |
| Rules tests, no manifests | `scrape-website-pr10` worktree | **183 passed, 2 skipped** | the cached manifests are not in this worktree; skips are an empty parameter set and "no cached QA manifests" |
| Rules tests, neither input | documented in the PR notes | 76 passed, 26 skipped | not re-run on 2026-10-16 |

Command: `../../../../.venv/bin/python -m pytest tests -q -rs` from `aidocs/feature/scraper-update-mode/rules`.

## What the tests cover

| Rules | Test file |
| --- | --- |
| R1, R14 (normalize, UTC) and URL kinds | `tests/test_rules_unit.py` |
| R2 to R9 scope | `tests/test_rules_unit.py` |
| R10 to R13b, R15, R20 plan | `tests/test_plan.py` |
| Per-host invariants and documented exceptions | `tests/test_all_hosts.py` |
| Handbook include-pattern bug (fixed in `sites.toml`) | `tests/test_handbook_regression.py` |
| `sites.toml` shape | `tests/test_sites_toml.py` |

## Cross-host validation (`validate_hosts.py`, report/summary.json)

| Measure | Value |
| --- | --- |
| Hosts in `sites.toml` | 87 entries (83 hosts plus 4 old moved names) |
| Hosts planned | 71 |
| In-scope sitemap pages | 56,992 |
| First update run | 4,339 pages (4,259 without resource pages) |
| Never captured, kept for backfill | 18,205 |
| Changed in 7 days / 30 days | 341 / 1,324 |
| Departure candidates | 821 |
| Removals held by the 30% cap | ofa.fas (616 of 1,085) |
| Blocked, host moved | oie.fas, summerfunding, incomingstudents, oaisc.fas |

## Not tested

- No test calls `rules.py` from the scraper; the seam is not wired.
- R16 confirmation fetches are tested as a pure function (`classify_confirmation`), not against live servers.
- R17 to R19 are policy, not code.
- The code tour has not been opened in VS Code; steps were validated by script only.
- Times (1.1 to 1.7 s per page) come from local scrape logs, not AWS.
