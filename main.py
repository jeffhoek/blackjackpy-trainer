#!/usr/bin/env python3
"""Entry point for the Blackjack Basic Strategy Trainer."""

import argparse
import sys
from pathlib import Path

from blackjack.levels import LEVEL_NAMES, get_keys_for_level
from blackjack.metrics import create_metrics_client
from blackjack.strategy import Strategy
from blackjack.ui import main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Blackjack Basic Strategy Trainer")
    parser.add_argument(
        "--table",
        metavar="NAME",
        help="Print a strategy table and exit (e.g. single-deck, multi-deck)",
    )
    parser.add_argument(
        "--level",
        type=int,
        metavar="N",
        help="With --table, filter to rows for skill level N (0-5)",
    )
    parser.add_argument(
        "--statsd-host",
        metavar="HOST",
        help="Enable StatsD metrics and send to HOST",
    )
    parser.add_argument(
        "--statsd-port",
        type=int,
        default=8125,
        metavar="PORT",
        help="StatsD port (default: 8125)",
    )
    return parser.parse_args()


def print_table(args: argparse.Namespace) -> None:
    csv_path = Path("data") / f"{args.table}.csv"
    if not csv_path.exists():
        print(f"Error: {csv_path} not found", file=sys.stderr)
        sys.exit(1)
    title = args.table.replace("-", " ").title() + " Basic Strategy"
    row_keys = None
    if args.level is not None:
        try:
            row_keys = get_keys_for_level(args.level)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
        level_name = LEVEL_NAMES.get(args.level, f"Level {args.level}")
        title += f" \u2014 Level {args.level}: {level_name}"
    strategy = Strategy(csv_path)
    strategy.print_table(title, row_keys=row_keys)


def cli() -> None:
    args = parse_args()
    if args.table:
        print_table(args)
        sys.exit(0)
    metrics = create_metrics_client(args.statsd_host, args.statsd_port)
    main(metrics=metrics)


if __name__ == "__main__":
    cli()
