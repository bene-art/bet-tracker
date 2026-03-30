"""Typed exception hierarchy for bet tracking."""


class BetTrackerError(Exception):
    """Base exception for bet-tracker."""


class BetNotFoundError(BetTrackerError, KeyError):
    """Raised when a bet ID does not exist."""


class DuplicateBetError(BetTrackerError, ValueError):
    """Raised on duplicate external_id."""


class InsufficientBalanceError(BetTrackerError, ValueError):
    """Raised when stake exceeds available balance."""


class InvalidSettlementError(BetTrackerError, ValueError):
    """Raised when settling an already-settled bet."""


class InvalidAmountError(BetTrackerError, ValueError):
    """Raised for non-positive stake, deposit, or withdrawal amounts."""
