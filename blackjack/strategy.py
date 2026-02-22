"""Strategy loading from CSV and action lookup."""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .hand import Hand
    from .rules import Rules

_COLOR_RESET = "\033[0m"

# Ordered most-prominent → least-prominent (rarest action gets index 0).
_ACTION_COLOR_TIERS = [
    "\033[1;95m",  # tier 1 (rarest) — bold bright magenta → R (Surrender)
    "\033[93m",    # tier 2          — bright yellow       → D (Double)
    "\033[96m",    # tier 3          — bright cyan         → P (Split)
]


class Action:
    """Constants for basic strategy actions."""

    STAND = "S"
    HIT = "H"
    DOUBLE = "D"
    SPLIT = "P"
    SURRENDER = "R"

    ALL = {STAND, HIT, DOUBLE, SPLIT, SURRENDER}

    NAMES = {
        STAND: "Stand",
        HIT: "Hit",
        DOUBLE: "Double",
        SPLIT: "Split",
        SURRENDER: "Surrender",
    }

    @classmethod
    def get_name(cls, action: str) -> str:
        """Get the full name of an action."""
        return cls.NAMES.get(action.upper(), action)


@dataclass
class StrategyException:
    """A context-dependent override to the base strategy table."""

    description: str
    row_key: str
    dealer: list[str]
    action: str
    when: dict[str, object] = field(default_factory=dict)


class Strategy:
    """Basic strategy table loaded from CSV."""

    DEALER_CARDS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]

    def __init__(self, csv_path: Path) -> None:
        self._table: dict[str, dict[str, str]] = {}
        self._exceptions: list[StrategyException] = []
        self._load_csv(csv_path)
        self._load_exceptions(csv_path)

    def _load_csv(self, csv_path: Path) -> None:
        """Load strategy table from CSV file."""
        with open(csv_path, newline="") as f:
            reader = csv.reader(f)
            header = next(reader)  # Column headers: empty, 2, 3, ..., 10, A

            for row in reader:
                if not row or not row[0]:
                    continue
                row_key = row[0]
                self._table[row_key] = {}
                for i, dealer_card in enumerate(header[1:], start=1):
                    if i < len(row):
                        self._table[row_key][dealer_card] = row[i].strip().upper()

    def _load_exceptions(self, csv_path: Path) -> None:
        """Load companion exception file if it exists.

        Derives the path from the CSV: single-deck.csv -> single-deck-exceptions.json
        """
        json_path = csv_path.with_name(csv_path.stem + "-exceptions.json")
        if not json_path.exists():
            return

        with open(json_path) as f:
            data = json.load(f)

        for entry in data:
            self._exceptions.append(
                StrategyException(
                    description=entry["description"],
                    row_key=entry["row_key"],
                    dealer=entry["dealer"],
                    action=entry["action"],
                    when=entry.get("when", {}),
                )
            )

    def _find_exception(
        self,
        row_key: str,
        dealer_card: str,
        hand: Hand | None,
        rules: Rules | None,
    ) -> StrategyException | None:
        """Find the first matching exception, or None."""
        for exc in self._exceptions:
            if exc.row_key != row_key:
                continue
            if dealer_card not in exc.dealer:
                continue
            if self._check_conditions(exc.when, hand, rules):
                return exc
        return None

    def _check_conditions(
        self,
        when: dict[str, object],
        hand: Hand | None,
        rules: Rules | None,
    ) -> bool:
        """Evaluate all conditions in a 'when' clause (AND logic).

        Unknown keys fail closed (return False).
        """
        for key, value in when.items():
            if key == "composition":
                if hand is None:
                    return False
                hand_values = sorted(card.rank.value for card in hand.cards)
                if hand_values != sorted(value):
                    return False
            elif key == "dealer_hits_soft_17":
                if rules is None:
                    return False
                if rules.dealer_hits_soft_17 != value:
                    return False
            else:
                # Unknown condition — fail closed
                return False
        return True

    def get_correct_action(
        self,
        row_key: str,
        dealer_card: str,
        hand: Hand | None = None,
        rules: Rules | None = None,
    ) -> str:
        """Look up the correct action for a hand vs dealer card.

        Args:
            row_key: Strategy row key ("16", "A7", "88", etc.)
            dealer_card: Dealer up card ("2"-"10" or "A")
            hand: Optional Hand for composition-dependent exceptions
            rules: Optional Rules for rule-dependent exceptions

        Returns:
            The correct action (S, H, D, P, or R)

        Raises:
            KeyError: If the combination is not found in the table
        """
        if row_key not in self._table:
            raise KeyError(f"Unknown hand: {row_key}")
        if dealer_card not in self._table[row_key]:
            raise KeyError(f"Unknown dealer card: {dealer_card}")

        base_action = self._table[row_key][dealer_card]

        exception = self._find_exception(row_key, dealer_card, hand, rules)
        if exception is not None:
            return exception.action

        return base_action

    def check_action(
        self,
        player_action: str,
        row_key: str,
        dealer_card: str,
        hand: Hand | None = None,
        rules: Rules | None = None,
    ) -> tuple[bool, str, StrategyException | None]:
        """Check if a player's action is correct.

        Args:
            player_action: The action chosen by the player
            row_key: Strategy row key ("16", "A7", "88", etc.)
            dealer_card: Dealer up card ("2"-"10" or "A")
            hand: Optional Hand for composition-dependent exceptions
            rules: Optional Rules for rule-dependent exceptions

        Returns:
            Tuple of (is_correct, correct_action, matched_exception)
        """
        if row_key not in self._table:
            raise KeyError(f"Unknown hand: {row_key}")
        if dealer_card not in self._table[row_key]:
            raise KeyError(f"Unknown dealer card: {dealer_card}")

        base_action = self._table[row_key][dealer_card]
        exception = self._find_exception(row_key, dealer_card, hand, rules)
        correct = exception.action if exception is not None else base_action
        is_correct = player_action.upper() == correct
        return is_correct, correct, exception

    def format_table(self, title: str, row_keys: set[str] | None = None) -> list[str]:
        """Return the strategy table as a list of formatted lines (with ANSI color)."""
        dealer_cols = self.DEALER_CARDS

        # Count action frequencies across displayed rows only.
        freq: dict[str, int] = {}
        for key in self._table:
            if row_keys is not None and key not in row_keys:
                continue
            for dc in dealer_cols:
                action = self._table[key].get(dc, "")
                if action:
                    freq[action] = freq.get(action, 0) + 1

        # Sort actions by frequency ascending (rarest first).
        sorted_by_freq = sorted(freq, key=lambda a: freq[a])

        # Assign color tiers to the rarest actions; most common get no color.
        color_map: dict[str, str] = {}
        for i, action in enumerate(sorted_by_freq):
            if i < len(_ACTION_COLOR_TIERS):
                color_map[action] = _ACTION_COLOR_TIERS[i]

        lines = [f"\n{title}\n", "      " + "".join(f"{c:>5}" for c in dealer_cols)]
        for key in self._table:
            if row_keys is not None and key not in row_keys:
                continue
            cells = []
            for dc in dealer_cols:
                action = self._table[key].get(dc, "?")
                color = color_map.get(action, "")
                if color:
                    cells.append(f"{color}{action:>5}{_COLOR_RESET}")
                else:
                    cells.append(f"{action:>5}")
            lines.append(f"  {key:>4}{''.join(cells)}")
        return lines

    def print_table(self, title: str, row_keys: set[str] | None = None) -> None:
        """Print the strategy table as a formatted ASCII table with color coding."""
        for line in self.format_table(title, row_keys=row_keys):
            print(line)
