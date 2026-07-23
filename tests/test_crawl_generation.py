import sqlite3
from pathlib import Path

from scrape_website.scraper import URLStore, _decide_crawl_gen


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
