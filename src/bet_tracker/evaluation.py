"""Optional betting-math-kit integration for model evaluation."""

from __future__ import annotations

from .types import Bet, BetStatus, EvaluationResult

try:
    from betting_math_kit import (
        brier_score,
        calibration_buckets,
        clv,
        edge_bucket_analysis,
        expected_calibration_error,
        log_loss,
    )

    _HAS_MATH_KIT = True
except ImportError:
    _HAS_MATH_KIT = False


def evaluate_bets(bets: list[Bet]) -> EvaluationResult:
    """Evaluate model performance across settled bets.

    Requires ``betting-math-kit >= 0.3.0``.

    Args:
        bets: Settled bets (won/lost) with ``model_prob`` set.
              Bets without ``model_prob`` are silently skipped.

    Returns:
        EvaluationResult with scoring metrics and calibration data.

    Raises:
        ImportError: If betting-math-kit is not installed.
        ValueError: If no evaluable bets are provided.
    """
    if not _HAS_MATH_KIT:
        raise ImportError(
            "Model evaluation requires betting-math-kit. "
            "Install it with: pip install betting-math-kit"
        )

    # Filter to evaluable bets
    evaluable = [
        b
        for b in bets
        if b.status in (BetStatus.WON, BetStatus.LOST) and b.model_prob is not None
    ]
    if not evaluable:
        raise ValueError("No evaluable bets (need settled bets with model_prob)")

    probs = [b.model_prob for b in evaluable]  # type: ignore[misc]
    outcomes = [1 if b.status is BetStatus.WON else 0 for b in evaluable]

    # CLV (only for bets with closing odds)
    clv_values: list[float] = []
    for b in evaluable:
        if b.odds_decimal > 1.0 and b.closing_odds_decimal is not None:
            opening_prob = 1.0 / b.odds_decimal
            closing_prob = 1.0 / b.closing_odds_decimal
            clv_values.append(clv(opening_prob, closing_prob))

    mean_clv = sum(clv_values) / len(clv_values) if clv_values else None

    # Edge buckets (only for bets with edge)
    edge_bets = [b for b in evaluable if b.edge is not None]
    if edge_bets:
        edge_probs = [b.model_prob for b in edge_bets]  # type: ignore[misc]
        edge_outcomes = [1 if b.status is BetStatus.WON else 0 for b in edge_bets]
        edge_vals = [b.edge for b in edge_bets]  # type: ignore[misc]
        edge_buckets_data = edge_bucket_analysis(  # type: ignore[arg-type]
            edge_probs, edge_outcomes, edge_vals, n_bins=5
        )
    else:
        edge_buckets_data = []

    return EvaluationResult(
        brier_score=brier_score(probs, outcomes),  # type: ignore[arg-type]
        log_loss_val=log_loss(probs, outcomes),  # type: ignore[arg-type]
        ece=expected_calibration_error(probs, outcomes),  # type: ignore[arg-type]
        mean_clv=mean_clv,
        calibration_buckets=calibration_buckets(probs, outcomes),  # type: ignore[arg-type]
        edge_buckets=edge_buckets_data,
        sample_size=len(evaluable),
    )
