# Exploration: Scraper Scope Limits + Incremental Mode

**Date**: 2026-07-22/23 | **Scope**: Large (multi-repo) | **Status**: Discovery complete, implementation not started

## 1. Motivation

Two intertwined problems surfaced while validating the tiered-fetch (Playwright) work:

1. **Tier 3 is unproven organically.** Every FAS site tested so far passes at Tier 2 (curl_cffi). We have never seen a page escalate to Tier 3 (headed Playwright) in a real run — so we can't confirm it works end-to-end under production conditions. To *force* the question we need a way to scrape a bounded sample of pages and observe tier behavior, from AWS IP space (where Akamai's IP-reputation gate is harshest).

2. **Scheduled scrapes have no incremental middle ground.** Resume skips everything (state.db says all URLs visited → 0 pages fetched); `--fresh` re-does everything. Neither discovers new pages, detects removals, or re-fetches only what changed.

Both point at the same missing capability set: **ways to bound and target the crawl** (scope limits + page caps) and **ways to re-run without a full wipe** (incremental mode).

## 2. Branch topology (the "3 places")

Work is split across two repos + a launcher repo. Critical finding: the branches are NOT linearly stacked.

| Branch / location | Tiered fetch | Jeremy's scope-limiting | max-pages | Notes |
|---|---|---|---|---|
| `scrape-website` `feature/narrower-scrape` (Jeremy) | ❌ none | ✅ full | ❌ | Cannot be the base — no Akamai bypass |
| `scrape-website` `test/qa-automation-enablement` (**deployed to QA**) | ✅ 41 markers | ✅ *partial* | ❌ | Has tiered fetch + scope_to_path/include_pattern |
| `apo-mcp-server` `test/qa-automation-enablement` | — | — | — | Pins scrape-website by **branch ref** (`branch = "test/qa-automation-enablement"`); plumbs flags through `scrape.py`/`scrape_and_ingest.py` |
| `atg-ops-appserver` `test/qa-automation-enablement` | — | — | — | `apps/apo-mcp/run_scrape.py` launcher (thin boto3 `ecs.run_task` wrapper) |

**Jeremy's 3 commits missing from the deployed branch** (his 2026-07-01 refinements):
- `0974422` exclude search pages
- `1a051d9` http→https canonicalization (dedup fix)
- `05d04f4` exclude .ics files

`git merge-base --is-ancestor` confirms `feature/narrower-scrape` is NOT fully merged into the deployed branch. His earlier scope work (`scope_to_path`, `include_pattern`, 2026-05-29) DID make it in; these 3 later commits did not.

## 3. The full menu of scope-limiting strategies

Jeremy's `narrower-scrape` covers only category A. Categories B/C/D and the sitemap-as-source part of A are net-new (exist in no branch).

### A. Which URLs enter the crawl (breadth reduction)
- **`scope-to-path`** (Jeremy, deployed) — crawl only URLs under the start path
- **`include-pattern`** (Jeremy, deployed) — regex allowlist
- **`exclude-pattern`** (Jeremy, partial) — regex denylist; search-page + .ics exclusions are in the 3 missing commits
- **http→https canonicalization** (Jeremy, missing commit `1a051d9`) — dedup so a page isn't crawled twice under two schemes. NOTE: this is a *dedup/correctness* fix, not scope narrowing — the bug *broadens* the crawl (double-counts one page as two).
- **Sitemap-as-source** (NEW — biggest lever) — seed the crawl from the sitemap URL list instead of link-graph discovery. On economics: **5,946 clean sitemap URLs vs 30,490 link-graph-crawled** (~25k are crawler-trap noise: `?search=X&page=N`, `.ics` feeds, calendar pagination). Cleaner than pattern-excluding trap URLs one at a time. Code exists (`use_sitemap`) but disabled in `sites.toml` (`use_sitemap` defaults False in `scrape.py:63`).

### B. How much of the crawl runs (volume caps) — NONE EXIST TODAY
- **`--max-pages`** — hard page-count cap. Crawl is currently unbounded BFS (`scraper.py:1268` loop; no depth/count limit). Caveat: BFS order gives "first N pages," not a representative sample.
- **`--max-depth`** — limit link-following depth. Queue tuples carry `(url, found_on)` where `found_on` is the parent for citations, NOT a depth counter — would need a new counter.

### C. Which pages re-fetch on later runs (incremental / temporal)
- **Sitemap `<lastmod>` comparison** (NEW — strongest incremental mechanism) — store each URL's `<lastmod>` in state.db; on re-run only re-fetch pages whose `<lastmod>` changed. Confirmed real on all 5 sites (a 2020 news article correctly shows `<lastmod>2020-03-16>`; not cache-regen time). Also detects NEW pages (sitemap URL not in state.db — 683 on economics, 1,120 on history) and REMOVED pages (state.db URL absent from sitemap).
- **Conditional requests (`If-Modified-Since`/`ETag`)** — REJECTED. Tested: these sites' HTTP `Last-Modified`/`ETag` reflect Akamai cache-regen time, not content edits (same URL → two different ETags minutes apart). Unreliable.
- **content_hash gate** — already stored in state.db per URL; ingest already dedups re-upload on this. Could also gate re-write.

### D. Per-page processing cost (volume-adjacent)
- **Drupal `.md` content negotiation** (NEW) — 4 of 5 sites serve native markdown via `.md` suffix / `?_format=markdown` / `Accept: text/markdown`, skipping local `trafilatura` extraction. SEAS does NOT support it (needs per-site capability detection). Caveat: Akamai doesn't vary cache on `Accept` header — use the `.md` suffix or `?_format=` param (distinct cache keys), not the `Accept` header.

## 4. Intermittent (incremental) mode — design concept

The "fetch everything but don't wipe everything" mode the crawl is missing. Distinct from both resume (skips all) and `--fresh` (wipes state.db, re-does all).

**Behavior:** re-crawl the link graph (or sitemap) to discover the current URL set, but preserve state.db so we can diff against the prior run:
- **New pages** → fetch + ingest
- **Removed pages** (in state.db, gone from crawl/sitemap) → mark for retirement
- **Changed pages** → re-fetch + re-ingest (detected via sitemap `<lastmod>`, since HTTP headers are unreliable)
- **Unchanged pages** → skip re-write / re-ingest (content_hash / lastmod match)

**Key realization:** without sitemap `<lastmod>`, "incremental" collapses into "same workload as fresh" — you still fetch every page to hash it. The `<lastmod>` comparison is what makes it genuinely cheaper (skip the fetch entirely for unchanged pages). So category C's sitemap-lastmod is the enabling primitive for this mode.

### 4b. Refined design: crawl-and-upsert (update state.db along the way)

The intermediary that resolves BOTH the §4a cascade AND the incremental mode: crawl through and **upsert** state.db rows as you go, WITHOUT clearing first. Because state.db is never emptied, the manifest stays complete → `deprecate_removed_urls` sees all URLs as active → no retire cascade. A `--max-pages` sample just refreshes N rows; everything untouched stays as-is.

**Required code change — decouple the two roles of `contains()`:** the crawl loop (`scraper.py:1272`) gates fetching on `contains()`, which conflates (1) in-run loop prevention and (2) cross-run resume-skip. Keeping state.db + not clearing currently means skip-everything (0 pages). Fix: use an in-memory `seen_this_run` set for loop prevention; STOP gating fetches on the persisted visited table; upsert each row on visit (re-fetch, update content_hash/lastmod/filename; new pages insert). `upsert_metadata` already exists for the metadata side.

**Strictly safer than `--fresh`:** an interrupted update crawl leaves a MERGED state.db (old rows for not-yet-visited + updated rows for visited) and a complete manifest — no truncation, no cascade at any intermediate point. `--fresh` interruption leaves a truncated state.db → partial manifest → cascade.

**Edge case — removal detection is separate and mutually exclusive with sampling:** upsert-only never deletes, so removed-from-site pages keep stale rows forever. Detecting removals requires a separate reconciliation pass (diff crawled-this-run set vs state.db, retire the difference) — which IS the retire cascade. It must be opt-in and run ONLY on a known-complete crawl, NEVER on a `--max-pages` sample (unvisited rows aren't removed, just unreached).

| Mode | state.db | Manifest | Reconcile/retire |
|---|---|---|---|
| `--max-pages` sample | upsert N, keep rest | complete | **never** |
| Incremental (full) update | upsert all crawled | complete | optional, opt-in |
| `--fresh` (today) | clear + rebuild | rebuilt (authoritative) | implicit-full |

### 4c. PREFERRED design: persisted re-fetch tracking (scrape generation column)

Supersedes the in-memory `seen_this_run` approach in §4b. Add a per-URL **scrape generation** to state.db — a `last_scraped` timestamp or run-epoch counter (`scrape_gen`). All modes become one mechanism read differently, and the re-scrape itself becomes CRASH-RESUMABLE (the in-memory set does not survive a crash → can't resume a half-done re-scrape).

**Skip rule per mode:** done-this-run = `scraped_at == current_gen`; exists-from-before = row present with older gen.
- fresh: no prior data → crawl all
- resume (crash recovery): same gen, skip `== current_gen`
- incremental re-scrape: NEW gen, skip `== current_gen` (crash recovery within re-scrape), RE-FETCH `< current_gen`
- max-pages: new gen, capped, reconcile off

**Kills the §4a cascade by construction:**
1. Never clears rows → state.db always a complete superset → manifest always complete; crash leaves MERGED (not truncated) state.
2. Defer manifest regeneration to run-COMPLETION and guard it (only rewrite on a completed, non-capped run). A partial/max-pages/crashed run leaves the last complete manifest untouched → `deprecate_removed_urls` never sees a shrunken manifest. Makes the manifest ATOMIC — stronger than §4b in-place upsert.

**Removal detection for free + safe:** after a KNOWN-COMPLETE re-scrape, any row still at an old generation = not-seen-this-run = removal candidate. Automatically inert on `--max-pages` (capped run flagged incomplete → reconcile skipped). Sampling and removal-detection cannot collide.

**Content-hash write-skip (near-free):** hash is already computed for `upsert_metadata`. `save_text` currently writes-then-hashes; reorder to hash-first, compare stored `content_hash`, skip write if equal (still bump `last_scraped`). ms-scale per page but 14k avoided writes on a mostly-unchanged re-scrape; the comparison also yields the change signal for manifest/ingest.

**One decision to nail:** generation lifecycle — stable `current_gen` across a resume, fresh value for a new incremental run. Store `current_gen` in stats/meta; new incremental invocation bumps it, plain resume reuses it. "Run complete" signal (so next invocation knows to bump) = queue empty AND no rows with `scraped_at < current_gen`.

**Migration:** `URLStore.__init__` already does additive `ALTER TABLE` migrations (how manifest columns were retrofitted) — adding `last_scraped`/`scrape_gen` fits, no schema reset.

## 4a. CRITICAL RISK: partial crawls violate the "complete & authoritative" invariant

A `--max-pages N --fresh` run through the full pipeline does NOT just produce a small scrape — it guts the host, cascading into the vector store. Traced end-to-end:

1. **sync down** — `scrape_and_ingest` pulls full prior scrape from S3 (thousands of `.md`, full state.db, full manifest).
2. **scrape** — `--fresh` → `clear()` only wipes state.db TABLES (`DELETE FROM visited/...`), NOT the `text/`/`pages/`/`files/` dirs. Crawls N pages, overwrites those N `.md`, leaves the other thousands on disk. Regenerates `manifest.json` from `export_manifest()` (reads visited table) → **manifest shrinks to N entries**.
3. **ingest** — globs ALL `.md` (thousands still present), looks each up in the PARTIAL manifest. Only N have `origin_url` → only N enter `active_urls`; rest skipped (`ingest.py:392`).
4. **cascade** — `deprecate_removed_urls(active_urls={N})` (`ingest.py:377,71`) retires every `WebContentFile` for the host whose URL isn't in those N → default flips `source_status="removed"` → **invisible to search**.

**Net: `--max-pages 50` on a 15k-page host retires ~14,950 pages from search visibility**, and the delete-then-upload S3 mirror (`scrape_and_ingest.py:174`, unconditional) clobbers state.db + manifest to N entries.

**Root cause:** three mechanisms — delete-then-upload S3 mirror, manifest regeneration, and `deprecate_removed_urls` — all assume *the local scrape is the complete authoritative set for the host*. A partial crawl violates this everywhere.

**Cannot dodge via no-`--fresh`:** without `--fresh` the scraper resumes, sees state.db complete, crawls 0 pages. `--max-pages` is only meaningful WITH `--fresh` (or a never-scraped host) — which reintroduces the destruction.

**Safe sampling for Tier-3 detection** (the answer lives in scraper LOGS, not the corpus):
- `--mode scrape` (no ingest) → stops the vector-store cascade (`deprecate_removed_urls` is ingest-only). S3 mirror still clobbered.
- Run in DEV on throwaway hosts (isolated bucket/vector-store/Postgres).
- Best: scrape-only into a scratch/diagnostic S3 prefix, or no upload — never mirror over the real host prefix.

**Design requirement (blocks BOTH features):** `--max-pages` must signal "partial/non-authoritative" so mirror-delete, manifest-regenerate, and retire are all skipped. Intermittent mode has the same problem in mirror image — it must NOT wipe, and manifest handling must be additive/merge (not regenerate-from-scratch), or every not-re-fetched page triggers the retire cascade. **Breaking the "complete & authoritative" assumption in the mirror + manifest + retire pipeline is the first thing to design, before either feature.**

## 5. Empirical results captured this session

**Tiered fetch validation (QA ECS, fresh scrapes, `test/qa-automation-enablement`):**
| Tier | Sites | Result |
|---|---|---|
| 1 | language | exit 0, 1 page (scope_to_path=/students), **denied=0** |
| 2 | ces, music | exit 0, parallel workers=2, **denied=0** both (ces: 2 pages+2 files; music: 11 pages) |
| 3 | seas + sociology + statistics + www.gov + www.mcb | IN PROGRESS — www.gov fresh at 06:29; seas (~15k) long pole |

3-for-3 FAS sites scraped from AWS with **zero denials** → tiered fetch reliably bypassing Akamai (curl_cffi Tier 2 doing the work; Tier 3 still not organically triggered — which is why max-pages sampling is needed).

**Sitemap findings (5 largest: economics, seas, history, socialstudies, chemistry):**
- All 5 are Drupal 10 with sitemaps (`simple_sitemap` module, sitemap-index format)
- Per-URL `<lastmod>` reflects real content-edit history (verified across all 5)
- economics: 5,946 sitemap URLs, 683 not in state.db (real new faculty/student pages)
- history: 5,801 sitemap URLs, 1,120 not in state.db
- ~80% of link-graph-crawled URLs are non-canonical trap noise

## 6. Handoff — recommended strategy

**Base branch:** cut a matched pair off the **deployed** `test/qa-automation-enablement` in BOTH repos (keeps tiered fetch). Do NOT base on `feature/narrower-scrape` (loses Tier 2/3).

**Step 1 — leverage Jeremy's work:** bring his 3 orphaned commits (`0974422`, `1a051d9`, `05d04f4`) into the new branch (cherry-pick or merge). Verify they don't conflict with tiered-fetch changes to `_normalize_url` / exclude-pattern list.

**Step 2 — add net-new limiting:** `--max-pages` in `scrape_website/scraper.py` (BFS-order counter + break) + plumb through `scrape.py` → `scrape_and_ingest.py`. Consider sitemap-sampling instead of raw BFS order for representative Tier-3 detection.

**Step 3 — enable sitemap-as-source** where available (flip `use_sitemap` per site, or make it the default seeding path).

**Step 4 — deploy to DEV** (not QA): rebuild the branch image (mutable tag = branch name `/`→`_`; task def already points at it, so re-push + run picks up fresh code), run a full scrape with `--max-pages` + tiered fetch + sitemaps.

**Step 5 (separate stream) — intermittent mode:** implement sitemap `<lastmod>` storage + comparison as the enabling primitive, then the new mode on top.

**Launch note:** ECS tasks can be launched from anywhere with AWS creds (`aws ecs run-task` / a script in apo-mcp-server) — the ops-appserver launcher is convenience only. But container CODE is always the deployed image; new scraper code REQUIRES a rebuild (RunTask overrides can't swap the image). `--local` is a data-source flag (local `data/` vs S3 sync), unrelated to code deployment.
