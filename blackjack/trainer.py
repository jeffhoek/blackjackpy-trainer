"""Training session orchestration."""

from dataclasses import dataclass
from pathlib import Path

from .cards import Card, Shoe
from .hand import Hand
from .levels import get_keys_for_level
from .metrics import NoOpMetricsClient, create_metrics_client
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
    exception_description: str | None = None

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
        self.current_streak = 0
        self.best_streak = 0

    def record(self, is_correct: bool) -> None:
        """Record a result."""
        self.total += 1
        if is_correct:
            self.correct += 1
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
        else:
            self.current_streak = 0

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

    def __init__(self, rules: Rules, data_dir: Path, metrics=None) -> None:
        self.rules = rules
        self.shoe = Shoe(rules.num_decks)
        self.strategy = Strategy(data_dir / rules.strategy_file)
        self.stats = TrainingStats()
        self.metrics = metrics if metrics is not None else NoOpMetricsClient()
        self._current_hand: Hand | None = None
        self._current_dealer_card: Card | None = None
        self._allowed_keys: set[str] | None = None
        if rules.level > 0:
            self._allowed_keys = get_keys_for_level(rules.level)

    def deal_hand(self) -> tuple[Hand, Card]:
        """Deal a new hand for training.

        Returns:
            Tuple of (player_hand, dealer_up_card)
        """
        for _ in range(1000):
            if self.shoe.needs_shuffle():
                self.shoe.shuffle()
                self.metrics.shoe_shuffled()

            # Deal player hand (2 cards)
            hand = Hand()
            card1 = self.shoe.deal()
            self.metrics.card_dealt(card1.strategy_symbol())
            hand.add_card(card1)
            card2 = self.shoe.deal()
            self.metrics.card_dealt(card2.strategy_symbol())
            hand.add_card(card2)

            # Deal dealer up card
            dealer_card = self.shoe.deal()
            self.metrics.card_dealt(dealer_card.strategy_symbol())

            # Skip blackjacks (no strategy decision needed)
            if hand.is_blackjack:
                continue

            # Skip hands not in the allowed set for the current level
            if self._allowed_keys is not None:
                if hand.get_strategy_key() not in self._allowed_keys:
                    continue

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

        is_correct, correct_action, exception = self.strategy.check_action(
            action, row_key, dealer_key, hand=self._current_hand, rules=self.rules
        )

        self.stats.record(is_correct)

        # Determine hand type for metrics
        if self._current_hand.is_pair:
            hand_type = "pair"
        elif self._current_hand.is_soft:
            hand_type = "soft"
        else:
            hand_type = "hard"

        self.metrics.answer(
            is_correct=is_correct,
            hand_type=hand_type,
            dealer_key=dealer_key,
            strategy_key=row_key,
            current_streak=self.stats.current_streak,
            best_streak=self.stats.best_streak,
        )

        return TrainingResult(
            player_hand=self._current_hand,
            dealer_card=self._current_dealer_card,
            player_action=action.upper(),
            correct_action=correct_action,
            is_correct=is_correct,
            exception_description=exception.description if exception is not None else None,
        )
