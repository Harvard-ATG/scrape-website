# Plan: Canonicalize http→https in `_normalize_url`

**Created**: 2026-07-01 | **Effort**: ~30 min | **Complexity**: Simple

## 1. Objective

**Goal**: Prevent the crawler from visiting the same page twice when links appear in both `http://` and `https://` forms.
**Why**: `_normalize_url` preserves the original scheme verbatim, so `http://example.com/foo` and `https://example.com/foo` are stored as two distinct keys in `URLStore` and both get fetched.
**Success**:
- A URL seen as both `http://` and `https://` is stored under one canonical key and fetched once.
- All existing normalization behavior (fragment removal, trailing slash, tracking params) is unchanged.

## 2. Approach

Single-function change in `scraper.py:_normalize_url` (~line 216). Add `scheme = "https"` canonicalization as the first step, before rebuilding the URL string. Because every dedup path — link extraction in workers, sitemap seeding, queue checks, CLI `--file`/`--retry` — calls `_normalize_url`, one change covers all of them.

`allow_redirects=True` is already set on fetches (line 679), so normalizing `http://` → `https://` is safe: the server redirects if needed.

**Trade-off considered**: Normalize only in `URLStore.contains`/`URLStore.add` (more conservative — preserve original scheme for fetching). Rejected: more complex, two places to maintain, harder to reason about; modern sites overwhelmingly prefer https.

## 3. Tasks

1. **Edit `_normalize_url`** (5 min) — add `scheme = "https" if parsed.scheme == "http" else parsed.scheme` before line 223. Update the docstring to document the canonicalization. | Deps: None | Risk: Low

2. **Manual smoke-test** (10 min) — call `_normalize_url("http://example.com/foo")` and `_normalize_url("https://example.com/foo")` in a Python REPL; confirm both return `https://example.com/foo`. | Deps: Task 1 | Risk: Low

## 4. Quality Strategy

No test suite exists. Verify by direct function call as noted above. Also confirm `_normalize_url("https://example.com/")` (root with trailing slash) and a URL with query params still normalize correctly — the change must not perturb existing logic.

## 5. Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Site only serves `http://` (no TLS) | L | `allow_redirects=True` handles it; scraper already fetches the final URL |
| Existing `state.db` with `http://` URLs causes re-crawl on resume | L | Only affects `--retry` on old run files; acceptable and expected behavior |
