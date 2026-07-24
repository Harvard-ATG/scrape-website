# FAS 403 Investigation → Tiered Fetch Solution

## Problem

ECS scrape tasks hitting `*.fas.harvard.edu` get 403 Forbidden. Works in a browser locally.

## Investigation (2026-07-13 → 2026-07-16)

We started by testing theories independently — running diagnostic scripts from ECS, comparing behavior from local vs AWS, swapping HTTP libraries, and varying headers. Each test isolated one variable at a time.

Five theories tested and discarded:

| Theory | Killed By |
|--------|-----------|
| IP block (AWS NAT not in Harvard range) | Browser from non-Harvard residential IP worked fine |
| Missing browser headers | Adding them didn't help; residential also failed under scripts |
| Library-specific (aiohttp vs http.client) | Byte-identical requests; "aiohttp=200" was a one-time fluke |
| Per-IP cached denial | Residential IP also 403'd under script, but 200 under browser |
| **Two gates: headless detection + IP reputation** | Headed browser from AWS → 200 (confirmed) |

Akamai's edge caching and reputation scoring made results inconsistent between runs — a request that returned 200 one minute could 403 the next. Reliable conclusions required running tests side-by-side in the same minute, not comparing results across sessions.

## Root Cause

FAS sites sit behind **Akamai Bot Manager** with two independent gates:

1. **Automation/headless detection** (primary) — a headed browser passes; any scripted client (aiohttp, curl_cffi, headless Chromium) gets denied
2. **IP/ASN reputation** (secondary) — AWS IPs treated more harshly, but a headed browser still beats the block even from AWS

## From Investigation to Solution

After confirming headed Playwright was the fix, we looked at upstream `ventz/scrape-website` (the package our fork is based on) and found it had added a tiered fetch architecture in June 2026 — aiohttp → curl_cffi → Playwright. The upstream implementation was designed for SPA rendering (re-rendering pages through a browser after successful fetch), but the tier escalation pattern was exactly what we needed for 403 bypass.

We adapted the upstream approach for our use case:
- Kept the three-tier escalation structure
- Changed the trigger from "SPA shell detected" to "403 received"
- Used headed (not headless) Chromium — our diagnostics proved headless still gets blocked
- Added exponential backoff and Retry-After support to Tier 1
- Preserved our fork's custom additions (found_on tracking, manifest generation, path scoping)

## Solution: Three-Tier Fetch

1. **Tier 1 (aiohttp)** — fast baseline for non-blocked sites
2. **Tier 2 (curl_cffi)** — Chrome TLS fingerprint, triggered on 403. Beats current Akamai config alone
3. **Tier 3 (Playwright headed)** — real browser under xvfb, triggered when Tier 2 fails. Safety net for future Akamai tightening

## Tests Run

### From ECS (QA environment, 2026-07-17)

| Site | Tier 1 | Tier 2 | Tier 3 | Final |
|------|--------|--------|--------|-------|
| library.harvard.edu | 200 | — | — | Tier 1 |
| celtic.fas.harvard.edu | 403 | 200 | — | Tier 2 |
| mbb.harvard.edu | 403 | 200 | — | Tier 2 |

### From ECS — full pipeline (2026-07-20)

`scrape_and_ingest.py --hostnames` with 5 FAS sites (celtic, edsecondary, medieval, ghhp, emr). Validates scrape → ingest → cleanup end-to-end. Results pending.

### Local curl_cffi probe (2026-07-20)

Tested 31 FAS sites from local machine — all 200 at both Tier 1 and Tier 2. Confirms the 403 is IP/ASN-triggered (only happens from AWS), not universal.

### Prior manual diagnostics (2026-07-16)

Headed Playwright from AWS ECS confirmed to return 200 on FAS sites that blocked everything else. Validates Tier 3 works, though it can't be triggered organically since Tier 2 handles all current blocks.

## Artifacts

Investigation scripts preserved locally in `deprecated-planning-docs/fix-scraper-browser-headers/scripts/` — probes for headless, headed, aiohttp, concurrent timing. Useful if Akamai changes behavior and the issue resurfaces.
