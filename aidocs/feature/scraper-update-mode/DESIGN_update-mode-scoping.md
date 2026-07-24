# Design: Update Mode Scoping & Open Questions

**Date**: 2026-07-23 | **Scope**: Scoping draft for human decision | **Status**: Draft — NOT implementation-ready
**Repo/branch**: `Harvard-ATG/scrape-website` `feat/scraper-update-mode`
**Foundation**: [DESIGN_crawl-generation-foundation.md](../scraper-scope-limits/DESIGN_crawl-generation-foundation.md)
**Discovery**: [EPCC_EXPLORE.md](../scraper-scope-limits/EPCC_EXPLORE.md) (§4, §4b, §4c)

## 1. Goal

Enable re-scraping that detects and fetches CHANGED pages (not just newly-discovered ones) via a `--update` flag, without wiping `state.db` or breaking the manifest-atomicity invariant.

## 2. What Exists vs. What `--update` Must Add

### Foundation already provides (merged into `feat/scraper-scope-limits`)

- **Per-URL state columns**: `crawl_gen INTEGER`, `last_fetched_at TEXT` on the `visited` table, populated on successful save.
- **Generation derivation**: `URLStore.max_crawl_gen()` computes `COALESCE(MAX(crawl_gen), 0)` baseline; `_decide_crawl_gen(baseline, fresh, resuming)` yields `current_gen`.
- **The re-fetch seam**: `_should_fetch(url, seen_this_run, url_store)` — today returns `url not in seen_this_run and not url_store.contains(url)` (skip anything already visited). This is the single decision point where update mode will flip behavior.
- **In-run loop prevention**: `seen_this_run: set[str]` separates within-pass dedup from cross-run skip.
- **Manifest atomicity**: `_should_write_manifest(crawl_complete, capped, has_entries)` guards regeneration; partial/crashed runs leave the last complete manifest untouched.
- **Three pathways with NO dedicated flag**: `--fresh` (clear + gen 1), resume (non-empty queue + same gen), emergent update pass (empty queue → gen advances, discovers NEW pages but never re-fetches changed ones).

### What `--update` must add

1. **Sitemap `<lastmod>` storage** — per-URL lastmod values must be persisted (new column or separate table) and compared to decide "changed."
2. **`<lastmod>` comparison logic** — fetch sitemap, compare stored vs. current lastmod per URL, mark changed URLs for re-fetch.
3. **`_should_fetch` extension** — flip the cross-run skip rule from `not contains(url)` to `crawl_gen < current_gen OR lastmod changed` (re-fetch old-gen OR changed pages).
4. **Removal reconciliation** (optional/risky) — after a known-complete crawl, rows with `crawl_gen < current` are removal candidates; decide how/whether to retire them WITHOUT triggering the §4a cascade on partial crawls.
5. **No-sitemap fallback** — decide behavior when a site has no sitemap or lastmod data (degrade to discover-new-only? error? force `--fresh`?). The corpus audit (§8) found only 5 of 83 hosts truly lack a sitemap, all small — so this fallback is a low-risk edge, not the common path.
6. **Interaction with `--max-pages`** — a capped update run is inherently partial/non-authoritative; must NOT trigger removal reconciliation.
7. **Sitemap-discovery robustness (prerequisite)** — `_should_fetch`'s lastmod gate is only as good as sitemap discovery. Today `_fetch_sitemap_urls` tries only `/sitemap.xml` + `/sitemap_index.xml` and ignores `robots.txt`, so it silently misses 6 WordPress hosts whose sitemap lives only at `/wp-sitemap.xml` (§8). Fix = parse the `robots.txt` `Sitemap:` directive and add `/wp-sitemap.xml` as a fallback. This is a shared prerequisite for both sitemap-as-source and `--update`.
8. **File preservation (design rule + safety net)** — under any sitemap-driven crawl, files (PDF/docx) must still be reached via link-following from crawled pages, and `--update` needs a carry-forward safety net so a valuable orphaned file can't silently vanish. See §5 "File preservation" for the locked rule and the empirical basis in §8.

## 3. Open Design Questions (Human Must Decide)

### Q1: Where is `<lastmod>` stored?

**Option A: New column on `visited` table** (`lastmod TEXT`)
- **Pros**: co-located with `crawl_gen`/`last_fetched_at`; single upsert per save; schema migration matches existing pattern.
- **Cons**: NULL for non-sitemap URLs (files, discovered-only pages); `visited` table grows wider.

**Option B: Separate `sitemap_metadata` table** (`url TEXT PRIMARY KEY, lastmod TEXT, ...`)
- **Pros**: cleaner separation (sitemap data vs. crawl state); NULL-free (only sitemap URLs present).
- **Cons**: two writes per save (upsert `visited` + upsert `sitemap_metadata`); join overhead on `_should_fetch` check.

**Recommendation**: **Option A** (column on `visited`). Simpler, matches the established retrofit pattern (`ALTER TABLE ... ADD COLUMN`), and the NULL-for-non-sitemap case is harmless (comparison skips NULL rows). Co-location keeps all per-URL state in one place.

---

### Q2: How is "changed" decided, and what if `<lastmod>` is absent/unreliable?

**Scenario 1: Sitemap present, URL has `<lastmod>`**
- Compare stored `lastmod` (from prior run) to current sitemap `<lastmod>`.
- If different → mark changed, re-fetch.
- If same → skip (unless `crawl_gen < current` for other reasons).

**Scenario 2: Sitemap present, URL lacks `<lastmod>`** (valid XML, but some `<url>` entries omit it)
- **Option A**: treat as "always changed" → re-fetch every pass.
- **Option B**: treat as unchanged → skip (assume no edit).
- **Option C**: fall back to HTTP conditional request (rejected in discovery as unreliable due to Akamai cache-regen noise).

**Scenario 3: No sitemap at all** — rare in practice: the corpus audit (§8) found only 5 of 83 hosts lack a sitemap (careerservices.fas, ces.fas, daviscenter.fas, www.hio, + a PDF entry), all small. So this is an edge, not the common path.
- **Option A**: error out / require `--fresh`.
- **Option B**: degrade to discover-new-only (same as today's emergent update pass).
- **Option C**: allow but log a warning; skip all re-fetch logic.

**Recommendation**: **Scenario 1** = strict comparison (only `!=` triggers re-fetch). **Scenario 2** = **Option A** (always re-fetch if lastmod missing — conservative, ensures no stale page). **Scenario 3** = **Option B** (degrade to discover-new-only + warn) — pragmatic, doesn't block the feature on 100% sitemap coverage.

---

### Q3: Does `--update` reconcile removals, and if so, how?

**Context**: After a complete update pass, rows with `crawl_gen < current` are removal candidates (not seen this run). Retiring them = the §4a cascade risk (partial crawl triggers mass retirement).

**Option A: No removal reconciliation** (safest)
- Old-gen rows stay forever; removed pages keep stale `state.db` entries.
- Downstream ingest/`deprecate_removed_urls` never sees a shrunken manifest (manifest regeneration already guarded by `crawl_complete and not capped`).
- **Tradeoff**: `state.db` grows unbounded with removed pages; manifest includes stale URLs until manual cleanup.

**Option B: Opt-in removal reconciliation** (separate flag, e.g. `--reconcile-removals`)
- Only runs when `crawl_complete and not capped and --reconcile-removals`.
- Marks old-gen rows as removed (new `source_status` column or delete from `visited`).
- Manifest reflects removals → downstream `deprecate_removed_urls` retires them.
- **Tradeoff**: adds a second flag; user must understand the complete-crawl requirement; mis-use = mass retirement.

**Option C: Automatic removal reconciliation on complete passes** (riskiest)
- `--update` + `crawl_complete and not capped` automatically retires old-gen rows.
- **Tradeoff**: no user control; any missed URL (excluded pattern, timeout, transient 403) = false removal.

**Recommendation**: **Option A** for initial implementation (no removal reconciliation). Defer removal to a future stream or manual cleanup script. The manifest-atomicity guard already prevents the §4a cascade; leaving stale rows is safer than risking false positives. If removal is needed later, add **Option B** (explicit opt-in flag) with heavy documentation.

---

### Q4: What does `_should_fetch` return on `--update`?

**Foundation behavior** (no flag): `url not in seen_this_run and not url_store.contains(url)`
- Skips anything already visited in any prior pass.

**`--update` extension**: must re-fetch changed pages. Two sub-decisions:

**Q4a: Does `--update` re-fetch ALL old-gen rows, or only those with changed `<lastmod>`?**
- **Option A**: `crawl_gen < current` → always re-fetch (generation-based, ignores lastmod).
- **Option B**: `(crawl_gen < current) AND (lastmod changed OR lastmod is NULL)` → only re-fetch if changed.

**Recommendation**: **Option B** (lastmod-gated). If `crawl_gen < current` but `lastmod == stored`, the page is unchanged → skip. This is the efficiency win of update mode (avoid fetching unchanged pages). Option A would re-fetch everything on every pass (same cost as `--fresh`).

**Q4b: New URLs (not in `visited`) — always fetch?**
- Yes, regardless of `--update`. They have no `crawl_gen` → treated as `crawl_gen = 0 < current` → fetch.

**Resulting `_should_fetch` logic on `--update`**:
```python
if url in seen_this_run:
    return False
if not url_store.contains(url):
    return True  # new URL, always fetch
# URL is in state.db; check if it needs re-fetch
row = url_store.get_metadata(url)  # hypothetical; needs implementation
if row.crawl_gen < current_gen:
    # Old generation; check if changed
    if row.lastmod is None or sitemap_lastmod_for(url) != row.lastmod:
        return True  # changed or unknown
return False  # unchanged, skip
```

---

### Q5: How does `--update` interact with `--max-pages`?

**Constraint**: A capped run is non-authoritative. The `_should_write_manifest` guard already prevents manifest regeneration (`crawl_complete and not capped`). But `--update` introduces a new question: **which N pages does a capped update pass fetch?**

**BFS order** (today's `--max-pages` behavior, if implemented):
- First N pages in breadth-first traversal order.
- On `--update` + `--max-pages N`, would this be "first N new/changed pages discovered" or "first N pages, then stop even if more changed pages exist in the queue"?

**Recommendation**: `--update` + `--max-pages` should fetch **up to N new OR changed pages**, stopping once N are processed. The capped run leaves untouched rows at old generations (safe, no cascade). Removal reconciliation MUST be skipped (already guarded by `not capped`). This makes capped update passes safe for sampling/testing without risking false removals.

---

### Q6: When is the sitemap fetched and parsed?

**Option A: At crawl-loop startup** (seed phase, like `use_sitemap` today)
- Fetch sitemap, build `{url: lastmod}` map in memory, pass to `_should_fetch`.
- **Pros**: single fetch, fast lookup during crawl loop.
- **Cons**: memory overhead (5k-30k URLs × 25-byte ISO timestamp = ~125KB-750KB, negligible); startup delay.

**Option B: On-demand per URL** (query sitemap data each `_should_fetch` call)
- **Cons**: massive overhead (N fetches or N database queries); sitemap is static per pass.

**Recommendation**: **Option A** (fetch at startup, build in-memory `lastmod_map: dict[str, str]`). Parse the sitemap in the seed phase (already exists for `use_sitemap`), extract both `<loc>` and `<lastmod>`, store in a dict, pass to the crawl loop. `_should_fetch` checks `lastmod_map.get(url)` against stored `row.lastmod`.

---

## 4. Proposed Approach (Leading Option per Hard Part)

### A. Sitemap `<lastmod>` storage
- **Add `lastmod TEXT` column to `visited` table** via existing `ALTER TABLE` migration loop (`URLStore.__init__`).
- **Populate on save**: `upsert_metadata(..., lastmod=sitemap_lastmod_for(url))` — upserted on successful fetch, like `crawl_gen`/`last_fetched_at`.
- **NULL handling**: non-sitemap URLs (files, discovered-only pages) have `NULL` lastmod; comparison logic treats NULL as "always changed" (conservative).

### B. Sitemap fetch and parse at startup
- **Extend `_fetch_sitemap_urls`** to return `list[tuple[str, str | None]]` — `(url, lastmod)` pairs instead of just URLs.
- Parse both `<loc>` and `<lastmod>` from each `<url>` entry; handle missing `<lastmod>` as `None`.
- **Build `lastmod_map: dict[str, str | None]`** at crawl-loop startup (stored on `WebScraper` instance).
- **No sitemap**: `lastmod_map = {}` → all lastmod lookups return `None` → all old-gen pages treated as changed (degrade to full re-fetch, same cost as `--fresh` but preserves `state.db`).

### C. `_should_fetch` extension
- **Add `update_mode: bool` parameter** (passed from `WebScraper`, derived from CLI flag).
- **Add `lastmod_map: dict[str, str | None]` parameter** (passed from crawl loop).
- **Add `current_gen: int` parameter** (so the function can compare `row.crawl_gen < current_gen`).
- **Extend `URLStore` with `get_metadata(url) -> row | None`** — returns `(crawl_gen, lastmod, ...)` for comparison.

**Logic**:
```python
def _should_fetch(url, seen_this_run, url_store, *, update_mode=False, 
                  current_gen=1, lastmod_map=None):
    if url in seen_this_run:
        return False
    if not url_store.contains(url):
        return True  # new URL
    if not update_mode:
        return False  # foundation behavior: skip visited
    # Update mode: check if changed
    row = url_store.get_metadata(url)
    if row.crawl_gen >= current_gen:
        return False  # already fetched this pass
    # Old generation; check lastmod
    sitemap_lastmod = lastmod_map.get(url) if lastmod_map else None
    stored_lastmod = row.lastmod
    if stored_lastmod is None or sitemap_lastmod != stored_lastmod:
        return True  # changed or unknown
    return False  # unchanged
```

### D. Removal reconciliation (deferred)
- **Not implemented in initial `--update`**. Stale rows remain in `state.db`; manifest stays complete.
- Future work: add `--reconcile-removals` flag (opt-in, runs only on `crawl_complete and not capped`).

### E. `--max-pages` interaction
- `--update` + `--max-pages N` → fetch up to N new/changed pages, stop.
- `_should_write_manifest` already guards manifest regeneration on `not capped` → untouched rows stay at old gen, no false removals.
- Removal reconciliation (when added) MUST skip capped runs.

---

## 5. Risks & Invariants to Preserve

### Manifest atomicity (critical)
- **Foundation guard**: `_should_write_manifest(crawl_complete, capped, has_entries)` prevents partial runs from rewriting the manifest.
- **Update mode must preserve this**: a crashed or capped `--update` run leaves the last complete manifest untouched.
- **Why it matters**: downstream `deprecate_removed_urls` reads the manifest as the authoritative URL set; a shrunken manifest = mass retirement (§4a cascade).

### Partial-crawl retire-cascade risk (critical)
- **Foundation mitigates**: manifest regeneration skipped on `not crawl_complete or capped`.
- **Update mode adds risk**: if removal reconciliation is implemented, it MUST check `crawl_complete and not capped` before marking old-gen rows as removed.
- **Mitigation**: defer removal reconciliation entirely (initial recommendation), or make it opt-in with a separate flag.

### Sitemap `<lastmod>` reliability (empirical, validated in discovery)
- **Confirmed real** on all 5 tested sites (Drupal 10 `simple_sitemap` module).
- **Rejected alternative**: HTTP `Last-Modified`/`ETag` headers reflect Akamai cache-regen time, not content edits (unreliable).
- **Edge case**: if a site's sitemap has stale/incorrect `<lastmod>`, `--update` will miss changes. No mitigation beyond manual `--fresh` on that host.

### `crawl_gen` column NULL handling (already correct)
- Foundation uses `COALESCE(MAX(crawl_gen), 0)` in derivation and `COALESCE(crawl_gen, 0) < current` in comparisons.
- **Update mode must match**: `row.crawl_gen is None` should be treated as `0 < current` → re-fetch.

### File preservation under sitemap-driven crawling (critical — corpus-validated)
- **The risk**: files (PDF/docx/xls/ppt) are almost never in the sitemap, so a *strict* sitemap-as-source crawl (page frontier = sitemap URLs only) reaches them only via one-hop link extraction from the sitemap pages it crawls. Files whose only referrer is a non-sitemap page are dropped.
- **Corpus evidence (§8)**: the crossover flagged large raw "at-risk" doc counts (economics 606, sociology 614, history 583), but canonicalization resolved these as an **artifact** — 100% have a `/search?page=N` faceted-search-trap referrer. `found_on` records only the first referrer, and the BFS fell into the search trap early, so it is NOT evidence these files are orphaned. True file-loss under strict sitemap-as-source is UNRESOLVED from `found_on` data (needs a link-graph crawl of sitemap pages; see §8). The design must be safe under that uncertainty.
- **Locked design rule**: sitemap-as-source restricts the *page* frontier to sitemap URLs but MUST keep extracting and downloading file-asset links from every crawled page — do NOT gate file downloads on sitemap membership. Files ride in via their good parent pages.
- **`--update` safety net** (Task 17): union prior `state.db` file URLs into the fetch set and re-verify (200 → keep, 404 → drop). This is the primary defense for files whose referrer isn't re-captured, and — per §8 — link-following alone recovers only a minority on the big sites, so the safety net is REQUIRED, not optional.

### Queue-based resume (unchanged)
- The `queue` table still owns resume-vs-new-pass (non-empty queue = resume, same gen).
- **Update mode does NOT change this**: a crashed `--update` run resumes at the same `current_gen`, continues re-fetching changed pages.

---

## 6. Suggested Task Breakdown (TDD Outline, NOT Full Plan)

This is a rough starting point for a later `writing-plans` pass. Human must refine and sequence.

1. **Schema: add `lastmod` column** — `ALTER TABLE visited ADD COLUMN lastmod TEXT` in `URLStore.__init__` migration loop. Test: open pre-existing `state.db`, confirm column added without data loss.

2. **Sitemap parsing: extract `<lastmod>`** — extend `_fetch_sitemap_urls` to return `list[tuple[str, str | None]]`. Parse `<lastmod>` from each `<url>` entry (handle missing as `None`). Test: parse real sitemap XML (economics, seas), confirm lastmod values extracted correctly.

3. **Startup: build `lastmod_map`** — in `WebScraper.crawl()` seed phase, call extended `_fetch_sitemap_urls`, build `self.lastmod_map: dict[str, str | None]`. Test: sitemap present → map populated; no sitemap → empty map.

4. **URLStore: add `get_metadata(url)`** — query `visited` table, return `(crawl_gen, lastmod, ...)` or `None`. Test: URL present → returns row; URL absent → returns `None`; NULL `crawl_gen`/`lastmod` → handled correctly.

5. **`_should_fetch` extension: add parameters** — add `update_mode`, `current_gen`, `lastmod_map` params (all optional, default to foundation behavior). Test: no parameters → same behavior as today.

6. **`_should_fetch` logic: `--update` re-fetch rule** — implement `crawl_gen < current AND (lastmod changed OR lastmod is NULL)` comparison. Test: old-gen + changed lastmod → returns `True`; old-gen + same lastmod → returns `False`; new URL → returns `True`; same-gen → returns `False`.

7. **CLI flag: `--update`** — add `--update` argument to scraper CLI, pass to `WebScraper(update_mode=...)`. Test: `--update` flag present → `update_mode=True`; absent → `False`.

8. **Wire `_should_fetch` in crawl loop** — pass `update_mode=self.update_mode`, `current_gen=self.crawl_gen`, `lastmod_map=self.lastmod_map` to `_should_fetch(...)` call in `WebScraper.crawl()`. Test: foundation run → skip visited; `--update` run → re-fetch changed.

9. **`upsert_metadata`: store `lastmod`** — add `lastmod` parameter, include in upsert SQL. Populate from `lastmod_map.get(url)` on save. Test: fetch + save → `lastmod` column updated; no sitemap → `NULL`.

10. **Integration test: `--update` re-fetches changed** — end-to-end test on a mock site: fresh run (gen 1), change sitemap `<lastmod>` for 2 URLs, `--update` run (gen 2), confirm only those 2 URLs re-fetched. Check `crawl_gen`, `lastmod`, `last_fetched_at` in `state.db`.

11. **Integration test: `--update` + `--max-pages`** — capped update run, confirm manifest NOT regenerated, old-gen rows preserved (no cascade). Check `_should_write_manifest` guard honored.

12. **Edge case test: no sitemap** — site with no `sitemap.xml`, run `--update`, confirm degrades to discover-new-only (no crash), logs warning.

13. **Edge case test: missing `<lastmod>`** — sitemap URL lacks `<lastmod>`, confirm treated as "always changed" (re-fetched every pass).

14. **Documentation: DESIGN doc** — finalize this scoping doc based on human decisions, convert to implementation spec.

15. **Documentation: code comments** — docstrings for `_should_fetch` extension, `get_metadata`, `lastmod` column lifecycle (when written, what NULL means).

16. **Sitemap-discovery robustness (prerequisite, do FIRST)** — extend `_fetch_sitemap_urls` to (a) fetch `robots.txt` and parse the `Sitemap:` directive, (b) add `/wp-sitemap.xml` to the standard fallback list, recursing one level into any sitemap-index, and **(c) route all sitemap/robots fetches through the tier-escalating fetcher (Tier 1→Tier 2 curl_cffi), NOT the plain `aiohttp.ClientSession`.** Part (c) is not optional: the AWS probe (§8.4) proved a naive client 403s on 51/83 hosts from production and silently returns `[]`, making sitemap-seeding a no-op in prod. Test: WordPress host (`writingprogram.college`) resolves via `robots.txt`→`/wp-sitemap.xml`; Drupal host resolves via `/sitemap.xml`; a 403-gated host resolves only after Tier-2 escalation; no-sitemap host returns empty without error. Evidence: §8.1 (6 WP hosts silently missed) + §8.4 (51 hosts 403 naive from AWS).

17. **File carry-forward safety net** — on an `--update` run, before pruning, union the prior `state.db`'s known file-asset URLs (pdf/docx/xls/ppt) into the fetch set and re-verify each still returns 200; drop only those that 404. Prevents a valuable file from silently vanishing when its referrer page isn't re-captured (the corpus at-risk finding, §8). Test: prior `state.db` has a file whose referrer is dropped from the new crawl → file still re-verified and retained; file that now 404s → dropped.

---

## 7. What This Draft Needs from the Human

This is a **scoping document**, not a spec. Before implementation, decide:

1. **Q1**: `lastmod` storage location (column vs. separate table) — **rec: column**.
2. **Q2**: "changed" definition + no-sitemap fallback — **rec: strict `!=`, degrade to discover-new-only if no sitemap**.
3. **Q3**: removal reconciliation (none / opt-in / automatic) — **rec: none (defer)**.
4. **Q4**: `_should_fetch` logic (generation-only vs. lastmod-gated) — **rec: lastmod-gated**.
5. **Q5**: `--update` + `--max-pages` interaction — **rec: fetch up to N changed, no removal reconciliation**.
6. **Q6**: sitemap fetch timing — **rec: startup, in-memory map**.

Once decided, this doc can be refined into an implementation plan and handed to a `writing-plans` / `executing-plans` workflow.

---

## 8. Empirical Evidence (sitemap audit + corpus crossover)

Raw evidence and reproducible scripts live in `evidence/crossover/` next to this doc; the honest synthesis is in `evidence/crossover/FINDINGS.md`. Summary of what backs the decisions above:

### 8.1 Sitemap audit (83 sites.toml hosts, Tier 2 curl_cffi)
- **78/83 have a sitemap, 5 do not** (careerservices.fas, ces.fas, daviscenter.fas, www.hio, + a PDF entry) — all small. No-sitemap is an edge, not the common path (grounds Q2 Scenario 3).
- **6 WordPress hosts are silently missed today** — their sitemap is only at `/wp-sitemap.xml`, and `_fetch_sitemap_urls` neither reads `robots.txt` nor tries that path (advising.college, emr.fas, firstyearseminarprogram.college, writingprogram.college, engagedscholarship.fas, placement.college). → **Task 16 (prerequisite).**

### 8.2 Corpus crossover (20 local hosts with a sitemap)
- **Duplication is universal**: raw `state.db` rows are 1.3–4.2× distinct pages everywhere. The "rows ≫ sitemap" gap is dupes (http/https, `?page=`, slash), not content.
- **Sitemap recovers missed pages everywhere**: sitemap-only-missed is large across the board (hscrb 1,939, mcb 6,518, seas 1,495). Sitemap-as-source is a net *page* gain on these hosts, not a loss.

### 8.3 The "at-risk file" scare is an artifact (canonicalization sample)
- Large raw at-risk doc counts (economics 606, sociology 614, history 583, statistics 363) are **100% referred by `/search?page=N`** faceted-search-trap pages (OpenScholar `sites/g/files/omnuum...`), the same pages Jeremy's exclusion work targets. Counts match exactly (e.g. economics 606/606).
- `found_on` is only the *first* referrer; BFS hit the search trap early. So at-risk ≠ orphaned. **True file-loss under strict sitemap-as-source is UNRESOLVED** from `found_on` — a link-graph crawl of sitemap pages is the only definitive test.
- **Design consequence**: because provenance is unreliable, the **file carry-forward safety net (Task 17) is REQUIRED, not optional**; it moots the question. sitemap-as-source additionally *eliminates* the `/search?page=N` trap that produced this bias.

### 8.4 AWS reachability — CONFIRMED (2026-07-23, ECS probe)
- **Resolved the tracked open item.** Ran an ephemeral ECS task in `atg-prod-default` (task def `atg-apo-mcp-qa-task-definition:12`, private subnets, `assignPublicIp=DISABLED` → egress via the **Akamai-gated NAT IP**) that fetched every sites.toml sitemap two ways from the NAT: Tier 1 (plain urllib) and Tier 2 (curl_cffi `impersonate='chrome'`). Result → `s3://atg-apo-mcp-qa-scrape/_sitemap_reachability/result.json`. Evidence: `evidence/aws-reachability/` (AWS_REACHABILITY.md, result.json, probe script).
- **Findings (83 hosts): reachable 79, naive Tier 1 = 200 on 28, Tier 1 = 403 → Tier 2 = 200 on 51, no-sitemap 4.** The Akamai gate IS live from AWS (51 hosts 403 a naive client); **Tier 2 curl_cffi defeats it 51/51** — every gated sitemap returns 200 with valid content. Tier 3 (Playwright) NOT needed for sitemaps. The 4 "unreachable" (ces, daviscenter, careerservices, www.hio) are genuine no-sitemap hosts (404 at BOTH tiers, all candidate paths), not blocks.
- **NEW DESIGN REQUIREMENT (LOCKED, folds into Task 16):** `_fetch_sitemap_urls` (scraper.py:217-220) fetches via the plain `aiohttp.ClientSession` — Tier 1 only. From AWS it 403s on those 51 hosts and silently returns `[]`, so **today's sitemap-seeding is a no-op in production for every Akamai-gated host** (the likely reason seas, which HAS a sitemap, still crawls as unbounded BFS from AWS). Sitemap discovery/fetch — `_fetch_sitemap_urls`, Task 16's robots.txt+wp-sitemap discovery, and the future `--update` `<lastmod>` fetch — **MUST route through the tier-escalating fetcher, not a naive aiohttp session**, or sitemap-as-source and `--update` are dead-on-arrival in production.

### 8.5 Open items / caveats
- **Possibly incomplete sitemaps (needs sample-test)**: histlit (1,579 `distinct-path` non-crossover vs 830 sitemap URLs), classics (516), economics (1,317), history (1,795). Unlike seas (non-crossover = dupes), these may omit real pages — a sitemap-as-source loss risk to confirm before rollout.

## 9. Spun-out streams

- **Remove `.md` frontmatter dependency (consolidate metadata into the
  manifest)** → `aidocs/feature/frontmatter-removal/BRAINSTORM_metadata-consolidation.md`.
  Verified 2026-07-23: frontmatter is stripped before vector-store upload
  (`ingest.py:348`), so it is ingest-plumbing only. `url`/`title` are
  redundant with the manifest; `http_status` (the skip-non-200 gate) is the
  sole frontmatter-only field. Converges with the sitemap-llm path — served
  `.md` also lacks frontmatter, so relocating `http_status` into the manifest
  unlocks both. Separate stream; brainstorm before implementing.
