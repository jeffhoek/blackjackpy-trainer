"""Training session orchestration."""

from dataclasses import dataclass
from pathlib import Path

from .cards import Card, Shoe
from .hand import Hand
from .rules import Rules
from .strategy import Action, Strategy


@dataclass
class TrainingResult:
    """Result of checking a player's answer."""

    player_hand: Hand
    dealer_card: Card
    player_action: str
    correct_action: str
    is_correct: bool

    @property
    def feedback(self) -> str:
        """Get feedback message for the result."""
        if self.is_correct:
            return "Correct!"
        return f"Wrong. Correct action: {Action.get_name(self.correct_action)}"


class TrainingStats:
    """Track training session statistics."""

    def __init__(self) -> None:
        self.correct = 0
        self.total = 0

    def record(self, is_correct: bool) -> None:
        """Record a result."""
        self.total += 1
        if is_correct:
            self.correct += 1

    @property
    def percentage(self) -> float:
        """Get the accuracy percentage."""
        if self.total == 0:
            return 0.0
        return (self.correct / self.total) * 100

    def __str__(self) -> str:
        return f"{self.correct}/{self.total} correct ({self.percentage:.0f}%)"


class Trainer:
    """Orchestrates a training session."""

    def __init__(self, rules: Rules, data_dir: Path) -> None:
        self.rules = rules
        self.shoe = Shoe(rules.num_decks)
        self.strategy = Strategy(data_dir / rules.strategy_file)
        self.stats = TrainingStats()
        self._current_hand: Hand | None = None
        self._current_dealer_card: Card | None = None

    def deal_hand(self) -> tuple[Hand, Card]:
        """Deal a new hand for training.

        Returns:
            Tuple of (player_hand, dealer_up_card)
        """
        while True:
            if self.shoe.needs_shuffle():
                self.shoe.shuffle()

            # Deal player hand (2 cards)
            hand = Hand()
            hand.add_card(self.shoe.deal())
            hand.add_card(self.shoe.deal())

            # Deal dealer up card
            dealer_card = self.shoe.deal()

            # Re-deal if player has blackjack (no strategy decision needed)
            if not hand.is_blackjack:
                break

        self._current_hand = hand
        self._current_dealer_card = dealer_card

        return hand, dealer_card

    def check_answer(self, action: str) -> TrainingResult:
        """Check the player's answer for the current hand.

        Args:
            action: The player's chosen action (S, H, D, P, or R)

        Returns:
            TrainingResult with feedback

        Raises:
            ValueError: If no hand has been dealt
        """
        if self._current_hand is None or self._current_dealer_card is None:
            raise ValueError("No hand has been dealt")

        row_key = self._current_hand.get_strategy_key()
        dealer_key = self._current_dealer_card.strategy_symbol()
        if dealer_key == "T":
            dealer_key = "10"

        is_correct, correct_action = self.strategy.check_action(
            action, row_key, dealer_key
        )

        self.stats.record(is_correct)

        return TrainingResult(
            player_hand=self._current_hand,
            dealer_card=self._current_dealer_card,
            player_action=action.upper(),
            correct_action=correct_action,
            is_correct=is_correct,
        )
