"""CSV and JSON export for bet history."""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

_BET_COLUMNS = [
    "id",
    "external_id",
    "sport",
    "league",
    "event",
    "market",
    "selection",
    "odds_american",
    "odds_decimal",
    "stake",
    "book",
    "model_prob",
    "fair_prob",
    "edge",
    "kelly_fraction",
    "closing_odds_american",
    "closing_odds_decimal",
    "status",
    "result_amount",
    "settled_at",
    "placed_at",
    "notes",
    "tags",
]


def write_csv(conn: sqlite3.Connection, path: str | Path) -> None:
    """Export all bets to a CSV file."""
    rows = conn.execute("SELECT * FROM bets ORDER BY id").fetchall()
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=_BET_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row[col] for col in _BET_COLUMNS})


def write_json(conn: sqlite3.Connection, path: str | Path) -> None:
    """Export all bets to a JSON file."""
    rows = conn.execute("SELECT * FROM bets ORDER BY id").fetchall()
    data = [{col: row[col] for col in _BET_COLUMNS} for row in rows]
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
