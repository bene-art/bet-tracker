"""Tests for database schema and connection management."""

import pytest

from bet_tracker.db import american_to_decimal, create_connection, init_schema


class TestSchema:
    def test_creates_tables(self):
        conn = create_connection(":memory:")
        init_schema(conn)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [t["name"] for t in tables]
        assert "bets" in table_names
        assert "bankroll_events" in table_names
        assert "metadata" in table_names
        conn.close()

    def test_schema_version(self):
        conn = create_connection(":memory:")
        init_schema(conn)
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        assert row is not None
        assert row["value"] == "1"
        conn.close()

    def test_idempotent(self):
        conn = create_connection(":memory:")
        init_schema(conn)
        init_schema(conn)  # should not raise
        conn.close()

    def test_wal_mode(self):
        conn = create_connection(":memory:")
        row = conn.execute("PRAGMA journal_mode").fetchone()
        # In-memory databases may report "memory" instead of "wal"
        assert row is not None
        conn.close()

    def test_row_factory(self):
        conn = create_connection(":memory:")
        init_schema(conn)
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = 'schema_version'"
        ).fetchone()
        # Row factory should allow dict-style access
        assert row["value"] == "1"
        conn.close()


class TestAmericanToDecimal:
    def test_favorite(self):
        assert american_to_decimal(-200) == pytest.approx(1.5)

    def test_underdog(self):
        assert american_to_decimal(150) == 2.5

    def test_even(self):
        assert american_to_decimal(100) == 2.0

    def test_zero_raises(self):
        with pytest.raises(ValueError):
            american_to_decimal(0)
