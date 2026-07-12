"""Core BetTracker class — the main entry point."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import american_to_decimal, create_connection, init_schema
from .exceptions import (
    BetNotFoundError,
    DuplicateBetError,
    InsufficientBalanceError,
    InvalidAmountError,
    InvalidSettlementError,
)
from .types import BankrollEvent, BankrollEventType, Bet, BetStatus


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_bet(row: sqlite3.Row) -> Bet:
    tags_raw = row["tags"]
    tags = tags_raw.split(",") if tags_raw else []
    status_str: str = row["status"]
    return Bet(
        id=row["id"],
        external_id=row["external_id"],
        sport=row["sport"],
        league=row["league"],
        event=row["event"],
        market=row["market"],
        selection=row["selection"],
        odds_american=row["odds_american"],
        odds_decimal=row["odds_decimal"],
        stake=row["stake"],
        book=row["book"],
        model_prob=row["model_prob"],
        fair_prob=row["fair_prob"],
        edge=row["edge"],
        kelly_fraction=row["kelly_fraction"],
        closing_odds_american=row["closing_odds_american"],
        closing_odds_decimal=row["closing_odds_decimal"],
        status=BetStatus(status_str),
        result_amount=row["result_amount"],
        settled_at=row["settled_at"],
        placed_at=row["placed_at"],
        notes=row["notes"],
        tags=tags,
    )


class BetTracker:
    """Bet logging, bankroll tracking, and performance queries.

    Args:
        db_path: Path to SQLite database file. Use ``\":memory:\"``
                 for an in-memory database (useful for tests).
    """

    def __init__(self, db_path: str | Path = "bets.db") -> None:
        self._conn = create_connection(db_path)
        init_schema(self._conn)
        self._bankroll_initialized = self._has_bankroll_events()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> BetTracker:
        return self

    def __exit__(
        self,
        exc_type: type | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Bankroll
    # ------------------------------------------------------------------

    def _has_bankroll_events(self) -> bool:
        row = self._conn.execute(
            "SELECT COUNT(*) AS cnt FROM bankroll_events "
            "WHERE event_type IN ('deposit', 'withdrawal', 'adjustment')"
        ).fetchone()
        return bool(row and row["cnt"] > 0)

    def balance(self) -> float:
        """Return the current bankroll balance."""
        row = self._conn.execute(
            "SELECT balance_after FROM bankroll_events ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return 0.0
        return float(row["balance_after"])

    def deposit(self, amount: float, note: str = "") -> int:
        """Add funds to the bankroll. Returns the event ID."""
        if amount <= 0:
            raise InvalidAmountError(f"Deposit amount must be positive, got {amount}")
        new_balance = self.balance() + amount
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO bankroll_events "
                "(event_type, amount, balance_after, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    BankrollEventType.DEPOSIT.value,
                    amount,
                    new_balance,
                    note or None,
                    _now_iso(),
                ),
            )
        self._bankroll_initialized = True
        return cur.lastrowid  # type: ignore[return-value]

    def withdraw(self, amount: float, note: str = "") -> int:
        """Remove funds from the bankroll. Returns the event ID."""
        if amount <= 0:
            raise InvalidAmountError(
                f"Withdrawal amount must be positive, got {amount}"
            )
        current = self.balance()
        if amount > current:
            raise InsufficientBalanceError(
                f"Cannot withdraw {amount}, balance is {current}"
            )
        new_balance = current - amount
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO bankroll_events "
                "(event_type, amount, balance_after, note, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    BankrollEventType.WITHDRAWAL.value,
                    -amount,
                    new_balance,
                    note or None,
                    _now_iso(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def bankroll_history(self) -> list[BankrollEvent]:
        """Return the full bankroll event ledger."""
        rows = self._conn.execute(
            "SELECT * FROM bankroll_events ORDER BY id"
        ).fetchall()
        return [
            BankrollEvent(
                id=r["id"],
                event_type=BankrollEventType(r["event_type"]),
                amount=r["amount"],
                balance_after=r["balance_after"],
                note=r["note"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def _record_bankroll_event(
        self,
        event_type: BankrollEventType,
        amount: float,
        note: str | None = None,
    ) -> None:
        new_balance = self.balance() + amount
        self._conn.execute(
            "INSERT INTO bankroll_events "
            "(event_type, amount, balance_after, note, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (event_type.value, amount, new_balance, note, _now_iso()),
        )

    # ------------------------------------------------------------------
    # Bet logging
    # ------------------------------------------------------------------

    def place_bet(
        self,
        sport: str,
        event: str,
        market: str,
        selection: str,
        odds: int,
        stake: float,
        *,
        book: str | None = None,
        model_prob: float | None = None,
        fair_prob: float | None = None,
        edge: float | None = None,
        kelly_fraction: float | None = None,
        external_id: str | None = None,
        league: str | None = None,
        notes: str | None = None,
        tags: list[str] | None = None,
    ) -> int:
        """Log a bet. Returns the bet ID.

        If bankroll tracking is active (at least one deposit), the stake
        is deducted from the balance. Raises InsufficientBalanceError
        if the stake exceeds the current balance.
        """
        if stake <= 0:
            raise InvalidAmountError(f"Stake must be positive, got {stake}")
        if odds == 0:
            raise ValueError("American odds cannot be 0")

        decimal_odds = american_to_decimal(odds)

        # Check bankroll if tracking is active
        if self._bankroll_initialized:
            current = self.balance()
            if stake > current:
                raise InsufficientBalanceError(
                    f"Stake {stake} exceeds balance {current}"
                )

        tags_str = ",".join(tags) if tags else None

        try:
            with self._conn:
                cur = self._conn.execute(
                    "INSERT INTO bets "
                    "(external_id, sport, league, event, market, selection, "
                    "odds_american, odds_decimal, stake, book, model_prob, "
                    "fair_prob, edge, kelly_fraction, status, placed_at, "
                    "notes, tags) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        external_id,
                        sport,
                        league,
                        event,
                        market,
                        selection,
                        odds,
                        decimal_odds,
                        stake,
                        book,
                        model_prob,
                        fair_prob,
                        edge,
                        kelly_fraction,
                        BetStatus.OPEN.value,
                        _now_iso(),
                        notes,
                        tags_str,
                    ),
                )
                bet_id: int = cur.lastrowid  # type: ignore[assignment]

                if self._bankroll_initialized:
                    self._record_bankroll_event(
                        BankrollEventType.BET_PLACED,
                        -stake,
                        f"Bet #{bet_id}",
                    )
        except sqlite3.IntegrityError as e:
            if "UNIQUE" in str(e) and external_id is not None:
                raise DuplicateBetError(
                    f"Bet with external_id '{external_id}' already exists"
                ) from None
            raise

        return bet_id

    def set_closing_odds(self, bet_id: int, closing_odds: int) -> None:
        """Record the closing line for a bet."""
        self._assert_bet_exists(bet_id)
        if closing_odds == 0:
            raise ValueError("American odds cannot be 0")
        closing_decimal = american_to_decimal(closing_odds)
        with self._conn:
            self._conn.execute(
                "UPDATE bets SET closing_odds_american = ?, "
                "closing_odds_decimal = ? WHERE id = ?",
                (closing_odds, closing_decimal, bet_id),
            )

    def settle(
        self,
        bet_id: int,
        status: BetStatus,
        result_amount: float | None = None,
    ) -> None:
        """Settle a bet. Auto-calculates result_amount if not provided.

        - WON: ``stake * (decimal_odds - 1)``
        - LOST: ``-stake``
        - PUSH / VOID: ``0.0`` (stake returned)
        """
        bet = self.get_bet(bet_id)
        if bet.status is not BetStatus.OPEN:
            raise InvalidSettlementError(f"Bet #{bet_id} is already {bet.status.value}")
        if status is BetStatus.OPEN:
            raise InvalidSettlementError("Cannot settle a bet as 'open'")

        if result_amount is None:
            if status is BetStatus.WON:
                result_amount = bet.stake * (bet.odds_decimal - 1.0)
            elif status is BetStatus.LOST:
                result_amount = -bet.stake
            else:
                result_amount = 0.0

        now = _now_iso()
        with self._conn:
            self._conn.execute(
                "UPDATE bets SET status = ?, result_amount = ?, "
                "settled_at = ? WHERE id = ?",
                (status.value, result_amount, now, bet_id),
            )
            if self._bankroll_initialized:
                # Return stake + profit for wins, return stake for push/void
                if status is BetStatus.WON:
                    bankroll_delta = bet.stake + result_amount
                elif status is BetStatus.LOST:
                    bankroll_delta = 0.0  # stake already deducted
                else:
                    # Push/void: return the stake
                    bankroll_delta = bet.stake
                self._record_bankroll_event(
                    BankrollEventType.BET_SETTLED,
                    bankroll_delta,
                    f"Bet #{bet_id} {status.value}",
                )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_bet(self, bet_id: int) -> Bet:
        """Return a single bet by ID."""
        row = self._conn.execute(
            "SELECT * FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            raise BetNotFoundError(f"Bet #{bet_id} not found")
        return _row_to_bet(row)

    def list_bets(
        self,
        *,
        status: BetStatus | None = None,
        sport: str | None = None,
        book: str | None = None,
        market: str | None = None,
        league: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> list[Bet]:
        """Return bets matching the given filters.

        Args:
            start: ISO date string (inclusive). Filters on ``placed_at``.
            end:   ISO date string (exclusive). Filters on ``placed_at``.
        """
        where, params = _build_where(
            status=status,
            sport=sport,
            book=book,
            market=market,
            league=league,
            start=start,
            end=end,
        )
        rows = self._conn.execute(
            f"SELECT * FROM bets{where} ORDER BY id", params
        ).fetchall()
        return [_row_to_bet(r) for r in rows]

    def pnl(
        self,
        *,
        sport: str | None = None,
        book: str | None = None,
        market: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> float:
        """Total profit and loss for settled bets."""
        where, params = _build_where(
            sport=sport,
            book=book,
            market=market,
            start=start,
            end=end,
            settled_only=True,
        )
        row = self._conn.execute(
            f"SELECT COALESCE(SUM(result_amount), 0.0) AS total FROM bets{where}",
            params,
        ).fetchone()
        return float(row["total"])  # type: ignore[index]

    def roi(
        self,
        *,
        sport: str | None = None,
        book: str | None = None,
        market: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> float:
        """Return on investment for settled bets (decimal, not %)."""
        where, params = _build_where(
            sport=sport,
            book=book,
            market=market,
            start=start,
            end=end,
            settled_only=True,
        )
        row = self._conn.execute(
            f"SELECT COALESCE(SUM(result_amount), 0.0) AS pnl, "
            f"COALESCE(SUM(stake), 0.0) AS wagered "
            f"FROM bets{where}",
            params,
        ).fetchone()
        wagered = float(row["wagered"])  # type: ignore[index]
        if wagered == 0:
            return 0.0
        return float(row["pnl"]) / wagered  # type: ignore[index]

    def win_rate(
        self,
        *,
        sport: str | None = None,
        book: str | None = None,
        market: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> float:
        """Win rate for settled bets (excludes push/void)."""
        where, params = _build_where(
            sport=sport,
            book=book,
            market=market,
            start=start,
            end=end,
            settled_only=True,
        )
        row = self._conn.execute(
            f"SELECT "
            f"COUNT(CASE WHEN status = 'won' THEN 1 END) AS wins, "
            f"COUNT(CASE WHEN status IN ('won','lost') THEN 1 END) AS total "
            f"FROM bets{where}",
            params,
        ).fetchone()
        total = int(row["total"])  # type: ignore[index]
        if total == 0:
            return 0.0
        return int(row["wins"]) / total  # type: ignore[index]

    def summary(
        self,
        *,
        sport: str | None = None,
        book: str | None = None,
        market: str | None = None,
        start: str | None = None,
        end: str | None = None,
    ) -> dict:
        """Aggregate performance summary for settled bets."""
        filters = dict(
            sport=sport,
            book=book,
            market=market,
            start=start,
            end=end,
        )
        return {
            "pnl": self.pnl(**filters),
            "roi": self.roi(**filters),
            "win_rate": self.win_rate(**filters),
            "total_bets": len(
                self.list_bets(
                    sport=sport,
                    book=book,
                    market=market,
                )
            ),
            "open_bets": len(
                self.list_bets(
                    status=BetStatus.OPEN,
                    sport=sport,
                    book=book,
                    market=market,
                )
            ),
        }

    def clv_summary(
        self,
        *,
        sport: str | None = None,
        book: str | None = None,
    ) -> dict:
        """Closing line value summary for bets with closing odds."""
        bets = self.list_bets(sport=sport, book=book)
        clv_values: list[float] = []
        for bet in bets:
            if (
                bet.closing_odds_decimal is not None
                and bet.odds_decimal > 1.0
                and bet.closing_odds_decimal > 1.0
            ):
                opening_prob = 1.0 / bet.odds_decimal
                closing_prob = 1.0 / bet.closing_odds_decimal
                clv_values.append(closing_prob - opening_prob)

        if not clv_values:
            return {
                "mean_clv": 0.0,
                "median_clv": 0.0,
                "pct_positive": 0.0,
                "sample_size": 0,
            }

        sorted_clv = sorted(clv_values)
        n = len(sorted_clv)
        mid = n // 2
        median = (
            sorted_clv[mid]
            if n % 2 == 1
            else (sorted_clv[mid - 1] + sorted_clv[mid]) / 2.0
        )

        return {
            "mean_clv": sum(clv_values) / n,
            "median_clv": median,
            "pct_positive": sum(1 for v in clv_values if v > 0) / n,
            "sample_size": n,
        }

    # ------------------------------------------------------------------
    # Evaluation (optional betting-math-kit integration)
    # ------------------------------------------------------------------

    def evaluate(self) -> EvaluationResult:
        """Evaluate model performance using betting-math-kit metrics.

        Requires ``betting-math-kit >= 0.3.0`` to be installed.
        Only considers settled bets (won/lost) that have ``model_prob``.

        Raises:
            ImportError: If betting-math-kit is not installed.
        """
        from .evaluation import evaluate_bets

        bets = [
            b
            for b in self.list_bets()
            if b.status in (BetStatus.WON, BetStatus.LOST) and b.model_prob is not None
        ]
        return evaluate_bets(bets)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_csv(self, path: str | Path) -> None:
        """Export all bets to a CSV file."""
        from .export import write_csv

        write_csv(self._conn, path)

    def export_json(self, path: str | Path) -> None:
        """Export all bets to a JSON file."""
        from .export import write_json

        write_json(self._conn, path)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _assert_bet_exists(self, bet_id: int) -> None:
        row = self._conn.execute(
            "SELECT id FROM bets WHERE id = ?", (bet_id,)
        ).fetchone()
        if row is None:
            raise BetNotFoundError(f"Bet #{bet_id} not found")




def _build_where(
    *,
    status: BetStatus | None = None,
    sport: str | None = None,
    book: str | None = None,
    market: str | None = None,
    league: str | None = None,
    start: str | None = None,
    end: str | None = None,
    settled_only: bool = False,
) -> tuple[str, list[str | int]]:
    """Build a WHERE clause from filter kwargs."""
    clauses: list[str] = []
    params: list[str | int] = []

    if status is not None:
        clauses.append("status = ?")
        params.append(status.value)
    if sport is not None:
        clauses.append("sport = ?")
        params.append(sport)
    if book is not None:
        clauses.append("book = ?")
        params.append(book)
    if market is not None:
        clauses.append("market = ?")
        params.append(market)
    if league is not None:
        clauses.append("league = ?")
        params.append(league)
    if start is not None:
        clauses.append("placed_at >= ?")
        params.append(start)
    if end is not None:
        clauses.append("placed_at < ?")
        params.append(end)
    if settled_only:
        clauses.append("status IN ('won', 'lost', 'push', 'void')")

    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params
