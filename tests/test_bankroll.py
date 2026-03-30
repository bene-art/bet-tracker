"""Tests for bankroll tracking."""

import pytest

from bet_tracker import (
    BetStatus,
    BetTracker,
    InsufficientBalanceError,
    InvalidAmountError,
)


def _make_tracker() -> BetTracker:
    return BetTracker(":memory:")


class TestDepositsWithdrawals:
    def test_initial_balance_zero(self):
        with _make_tracker() as t:
            assert t.balance() == 0.0

    def test_deposit(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            assert t.balance() == 1000.0

    def test_multiple_deposits(self):
        with _make_tracker() as t:
            t.deposit(500.0)
            t.deposit(300.0)
            assert t.balance() == 800.0

    def test_withdraw(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            t.withdraw(200.0)
            assert t.balance() == 800.0

    def test_withdraw_exceeds_balance_raises(self):
        with _make_tracker() as t:
            t.deposit(100.0)
            with pytest.raises(InsufficientBalanceError):
                t.withdraw(200.0)

    def test_zero_deposit_raises(self):
        with _make_tracker() as t, pytest.raises(InvalidAmountError):
            t.deposit(0.0)

    def test_negative_deposit_raises(self):
        with _make_tracker() as t, pytest.raises(InvalidAmountError):
            t.deposit(-50.0)

    def test_zero_withdrawal_raises(self):
        with _make_tracker() as t:
            t.deposit(100.0)
            with pytest.raises(InvalidAmountError):
                t.withdraw(0.0)

    def test_deposit_returns_event_id(self):
        with _make_tracker() as t:
            eid = t.deposit(100.0)
            assert isinstance(eid, int)
            assert eid > 0


class TestBankrollWithBets:
    def test_bet_deducts_balance(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            t.place_bet(
                sport="NFL",
                event="A vs B",
                market="ml",
                selection="A",
                odds=-110,
                stake=100.0,
            )
            assert t.balance() == 900.0

    def test_bet_exceeds_balance_raises(self):
        with _make_tracker() as t:
            t.deposit(50.0)
            with pytest.raises(InsufficientBalanceError):
                t.place_bet(
                    sport="NFL",
                    event="A vs B",
                    market="ml",
                    selection="A",
                    odds=-110,
                    stake=100.0,
                )

    def test_win_credits_balance(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            bet_id = t.place_bet(
                sport="NFL",
                event="A vs B",
                market="ml",
                selection="A",
                odds=100,
                stake=100.0,
            )
            # Balance: 1000 - 100 = 900
            assert t.balance() == 900.0
            t.settle(bet_id, BetStatus.WON)
            # Win at +100: profit = 100, return stake + profit = 200
            assert t.balance() == 1100.0

    def test_loss_no_credit(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            bet_id = t.place_bet(
                sport="NFL",
                event="A vs B",
                market="ml",
                selection="A",
                odds=-110,
                stake=100.0,
            )
            assert t.balance() == 900.0
            t.settle(bet_id, BetStatus.LOST)
            # Stake already deducted, no credit
            assert t.balance() == 900.0

    def test_push_returns_stake(self):
        with _make_tracker() as t:
            t.deposit(1000.0)
            bet_id = t.place_bet(
                sport="NFL",
                event="A vs B",
                market="ml",
                selection="A",
                odds=-110,
                stake=100.0,
            )
            assert t.balance() == 900.0
            t.settle(bet_id, BetStatus.PUSH)
            assert t.balance() == 1000.0

    def test_no_bankroll_tracking_without_deposit(self):
        with _make_tracker() as t:
            # No deposit — bets are logged but balance isn't enforced
            bet_id = t.place_bet(
                sport="NFL",
                event="A vs B",
                market="ml",
                selection="A",
                odds=-110,
                stake=100.0,
            )
            assert bet_id > 0
            assert t.balance() == 0.0

    def test_bankroll_history(self):
        with _make_tracker() as t:
            t.deposit(1000.0, note="Initial")
            t.withdraw(200.0, note="Cash out")
            history = t.bankroll_history()
            assert len(history) == 2
            assert history[0].amount == 1000.0
            assert history[1].amount == -200.0
