# Tiered Fetch QA Testing Results

**Date:** 2026-07-17 (updated 2026-07-20)
**Environment:** QA (ECS Fargate, `atg-prod-default` cluster)
**Image:** `feature_scraper-tiered-fetch-playwright` (commit `983b70c`)
**Task Definition:** `atg-apo-mcp-qa-task-definition:11`

---

## Test Results

### Round 1: Scrape-only (2026-07-17)

Single-page probes via `scrape.py --hostname --fresh`:

| Site | Tier Used | Pages | Text | Files | Denied | Duration | Result |
|------|-----------|-------|------|-------|--------|----------|--------|
| celtic.fas.harvard.edu | Tier 2 (curl_cffi) | 1 | 1 | 0 | 0 | 6.50s | PASS |
| library.harvard.edu | Tier 1 (aiohttp) | 1 | 1 | 0 | 0 | 4.06s | PASS |
| mbb.harvard.edu | Tier 2 (curl_cffi) | 1 | 1 | 1 | 0 | 7.58s | PASS |

**Scheduler run (01:34 ET):** EventBridge → ECS → S3 log upload confirmed. Same results as manual runs.

### Round 2: Full pipeline — scrape_and_ingest (2026-07-20)

Full `scrape_and_ingest.py --hostnames` with 5 FAS sites (scrape → ingest → cleanup):

| Site | Expected Tier | Purpose |
|------|--------------|---------|
| celtic.fas.harvard.edu | Tier 2 | Re-test known working |
| edsecondary.fas.harvard.edu | Tier 2 | New site, path-scoped |
| medieval.fas.harvard.edu | Tier 2 | New site, path-scoped |
| ghhp.fas.harvard.edu | Tier 2 | New site, path-scoped |
| emr.fas.harvard.edu | Tier 2 | New site, path-scoped |

**Status:** Scheduled 14:41 ET 2026-07-20. Awaiting results.
**Log:** `s3://atg-apo-mcp-qa-scrape/diagnostics/scrape-and-ingest-5fas.log`

---

## Tier Coverage

| Tier | How Tested | Result |
|------|-----------|--------|
| Tier 1 (aiohttp) | library.harvard.edu — no bot protection | PASS: stays on fast path |
| Tier 2 (curl_cffi) | FAS sites — Akamai 403s Tier 1 from AWS | PASS: curl_cffi Chrome fingerprint bypasses |
| Tier 3 (Playwright) | Prior manual diagnostics (FAS 403 investigation) | PASS: headed browser beats Akamai from AWS |

**Tier 3 note:** Cannot be triggered organically — all FAS sites currently pass at Tier 2. Tier 3 is validated from prior diagnostic sessions where headed Playwright was confirmed to return 200 from ECS on sites that blocked all other methods. It's a safety net for future Akamai tightening.

---

## Remaining Test Plan

- [ ] **Round 2 results** — confirm scrape_and_ingest log shows scrape + ingest success for all 5 sites
- [ ] **Vector store verification** — query QA vector store to confirm ingested files are searchable
- [ ] **Idempotency** — re-run same 5 sites, verify ingest skips unchanged files (content-hash dedup)
- [ ] **Scale test** — registrar.fas.harvard.edu (~260 pages) to validate Tier 2 under sustained crawl
- [ ] **xvfb interaction** — if Round 2 fails with exit 3, re-run without xvfb-run wrapper

---

## Issues Found and Fixed

### Deployment Issues

| # | Issue | Root Cause | Fix |
|---|-------|-----------|-----|
| 1 | `ModuleNotFoundError: scrape_website` | Dockerfile `--no-install-package` flag | Removed flag (commit `983b70c`) |
| 2 | `xvfb-run` exit code 3 | xvfb wraps exit codes non-transparently | Use `sh -c` directly; xvfb only needed for Tier 3 |
| 3 | No `aws` CLI in container | `python:3.14-slim` base image | Use boto3 for S3 uploads |

### Code Review Fixes (scrape-website)

| # | Issue | Status |
|---|-------|--------|
| 1 | aiohttp retry exits without `response.read()` → connection pool leak | Fixed (`40bda67`) |
| 2 | curl_cffi returns None for 5xx, blocks retry | Fixed (`40bda67`) |
| 3 | Playwright timeout ignores `--timeout` setting | Kept 25s (design decision) |
| 4 | Filename collision counter removed → silent overwrites | Fixed (`6724604`) |
| 5 | `render_mode` conflation | Removed — replaced with `playwright_enabled` bool |
| 6 | curl_cffi session per request (TCP+TLS overhead) | Deferred — acceptable at current volume |

### Design Cleanup: render_mode removal (2026-07-20)

`render_mode` (`never`/`auto`/`always`) was removed from both repos. It conflated two unrelated concepts:

- **Ventz's upstream meaning:** "should I re-render a successfully fetched SPA shell through headless Chromium?" (post-fetch content quality)
- **Our implementation:** "should I escalate to Playwright when 403'd?" (fetch access)

In practice `auto` and `always` were identical in our code — both just meant "Tier 3 is allowed." Replaced with `playwright_enabled: bool = True` and `--no-playwright` CLI flag, which honestly describes what it controls.

---

## Run Commands

### Manual ECS scrape (one site)
```bash
aws ecs run-task \
  --cluster atg-prod-default \
  --task-definition atg-apo-mcp-qa-task-definition:11 \
  --launch-type FARGATE \
  --network-configuration '{"awsvpcConfiguration":{"subnets":["subnet-6440273d","subnet-275a1950"],"securityGroups":["sg-06755c4b95801a42d"],"assignPublicIp":"DISABLED"}}' \
  --overrides '{"containerOverrides":[{"name":"apo-mcp","command":["sh","-c",".venv/bin/python scrape.py --hostname <HOSTNAME> --fresh > /tmp/out.log 2>&1; .venv/bin/python -c \"import boto3; boto3.client(\\\"s3\\\", region_name=\\\"us-east-1\\\").upload_file(\\\"/tmp/out.log\\\", \\\"atg-apo-mcp-qa-scrape\\\", \\\"diagnostics/<HOSTNAME>-debug.log\\\")\""]}]}' \
  --profile tlt-prod
```

### Check S3 log
```bash
aws s3 cp s3://atg-apo-mcp-qa-scrape/diagnostics/<LOG_NAME> - --profile tlt-prod
```

### Full pipeline (scrape + ingest)
```bash
aws scheduler update-schedule --profile tlt-prod --region us-east-1 \
  --name atg-apo-mcp-qa-scrape-and-ingest \
  --schedule-expression "at(2026-07-20T14:41:00)" \
  --schedule-expression-timezone "America/New_York" \
  --flexible-time-window '{"Mode":"OFF"}' \
  --target '{...}'  # see STATUS_2026-07-17.md for full payload
```
