#!/usr/bin/env python3
"""Entry point for the Blackjack Basic Strategy Trainer."""

import argparse
import sys
from pathlib import Path

from blackjack.strategy import Strategy
from blackjack.ui import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Blackjack Basic Strategy Trainer")
    parser.add_argument(
        "--table",
        metavar="NAME",
        help="Print a strategy table and exit (e.g. single-deck, multi-deck)",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.table:
        csv_path = Path("data") / f"{args.table}.csv"
        if not csv_path.exists():
            print(f"Error: {csv_path} not found", file=sys.stderr)
            sys.exit(1)
        title = args.table.replace("-", " ").title() + " Basic Strategy"
        strategy = Strategy(csv_path)
        strategy.print_table(title)
        sys.exit(0)
    main()
