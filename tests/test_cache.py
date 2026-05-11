"""
Tests for the SQLite cache layer.

Covers the highest-risk paths identified in the review findings:
- M-7: Async wrapper (aset/aget) does not block the event loop.
- M-8: WAL journal mode is active; concurrent writes do not deadlock.
- L-9: CacheLayer with an unwritable parent path raises CacheError, not
       PermissionError.

All tests are hermetic: they use tmp_path so no on-disk state leaks between
runs, and no network calls are made.
"""

import asyncio
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from dhm.cache.sqlite import CacheLayer
from dhm.core.exceptions import CacheError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache(tmp_path: Path, **kwargs) -> CacheLayer:
    """Create a CacheLayer backed by a temp DB."""
    db_path = tmp_path / "test_cache.db"
    return CacheLayer(db_path=db_path, **kwargs)


# ===========================================================================
# 1. TTL expiry
# ===========================================================================


class TestTTLExpiry:
    """TTL-based expiration tests."""

    def test_entry_missing_after_ttl_expiry(self, tmp_path: Path):
        """Set with ttl_seconds=1, sleep 2 s, get returns None.

        We sleep 2 s (not 1.1 s) because SQLite's datetime('now') has
        second-level granularity; sleeping for only 1.1 s may land on the
        same second boundary and leave the row technically unexpired.
        """
        cache = _make_cache(tmp_path)
        cache.set("mykey", {"data": 42}, ttl_seconds=1)

        # Confirm it exists immediately
        assert cache.get_value("mykey") == {"data": 42}

        # Wait past expiry — 2 s ensures we cross a full SQLite second boundary
        time.sleep(2)

        assert cache.get_value("mykey") is None

    def test_get_returns_none_for_expired_entry(self, tmp_path: Path):
        """get() (not just get_value) also returns None for expired entries.

        Uses a negative TTL (-1 s) to place the expiry in the past immediately,
        avoiding a real sleep and SQLite second-boundary issues.
        """
        cache = _make_cache(tmp_path)
        # ttl_seconds=-1 puts expires_at one second in the past, which is
        # reliably expired from SQLite's perspective.
        cache.set("k", "v", ttl_seconds=-1)
        assert cache.get("k") is None


# ===========================================================================
# 2. Set + get round-trip
# ===========================================================================


class TestSetGetRoundTrip:
    """Basic set/get round-trip tests."""

    def test_simple_string_value(self, tmp_path: Path):
        """A plain string value round-trips correctly."""
        cache = _make_cache(tmp_path)
        cache.set("hello", "world")
        assert cache.get_value("hello") == "world"

    def test_dict_value(self, tmp_path: Path):
        """A nested dict value round-trips correctly."""
        cache = _make_cache(tmp_path)
        value = {"name": "requests", "version": "2.28.0", "score": 95.5}
        cache.set("pkg:requests", value)
        assert cache.get_value("pkg:requests") == value

    def test_list_value(self, tmp_path: Path):
        """A list value round-trips correctly."""
        cache = _make_cache(tmp_path)
        value = [1, "two", {"three": 3}]
        cache.set("list_key", value)
        assert cache.get_value("list_key") == value

    def test_get_returns_tuple_with_none_etag_when_not_set(self, tmp_path: Path):
        """get() returns (value, None) when no ETag was stored."""
        cache = _make_cache(tmp_path)
        cache.set("k", "v")
        result = cache.get("k")
        assert result is not None
        val, etag = result
        assert val == "v"
        assert etag is None

    def test_get_returns_tuple_with_etag_when_set(self, tmp_path: Path):
        """get() returns (value, etag) when an ETag was stored."""
        cache = _make_cache(tmp_path)
        cache.set("k", "v", etag="abc123")
        result = cache.get("k")
        assert result is not None
        val, etag = result
        assert val == "v"
        assert etag == "abc123"

    def test_missing_key_returns_none(self, tmp_path: Path):
        """get_value() returns None for a key that was never set."""
        cache = _make_cache(tmp_path)
        assert cache.get_value("nonexistent") is None


# ===========================================================================
# 3. Invalidate by pattern
# ===========================================================================


class TestInvalidateByPattern:
    """Pattern-based invalidation tests."""

    def test_invalidate_github_pattern_removes_only_github_entries(self, tmp_path: Path):
        """invalidate('github:%') removes only github-prefixed keys."""
        cache = _make_cache(tmp_path)
        cache.set("github:psf/requests", {"stars": 50000})
        cache.set("github:encode/httpx", {"stars": 10000})
        cache.set("pypi:requests", {"version": "2.28.0"})
        cache.set("osv:vulns:requests", [])

        removed = cache.invalidate("github:%")
        assert removed == 2

        assert cache.get_value("github:psf/requests") is None
        assert cache.get_value("github:encode/httpx") is None
        # PyPI and OSV entries must survive
        assert cache.get_value("pypi:requests") is not None
        assert cache.get_value("osv:vulns:requests") is not None

    def test_invalidate_pypi_pattern(self, tmp_path: Path):
        """invalidate('pypi:%') removes only pypi-prefixed keys."""
        cache = _make_cache(tmp_path)
        cache.set("pypi:requests", {"v": "2.28.0"})
        cache.set("pypi:click", {"v": "8.0.0"})
        cache.set("github:click", {"stars": 1000})

        removed = cache.invalidate("pypi:%")
        assert removed == 2
        assert cache.get_value("github:click") is not None

    def test_invalidate_nonexistent_pattern_returns_zero(self, tmp_path: Path):
        """invalidate with a pattern matching nothing returns 0."""
        cache = _make_cache(tmp_path)
        cache.set("pypi:requests", {"v": "2.28.0"})
        assert cache.invalidate("nope:%") == 0


# ===========================================================================
# 4. Cleanup expired entries
# ===========================================================================


class TestCleanup:
    """cleanup() removes only expired entries."""

    def test_cleanup_removes_expired_but_keeps_fresh(self, tmp_path: Path):
        """cleanup() removes the expired entry and keeps the fresh one.

        Uses ttl_seconds=-1 (past expiry) rather than a real sleep to avoid
        SQLite second-boundary timing issues.
        """
        cache = _make_cache(tmp_path)
        # Immediately-expired entry (ttl = -1 puts expires_at in the past)
        cache.set("expired", "old", ttl_seconds=-1)
        # Fresh entry (1 hour TTL)
        cache.set("fresh", "new", ttl_seconds=3600)

        removed = cache.cleanup()
        assert removed == 1

        assert cache.get_value("expired") is None
        assert cache.get_value("fresh") == "new"

    def test_cleanup_returns_zero_when_nothing_expired(self, tmp_path: Path):
        """cleanup() returns 0 when there are no expired entries."""
        cache = _make_cache(tmp_path)
        cache.set("fresh", "data", ttl_seconds=3600)
        assert cache.cleanup() == 0


# ===========================================================================
# 5. Clear
# ===========================================================================


class TestClear:
    """clear() removes all entries and returns the count."""

    def test_clear_removes_everything(self, tmp_path: Path):
        """clear() removes all entries regardless of expiry."""
        cache = _make_cache(tmp_path)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)

        removed = cache.clear()
        assert removed == 3

        assert cache.get_value("a") is None
        assert cache.get_value("b") is None
        assert cache.get_value("c") is None

    def test_clear_returns_zero_on_empty_cache(self, tmp_path: Path):
        """clear() on an already-empty cache returns 0."""
        cache = _make_cache(tmp_path)
        assert cache.clear() == 0

    def test_clear_counts_both_expired_and_fresh(self, tmp_path: Path):
        """clear() counts all entries, including those that haven't expired yet."""
        cache = _make_cache(tmp_path)
        cache.set("short", "v", ttl_seconds=-1)  # already expired
        cache.set("long", "v", ttl_seconds=3600)

        removed = cache.clear()
        assert removed == 2


# ===========================================================================
# 6. WAL mode is active (M-8)
# ===========================================================================


class TestWALMode:
    """Verify that WAL journal mode is enabled on the SQLite database."""

    def test_wal_journal_mode_is_on(self, tmp_path: Path):
        """After CacheLayer initialises, PRAGMA journal_mode returns 'wal'."""
        cache = _make_cache(tmp_path)
        conn = sqlite3.connect(cache.db_path)
        try:
            row = conn.execute("PRAGMA journal_mode;").fetchone()
            journal_mode = row[0] if row else ""
        finally:
            conn.close()

        assert journal_mode == "wal", (
            f"Expected WAL journal mode but got '{journal_mode}'. "
            "M-8 fix may not be active."
        )


# ===========================================================================
# 7. mkdir failure raises CacheError (L-9)
# ===========================================================================


class TestMkdirFailureRaisesCacheError:
    """L-9: PermissionError from mkdir must be wrapped as CacheError."""

    def test_unwritable_parent_raises_cache_error_not_permission_error(self, tmp_path: Path):
        """Mocking Path.mkdir to raise PermissionError → CacheError is raised."""
        bad_path = tmp_path / "nope" / "cache.db"

        with patch.object(Path, "mkdir", side_effect=PermissionError("read-only")):
            with pytest.raises(CacheError):
                CacheLayer(db_path=bad_path)

    def test_cache_error_not_permission_error_specifically(self, tmp_path: Path):
        """The raised exception is CacheError, not PermissionError."""
        bad_path = tmp_path / "nope" / "cache.db"

        with patch.object(Path, "mkdir", side_effect=PermissionError("read-only")):
            try:
                CacheLayer(db_path=bad_path)
                pytest.fail("Expected CacheError to be raised")
            except CacheError:
                pass  # Correct — we expect CacheError
            except PermissionError:
                pytest.fail(
                    "Got PermissionError instead of CacheError. "
                    "L-9 fix may not be active."
                )


# ===========================================================================
# 8. Async wrapper smoke test (M-7)
# ===========================================================================


class TestAsyncWrapper:
    """M-7: Async aset/aget wrappers work correctly."""

    @pytest.mark.asyncio
    async def test_aset_aget_round_trip(self, tmp_path: Path):
        """aset + aget round-trips a value correctly."""
        cache = _make_cache(tmp_path)
        await cache.aset("async_key", {"value": 42})
        result = await cache.aget("async_key")
        assert result is not None
        value, _etag = result
        assert value == {"value": 42}

    @pytest.mark.asyncio
    async def test_aset_then_sync_get(self, tmp_path: Path):
        """Value written via aset is readable via the synchronous get."""
        cache = _make_cache(tmp_path)
        await cache.aset("k", "hello")
        assert cache.get_value("k") == "hello"

    @pytest.mark.asyncio
    async def test_aget_returns_none_for_missing_key(self, tmp_path: Path):
        """aget returns None for a key that was never set."""
        cache = _make_cache(tmp_path)
        result = await cache.aget("missing")
        assert result is None

    @pytest.mark.asyncio
    async def test_adelete_removes_entry(self, tmp_path: Path):
        """adelete removes the entry; subsequent aget returns None."""
        cache = _make_cache(tmp_path)
        await cache.aset("to_delete", "value")
        deleted = await cache.adelete("to_delete")
        assert deleted is True
        result = await cache.aget("to_delete")
        assert result is None

    @pytest.mark.asyncio
    async def test_concurrent_aset_calls(self, tmp_path: Path):
        """Multiple concurrent aset calls complete without error (M-7 smoke)."""
        cache = _make_cache(tmp_path)

        async def write(i: int) -> None:
            await cache.aset(f"key:{i}", {"index": i})

        await asyncio.gather(*[write(i) for i in range(20)])

        # Spot-check a few entries
        for i in range(20):
            result = await cache.aget(f"key:{i}")
            assert result is not None
            val, _ = result
            assert val == {"index": i}


# ===========================================================================
# 9. Concurrent writes don't deadlock (M-8)
# ===========================================================================


class TestConcurrentWrites:
    """M-8: WAL mode prevents database-is-locked errors under concurrent writes."""

    def test_threaded_concurrent_writes_no_operational_error(self, tmp_path: Path):
        """~10 threads writing to the same cache must not raise OperationalError."""
        cache = _make_cache(tmp_path)
        errors: list[Exception] = []

        def worker(thread_id: int) -> None:
            try:
                for j in range(5):
                    cache.set(f"thread:{thread_id}:item:{j}", {"t": thread_id, "j": j})
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        operational_errors = [e for e in errors if isinstance(e, sqlite3.OperationalError)]
        assert not operational_errors, (
            f"Got OperationalError(s) under concurrent writes: {operational_errors}. "
            "WAL mode (M-8 fix) should prevent this."
        )
        # All other errors (e.g. CacheError wrapping sqlite errors) also fail the test
        assert not errors, f"Unexpected errors during concurrent writes: {errors}"

    @pytest.mark.asyncio
    async def test_asyncio_concurrent_aset_no_error(self, tmp_path: Path):
        """asyncio.gather with many aset calls does not raise OperationalError."""
        cache = _make_cache(tmp_path)

        async def write(i: int) -> None:
            await cache.aset(f"async:{i}", i)

        # Run 30 concurrent writes
        await asyncio.gather(*[write(i) for i in range(30)])

        # Verify all writes landed
        for i in range(30):
            result = await cache.aget(f"async:{i}")
            assert result is not None, f"Expected key 'async:{i}' to exist after concurrent writes"
            val, _ = result
            assert val == i
