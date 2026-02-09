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
    ) -> str | None:
        """Find the first matching exception, or None."""
        for exc in self._exceptions:
            if exc.row_key != row_key:
                continue
            if dealer_card not in exc.dealer:
                continue
            if self._check_conditions(exc.when, hand, rules):
                return exc.action
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

        exception_action = self._find_exception(row_key, dealer_card, hand, rules)
        if exception_action is not None:
            return exception_action

        return base_action

    def check_action(
        self,
        player_action: str,
        row_key: str,
        dealer_card: str,
        hand: Hand | None = None,
        rules: Rules | None = None,
    ) -> tuple[bool, str]:
        """Check if a player's action is correct.

        Args:
            player_action: The action chosen by the player
            row_key: Strategy row key ("16", "A7", "88", etc.)
            dealer_card: Dealer up card ("2"-"10" or "A")
            hand: Optional Hand for composition-dependent exceptions
            rules: Optional Rules for rule-dependent exceptions

        Returns:
            Tuple of (is_correct, correct_action)
        """
        correct = self.get_correct_action(row_key, dealer_card, hand, rules)
        is_correct = player_action.upper() == correct
        return is_correct, correct
