"""Tests for bet logging, closing lines, and settlement."""

import pytest

from bet_tracker import (
    BetNotFoundError,
    BetStatus,
    BetTracker,
    DuplicateBetError,
    InvalidAmountError,
    InvalidSettlementError,
)


def _make_tracker() -> BetTracker:
    return BetTracker(":memory:")


def _place_sample_bet(t: BetTracker, **overrides: object) -> int:
    defaults = dict(
        sport="NFL",
        event="Chiefs vs Ravens",
        market="moneyline",
        selection="Chiefs ML",
        odds=-110,
        stake=50.0,
    )
    defaults.update(overrides)
    return t.place_bet(**defaults)  # type: ignore[arg-type]


class TestPlaceBet:
    def test_returns_id(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            assert isinstance(bet_id, int)
            assert bet_id > 0

    def test_bet_is_open(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            bet = t.get_bet(bet_id)
            assert bet.status is BetStatus.OPEN

    def test_odds_converted(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t, odds=-200)
            bet = t.get_bet(bet_id)
            assert bet.odds_american == -200
            assert bet.odds_decimal == pytest.approx(1.5)

    def test_optional_fields(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(
                t,
                book="FanDuel",
                model_prob=0.60,
                fair_prob=0.50,
                edge=0.10,
                kelly_fraction=0.033,
                league="AFC",
                notes="Strong signal",
                tags=["week14", "primetime"],
            )
            bet = t.get_bet(bet_id)
            assert bet.book == "FanDuel"
            assert bet.model_prob == 0.60
            assert bet.tags == ["week14", "primetime"]

    def test_zero_odds_raises(self):
        with _make_tracker() as t, pytest.raises(ValueError):
            _place_sample_bet(t, odds=0)

    def test_zero_stake_raises(self):
        with _make_tracker() as t, pytest.raises(InvalidAmountError):
            _place_sample_bet(t, stake=0.0)

    def test_negative_stake_raises(self):
        with _make_tracker() as t, pytest.raises(InvalidAmountError):
            _place_sample_bet(t, stake=-10.0)

    def test_duplicate_external_id_raises(self):
        with _make_tracker() as t:
            _place_sample_bet(t, external_id="abc123")
            with pytest.raises(DuplicateBetError):
                _place_sample_bet(t, external_id="abc123")

    def test_list_bets(self):
        with _make_tracker() as t:
            _place_sample_bet(t, sport="NFL")
            _place_sample_bet(t, sport="NBA")
            assert len(t.list_bets()) == 2
            assert len(t.list_bets(sport="NFL")) == 1

    def test_get_nonexistent_raises(self):
        with _make_tracker() as t, pytest.raises(BetNotFoundError):
            t.get_bet(9999)


class TestClosingOdds:
    def test_set_closing_odds(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            t.set_closing_odds(bet_id, -130)
            bet = t.get_bet(bet_id)
            assert bet.closing_odds_american == -130
            assert bet.closing_odds_decimal is not None
            assert bet.closing_odds_decimal == pytest.approx(1.769, rel=0.01)

    def test_closing_odds_nonexistent_raises(self):
        with _make_tracker() as t, pytest.raises(BetNotFoundError):
            t.set_closing_odds(9999, -130)

    def test_closing_odds_zero_raises(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            with pytest.raises(ValueError):
                t.set_closing_odds(bet_id, 0)


class TestSettle:
    def test_win(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t, odds=-110, stake=110.0)
            t.settle(bet_id, BetStatus.WON)
            bet = t.get_bet(bet_id)
            assert bet.status is BetStatus.WON
            assert bet.result_amount is not None
            assert bet.result_amount == pytest.approx(100.0, rel=0.01)
            assert bet.settled_at is not None

    def test_loss(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t, stake=50.0)
            t.settle(bet_id, BetStatus.LOST)
            bet = t.get_bet(bet_id)
            assert bet.result_amount == -50.0

    def test_push(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            t.settle(bet_id, BetStatus.PUSH)
            bet = t.get_bet(bet_id)
            assert bet.result_amount == 0.0

    def test_void(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            t.settle(bet_id, BetStatus.VOID)
            bet = t.get_bet(bet_id)
            assert bet.result_amount == 0.0

    def test_custom_result_amount(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            t.settle(bet_id, BetStatus.WON, result_amount=42.0)
            bet = t.get_bet(bet_id)
            assert bet.result_amount == 42.0

    def test_double_settle_raises(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            t.settle(bet_id, BetStatus.WON)
            with pytest.raises(InvalidSettlementError):
                t.settle(bet_id, BetStatus.LOST)

    def test_settle_as_open_raises(self):
        with _make_tracker() as t:
            bet_id = _place_sample_bet(t)
            with pytest.raises(InvalidSettlementError):
                t.settle(bet_id, BetStatus.OPEN)

    def test_settle_nonexistent_raises(self):
        with _make_tracker() as t, pytest.raises(BetNotFoundError):
            t.settle(9999, BetStatus.WON)


class TestListBetsDateFilter:
    """list_bets start/end filter tests."""

    def _make_tracker(self) -> BetTracker:
        t = BetTracker(":memory:")
        # Three bets on different dates — use placed_at via direct DB insert
        # to control timestamps deterministically.
        conn = t._conn
        for i, date in enumerate(["2024-01-10", "2024-02-15", "2024-03-20"], 1):
            conn.execute(
                """
                INSERT INTO bets
                  (sport, league, event, market, selection,
                   odds_american, odds_decimal, stake, book,
                   model_prob, fair_prob, edge, kelly_fraction,
                   status, placed_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "NFL",
                    None,
                    f"game{i}",
                    "moneyline",
                    "home",
                    -110,
                    1.909,
                    100.0,
                    "FanDuel",
                    0.55,
                    0.50,
                    0.05,
                    0.10,
                    "open",
                    f"{date}T12:00:00",
                ),
            )
        conn.commit()
        return t

    def test_start_filter_excludes_earlier(self):
        t = self._make_tracker()
        bets = t.list_bets(start="2024-02-01")
        placed = [b.placed_at for b in bets]
        assert all(p >= "2024-02-01" for p in placed)
        assert len(bets) == 2

    def test_end_filter_excludes_later(self):
        t = self._make_tracker()
        bets = t.list_bets(end="2024-02-01")
        assert len(bets) == 1

    def test_start_and_end_filter(self):
        t = self._make_tracker()
        bets = t.list_bets(start="2024-02-01", end="2024-03-01")
        assert len(bets) == 1

    def test_no_date_filter_returns_all(self):
        t = self._make_tracker()
        assert len(t.list_bets()) == 3

    def test_date_filter_combined_with_sport(self):
        t = self._make_tracker()
        bets = t.list_bets(sport="NFL", start="2024-02-01")
        assert len(bets) == 2
