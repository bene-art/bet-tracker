"""
bet-tracker: Bet logging, bankroll tracking, and model evaluation.

Pure Python. SQLite. Zero dependencies.
"""

from .exceptions import (
    BetNotFoundError,
    BetTrackerError,
    DuplicateBetError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidSettlementError,
)
from .tracker import BetTracker
from .types import (
    BankrollEvent,
    BankrollEventType,
    Bet,
    BetStatus,
    EvaluationResult,
)

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # Core
    "BetTracker",
    # Types
    "Bet",
    "BetStatus",
    "BankrollEvent",
    "BankrollEventType",
    "EvaluationResult",
    # Exceptions
    "BetTrackerError",
    "BetNotFoundError",
    "DuplicateBetError",
    "InsufficientBalanceError",
    "InvalidSettlementError",
    "InvalidAmountError",
]
