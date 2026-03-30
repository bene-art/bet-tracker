"""Tests for performance queries."""

import pytest

from bet_tracker import BetStatus, BetTracker


def _make_tracker_with_bets() -> BetTracker:
    t = BetTracker(":memory:")
    # Bet 1: NFL win at -110, stake 110
    b1 = t.place_bet(
        sport="NFL",
        event="A vs B",
        market="moneyline",
        selection="A",
        odds=-110,
        stake=110.0,
        book="FanDuel",
        model_prob=0.60,
    )
    t.settle(b1, BetStatus.WON)  # profit = 100

    # Bet 2: NBA loss at +150, stake 50
    b2 = t.place_bet(
        sport="NBA",
        event="C vs D",
        market="moneyline",
        selection="C",
        odds=150,
        stake=50.0,
        book="DraftKings",
        model_prob=0.40,
    )
    t.settle(b2, BetStatus.LOST)  # loss = -50

    # Bet 3: NFL loss at -200, stake 200
    b3 = t.place_bet(
        sport="NFL",
        event="E vs F",
        market="spread",
        selection="E -3.5",
        odds=-200,
        stake=200.0,
        book="FanDuel",
        model_prob=0.70,
    )
    t.settle(b3, BetStatus.LOST)  # loss = -200

    # Bet 4: open bet
    t.place_bet(
        sport="NFL",
        event="G vs H",
        market="moneyline",
        selection="G",
        odds=-110,
        stake=55.0,
    )

    return t


class TestPnL:
    def test_total_pnl(self):
        t = _make_tracker_with_bets()
        # 100 - 50 - 200 = -150
        assert t.pnl() == pytest.approx(-150.0, rel=0.01)

    def test_pnl_by_sport(self):
        t = _make_tracker_with_bets()
        # NFL: 100 - 200 = -100
        assert t.pnl(sport="NFL") == pytest.approx(-100.0, rel=0.01)
        # NBA: -50
        assert t.pnl(sport="NBA") == pytest.approx(-50.0)

    def test_pnl_by_book(self):
        t = _make_tracker_with_bets()
        # FanDuel: 100 - 200 = -100
        assert t.pnl(book="FanDuel") == pytest.approx(-100.0, rel=0.01)

    def test_empty_pnl(self):
        t = BetTracker(":memory:")
        assert t.pnl() == 0.0


class TestROI:
    def test_total_roi(self):
        t = _make_tracker_with_bets()
        # PnL: -150, wagered: 110+50+200 = 360
        assert t.roi() == pytest.approx(-150.0 / 360.0, rel=0.01)

    def test_empty_roi(self):
        t = BetTracker(":memory:")
        assert t.roi() == 0.0


class TestWinRate:
    def test_total_win_rate(self):
        t = _make_tracker_with_bets()
        # 1 win, 2 losses = 1/3
        assert t.win_rate() == pytest.approx(1.0 / 3.0)

    def test_win_rate_by_sport(self):
        t = _make_tracker_with_bets()
        # NFL: 1 win, 1 loss = 0.5
        assert t.win_rate(sport="NFL") == pytest.approx(0.5)
        # NBA: 0 wins, 1 loss = 0.0
        assert t.win_rate(sport="NBA") == 0.0

    def test_empty_win_rate(self):
        t = BetTracker(":memory:")
        assert t.win_rate() == 0.0


class TestSummary:
    def test_returns_dict(self):
        t = _make_tracker_with_bets()
        s = t.summary()
        assert "pnl" in s
        assert "roi" in s
        assert "win_rate" in s
        assert "total_bets" in s
        assert "open_bets" in s

    def test_open_bets_counted(self):
        t = _make_tracker_with_bets()
        s = t.summary()
        assert s["open_bets"] == 1


class TestCLVSummary:
    def test_no_closing_odds(self):
        t = _make_tracker_with_bets()
        clv = t.clv_summary()
        assert clv["sample_size"] == 0

    def test_with_closing_odds(self):
        t = BetTracker(":memory:")
        b1 = t.place_bet(
            sport="NFL",
            event="A vs B",
            market="ml",
            selection="A",
            odds=-110,
            stake=50.0,
        )
        t.set_closing_odds(b1, -130)

        b2 = t.place_bet(
            sport="NFL",
            event="C vs D",
            market="ml",
            selection="C",
            odds=-110,
            stake=50.0,
        )
        t.set_closing_odds(b2, -105)

        clv = t.clv_summary()
        assert clv["sample_size"] == 2
        # -110 -> -130: line moved toward us (positive CLV)
        # -110 -> -105: line moved away (negative CLV)
        assert clv["pct_positive"] == 0.5
