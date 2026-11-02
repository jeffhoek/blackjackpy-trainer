"""Training session orchestration."""

import random
from dataclasses import dataclass
from pathlib import Path

from .cards import Card, Shoe
from .hand import Hand
from .levels import get_keys_for_level
from .metrics import NoOpMetricsClient, create_metrics_client
from .rules import Rules
from .strategy import Action, Band, CountStrategy, Strategy

# True count ranges drawn for each band in Omega II drills
_TC_RANGES = {
    Band.MINUS6: (-12, -6),
    Band.BASIC: (-5, 5),
    Band.PLUS6: (6, 12),
}


def format_true_count(true_count: int) -> str:
    """Format a true count with an explicit sign (+8, -7, 0)."""
    return f"{true_count:+d}" if true_count else "0"


def _dealer_key(card: Card) -> str:
    """Strategy table column key for a dealer up card."""
    key = card.strategy_symbol()
    return "10" if key == "T" else key


@dataclass
class TrainingResult:
    """Result of checking a player's answer."""

    player_hand: Hand
    dealer_card: Card
    player_action: str
    correct_action: str
    is_correct: bool
    exception_description: str | None = None
    true_count: int | None = None
    basic_action: str | None = None

    @property
    def is_deviation(self) -> bool:
        """True when the count changed the play from basic strategy."""
        return self.basic_action is not None and self.basic_action != self.correct_action

    @property
    def feedback(self) -> str:
        """Get feedback message for the result."""
        if self.true_count is None:
            if self.is_correct:
                return "Correct!"
            return f"Wrong. Correct action: {Action.get_name(self.correct_action)}"

        tc = format_true_count(self.true_count)
        correct = Action.get_name(self.correct_action)
        if self.is_deviation:
            basic = Action.get_name(self.basic_action)
            if self.is_correct:
                return f"Correct! At TC {tc} the play is {correct} (basic: {basic})"
            return f"Wrong. At TC {tc} the play is {correct} (basic: {basic})"
        if self.is_correct:
            return "Correct!"
        return f"Wrong. At TC {tc} the play is {correct}, same as basic"


class TrainingStats:
    """Track training session statistics."""

    def __init__(self) -> None:
        self.correct = 0
        self.total = 0
        self.current_streak = 0
        self.best_streak = 0
        self._correct_times: list[float] = []

    def record(self, is_correct: bool, response_time: float = 0.0) -> None:
        """Record a result."""
        self.total += 1
        if is_correct:
            self.correct += 1
            self.current_streak += 1
            if self.current_streak > self.best_streak:
                self.best_streak = self.current_streak
            if response_time > 0:
                self._correct_times.append(response_time)
        else:
            self.current_streak = 0

    @property
    def percentage(self) -> float:
        """Get the accuracy percentage."""
        if self.total == 0:
            return 0.0
        return (self.correct / self.total) * 100

    @property
    def avg_time(self) -> float | None:
        """Average response time for correct answers in seconds."""
        if not self._correct_times:
            return None
        return sum(self._correct_times) / len(self._correct_times)

    @property
    def best_time(self) -> float | None:
        """Fastest correct response time in seconds."""
        if not self._correct_times:
            return None
        return min(self._correct_times)

    def __str__(self) -> str:
        s = f"{self.correct}/{self.total} correct ({self.percentage:.0f}%)"
        if self.avg_time is not None:
            s += f"  avg: {self.avg_time:.1f}s"
        return s


class Trainer:
    """Orchestrates a training session."""

    def __init__(self, rules: Rules, data_dir: Path, metrics=None) -> None:
        self.rules = rules
        self.shoe = Shoe(rules.num_decks)
        self.strategy = Strategy(data_dir / rules.strategy_file)
        self.count_strategy: CountStrategy | None = None
        if rules.omega2:
            self.count_strategy = CountStrategy(data_dir)
        self.stats = TrainingStats()
        self.metrics = metrics if metrics is not None else NoOpMetricsClient()
        self._current_hand: Hand | None = None
        self._current_dealer_card: Card | None = None
        self._current_true_count: int | None = None
        self._allowed_keys: set[str] | None = None
        if rules.level > 0:
            self._allowed_keys = get_keys_for_level(rules.level)

    @property
    def current_true_count(self) -> int | None:
        """True count for the current hand (Omega II sessions only)."""
        return self._current_true_count

    def _reachable_deviation_bands(self) -> list[str]:
        """Bands with at least one deviation cell allowed at the current skill level."""
        assert self.count_strategy is not None
        return [
            band
            for band in (Band.MINUS6, Band.PLUS6)
            if any(
                self._allowed_keys is None or key in self._allowed_keys
                for key, _ in self.count_strategy.deviations(band)
            )
        ]

    def deal_hand(self) -> tuple[Hand, Card]:
        """Deal a new hand for training.

        In Omega II sessions this also draws a true count for the hand
        (see ``current_true_count``).

        Returns:
            Tuple of (player_hand, dealer_up_card)
        """
        # When drilling deviations, pick the band first so the +6 table's few
        # changes come up as often as the -6 table's many
        band: str | None = None
        if self.count_strategy is not None and self.rules.deviations_only:
            bands = self._reachable_deviation_bands()
            if bands:
                band = random.choice(bands)
        deviation_cells = self.count_strategy.deviations(band) if band else None
        # Deviation cells can be rare (3,3 vs 3 is about 1 in 5000 deals),
        # so allow more attempts
        attempts = 100000 if deviation_cells else 1000
        for _ in range(attempts):
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

            # Skip hands the count doesn't change when drilling deviations
            if deviation_cells:
                if (hand.get_strategy_key(), _dealer_key(dealer_card)) not in deviation_cells:
                    continue

            break

        self._current_hand = hand
        self._current_dealer_card = dealer_card
        self._current_true_count = None
        if self.count_strategy is not None:
            if band is None:
                band = random.choice(Band.ALL)
            self._current_true_count = random.randint(*_TC_RANGES[band])

        return hand, dealer_card

    def check_answer(self, action: str, response_time: float = 0.0) -> TrainingResult:
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
        dealer_key = _dealer_key(self._current_dealer_card)

        basic_action: str | None = None
        if self.count_strategy is not None and self._current_true_count is not None:
            is_correct, correct_action, exception = self.count_strategy.check_action(
                action,
                row_key,
                dealer_key,
                self._current_true_count,
                hand=self._current_hand,
                rules=self.rules,
            )
            basic_action = self.count_strategy.basic_action(row_key, dealer_key)
        else:
            is_correct, correct_action, exception = self.strategy.check_action(
                action, row_key, dealer_key, hand=self._current_hand, rules=self.rules
            )

        self.stats.record(is_correct, response_time=response_time)

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
            true_count=self._current_true_count,
            basic_action=basic_action,
        )
