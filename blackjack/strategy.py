"""Strategy loading from CSV and action lookup."""

import csv
from pathlib import Path


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


class Strategy:
    """Basic strategy table loaded from CSV."""

    DEALER_CARDS = ["2", "3", "4", "5", "6", "7", "8", "9", "10", "A"]

    def __init__(self, csv_path: Path) -> None:
        self._table: dict[str, dict[str, str]] = {}
        self._load_csv(csv_path)

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

    def get_correct_action(self, row_key: str, dealer_card: str) -> str:
        """Look up the correct action for a hand vs dealer card.

        Args:
            row_key: Strategy row key ("16", "A7", "88", etc.)
            dealer_card: Dealer up card ("2"-"10" or "A")

        Returns:
            The correct action (S, H, D, P, or R)

        Raises:
            KeyError: If the combination is not found in the table
        """
        if row_key not in self._table:
            raise KeyError(f"Unknown hand: {row_key}")
        if dealer_card not in self._table[row_key]:
            raise KeyError(f"Unknown dealer card: {dealer_card}")
        return self._table[row_key][dealer_card]

    def check_action(
        self, player_action: str, row_key: str, dealer_card: str
    ) -> tuple[bool, str]:
        """Check if a player's action is correct.

        Args:
            player_action: The action chosen by the player
            row_key: Strategy row key ("16", "A7", "88", etc.)
            dealer_card: Dealer up card ("2"-"10" or "A")

        Returns:
            Tuple of (is_correct, correct_action)
        """
        correct = self.get_correct_action(row_key, dealer_card)
        is_correct = player_action.upper() == correct
        return is_correct, correct

    def print_table(self, title: str) -> None:
        """Print the strategy table as a formatted ASCII table."""
        dealer_cols = self.DEALER_CARDS
        print(f"\n{title}\n")
        print("      " + "".join(f"{c:>5}" for c in dealer_cols))
        for key in self._table:
            actions = "".join(
                f"{self._table[key].get(dc, '?'):>5}" for dc in dealer_cols
            )
            print(f"  {key:>4}{actions}")
