"""Card, Rank, Suit, and Shoe classes for blackjack."""

import random
from dataclasses import dataclass
from enum import Enum


class Suit(Enum):
    """Card suits with Unicode symbols."""

    HEARTS = "♥"
    DIAMONDS = "♦"
    CLUBS = "♣"
    SPADES = "♠"


class Rank(Enum):
    """Card ranks with blackjack values."""

    TWO = (2, "2")
    THREE = (3, "3")
    FOUR = (4, "4")
    FIVE = (5, "5")
    SIX = (6, "6")
    SEVEN = (7, "7")
    EIGHT = (8, "8")
    NINE = (9, "9")
    TEN = (10, "10")
    JACK = (10, "J")
    QUEEN = (10, "Q")
    KING = (10, "K")
    ACE = (11, "A")

    def __init__(self, value: int, symbol: str) -> None:
        self._value = value
        self._symbol = symbol

    @property
    def value(self) -> int:
        """Blackjack value of the rank (Ace = 11)."""
        return self._value

    @property
    def symbol(self) -> str:
        """Display symbol for the rank."""
        return self._symbol

    @property
    def is_ten_value(self) -> bool:
        """Check if this rank has a value of 10."""
        return self._value == 10 and self != Rank.ACE


@dataclass(frozen=True)
class Card:
    """An immutable playing card."""

    rank: Rank
    suit: Suit

    def __str__(self) -> str:
        return f"{self.rank.symbol}{self.suit.value}"

    @property
    def value(self) -> int:
        """Blackjack value of this card."""
        return self.rank.value

    @property
    def is_ace(self) -> bool:
        """Check if this card is an Ace."""
        return self.rank == Rank.ACE

    def strategy_symbol(self) -> str:
        """Symbol used in strategy table lookup (T for 10-value cards)."""
        if self.rank.is_ten_value:
            return "T"
        return self.rank.symbol


class Shoe:
    """A multi-deck shoe that can shuffle and deal cards."""

    RESHUFFLE_THRESHOLD = 0.25  # Reshuffle when 25% of cards remain

    def __init__(self, num_decks: int = 6) -> None:
        self.num_decks = num_decks
        self._cards: list[Card] = []
        self._build_shoe()
        self.shuffle()

    def _build_shoe(self) -> None:
        """Build the shoe with the specified number of decks."""
        self._cards = []
        for _ in range(self.num_decks):
            for suit in Suit:
                for rank in Rank:
                    self._cards.append(Card(rank, suit))

    def shuffle(self) -> None:
        """Shuffle all cards back into the shoe."""
        self._build_shoe()
        random.shuffle(self._cards)

    def deal(self) -> Card:
        """Deal one card from the shoe."""
        if not self._cards:
            self.shuffle()
        return self._cards.pop()

    def needs_shuffle(self) -> bool:
        """Check if the shoe needs to be reshuffled."""
        total_cards = self.num_decks * 52
        return len(self._cards) < total_cards * self.RESHUFFLE_THRESHOLD

    @property
    def cards_remaining(self) -> int:
        """Number of cards remaining in the shoe."""
        return len(self._cards)
