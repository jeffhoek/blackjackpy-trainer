# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app
uv run python main.py

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_strategy.py

# Run a specific test
uv run pytest tests/test_strategy.py::TestStrategyMultiDeck::test_hard_16_vs_10_surrender
```

## Architecture

This is a console-based blackjack basic strategy trainer. The user is dealt hands and must choose the correct action (Stand, Hit, Double, Split, Surrender) based on basic strategy.

### Core Components

- **`main.py`** - Entry point, calls `blackjack.ui.main()`
- **`blackjack/trainer.py`** - `Trainer` class orchestrates sessions: deals hands, checks answers against strategy, tracks stats
- **`blackjack/strategy.py`** - `Strategy` class loads CSV strategy tables and performs lookups
- **`blackjack/hand.py`** - `Hand` class calculates blackjack values (soft/hard), generates strategy keys
- **`blackjack/cards.py`** - `Card`, `Rank`, `Suit`, `Shoe` classes for deck management
- **`blackjack/rules.py`** - `Rules` dataclass for game configuration (deck count, dealer soft 17)
- **`blackjack/ui.py`** - Console I/O, single-keypress input via `getch()`

### Strategy Keys

The strategy table uses specific row keys:
- **Hard hands**: total value as string (`"16"`, `"11"`, etc.)
- **Soft hands**: `"A"` + non-ace value (`"A6"` for Ace+6, `"A7"` for Ace+7)
- **Pairs**: doubled symbol (`"AA"`, `"88"`, `"TT"` where T = any 10-value card)

Dealer column keys: `"2"` through `"10"` and `"A"`

### Data Files

Strategy tables in `data/`:
- `single-deck.csv` - Optimal strategy for 1-deck games
- `multi-deck.csv` - Optimal strategy for 4-8 deck shoes

CSV format: first column is row key, remaining columns are actions (S/H/D/P/R) for dealer upcards 2-A.
