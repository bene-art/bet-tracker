# bet-tracker

[![CI](https://github.com/bene-art/bet-tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/bene-art/bet-tracker/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Bet logging, bankroll tracking, and model evaluation. Pure Python. SQLite. Zero dependencies.

> **Status:** Stable. Pulled from a larger private system to demonstrate this slice as a standalone tool. Treat as a snapshot, not current production.

## Where this fits

[props-scorer](https://github.com/bene-art/props-scorer) tells you *what's going to happen*. [betting-math-kit](https://github.com/bene-art/betting-math-kit) tells you *what to do about it*. This library answers the question that comes after: **did it work?**

```
props-scorer              betting-math-kit              bet-tracker
┌──────────────┐  prob   ┌────────────────────┐  bet   ┌──────────────────────┐
│ player stats │ ──────→ │ de-vig → edge →    │ ─────→ │ log bet              │
│ → XGBoost    │         │ Kelly → stake size  │        │ capture closing line │
│ → probability│         │                    │        │ settle → evaluate    │
└──────────────┘         └────────────────────┘        └──────────────────────┘
                               ▲                              │
                               └──── metrics ◄────────────────┘
```

You place a bet. You record the closing line. The result comes in. Now you can answer: is my model calibrated? Am I beating the closing line? Are my higher-edge bets actually winning more? That feedback loop is what separates a system from a spreadsheet.

## Install

```bash
pip install bet-tracker
```

With [betting-math-kit](https://github.com/bene-art/betting-math-kit) integration for model evaluation:

```bash
pip install bet-tracker[math]
```

Or from source:

```bash
git clone https://github.com/bene-art/bet-tracker.git
cd bet-tracker
pip install -e ".[dev]"
```

---

## Quick start

```python
from bet_tracker import BetTracker, BetStatus

tracker = BetTracker("my_bets.db")

# Fund your bankroll
tracker.deposit(1000.00, note="Initial bankroll")

# Log a bet
bet_id = tracker.place_bet(
    sport="NFL",
    event="Chiefs vs Ravens",
    market="moneyline",
    selection="Chiefs ML",
    odds=-110,
    stake=50.00,
    book="FanDuel",
    model_prob=0.60,     # from props-scorer or your own model
    fair_prob=0.50,      # from betting-math-kit de-vig
    edge=0.10,           # from betting-math-kit edge calc
)

# Capture the closing line before kickoff
tracker.set_closing_odds(bet_id, closing_odds=-130)

# Record the result
tracker.settle(bet_id, BetStatus.WON)
# result_amount auto-calculated: stake * (decimal_odds - 1)

# Check your numbers
print(f"Balance: ${tracker.balance():.2f}")
print(f"P&L: ${tracker.pnl():.2f}")
print(f"ROI: {tracker.roi():.1%}")
print(f"Win rate: {tracker.win_rate():.1%}")
```

## Bankroll tracking

Bankroll tracking activates when you make your first deposit. After that, every bet deducts from your balance, and settlements credit it back.

```python
tracker.deposit(1000.00)
tracker.balance()        # 1000.00

# Bet deducts stake
tracker.place_bet(sport="NFL", event="A vs B", market="ml",
                  selection="A", odds=-110, stake=100.00)
tracker.balance()        # 900.00

# Win credits stake + profit
tracker.settle(bet_id, BetStatus.WON)
tracker.balance()        # ~990.91 (stake back + profit at -110)

# Push returns stake
tracker.settle(bet_id, BetStatus.PUSH)
tracker.balance()        # stake returned, no profit

# Full audit trail
for event in tracker.bankroll_history():
    print(f"{event.event_type.value}: ${event.amount:+.2f} → ${event.balance_after:.2f}")
```

If you don't deposit, bets are still logged — bankroll just isn't enforced. Useful if you only want the tracking without the accounting.

## Performance queries

Everything filters by sport, book, market, and date range.

```python
# Total P&L
tracker.pnl()                              # all bets
tracker.pnl(sport="NFL")                   # NFL only
tracker.pnl(book="FanDuel", start="2026-01-01", end="2026-04-01")

# ROI (decimal, not %)
tracker.roi(sport="NBA")

# Win rate (excludes push/void)
tracker.win_rate(market="moneyline")

# Everything at once
tracker.summary()
# {'pnl': 150.0, 'roi': 0.042, 'win_rate': 0.55, 'total_bets': 47, 'open_bets': 3}
```

## Closing line value

CLV is the single best indicator of long-term profitability. If the line moves toward your number after you bet, you had real edge — regardless of short-term variance.

```python
# Record closing odds before events start
tracker.set_closing_odds(bet_id, closing_odds=-130)

# CLV summary across all bets with closing lines
clv = tracker.clv_summary()
# {'mean_clv': 0.023, 'median_clv': 0.018, 'pct_positive': 0.62, 'sample_size': 34}
```

No dependency needed for basic CLV. The tracker computes it from the odds you logged.

## Model evaluation

If you have [betting-math-kit](https://github.com/bene-art/betting-math-kit) installed, you get full model evaluation — Brier score, log loss, ECE, calibration buckets, and edge-bucket analysis — computed over your actual bet history.

```python
result = tracker.evaluate()

print(f"Brier score: {result.brier_score:.4f}")     # lower is better
print(f"Log loss: {result.log_loss_val:.4f}")
print(f"ECE: {result.ece:.4f}")                      # calibration error
print(f"Mean CLV: {result.mean_clv:.4f}")
print(f"Sample size: {result.sample_size}")

# Calibration buckets: are your 60% predictions winning 60% of the time?
for bucket in result.calibration_buckets:
    print(f"  {bucket['avg_predicted']:.0%} predicted → "
          f"{bucket['avg_actual']:.0%} actual ({bucket['count']} bets)")

# Edge buckets: do higher-edge bets actually win more?
for bucket in result.edge_buckets:
    print(f"  Edge {bucket['avg_edge']:.1%}: "
          f"win rate {bucket['win_rate']:.0%} ({bucket['count']} bets)")
```

Only settled bets with `model_prob` are included. If betting-math-kit isn't installed, `evaluate()` raises `ImportError` with install instructions.

## Export

```python
tracker.export_csv("bets.csv")     # for spreadsheets
tracker.export_json("bets.json")   # for everything else
```

## API reference

| Method | What it does |
|--------|-------------|
| `BetTracker(db_path)` | Open or create a tracker database |
| `deposit(amount)` | Add funds |
| `withdraw(amount)` | Remove funds |
| `balance()` | Current bankroll |
| `place_bet(...)` | Log a bet, deducts from bankroll |
| `set_closing_odds(bet_id, odds)` | Record the closing line |
| `settle(bet_id, status)` | Mark as won/lost/push/void |
| `get_bet(bet_id)` | Retrieve a single bet |
| `list_bets(**filters)` | Filter by status, sport, book, etc. |
| `pnl(**filters)` | Total profit/loss |
| `roi(**filters)` | Return on investment |
| `win_rate(**filters)` | Win rate (excludes push/void) |
| `summary(**filters)` | Aggregate stats |
| `clv_summary(**filters)` | Closing line value analysis |
| `evaluate()` | Full model evaluation (requires betting-math-kit) |
| `export_csv(path)` | Export to CSV |
| `export_json(path)` | Export to JSON |

## Schema

Three SQLite tables. Deliberately simple.

- **`bets`** — One row per bet. Odds, stake, model probability, fair probability, edge, closing odds, status, result, timestamps, tags.
- **`bankroll_events`** — Ledger of every deposit, withdrawal, bet placement, and settlement. `balance_after` is denormalized so current balance is always a single-row read.
- **`metadata`** — Schema version for future migrations.

## Validation

| Exception | When |
|-----------|------|
| `BetNotFoundError` | Bet ID doesn't exist |
| `DuplicateBetError` | Duplicate `external_id` |
| `InsufficientBalanceError` | Stake exceeds bankroll |
| `InvalidSettlementError` | Settling an already-settled bet |
| `InvalidAmountError` | Non-positive stake, deposit, or withdrawal |

## Testing

```bash
pip install -e ".[dev]"
pip install betting-math-kit   # for evaluation tests
pytest
```

68 tests covering bet logging, bankroll tracking, settlement (won/lost/push/void), performance queries, CLV analysis, CSV/JSON export, model evaluation integration, validation errors, and edge cases.

```bash
ruff check src/ tests/       # lint
ruff format src/ tests/      # format
mypy src/bet_tracker/        # type check
```

CI runs on Python 3.10 - 3.13.

---

## Where this fits in the system

Three repos, three concerns:

| Repo | Question it answers |
|------|-------------------|
| [**props-scorer**](https://github.com/bene-art/props-scorer) | What's going to happen? |
| [**betting-math-kit**](https://github.com/bene-art/betting-math-kit) | What should I do about it? |
| [**bet-tracker**](https://github.com/bene-art/bet-tracker) | Did it work? |

They work independently or together. props-scorer gives you a probability. betting-math-kit turns it into a stake. bet-tracker logs the bet, tracks your bankroll, and tells you whether your model is actually making money.

## License

MIT

## Author

Benjamin Easington — [GitHub](https://github.com/bene-art)
