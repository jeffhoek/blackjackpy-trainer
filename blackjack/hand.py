"""Hand class with blackjack value calculation."""

from .cards import Card


class Hand:
    """A blackjack hand with value calculation."""

    def __init__(self, cards: list[Card] | None = None) -> None:
        self._cards: list[Card] = cards if cards is not None else []

    def add_card(self, card: Card) -> None:
        """Add a card to the hand."""
        self._cards.append(card)

    @property
    def cards(self) -> list[Card]:
        """List of cards in the hand."""
        return self._cards.copy()

    @property
    def value(self) -> int:
        """Best blackjack value (highest <= 21, or lowest if bust)."""
        total = sum(card.value for card in self._cards)
        aces = sum(1 for card in self._cards if card.is_ace)

        # Convert Aces from 11 to 1 as needed to avoid busting
        while total > 21 and aces > 0:
            total -= 10
            aces -= 1

        return total

    @property
    def is_soft(self) -> bool:
        """Check if the hand is soft (Ace counted as 11)."""
        if not any(card.is_ace for card in self._cards):
            return False

        # Calculate value with all Aces as 1
        hard_total = sum(1 if card.is_ace else card.value for card in self._cards)
        # If we can add 10 (making one Ace = 11) without busting, it's soft
        return hard_total + 10 <= 21

    @property
    def is_pair(self) -> bool:
        """Check if the hand is a splittable pair."""
        if len(self._cards) != 2:
            return False
        return self._cards[0].rank == self._cards[1].rank

    @property
    def is_blackjack(self) -> bool:
        """Check if the hand is a natural blackjack."""
        return len(self._cards) == 2 and self.value == 21

    def get_strategy_key(self) -> str:
        """Get the row key for strategy table lookup.

        Returns:
            - Pairs: "AA", "TT", "99", etc. (T for 10-value cards)
            - Soft hands: "A9", "A8", etc.
            - Hard hands: "20", "19", etc.
        """
        if self.is_pair:
            symbol = self._cards[0].strategy_symbol()
            return f"{symbol}{symbol}"

        if self.is_soft:
            # Find the non-Ace card value for soft hand notation
            non_ace_total = sum(
                card.value for card in self._cards if not card.is_ace
            )
            # Add value of additional Aces (as 1 each) beyond the first
            ace_count = sum(1 for card in self._cards if card.is_ace)
            non_ace_total += ace_count - 1  # Extra aces count as 1
            return f"A{non_ace_total}"

        return str(self.value)

    def __str__(self) -> str:
        cards_str = " ".join(str(card) for card in self._cards)
        return f"{cards_str} ({self.value})"

    def __len__(self) -> int:
        return len(self._cards)
