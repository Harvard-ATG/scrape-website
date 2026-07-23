# Design: Crawl-Generation State-Model Foundation

**Date**: 2026-07-23 | **Scope**: Foundation only | **Status**: Design — approved, spec review pending
**Repo/branch**: `Harvard-ATG/scrape-website` `feat/scraper-scope-limits`
**Discovery**: [EPCC_EXPLORE.md](./EPCC_EXPLORE.md) (§4a, §4b, §4c)

## 1. Purpose

The scraper has two fetch modes — **resume** (skip everything already visited → 0 pages) and
**`--fresh`** (wipe `state.db`, re-do everything). There is no safe middle ground, and partial
crawls violate a "complete & authoritative" invariant that cascades into the vector store
(discovery §4a: a `--max-pages 50` run can retire ~14,950 pages from search).

This spec builds the **state-model foundation** that makes a safe middle ground *possible*:
per-URL crawl-generation tracking, a decoupled skip decision, and an atomic manifest. It is the
"design the invariant-break FIRST" requirement from discovery §4a.

It deliberately does **not** implement incremental mode or `--max-pages` — it lays the seam both
will build on, with **zero change to default fetch behavior**.

## 2. Goals / Non-goals

**Goals**
- Add per-URL crawl-generation + freshness columns to `state.db`, populated on every successful save.
- Derive the current generation from existing state (no new lifecycle/meta storage).
- Decouple `contains()`'s two conflated roles (in-run loop prevention vs. cross-run skip) so a
  future re-fetch is *possible* — without triggering one now.
- Make manifest regeneration **atomic**: a partial/crashed/capped run never rewrites the last
  complete manifest, so `deprecate_removed_urls` never sees a shrunken set.
- Document the generation concept in four places (§7).

**Non-goals (deferred to follow-on streams)**
- `--max-pages` and its partial/non-authoritative S3-mirror signal (max-pages stream).
- Sitemap `<lastmod>` comparison, new/changed/unchanged/removed handling, removal reconciliation,
  content-hash write-skip (update-mode stream; see §8 terminology note).
- Any change to *which* URLs are fetched on a normal run. The re-fetch switch is flipped by
  update mode, not here.

## 3. Design

### 3.1 Schema — two additive columns on `visited`

Added via the existing `ALTER TABLE ... ADD COLUMN` migration loop in `URLStore.__init__`
(`scraper.py:436-444`), which is how manifest columns were retrofitted. No schema reset.

| Column | Type | Role | Written |
|---|---|---|---|
| `crawl_gen` | `INTEGER` | **Control.** Which crawl generation last fetched this row. | On successful save |
| `last_fetched_at` | `TEXT` | **Freshness data.** UTC ISO-8601 of the most recent successful fetch. | On successful save |

- `crawl_gen` is net-new to the codebase — no existing pattern to pattern-match — so it carries a
  heavy documentation burden (§7). Rationale for the name: a *generation* is scoped (has a start
  and end) and progressive (monotonic), matching both the lay and CS meaning; "crawl" (graph
  traversal), not "scrape" (the full fetch→extract→ingest pipeline), is the thing being counted.
- `last_fetched_at` mirrors the repo's established `last_<verb>_at` convention — directly parallel
  to `last_ingested_at` (`apo-mcp-server/ingest.py`) and `last_active_at`; `_at` = UTC + tz-aware
  instant, stored as an ISO string like `manifest.py`'s `generated_at`.

### 3.2 Two independent axes

The discovery doc's "generation lifecycle" knot dissolves once two questions are separated:

| Question | Owned by | New state? |
|---|---|---|
| **Resume the in-flight pass, or start a new one?** | the `queue` table — non-empty = mid-pass, empty = last pass complete | No (exists) |
| **Within a pass, re-fetch this row or skip it?** | `crawl_gen`: `row.crawl_gen < current` = re-fetch; `== current` = skip | Yes (this spec) |

Resume-without-`--fresh` was never unclear once you see the queue already carries it (it is
checkpointed periodically and in `finally`, `scraper.py:1219,1285`). Completion signal =
**queue empty**; the doc's "and no rows `< current_gen`" clause is unreliable (a removed page keeps
an old gen forever) and is dropped.

### 3.3 Generation register — derive via MAX (no meta coupling)

`current_gen` is computed once at startup from the table itself; nothing new is persisted:

Let `baseline = COALESCE(MAX(crawl_gen), 0)` (the `COALESCE` guards both an empty table and the
one-time post-migration state where existing rows have `NULL` `crawl_gen`):

| Mode | `current_gen` |
|---|---|
| `--fresh` | `clear()` empties `visited` → `baseline = 0` → **1** |
| Resume (queue non-empty) | `max(baseline, 1)` — continue the in-flight pass |
| New pass (queue empty, no `--fresh`) | `baseline + 1` |

This keeps all generation logic in one place (the crawl loop) and out of the `stats` KV table.
Parking `current_gen` in `stats` was rejected: `stats` is a transient scratchpad that `clear()`
wipes (`scraper.py:553`) and `save_stats` overwrites (`540`) — coupling a monotonic-must-survive
value to it would make three code paths (fresh, checkpoint, resume) silently generation-aware.

**Accepted edge case:** if a new pass crashes *after* re-seeding the queue but *before* the first
row commits, `MAX` still reads the old gen and the pass self-corrects with redundant fetches. The
window is sub-second and, given rows autocommit (WAL, `isolation_level=None`) while the queue is
only persisted at checkpoint intervals, effectively unreachable. We accept it rather than add a
durable pass-start marker.

### 3.4 Stamp on successful save

`crawl_gen`/`last_fetched_at` are written in `upsert_metadata` (on successful fetch+save), **not**
at `add()` (`scraper.py:1273`, when a URL is popped). A popped-but-failed fetch therefore stays at
the old generation and is naturally retried on the next pass, instead of being marked current and
skipped.

### 3.5 `contains()` decoupling — lay the seam, don't flip the switch

`contains()` (`scraper.py:454`) currently answers both "seen this URL *this run*" (loop prevention)
and "seen it *ever*" (cross-run skip). The crawl loop gates fetching on it (`1272`).

- Introduce an in-memory `seen_this_run: set[str]` for **loop prevention** within a pass.
- Route the fetch decision through a single generation-aware seam (e.g. `should_fetch(url)`), so
  incremental mode can later change *only* that rule.
- **Foundation preserves today's behavior exactly:** a normal resume still skips visited URLs; a
  normal fresh run still fetches all. No re-fetch of old-gen rows happens until incremental mode
  turns it on. This is a zero-regression change that only *enables* the future switch.

### 3.6 Manifest atomicity

Defer `export_manifest`/manifest write (`scraper.py:1297-1302`) to run **completion**, guarded on a
completed, non-capped pass:

- Set a `crawl_complete` flag when the crawl loop exits normally (queue drained, no in-flight tasks).
- Regenerate the manifest only when `crawl_complete and not capped`. (`capped` is always `False`
  now; the guard is installed for the deferred `--max-pages` stream.)
- A partial, crashed, or capped run leaves the **last complete `manifest.json` untouched**, so the
  downstream ingest/`deprecate_removed_urls` cascade never sees a shrunken manifest.

This also produces the "was this a complete authoritative pass?" signal the deferred S3-mirror
guard (`apo-mcp-server/scrape_and_ingest.py`) will consume.

## 4. Why this is safe to deploy

- Columns are additive; existing rows get `NULL` `crawl_gen`/`last_fetched_at`. NULL is *not*
  automatically "older" in SQL (`NULL < 1` is NULL, not true), so any generation comparison — and
  the MAX derivation in §3.3 — must `COALESCE(crawl_gen, 0)` to treat un-stamped rows as oldest.
  With that, the post-migration transition is correct by construction.
- No default fetch behavior changes (§3.5). Fresh and resume runs produce the same page sets as
  today; the only observable differences are two newly-populated columns and an atomic manifest.
- Manifest atomicity is strictly safer than today (partial runs can only *fail to update*, never
  *shrink*, the manifest).

## 5. Naming (locked)

- `crawl_gen` — integer, control. Net-new concept; nearest conceptual cousin in-repo is Alembic's
  `revision`/`down_revision` chain (ordered generations), but that is hash-based and external.
- `last_fetched_at` — UTC ISO-8601 string, freshness. Mirrors `last_ingested_at`.

## 6. Testing / rollout

Isolated on `feat/scraper-scope-limits`, then deployed to **DEV** and exercised there (per
discovery §6 launch mechanics: mutable image tag = branch name, rebuild + re-push + run task):

- **Migration**: opening a pre-existing `state.db` adds both columns without data loss; a fresh DB
  creates them.
- **Fresh run**: all rows get `crawl_gen = 1` and a `last_fetched_at`; manifest written once at
  completion; page set identical to pre-change fresh run.
- **Resume run** (crash mid-pass): re-invocation continues the same generation (`MAX`), skips
  `== current` rows, and does not re-fetch; page set matches a single uninterrupted run.
- **Manifest atomicity**: a run killed before completion leaves the prior `manifest.json` byte-for-
  byte unchanged.
- **No regression**: fetched page counts for fresh and resume match the pre-change baseline on a
  DEV host.

## 7. Documentation requirement

Because `crawl_gen` has no in-repo analogue to lean on, its meaning and lifecycle are documented in
all four places, kept consistent:

1. **This spec** — the authoritative what/why.
2. **The migration** (`URLStore.__init__`) — an inline comment per column: meaning + when written.
3. **The skip-logic seam** (`should_fetch`/crawl loop) — a docstring: `crawl_gen < current` =
   re-fetch, `== current` = skip, and why the queue (not the column) decides resume.
4. **Module/README mental model** — resume vs. fresh vs. (future) incremental, and what a
   "generation" is.

## 8. Deferred hooks this foundation exposes

> **Terminology:** what this doc (and EPCC_EXPLORE) originally called "incremental mode" is now
> named **update mode** / the **`--update`** flag. The foundation adds no flag; a plain re-run with
> a drained queue is already an "update pass" (new generation, discover-new, skip-existing). The
> `--update` flag only adds re-fetching of *changed* pages on top.

- **`--max-pages`**: consumes the `capped` guard (§3.6) and the "complete authoritative pass" signal.
- **`--update` (update mode)**: flips the `should_fetch` seam (§3.5) to re-fetch `crawl_gen < current`,
  adds sitemap `<lastmod>` comparison and removal reconciliation over old-gen rows, and content-hash
  write-skip keyed on the already-computed hash.
