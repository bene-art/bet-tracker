"""SQLite schema and connection management."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = 1

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS bets (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    external_id            TEXT UNIQUE,
    sport                  TEXT NOT NULL,
    league                 TEXT,
    event                  TEXT NOT NULL,
    market                 TEXT NOT NULL,
    selection              TEXT NOT NULL,
    odds_american          INTEGER NOT NULL,
    odds_decimal           REAL NOT NULL,
    stake                  REAL NOT NULL,
    book                   TEXT,
    model_prob             REAL,
    fair_prob              REAL,
    edge                   REAL,
    kelly_fraction         REAL,
    closing_odds_american  INTEGER,
    closing_odds_decimal   REAL,
    status                 TEXT NOT NULL DEFAULT 'open'
                           CHECK (status IN ('open','won','lost','push','void')),
    result_amount          REAL,
    settled_at             TEXT,
    placed_at              TEXT NOT NULL,
    notes                  TEXT,
    tags                   TEXT
);

CREATE TABLE IF NOT EXISTS bankroll_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type    TEXT NOT NULL,
    amount        REAL NOT NULL,
    balance_after REAL NOT NULL,
    note          TEXT,
    created_at    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bets_status    ON bets(status);
CREATE INDEX IF NOT EXISTS idx_bets_sport     ON bets(sport);
CREATE INDEX IF NOT EXISTS idx_bets_placed_at ON bets(placed_at);
CREATE INDEX IF NOT EXISTS idx_bets_book      ON bets(book);
CREATE INDEX IF NOT EXISTS idx_bankroll_created_at
    ON bankroll_events(created_at);
"""


def create_connection(db_path: str | Path) -> sqlite3.Connection:
    """Open a SQLite connection with WAL mode and foreign keys."""
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    """Create tables and indexes if they don't exist."""
    conn.executescript(_SCHEMA_SQL)
    row = conn.execute(
        "SELECT value FROM metadata WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)),
        )
        conn.commit()


def american_to_decimal(odds: int) -> float:
    """Convert American odds to decimal odds.

    Duplicated from betting-math-kit to keep zero-dependency promise.
    """
    if odds == 0:
        raise ValueError("American odds cannot be 0")
    if odds > 0:
        return 1.0 + (odds / 100.0)
    return 1.0 + (100.0 / abs(odds))
