# Blackjack Basic Strategy Trainer

A console application to help you master blackjack basic strategy through practice. You're dealt hands against a dealer up card and must choose the correct action - the trainer gives immediate feedback on your decisions.

## Quickstart

Clone and enter the directory
```bash
git clone https://github.com/jeffhoek/blackjackpy-trainer.git && cd blackjackpy-trainer
```

### `uv`
Update dependencies
```
uv sync
```

Run with uv (recommended)
```
uv run python main.py
```

### Or with standard Python
```
pip install -e .
```
```
python main.py
```

## CLI Options

Print a strategy table and exit
```bash
uv run python main.py --table multi-deck
```
```
Multi Deck Basic Strategy

          2    3    4    5    6    7    8    9   10    A
    20    S    S    S    S    S    S    S    S    S    S
    19    S    S    S    S    S    S    S    S    S    S
    18    S    S    S    S    S    S    S    S    S    S
    17    S    S    S    S    S    S    S    S    S    S
    16    S    S    S    S    S    H    H    R    R    R
    15    S    S    S    S    S    H    H    H    R    H
    14    S    S    S    S    S    H    H    H    H    H
    13    S    S    S    S    S    H    H    H    H    H
    12    H    H    S    S    S    H    H    H    H    H
    11    D    D    D    D    D    D    D    D    D    H
    10    D    D    D    D    D    D    D    D    H    H
     9    H    D    D    D    D    H    H    H    H    H
     8    H    H    H    H    H    H    H    H    H    H
     7    H    H    H    H    H    H    H    H    H    H
     6    H    H    H    H    H    H    H    H    H    H
     5    H    H    H    H    H    H    H    H    H    H
    A9    S    S    S    S    S    S    S    S    S    S
    A8    S    S    S    S    S    S    S    S    S    S
    A7    S    D    D    D    D    S    S    H    H    H
    A6    H    D    D    D    D    H    H    H    H    H
    A5    H    H    D    D    D    H    H    H    H    H
    A4    H    H    D    D    D    H    H    H    H    H
    A3    H    H    H    D    D    H    H    H    H    H
    A2    H    H    H    D    D    H    H    H    H    H
    AA    P    P    P    P    P    P    P    P    P    P
    TT    S    S    S    S    S    S    S    S    S    S
    99    P    P    P    P    P    S    P    P    S    S
    88    P    P    P    P    P    P    P    P    P    R
    77    P    P    P    P    P    P    H    H    H    H
    66    P    P    P    P    P    H    H    H    H    H
    55    D    D    D    D    D    D    D    D    H    H
    44    H    H    H    H    P    P    H    H    H    H
    33    P    P    P    P    P    P    H    H    H    H
    22    P    P    P    P    P    P    H    H    H    H
```

Filter the table to a specific skill level (0-5)
```
uv run python main.py --table multi-deck --level 7
```
```
Multi Deck Basic Strategy — Level 7: Expert

          2    3    4    5    6    7    8    9   10    A
    16    S    S    S    S    S    H    H    R    R    R
    15    S    S    S    S    S    H    H    H    R    H
    A7    S    D    D    D    D    S    S    H    H    H
    A6    H    D    D    D    D    H    H    H    H    H
    99    P    P    P    P    P    S    P    P    S    S
    77    P    P    P    P    P    P    H    H    H    H
    44    H    H    H    H    P    P    H    H    H    H
```

| Flag | Description |
|------|-------------|
| `--table NAME` | Print a strategy table and exit (e.g. `single-deck`, `multi-deck`) |
| `--level N` | With `--table`, filter to rows for skill level N (0=All, 1=Fundamentals, 2=Standard Decisions, 3=Splits, 4=Doubles & Soft Hands, 5=Expert) |


## How to Play

1. **Configure rules** - Choose number of decks (1 or 6) and dealer soft 17 rule
2. **Read your hand** - You'll see your two cards with total value and the dealer's up card
3. **Press an action key** - Single keypress, no Enter needed:
   - `S` - Stand
   - `H` - Hit
   - `D` - Double down
   - `P` - Split (for pairs)
   - `R` - Surrender
   - `Q` - Quit
4. **Get feedback** - See if you were correct and what the right play was
5. **Track progress** - Running accuracy shown after each hand

### Example Session

```
Your hand: 10♠ 6♥ (16)  Dealer shows: 10♦

[S]tand  [H]it  [D]ouble  s[P]lit  su[R]render  [Q]uit
Your action: R

Correct!
Session: 1/1 correct (100%)
```

## Basic Strategy

The trainer uses mathematically optimal basic strategy charts:

- **Single deck** - Optimized for 1-deck games
- **Multi-deck** - Optimized for 4-8 deck shoes

Key differences exist between single and multi-deck strategy, particularly for doubling and splitting decisions.

### Actions Explained

| Action | When to Use |
|--------|-------------|
| Stand | Keep your current total, end your turn |
| Hit | Take another card |
| Double | Double your bet, take exactly one more card |
| Split | Separate a pair into two hands (pairs only) |
| Surrender | Forfeit half your bet, end the hand |

## Project Structure

```
blackjackpy-trainer/
├── main.py              # Entry point
├── blackjack/           # Main package
│   ├── cards.py         # Card, Rank, Suit, Shoe
│   ├── hand.py          # Hand value calculation
│   ├── strategy.py      # Strategy table lookup
│   ├── rules.py         # Game configuration
│   ├── trainer.py       # Training orchestration
│   └── ui.py            # Console interface
├── data/                # Strategy CSV files
│   ├── single-deck.csv
│   └── multi-deck.csv
└── tests/               # Unit tests
```

## Running Tests

```bash
uv run pytest
```

## License

MIT
