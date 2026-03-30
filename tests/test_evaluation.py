"""Tests for optional betting-math-kit evaluation integration."""

import pytest

from bet_tracker import BetStatus, BetTracker, EvaluationResult


class TestEvaluation:
    def test_evaluate_returns_result(self):
        t = BetTracker(":memory:")
        # Place bets with model_prob
        for i in range(10):
            b = t.place_bet(
                sport="NFL",
                event=f"Game {i}",
                market="moneyline",
                selection="Home",
                odds=-110,
                stake=10.0,
                model_prob=0.55 + i * 0.02,
            )
            t.settle(b, BetStatus.WON if i % 2 == 0 else BetStatus.LOST)

        result = t.evaluate()
        assert isinstance(result, EvaluationResult)
        assert result.sample_size == 10
        assert 0.0 <= result.brier_score <= 1.0
        assert result.log_loss_val > 0
        assert 0.0 <= result.ece <= 1.0

    def test_evaluate_with_closing_odds(self):
        t = BetTracker(":memory:")
        b = t.place_bet(
            sport="NFL",
            event="A vs B",
            market="ml",
            selection="A",
            odds=-110,
            stake=50.0,
            model_prob=0.60,
        )
        t.set_closing_odds(b, -130)
        t.settle(b, BetStatus.WON)

        result = t.evaluate()
        assert result.mean_clv is not None
        assert result.mean_clv > 0  # line moved toward us

    def test_evaluate_no_model_prob_raises(self):
        t = BetTracker(":memory:")
        b = t.place_bet(
            sport="NFL",
            event="A vs B",
            market="ml",
            selection="A",
            odds=-110,
            stake=50.0,
        )
        t.settle(b, BetStatus.WON)

        with pytest.raises(ValueError, match="No evaluable bets"):
            t.evaluate()

    def test_evaluate_no_settled_bets_raises(self):
        t = BetTracker(":memory:")
        t.place_bet(
            sport="NFL",
            event="A vs B",
            market="ml",
            selection="A",
            odds=-110,
            stake=50.0,
            model_prob=0.60,
        )
        with pytest.raises(ValueError, match="No evaluable bets"):
            t.evaluate()

    def test_evaluate_skips_bets_without_model_prob(self):
        t = BetTracker(":memory:")
        # Bet with model_prob
        b1 = t.place_bet(
            sport="NFL",
            event="A vs B",
            market="ml",
            selection="A",
            odds=-110,
            stake=50.0,
            model_prob=0.60,
        )
        t.settle(b1, BetStatus.WON)

        # Bet without model_prob
        b2 = t.place_bet(
            sport="NFL",
            event="C vs D",
            market="ml",
            selection="C",
            odds=-110,
            stake=50.0,
        )
        t.settle(b2, BetStatus.LOST)

        result = t.evaluate()
        assert result.sample_size == 1
