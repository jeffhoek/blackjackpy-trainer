"""Game rules configuration."""

from dataclasses import dataclass


@dataclass
class Rules:
    """Configuration for blackjack game rules."""

    num_decks: int = 1
    dealer_hits_soft_17: bool = True  # H17 vs S17 (for future use)

    @property
    def strategy_file(self) -> str:
        """Get the strategy filename based on deck count."""
        if self.num_decks == 1:
            return "single-deck.csv"
        return "multi-deck.csv"

    def __str__(self) -> str:
        deck_str = "1 deck" if self.num_decks == 1 else f"{self.num_decks} decks"
        h17_str = "H17" if self.dealer_hits_soft_17 else "S17"
        return f"{deck_str}, {h17_str}"
