# Crawl-Generation State-Model Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-URL crawl-generation tracking + freshness to `state.db` and make manifest regeneration atomic, laying the safe seam for incremental mode and `--max-pages` — with zero change to current fetch behavior.

**Architecture:** Two additive columns on the `visited` table (`crawl_gen` INTEGER, `last_fetched_at` TEXT). The current generation is *derived* from `COALESCE(MAX(crawl_gen),0)` — no new lifecycle storage. The `queue` table already decides resume-vs-new-pass; `crawl_gen` will decide re-fetch-vs-skip. This foundation routes the fetch decision through a `_should_fetch` seam and gates manifest writes on a completed, non-capped pass, but does not yet re-fetch old-generation rows.

**Tech Stack:** Python 3.13, `sqlite3` (WAL, autocommit `isolation_level=None`), `asyncio`, `pytest>=8`. Source: `scrape_website/scraper.py`. Tests: `tests/`.

**Design doc:** [DESIGN_crawl-generation-foundation.md](./DESIGN_crawl-generation-foundation.md)

## Global Constraints

- **Zero behavior change**: fetched page sets for `--fresh` and resume runs must match the pre-change baseline. The re-fetch switch belongs to incremental mode, not this plan.
- **Additive migration only**: use the existing `ALTER TABLE visited ADD COLUMN` try/except pattern in `URLStore.__init__`; never reset or clear schema.
- **Timestamps are UTC ISO-8601**: `datetime.now(timezone.utc).isoformat()`, matching `manifest.py`'s `generated_at` and the `_at` convention.
- **NULL-safe generations**: any `MAX`/comparison on `crawl_gen` uses `COALESCE(crawl_gen, 0)` — SQL `NULL < 1` is NULL, not true.
- **Stamp on successful save** (`upsert_metadata`), never at `add()`.
- **Queue owns resume**; `crawl_gen` never decides resume-vs-new-pass.
- **Manifest is atomic**: only (re)write `manifest.json` after a complete, non-capped pass with entries.
- **Commits**: conventional format, scope `scraper` (e.g. `feat(scraper): ...`). No AI attribution.
- **Run tests with**: `uv run pytest`.

## File Structure

- **Modify** `scrape_website/scraper.py`:
  - `URLStore.__init__` — add two columns to the migration list
  - `URLStore.max_crawl_gen()` — new method
  - `URLStore.upsert_metadata()` — accept + persist `crawl_gen` and `last_fetched_at`
  - module-level `_decide_crawl_gen()`, `_should_fetch()`, `_should_write_manifest()` — new helpers (matches existing `_normalize_url`/`_url_excluded` helper idiom)
  - `WebScraper.__init__` — compute `self.crawl_gen`, init `seen_this_run`/`capped`/`crawl_complete`
  - `WebScraper.crawl()` — use `_should_fetch`; set `crawl_complete` on normal exit
  - `WebScraper.save_file`/`save_text` upsert calls — pass `crawl_gen`
  - `WebScraper.run()` — gate manifest write on `_should_write_manifest`
  - comment block above `class URLStore` documenting generations
- **Create** `tests/test_crawl_generation.py` — unit tests for schema, helpers, and stamping
- **Create** `tests/test_scraper_wiring.py` — construction smoke test for the wired scraper

---

### Task 1: Add `crawl_gen` + `last_fetched_at` columns

**Files:**
- Modify: `scrape_website/scraper.py:436-444` (`URLStore.__init__` migration loop)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Produces: `visited` table gains `crawl_gen INTEGER`, `last_fetched_at TEXT` (both nullable).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py
import sqlite3
from pathlib import Path

from scrape_website.scraper import URLStore


def _columns(store: URLStore) -> set[str]:
    return {row[1] for row in store.conn.execute("PRAGMA table_info(visited)")}


def test_new_store_has_generation_columns(tmp_path):
    store = URLStore(tmp_path / "state.db")
    cols = _columns(store)
    assert "crawl_gen" in cols
    assert "last_fetched_at" in cols
    store.close()


def test_migration_adds_columns_to_legacy_db(tmp_path):
    # Simulate a pre-generation state.db: visited table with only url.
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE visited (url TEXT PRIMARY KEY)")
    conn.execute("INSERT INTO visited (url) VALUES ('https://x/a')")
    conn.commit()
    conn.close()

    store = URLStore(db_path)  # __init__ runs the additive migration
    cols = _columns(store)
    assert "crawl_gen" in cols
    assert "last_fetched_at" in cols
    # Existing row preserved, new columns NULL.
    row = store.conn.execute(
        "SELECT crawl_gen, last_fetched_at FROM visited WHERE url='https://x/a'"
    ).fetchone()
    assert row == (None, None)
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py -v`
Expected: FAIL — `crawl_gen` not in columns.

- [ ] **Step 3: Add the columns to the migration list**

In `URLStore.__init__`, extend the migration loop (currently ends with `content_hash`/`file_size`):

```python
        # Migrate existing tables from pre-manifest schema
        for col, col_type in [
            ("filename", "TEXT"), ("hostname", "TEXT"), ("title", "TEXT"),
            ("found_on", "TEXT"), ("file_type", "TEXT"),
            ("content_hash", "TEXT"), ("file_size", "INTEGER"),
            # Crawl-generation foundation (see comment block above class URLStore):
            ("crawl_gen", "INTEGER"),      # which crawl generation last fetched this row
            ("last_fetched_at", "TEXT"),   # UTC ISO-8601 of the most recent successful fetch
        ]:
            try:
                self.conn.execute(f"ALTER TABLE visited ADD COLUMN {col} {col_type}")
            except sqlite3.OperationalError:
                pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): add crawl_gen and last_fetched_at columns to state.db"
```

---

### Task 2: `URLStore.max_crawl_gen()`

**Files:**
- Modify: `scrape_website/scraper.py` (add method to `URLStore`, e.g. after `count`)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Produces: `URLStore.max_crawl_gen() -> int` — `COALESCE(MAX(crawl_gen), 0)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py  (append)
def test_max_crawl_gen_empty_is_zero(tmp_path):
    store = URLStore(tmp_path / "state.db")
    assert store.max_crawl_gen() == 0
    store.close()


def test_max_crawl_gen_ignores_null_and_returns_max(tmp_path):
    store = URLStore(tmp_path / "state.db")
    store.add("https://x/a")  # crawl_gen stays NULL
    store.add("https://x/b")
    store.conn.execute("UPDATE visited SET crawl_gen=3 WHERE url='https://x/b'")
    assert store.max_crawl_gen() == 3
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py::test_max_crawl_gen_empty_is_zero -v`
Expected: FAIL — `URLStore` has no attribute `max_crawl_gen`.

- [ ] **Step 3: Add the method**

```python
    def max_crawl_gen(self) -> int:
        """Highest crawl generation recorded, or 0 if none.

        COALESCE guards both an empty table and the one-time post-migration
        state where existing rows have NULL crawl_gen.
        """
        row = self.conn.execute(
            "SELECT COALESCE(MAX(crawl_gen), 0) FROM visited"
        ).fetchone()
        return row[0]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): add URLStore.max_crawl_gen helper"
```

---

### Task 3: `_decide_crawl_gen()` generation decision

**Files:**
- Modify: `scrape_website/scraper.py` (module-level helper, near `_normalize_url`)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Produces: `_decide_crawl_gen(baseline: int, *, fresh: bool, resuming: bool) -> int`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py  (append)
from scrape_website.scraper import _decide_crawl_gen


def test_decide_crawl_gen_fresh_always_one():
    assert _decide_crawl_gen(5, fresh=True, resuming=False) == 1
    assert _decide_crawl_gen(0, fresh=True, resuming=False) == 1


def test_decide_crawl_gen_resume_continues_pass():
    assert _decide_crawl_gen(5, fresh=False, resuming=True) == 5
    # Post-migration: baseline 0 but resuming → floor at 1.
    assert _decide_crawl_gen(0, fresh=False, resuming=True) == 1


def test_decide_crawl_gen_new_pass_advances():
    assert _decide_crawl_gen(5, fresh=False, resuming=False) == 6
    assert _decide_crawl_gen(0, fresh=False, resuming=False) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py -k decide_crawl_gen -v`
Expected: FAIL — cannot import `_decide_crawl_gen`.

- [ ] **Step 3: Add the helper**

```python
def _decide_crawl_gen(baseline: int, *, fresh: bool, resuming: bool) -> int:
    """Choose this run's crawl generation from the highest one recorded.

    `baseline` = COALESCE(MAX(crawl_gen), 0) from state.db.
      - fresh:    state was cleared → start at generation 1.
      - resuming: continue the in-flight pass (its rows already carry `baseline`);
                  max(baseline, 1) guards the one-time post-migration case.
      - update:   the last pass completed → new pass, advance to baseline + 1.

    The queue (not this value) decides fresh/resume/update; see _should_fetch.
    """
    if fresh:
        return 1
    if resuming:
        return max(baseline, 1)
    return baseline + 1
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -k decide_crawl_gen -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): add crawl-generation decision helper"
```

---

### Task 4: Stamp `crawl_gen` + `last_fetched_at` on `upsert_metadata`

**Files:**
- Modify: `scrape_website/scraper.py:493-501` (`URLStore.upsert_metadata`)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `upsert_metadata(..., crawl_gen: int | None = None)`; when `crawl_gen` is provided, `last_fetched_at` is set to the current UTC ISO timestamp.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py  (append)
from datetime import datetime


def test_upsert_stamps_gen_and_timestamp(tmp_path):
    store = URLStore(tmp_path / "state.db")
    store.add("https://x/a")
    store.upsert_metadata(
        "https://x/a", filename="a.md", hostname="x", crawl_gen=2,
    )
    gen, fetched_at = store.conn.execute(
        "SELECT crawl_gen, last_fetched_at FROM visited WHERE url='https://x/a'"
    ).fetchone()
    assert gen == 2
    parsed = datetime.fromisoformat(fetched_at)  # valid ISO-8601
    assert parsed.tzinfo is not None             # tz-aware / UTC
    store.close()


def test_upsert_without_gen_leaves_fields_null(tmp_path):
    store = URLStore(tmp_path / "state.db")
    store.add("https://x/a")
    store.upsert_metadata("https://x/a", filename="a.md", hostname="x")
    gen, fetched_at = store.conn.execute(
        "SELECT crawl_gen, last_fetched_at FROM visited WHERE url='https://x/a'"
    ).fetchone()
    assert gen is None
    assert fetched_at is None
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py -k upsert -v`
Expected: FAIL — `upsert_metadata` got unexpected keyword `crawl_gen`.

- [ ] **Step 3: Extend `upsert_metadata`**

Replace the method body:

```python
    def upsert_metadata(self, url: str, *, filename: str, hostname: str,
                        title: str | None = None, found_on: str | None = None,
                        file_type: str = "web", content_hash: str | None = None,
                        file_size: int | None = None, crawl_gen: int | None = None):
        # last_fetched_at stamps the UTC instant of this successful save (freshness);
        # crawl_gen records which crawl generation last fetched the row (control).
        # Only stamp them on a real fetch save (crawl_gen provided).
        fetched_at = (
            datetime.now(timezone.utc).isoformat() if crawl_gen is not None else None
        )
        self.conn.execute("""
            UPDATE visited SET filename=?, hostname=?, title=?, found_on=?,
                file_type=?, content_hash=?, file_size=?, crawl_gen=?, last_fetched_at=?
            WHERE url=?
        """, (filename, hostname, title, found_on, file_type, content_hash,
              file_size, crawl_gen, fetched_at, url))
```

(`datetime` and `timezone` are already imported at `scraper.py:20`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -v`
Expected: PASS (all tests so far).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): stamp crawl_gen and last_fetched_at on metadata upsert"
```

---

### Task 5: `_should_fetch()` fetch-decision seam

**Files:**
- Modify: `scrape_website/scraper.py` (module-level helper, near `_decide_crawl_gen`)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Consumes: `URLStore.contains`.
- Produces: `_should_fetch(url: str, seen_this_run: set[str], url_store: URLStore) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py  (append)
from scrape_website.scraper import _should_fetch


def test_should_fetch_unseen_url(tmp_path):
    store = URLStore(tmp_path / "state.db")
    assert _should_fetch("https://x/a", set(), store) is True
    store.close()


def test_should_fetch_skips_seen_this_run(tmp_path):
    store = URLStore(tmp_path / "state.db")
    seen = {"https://x/a"}
    assert _should_fetch("https://x/a", seen, store) is False
    store.close()


def test_should_fetch_skips_already_visited(tmp_path):
    store = URLStore(tmp_path / "state.db")
    store.add("https://x/a")
    assert _should_fetch("https://x/a", set(), store) is False
    store.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py -k should_fetch -v`
Expected: FAIL — cannot import `_should_fetch`.

- [ ] **Step 3: Add the helper**

```python
def _should_fetch(url: str, seen_this_run: set[str], url_store: "URLStore") -> bool:
    """Decide whether to fetch a URL during this pass.

    Foundation behavior (zero regression):
      - skip if already fetched this run (`seen_this_run`, in-run loop prevention), OR
      - skip if visited in a prior run (`url_store.contains`, cross-run skip).

    The deferred --update flag later extends ONLY the cross-run half to re-fetch
    rows whose crawl_gen < the current generation. Resume vs. new-pass is decided
    by the queue, never here.
    """
    if url in seen_this_run:
        return False
    return not url_store.contains(url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -k should_fetch -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): add _should_fetch seam for fetch decision"
```

---

### Task 6: `_should_write_manifest()` atomicity guard

**Files:**
- Modify: `scrape_website/scraper.py` (module-level helper)
- Test: `tests/test_crawl_generation.py`

**Interfaces:**
- Produces: `_should_write_manifest(*, crawl_complete: bool, capped: bool, has_entries: bool) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_crawl_generation.py  (append)
from scrape_website.scraper import _should_write_manifest


def test_should_write_manifest_complete_uncapped_with_entries():
    assert _should_write_manifest(crawl_complete=True, capped=False, has_entries=True) is True


def test_should_write_manifest_blocks_incomplete():
    assert _should_write_manifest(crawl_complete=False, capped=False, has_entries=True) is False


def test_should_write_manifest_blocks_capped():
    assert _should_write_manifest(crawl_complete=True, capped=True, has_entries=True) is False


def test_should_write_manifest_blocks_no_entries():
    assert _should_write_manifest(crawl_complete=True, capped=False, has_entries=False) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_crawl_generation.py -k should_write_manifest -v`
Expected: FAIL — cannot import `_should_write_manifest`.

- [ ] **Step 3: Add the helper**

```python
def _should_write_manifest(*, crawl_complete: bool, capped: bool, has_entries: bool) -> bool:
    """Only (re)write manifest.json after a complete, non-capped pass with entries.

    Guards the 'complete & authoritative' invariant: a partial, crashed, or capped
    run leaves the last complete manifest untouched, so downstream ingest /
    deprecate_removed_urls never sees a shrunken set. `capped` is always False
    today; the guard is installed for the deferred --max-pages stream.
    """
    return crawl_complete and not capped and has_entries
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_crawl_generation.py -k should_write_manifest -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_crawl_generation.py
git commit -m "feat(scraper): add manifest-write guard for complete passes"
```

---

### Task 7: Wire generation tracking into `WebScraper`

**Files:**
- Modify: `scrape_website/scraper.py:675-690` (`WebScraper.__init__` fresh/resume block)
- Modify: `scrape_website/scraper.py:1268-1281` (`crawl()` loop + normal-exit flag)
- Modify: `scrape_website/scraper.py:1093-1097` and `:1139-1144` (upsert calls)
- Modify: `scrape_website/scraper.py:1296-1302` (`run()` manifest gate)
- Test: `tests/test_scraper_wiring.py`

**Interfaces:**
- Consumes: `_decide_crawl_gen`, `_should_fetch`, `_should_write_manifest`, `URLStore.max_crawl_gen`, `upsert_metadata(crawl_gen=...)`.
- Produces: `WebScraper.crawl_gen: int`, `WebScraper.seen_this_run: set[str]`, `WebScraper.capped: bool`, `WebScraper.crawl_complete: bool`.

- [ ] **Step 1: Write the failing test**

These tests exercise the three fetch pathways end-to-end at construction level, so
the derive-from-MAX generation logic (`_decide_crawl_gen(max_crawl_gen(), ...)`) is
verified against the actual state.db each pathway leaves behind — not just the pure
helper in Task 3. The three pathways are the entire flag surface:

| Pathway | Invocation | `crawl_gen` | Fetches |
|---|---|---|---|
| **fresh** | `--fresh` | `1` (state cleared) | everything |
| **resume** | no flag, queue non-empty (interrupted) | `max(baseline, 1)` — same gen | the leftover queue |
| **update** | no flag, queue empty (last pass complete) | `baseline + 1` | newly-discovered URLs only; existing skip |

There is no dedicated flag for **update** — it is what a plain re-run does once the
previous pass drained the queue. The deferred `--update` flag (see design §8) only
adds re-fetching of *changed* pages on top of this.

```python
# tests/test_scraper_wiring.py
from scrape_website.scraper import WebScraper, _should_fetch


def _make(tmp_path, **kw):
    scraper = WebScraper("https://example.com/", output_dir=tmp_path, **kw)
    return scraper


def test_fresh_run_starts_generation_one(tmp_path):
    scraper = _make(tmp_path, fresh=True)
    try:
        assert scraper.crawl_gen == 1
        assert scraper.seen_this_run == set()
        assert scraper.capped is False
        assert scraper.crawl_complete is False
    finally:
        scraper.executor.shutdown(wait=False)


def test_resume_keeps_same_generation(tmp_path):
    # A pass that was interrupted mid-crawl: one row saved, queue still non-empty.
    first = _make(tmp_path, fresh=True)
    first.url_store.add("https://example.com/a")
    first.url_store.upsert_metadata(
        "https://example.com/a", filename="a.md", hostname="example.com", crawl_gen=1,
    )
    first.url_store.save_queue([("https://example.com/b", None)])  # leftover → mid-pass
    first.executor.shutdown(wait=False)
    first.url_store.close()

    # Re-invoke without --fresh: queue non-empty + count > 0 → resume the SAME gen.
    second = _make(tmp_path, fresh=False)
    try:
        assert second.crawl_gen == 1  # max(baseline=1, 1) — NOT advanced to 2
    finally:
        second.executor.shutdown(wait=False)


def test_new_pass_advances_generation(tmp_path):
    # First run leaves a row at generation 1 and an empty queue (complete pass).
    first = _make(tmp_path, fresh=True)
    first.url_store.add("https://example.com/a")
    first.url_store.upsert_metadata(
        "https://example.com/a", filename="a.md", hostname="example.com", crawl_gen=1,
    )
    first.url_store.save_queue([])  # completed pass → empty queue
    first.executor.shutdown(wait=False)
    first.url_store.close()

    # Re-invoke without --fresh, empty queue → new (update) pass → generation 2.
    second = _make(tmp_path, fresh=False)
    try:
        assert second.crawl_gen == 2  # baseline=1 + 1
    finally:
        second.executor.shutdown(wait=False)


def test_update_pass_stamps_new_url_at_advanced_gen(tmp_path):
    # Prior complete pass at gen 1.
    first = _make(tmp_path, fresh=True)
    first.url_store.add("https://example.com/old")
    first.url_store.upsert_metadata(
        "https://example.com/old", filename="old.md", hostname="example.com", crawl_gen=1,
    )
    first.url_store.save_queue([])
    first.executor.shutdown(wait=False)
    first.url_store.close()

    # Update pass: gen advances to 2; existing URL skips, a new URL is fetched
    # and stamped at the advanced generation — this is the "update" mechanism.
    second = _make(tmp_path, fresh=False)
    try:
        assert second.crawl_gen == 2
        assert _should_fetch("https://example.com/old", second.seen_this_run, second.url_store) is False
        assert _should_fetch("https://example.com/new", second.seen_this_run, second.url_store) is True

        second.url_store.add("https://example.com/new")
        second.url_store.upsert_metadata(
            "https://example.com/new", filename="new.md", hostname="example.com",
            crawl_gen=second.crawl_gen,
        )
        new_gen = second.url_store.conn.execute(
            "SELECT crawl_gen FROM visited WHERE url='https://example.com/new'"
        ).fetchone()[0]
        old_gen = second.url_store.conn.execute(
            "SELECT crawl_gen FROM visited WHERE url='https://example.com/old'"
        ).fetchone()[0]
        assert new_gen == 2   # newly-discovered page carries the update generation
        assert old_gen == 1   # untouched page keeps its original generation
    finally:
        second.executor.shutdown(wait=False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_scraper_wiring.py -v`
Expected: FAIL — `WebScraper` has no attribute `crawl_gen` (and `_should_fetch` import fails until Task 5 is merged; run Tasks in order).

- [ ] **Step 3a: Compute generation in `__init__`**

Replace the fresh/resume block (`scraper.py:675-690`) with:

```python
        # Handle fresh start vs resume
        resuming = False
        if fresh:
            self.url_store.clear()
            self.urls_to_visit: Deque[tuple[str, str | None]] = deque([(start_url, None)])
            self.logger.info("Fresh start (--fresh): cleared previous state")
        else:
            # Try to resume from checkpoint
            saved_queue = self.url_store.load_queue()
            saved_stats = self.url_store.load_stats()
            if saved_queue and self.url_store.count > 0:
                self.urls_to_visit = saved_queue
                if saved_stats:
                    self.stats.update(saved_stats)
                resuming = True
                self.logger.info(f"Resuming: {self.url_store.count} URLs visited, {len(saved_queue)} in queue")
            else:
                self.urls_to_visit = deque([(start_url, None)])

        # Crawl-generation state. The queue above (not this value) decides
        # fresh/resume/new-pass; crawl_gen only marks which rows this pass fetched.
        self.crawl_gen = _decide_crawl_gen(
            self.url_store.max_crawl_gen(), fresh=fresh, resuming=resuming
        )
        self.seen_this_run: set[str] = set()   # in-run loop prevention (see _should_fetch)
        self.capped = False                    # --max-pages sets this (deferred stream)
        self.crawl_complete = False            # set True only on normal crawl() completion
        self.logger.info(f"Crawl generation: {self.crawl_gen}")
```

- [ ] **Step 3b: Route the loop through `_should_fetch` and flag completion**

Replace the crawl loop body (`scraper.py:1268-1281`):

```python
            while self.urls_to_visit or tasks:
                while self.urls_to_visit and len(tasks) < self.max_concurrent:
                    url, found_on = self.urls_to_visit.popleft()

                    if _should_fetch(url, self.seen_this_run, self.url_store):
                        self.seen_this_run.add(url)
                        self.url_store.add(url)
                        task = asyncio.create_task(self.process_url(url, found_on=found_on))
                        tasks.append(task)

                if tasks:
                    done, tasks = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                    tasks = list(tasks)

            # Loop exited normally (queue drained, no in-flight tasks) → complete pass.
            self.crawl_complete = True

        finally:
```

- [ ] **Step 3c: Pass `crawl_gen` on both upsert calls**

`save_file` (`scraper.py:1093-1097`):

```python
        self.url_store.upsert_metadata(
            url, filename=filename, hostname=self.base_domain,
            title=title, found_on=found_on, file_type="binary",
            content_hash=file_hash, file_size=len(content),
            crawl_gen=self.crawl_gen,
        )
```

`save_text` (`scraper.py:1139-1144`):

```python
        self.url_store.upsert_metadata(
            url, filename=filename, hostname=self.base_domain,
            title=title, file_type="web",
            content_hash=compute_hash(text),
            file_size=len(text.encode()),
            crawl_gen=self.crawl_gen,
        )
```

- [ ] **Step 3d: Gate the manifest write in `run()`**

Replace the manifest block (`scraper.py:1296-1302`):

```python
        # Generate manifest.json — only after a complete, non-capped pass, so a
        # partial/crashed/capped run leaves the last complete manifest intact.
        manifest_files = self.url_store.export_manifest(self.base_domain)
        if _should_write_manifest(
            crawl_complete=self.crawl_complete,
            capped=self.capped,
            has_entries=bool(manifest_files),
        ):
            manifest = build_manifest(manifest_files, self.base_domain)
            manifest_path = self.base_dir / "manifest.json"
            write_manifest(manifest, manifest_path)
            self.logger.info(f"Generated manifest.json: {len(manifest_files)} entries")
        elif manifest_files:
            self.logger.info(
                "Skipped manifest regeneration (incomplete or capped pass); "
                "kept last complete manifest.json"
            )
```

- [ ] **Step 4: Run the wiring test AND the full suite**

Run: `uv run pytest tests/test_scraper_wiring.py -v`
Expected: PASS (4 tests — fresh, resume, new-pass/update, update-stamps-new-url).

Run: `uv run pytest`
Expected: PASS — all tests, including the pre-existing `tests/test_browser_slots.py` (no regression).

- [ ] **Step 5: Commit**

```bash
git add scrape_website/scraper.py tests/test_scraper_wiring.py
git commit -m "feat(scraper): wire crawl-generation tracking into crawl loop"
```

---

### Task 8: Document crawl generations

**Files:**
- Modify: `scrape_website/scraper.py` (comment block immediately above `class URLStore`, currently `scraper.py:422`)

**Interfaces:** none.

- [ ] **Step 1: Add the documentation block above `class URLStore`**

Insert directly above the `class URLStore:` line:

```python
# --- Crawl generations & fetch pathways -------------------------------------
# state.db tracks a per-URL `crawl_gen` (integer) and `last_fetched_at` (UTC
# ISO-8601). A "generation" is one scoped, monotonic crawl pass over the site.
#
#   crawl_gen (control)  — which generation last fetched this row.
#   last_fetched_at (data) — when that fetch happened (freshness/debugging).
#
# Three fetch pathways, selected by --fresh and the queue (NOT by crawl_gen):
#   * fresh   (--fresh)              → clear state, crawl_gen = 1, re-fetch all.
#   * resume  (no flag, queue full)  → an interrupted pass; continue the SAME
#                                       generation (max(baseline, 1)) on the
#                                       leftover queue.
#   * update  (no flag, queue empty) → the last pass completed; start a new
#                                       generation (baseline + 1), discover new
#                                       pages, skip existing ones. This is the
#                                       "run again without wiping" path — it has
#                                       no dedicated flag.
#
# The current generation is DERIVED (see _decide_crawl_gen) from
# COALESCE(MAX(crawl_gen), 0); nothing is stored in the `stats` table. Two
# independent axes: the `queue` table owns resume-vs-new-pass; `crawl_gen` owns
# re-fetch-vs-skip (see _should_fetch). Today `_should_fetch` skips any
# already-visited URL, so `update` only picks up NEW pages. The deferred
# `--update` flag will re-fetch pages whose sitemap <lastmod> changed by making
# `_should_fetch` re-fetch rows with crawl_gen < current — this foundation lays
# that seam WITHOUT changing behavior.
# ----------------------------------------------------------------------------
```

- [ ] **Step 2: Verify nothing broke**

Run: `uv run pytest`
Expected: PASS (comment-only change; all tests still green).

- [ ] **Step 3: Commit**

```bash
git add scrape_website/scraper.py
git commit -m "docs(scraper): document crawl generations and re-fetch modes"
```

---

## Self-Review

**Spec coverage** (design doc §3):
- §3.1 two columns → Task 1 ✅
- §3.2 two axes (queue vs crawl_gen) → Tasks 5 (`_should_fetch`) + 7 (loop wiring), documented Task 8 ✅
- §3.3 derive via COALESCE(MAX) → Tasks 2 + 3 ✅
- §3.4 stamp on successful save → Task 4 (+ Task 7 call sites) ✅
- §3.5 `contains()` decoupling, zero regression → Tasks 5 + 7 (`seen_this_run`, `_should_fetch`) ✅
- §3.6 manifest atomicity → Tasks 6 + 7 (`_should_write_manifest`, `crawl_complete`) ✅
- §7 documentation (4 places): spec ✅ (exists), migration comments → Task 1, skip-logic docstring → Task 5, module mental model → Task 8 ✅
- §6 testing (migration, fresh, resume, atomicity, no-regression) → unit Tasks 1–7 + full-suite gate in Task 7; deep resume/atomicity integration runs on DEV per §6 ✅

**Placeholder scan:** every code step contains full code; test steps contain real assertions; commands have expected output. No TBD/TODO. ✅

**Type consistency:** `crawl_gen: int`, `_decide_crawl_gen(baseline:int,*,fresh:bool,resuming:bool)->int`, `_should_fetch(url:str,seen_this_run:set[str],url_store:URLStore)->bool`, `_should_write_manifest(*,crawl_complete:bool,capped:bool,has_entries:bool)->bool`, `max_crawl_gen()->int`, `upsert_metadata(...,crawl_gen:int|None=None)` — names/signatures match across defining and consuming tasks. ✅

**Deferred (not in this plan, by design):** `--max-pages` and its `capped=True` wiring + S3-mirror partial-authoritative signal; the `--update` flag (formerly called "incremental mode") — sitemap `<lastmod>`, changed/removed handling, removal reconciliation, content-hash write-skip. Hooks (`capped`, `_should_fetch` seam, `crawl_complete`) are installed for them. Terminology: the discovery (EPCC_EXPLORE) and design (DESIGN) docs use "incremental mode"; that is now named "update mode" / `--update`.
