"""Domain types for bet tracking."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class BetStatus(Enum):
    """Settlement status of a bet."""

    OPEN = "open"
    WON = "won"
    LOST = "lost"
    PUSH = "push"
    VOID = "void"


class BankrollEventType(Enum):
    """Type of bankroll ledger entry."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    ADJUSTMENT = "adjustment"
    BET_PLACED = "bet_placed"
    BET_SETTLED = "bet_settled"


@dataclass(frozen=True)
class Bet:
    """Immutable representation of a logged bet."""

    id: int
    sport: str
    event: str
    market: str
    selection: str
    odds_american: int
    odds_decimal: float
    stake: float
    status: BetStatus
    placed_at: str
    external_id: str | None = None
    league: str | None = None
    book: str | None = None
    model_prob: float | None = None
    fair_prob: float | None = None
    edge: float | None = None
    kelly_fraction: float | None = None
    closing_odds_american: int | None = None
    closing_odds_decimal: float | None = None
    result_amount: float | None = None
    settled_at: str | None = None
    notes: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class BankrollEvent:
    """Immutable representation of a bankroll ledger entry."""

    id: int
    event_type: BankrollEventType
    amount: float
    balance_after: float
    created_at: str
    note: str | None = None


@dataclass(frozen=True)
class EvaluationResult:
    """Result of model evaluation using betting-math-kit metrics."""

    brier_score: float
    log_loss_val: float
    ece: float
    mean_clv: float | None
    calibration_buckets: list[dict]
    edge_buckets: list[dict]
    sample_size: int
