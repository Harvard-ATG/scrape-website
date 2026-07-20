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

## What render_mode Was (and Why It's Gone)

Ventz's upstream `render_mode` means: "after fetching a page successfully, should I re-render it through headless Chromium to hydrate SPA shells?" Our implementation repurposed it to mean: "should I escalate to Playwright when 403'd?" These are unrelated concerns. In our code `auto` and `always` were identical — both just gated Tier 3. Replaced with a clear boolean.

## Remaining Work

See `TESTING.md` for test plan and `STATUS_2026-07-17.md` for production readiness items.
