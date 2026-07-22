# Tiered Fetch Implementation Summary

## What Changed

### scrape-website (Harvard-ATG fork, `feature/scraper-tiered-fetch-playwright`)

Added three-tier fetch escalation to `WebsiteScraper`:

**Tier 1 — aiohttp (existing, enhanced)**
- Exponential backoff with jitter (replaces linear)
- Honors `Retry-After` header on 429
- Retries only transient errors (429, 500-504)

**Tier 2 — curl_cffi (new)**
- Chrome 124 TLS/HTTP2 fingerprint
- Triggered on 403 from Tier 1
- Returns None if still blocked → escalates

**Tier 3 — Playwright headed (new)**
- Real Chromium under xvfb (not headless — headless leaks `HeadlessChrome` UA)
- Triggered when Tier 2 fails on 403
- Lazy browser init with async lock, clean shutdown
- Resource blocking (images/fonts) for speed

**Configuration:** `playwright_enabled: bool = True` (default on). CLI: `--no-playwright` to disable Tier 3. No per-site config needed — escalation is self-governing.

### apo-mcp-server (`feature/scraper-tiered-fetch-playwright`)

- Dockerfile: Chromium + xvfb installed, `DISPLAY=:99`
- `pyproject.toml`: pinned scrape-website to tiered fetch commit
- `scrape.py`: removed `render_mode` config plumbing (was dead code)
- `sites.toml`: removed `render_mode` comment

## Cross-Process Browser Slot Cap

When `scrape_and_ingest.py` runs 8 workers in parallel, each is a separate OS process. Without coordination, all 8 could launch a headed Chromium (~300 MB each), risking OOM on the 8 GB Fargate task.

**Solution:** POSIX advisory locks (`fcntl.flock`) on numbered files in `/tmp/scrape-browser-slots/`. Each process holds `LOCK_EX` on one file while its browser is alive. Default cap: 3 concurrent browsers (tunable via `SCRAPE_MAX_BROWSERS` env var).

| Property | Behavior |
|----------|----------|
| Slot denied | Worker skips Tier 3 gracefully (URLs logged as denied) |
| Process crash / OOM-kill | Kernel auto-releases the lock — no stale state |
| Debugging | `ls /tmp/scrape-browser-slots/` or `lsof browser-*.lock` |
| Cap exhausted | Worker sets `_browser_unavailable=True`, never retries |

## PR Review Fixes (2026-07-21)

Five corrections from the PR #6 code review:

**1. aiohttp connection released before Tier 2/3 escalation**

The `async with session.request(url)` block holds a TCP connection from the pool. When a 403 triggers escalation, the code now calls `await response.read()` before doing Tier 2/3 work. Without this, slow Playwright fetches (2-5s) hold idle connections hostage, starving other coroutines waiting for pool slots.

**2. Retry-After HTTP-date parsing**

`Retry-After` can legally be seconds (`120`) or an HTTP-date (`Thu, 01 Jan 2026 00:00:00 GMT`). Previously only handled seconds; date form silently fell back to backoff. Now uses `email.utils.parsedate_to_datetime` to compute delta.

**3. Playwright route handler signature**

Playwright's `page.route()` may call the handler with `(route)` or `(route, request)` depending on version. Single-arg definition would raise `TypeError` at runtime, silently breaking all Tier 3 fetches. Fixed by adding optional `request=None` parameter.

**4 & 5. Filename collision loop compounding**

Both binary and HTML collision loops re-read `stem` from the already-modified filename inside the loop, producing `name_1_2.ext` on multiple collisions. Fixed by hoisting `orig_stem`/`orig_ext` before the loop so collisions produce `name_1.ext`, `name_2.ext`, `name_3.ext`.

## Commits (scrape-website)

| Hash | Description |
|------|-------------|
| `39d6388` | Tier 1: exponential backoff + Retry-After |
| `176a86b` | Tier 2: curl_cffi Chrome fingerprint on 403 |
| `0600fa5` | Tier 3: Playwright headed + render_mode |
| `40bda67` | Code review fixes (connection leak, 5xx retry, CLI) |
| `85192a3` | Revert Playwright timeout to 25s |
| `6724604` | Restore filename collision counter |
| `37bce63` | Replace render_mode with playwright_enabled bool |
| `1876676` | Cross-process browser slot cap (flock) |
| `38c65c3` | PR review fixes (5 items) |

## Commits (apo-mcp-server)

| Hash | Description |
|------|-------------|
| `48ac682` | Dockerfile: xvfb + Chromium |
| `f6268da` | Wire render_mode from sites.toml |
| `a06328b` | Pin scrape-website to tiered fetch |
| `983b70c` | Fix: remove --no-install-package flag |
| `7a3c7ca` | Remove render_mode, pin playwright_enabled commit |

## Design Decisions

| Decision | Why |
|----------|-----|
| 3 tiers (not just browser) | Playwright is 15x slower; only pay the cost on actual blocks |
| Headed (not headless) | Headless gets 403'd — leaks automation signals |
| `playwright_enabled` bool (not render_mode) | render_mode conflated SPA rendering with 403 escalation; bool is honest |
| Required deps (not optional) | Simpler — no lazy import complexity |
| 25s Playwright timeout | Separate from aiohttp timeout; headed browser needs more time for page load |
| Container size +400MB | Acceptable tradeoff for Chromium + xvfb |
| flock cap (not bump resources) | 3 browsers in 8 GB is safe; bumping to 16 GB doubles cost and makes the scrape task 8x the cluster baseline |
| flock (not lockdir or semaphore) | Kernel auto-releases on crash; multiprocessing.Semaphore doesn't work across unrelated processes |
| Cap at 3 (not 1 shared browser) | Keeps implementation self-contained in scrape-website; shared browser requires changes in both repos |

## What render_mode Was (and Why It's Gone)

Ventz's upstream `render_mode` means: "after fetching a page successfully, should I re-render it through headless Chromium to hydrate SPA shells?" Our implementation repurposed it to mean: "should I escalate to Playwright when 403'd?" These are unrelated concerns. In our code `auto` and `always` were identical — both just gated Tier 3. Replaced with a clear boolean.

## Remaining Work

See `TESTING.md` for test plan and `STATUS_2026-07-17.md` for production readiness items.
