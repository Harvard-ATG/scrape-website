# Implementation: Canonicalize http→https in `_normalize_url`

**Mode**: default | **Date**: 2026-07-01 | **Status**: Complete

## 1. Changes (1 file, +3 -1 lines)
**Modified**: `scrape_website/scraper.py:216` — added `scheme = "https" if parsed.scheme == "http" else parsed.scheme` before URL reconstruction; updated docstring.

## 2. Quality (Tests pass | Docs updated)
**Tests**: 6 smoke-test cases covering http→https, https passthrough, trailing slash, root slash, query params, fragment stripping — all pass.

## 3. Decisions
**Normalize at `_normalize_url`, not at `URLStore`**: Single change point covers all dedup paths (link extraction in workers, sitemap seeding, queue checks, CLI `--retry`). Alternative of normalizing inside `URLStore` would require two places and diverge fetch URL from stored key.

## 4. Handoff
**Run**: `/epcc-workflow:epcc-commit`
**Blockers**: None
