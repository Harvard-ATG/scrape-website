# tests/test_scraper_wiring.py
from scrape_website.scraper import WebsiteScraper, _should_fetch


def _make(tmp_path, **kw):
    scraper = WebsiteScraper("https://example.com/", output_dir=tmp_path, **kw)
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
