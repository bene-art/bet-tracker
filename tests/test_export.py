"""Tests for CSV and JSON export."""

from __future__ import annotations

import csv
import json
import tempfile
from pathlib import Path

from bet_tracker import BetStatus, BetTracker


def _make_tracker_with_bet() -> BetTracker:
    t = BetTracker(":memory:")
    b = t.place_bet(
        sport="NFL",
        event="A vs B",
        market="moneyline",
        selection="A ML",
        odds=-110,
        stake=50.0,
        book="FanDuel",
    )
    t.settle(b, BetStatus.WON)
    return t


class TestCSVExport:
    def test_writes_file(self):
        t = _make_tracker_with_bet()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        t.export_csv(path)
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["sport"] == "NFL"
        assert rows[0]["status"] == "won"
        Path(path).unlink()

    def test_empty_db(self):
        t = BetTracker(":memory:")
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = f.name
        t.export_csv(path)
        with open(path) as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 0
        Path(path).unlink()


class TestJSONExport:
    def test_writes_file(self):
        t = _make_tracker_with_bet()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        t.export_json(path)
        with open(path) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["sport"] == "NFL"
        assert data[0]["status"] == "won"
        Path(path).unlink()

    def test_round_trip(self):
        t = _make_tracker_with_bet()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        t.export_json(path)
        with open(path) as f:
            data = json.load(f)
        assert data[0]["odds_american"] == -110
        assert abs(data[0]["odds_decimal"] - 1.909) < 0.01
        Path(path).unlink()
