"""Tests for the cross-process browser slot limiter.

Verifies that:
1. Slots can be acquired up to the configured max
2. Acquiring beyond the max returns None (graceful denial)
3. Releasing a slot allows reacquisition
4. Slots are released on process death (flock kernel guarantee)
5. Multiple processes compete correctly for limited slots
"""

import fcntl
import logging
import multiprocessing
import os
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from scrape_website.scraper import (
    _BROWSER_SLOT_DIR,
    _MAX_BROWSER_SLOTS,
    _acquire_browser_slot,
    _release_browser_slot,
)

# Use fork context so child processes inherit module state and can use local references.
# macOS defaults to 'spawn' which requires picklable targets.
_mp = multiprocessing.get_context("fork")


# --- Module-level worker functions (picklable for any start method) ---

def _worker_hold_and_wait(slot_dir, ready_event, release_event):
    """Child: acquire slot, signal parent, wait for release signal."""
    import scrape_website.scraper as mod
    mod._BROWSER_SLOT_DIR = slot_dir
    mod._MAX_BROWSER_SLOTS = 1
    child_logger = logging.getLogger("child")
    fd = _acquire_browser_slot(child_logger)
    assert fd is not None
    ready_event.set()
    release_event.wait(timeout=5)
    _release_browser_slot(fd, child_logger)


def _worker_die_without_release(slot_dir):
    """Child: acquire slot then exit without releasing (simulates crash)."""
    import scrape_website.scraper as mod
    mod._BROWSER_SLOT_DIR = slot_dir
    mod._MAX_BROWSER_SLOTS = 1
    child_logger = logging.getLogger("child")
    fd = _acquire_browser_slot(child_logger)
    assert fd is not None
    os._exit(0)


def _worker_compete(slot_dir, max_slots, worker_id, results_queue):
    """Child: try to acquire slot, report result, hold briefly."""
    import scrape_website.scraper as mod
    mod._BROWSER_SLOT_DIR = slot_dir
    mod._MAX_BROWSER_SLOTS = max_slots
    w_logger = logging.getLogger(f"worker-{worker_id}")
    fd = _acquire_browser_slot(w_logger)
    results_queue.put((worker_id, fd is not None))
    time.sleep(0.5)
    _release_browser_slot(fd, w_logger)


@pytest.fixture
def logger():
    return logging.getLogger("test_browser_slots")


@pytest.fixture(autouse=True)
def clean_slot_dir(tmp_path, monkeypatch):
    """Use a temp directory for slot files so tests don't interfere with each other."""
    slot_dir = tmp_path / "scrape-browser-slots"
    monkeypatch.setattr("scrape_website.scraper._BROWSER_SLOT_DIR", slot_dir)
    return slot_dir


class TestAcquireSlot:
    """Tests for _acquire_browser_slot."""

    def test_acquire_first_slot(self, logger):
        fd = _acquire_browser_slot(logger)
        assert fd is not None
        assert isinstance(fd, int)
        _release_browser_slot(fd, logger)

    def test_acquire_all_slots(self, logger, monkeypatch):
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 3)
        fds = []
        for _ in range(3):
            fd = _acquire_browser_slot(logger)
            assert fd is not None
            fds.append(fd)
        for fd in fds:
            _release_browser_slot(fd, logger)

    def test_deny_beyond_max(self, logger, monkeypatch):
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 2)
        fd1 = _acquire_browser_slot(logger)
        fd2 = _acquire_browser_slot(logger)
        assert fd1 is not None
        assert fd2 is not None

        # Third attempt should fail
        fd3 = _acquire_browser_slot(logger)
        assert fd3 is None

        _release_browser_slot(fd1, logger)
        _release_browser_slot(fd2, logger)

    def test_deny_with_single_slot(self, logger, monkeypatch):
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 1)
        fd1 = _acquire_browser_slot(logger)
        assert fd1 is not None

        fd2 = _acquire_browser_slot(logger)
        assert fd2 is None

        _release_browser_slot(fd1, logger)


class TestReleaseSlot:
    """Tests for _release_browser_slot."""

    def test_release_allows_reacquire(self, logger, monkeypatch):
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 1)

        fd1 = _acquire_browser_slot(logger)
        assert fd1 is not None

        # Can't get another
        assert _acquire_browser_slot(logger) is None

        # Release and try again
        _release_browser_slot(fd1, logger)
        fd2 = _acquire_browser_slot(logger)
        assert fd2 is not None
        _release_browser_slot(fd2, logger)

    def test_release_none_is_noop(self, logger):
        """Releasing None should not raise."""
        _release_browser_slot(None, logger)

    def test_release_invalid_fd_logs_debug(self, logger):
        """Releasing a closed fd should handle the error gracefully."""
        _release_browser_slot(9999, logger)


class TestSlotDirCreation:
    """Tests for slot directory auto-creation."""

    def test_creates_slot_dir(self, logger, tmp_path, monkeypatch):
        slot_dir = tmp_path / "new-dir" / "nested"
        monkeypatch.setattr("scrape_website.scraper._BROWSER_SLOT_DIR", slot_dir)
        fd = _acquire_browser_slot(logger)
        assert fd is not None
        assert slot_dir.exists()
        _release_browser_slot(fd, logger)

    def test_lock_files_visible(self, logger, clean_slot_dir, monkeypatch):
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 2)
        fd1 = _acquire_browser_slot(logger)
        fd2 = _acquire_browser_slot(logger)

        lock_files = list(clean_slot_dir.glob("browser-*.lock"))
        assert len(lock_files) == 2

        _release_browser_slot(fd1, logger)
        _release_browser_slot(fd2, logger)


class TestCrossProcessSlots:
    """Tests verifying flock behavior across OS processes.

    Uses the 'fork' multiprocessing context so child processes inherit the
    monkeypatched _BROWSER_SLOT_DIR without needing to pickle it.
    """

    def test_child_process_holds_slot(self, logger, clean_slot_dir, monkeypatch):
        """A slot held by a child process blocks the parent from acquiring it."""
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 1)

        ready_event = _mp.Event()
        release_event = _mp.Event()

        proc = _mp.Process(
            target=_worker_hold_and_wait,
            args=(clean_slot_dir, ready_event, release_event),
        )
        proc.start()
        ready_event.wait(timeout=5)

        # Parent should be denied while child holds the slot
        fd = _acquire_browser_slot(logger)
        assert fd is None

        # Tell child to release, then parent should succeed
        release_event.set()
        proc.join(timeout=5)

        fd = _acquire_browser_slot(logger)
        assert fd is not None
        _release_browser_slot(fd, logger)

    def test_process_death_releases_slot(self, logger, clean_slot_dir, monkeypatch):
        """When a process dies (OOM-kill, crash), flock auto-releases the slot."""
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", 1)

        proc = _mp.Process(target=_worker_die_without_release, args=(clean_slot_dir,))
        proc.start()
        proc.join(timeout=5)

        # Slot should be available again (kernel released flock on process exit)
        fd = _acquire_browser_slot(logger)
        assert fd is not None
        _release_browser_slot(fd, logger)

    def test_multiple_processes_compete(self, logger, clean_slot_dir, monkeypatch):
        """Only MAX slots are granted when many processes try simultaneously."""
        max_slots = 3
        num_workers = 6
        monkeypatch.setattr("scrape_website.scraper._MAX_BROWSER_SLOTS", max_slots)

        results = _mp.Queue()

        procs = []
        for i in range(num_workers):
            p = _mp.Process(
                target=_worker_compete,
                args=(clean_slot_dir, max_slots, i, results),
            )
            procs.append(p)
            p.start()

        for p in procs:
            p.join(timeout=10)

        acquired = 0
        denied = 0
        while not results.empty():
            _, got_slot = results.get_nowait()
            if got_slot:
                acquired += 1
            else:
                denied += 1

        # Exactly max_slots should have succeeded, the rest denied
        assert acquired == max_slots
        assert denied == num_workers - max_slots


class TestEnvVarConfig:
    """Tests for SCRAPE_MAX_BROWSERS environment variable."""

    def test_default_is_three(self):
        assert _MAX_BROWSER_SLOTS == 3

    def test_env_var_override(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_MAX_BROWSERS", "5")
        # Re-import to pick up the env var
        import importlib
        import scrape_website.scraper as mod
        importlib.reload(mod)
        assert mod._MAX_BROWSER_SLOTS == 5
        # Restore
        monkeypatch.delenv("SCRAPE_MAX_BROWSERS")
        importlib.reload(mod)
