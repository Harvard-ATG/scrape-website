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
