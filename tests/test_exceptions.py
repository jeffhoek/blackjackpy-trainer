"""Tests for strategy exception system."""

from pathlib import Path

import pytest

from blackjack.cards import Card, Rank, Suit
from blackjack.hand import Hand
from blackjack.rules import Rules
from blackjack.strategy import Strategy
from blackjack.trainer import Trainer


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def single_deck_strategy(data_dir):
    return Strategy(data_dir / "single-deck.csv")


@pytest.fixture
def multi_deck_strategy(data_dir):
    return Strategy(data_dir / "multi-deck.csv")


class TestExceptionLoading:
    def test_single_deck_loads_exceptions(self, single_deck_strategy):
        assert len(single_deck_strategy._exceptions) == 2

    def test_multi_deck_no_exceptions(self, multi_deck_strategy):
        assert len(multi_deck_strategy._exceptions) == 0

    def test_base_table_unchanged(self, single_deck_strategy):
        """Exceptions don't alter the base table values."""
        # Hard 8 vs 5 base is still D in the table
        assert single_deck_strategy._table["8"]["5"] == "D"
        assert single_deck_strategy._table["8"]["6"] == "D"
        # A7 vs A base is still S in the table
        assert single_deck_strategy._table["A7"]["A"] == "S"


class TestCompositionException:
    def _make_hand(self, rank1, rank2):
        return Hand([Card(rank1, Suit.HEARTS), Card(rank2, Suit.CLUBS)])

    def test_6_2_vs_5_hits(self, single_deck_strategy):
        """(6,2) hard 8 vs dealer 5 should Hit (exception overrides Double)."""
        hand = self._make_hand(Rank.SIX, Rank.TWO)
        action = single_deck_strategy.get_correct_action("8", "5", hand=hand)
        assert action == "H"

    def test_6_2_vs_6_hits(self, single_deck_strategy):
        """(6,2) hard 8 vs dealer 6 should Hit (exception overrides Double)."""
        hand = self._make_hand(Rank.SIX, Rank.TWO)
        action = single_deck_strategy.get_correct_action("8", "6", hand=hand)
        assert action == "H"

    def test_5_3_vs_5_doubles(self, single_deck_strategy):
        """(5,3) hard 8 vs dealer 5 should Double (no composition match)."""
        hand = self._make_hand(Rank.FIVE, Rank.THREE)
        action = single_deck_strategy.get_correct_action("8", "5", hand=hand)
        assert action == "D"

    def test_5_3_vs_6_doubles(self, single_deck_strategy):
        """(5,3) hard 8 vs dealer 6 should Double (no composition match)."""
        hand = self._make_hand(Rank.FIVE, Rank.THREE)
        action = single_deck_strategy.get_correct_action("8", "6", hand=hand)
        assert action == "D"

    def test_6_2_vs_4_no_exception(self, single_deck_strategy):
        """(6,2) vs dealer 4 — exception only covers 5 and 6."""
        hand = self._make_hand(Rank.SIX, Rank.TWO)
        action = single_deck_strategy.get_correct_action("8", "4", hand=hand)
        assert action == "H"  # Base table: hard 8 vs 4 is H

    def test_no_hand_returns_base_action(self, single_deck_strategy):
        """Without a hand, composition can't match — returns base action."""
        action = single_deck_strategy.get_correct_action("8", "5")
        assert action == "D"


class TestRuleDependentException:
    def _make_soft_18(self):
        return Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SEVEN, Suit.CLUBS)])

    def test_a7_vs_ace_h17_hits(self, single_deck_strategy):
        """A7 vs Ace with H17 should Hit (exception overrides Stand)."""
        hand = self._make_soft_18()
        rules = Rules(num_decks=1, dealer_hits_soft_17=True)
        action = single_deck_strategy.get_correct_action(
            "A7", "A", hand=hand, rules=rules
        )
        assert action == "H"

    def test_a7_vs_ace_s17_stands(self, single_deck_strategy):
        """A7 vs Ace with S17 should Stand (exception doesn't match)."""
        hand = self._make_soft_18()
        rules = Rules(num_decks=1, dealer_hits_soft_17=False)
        action = single_deck_strategy.get_correct_action(
            "A7", "A", hand=hand, rules=rules
        )
        assert action == "S"

    def test_no_rules_returns_base_action(self, single_deck_strategy):
        """Without rules, rule-dependent exception can't match."""
        hand = self._make_soft_18()
        action = single_deck_strategy.get_correct_action("A7", "A", hand=hand)
        assert action == "S"


class TestCheckActionWithExceptions:
    def test_check_action_composition_correct(self, single_deck_strategy):
        """check_action should respect composition exceptions."""
        hand = Hand([Card(Rank.SIX, Suit.HEARTS), Card(Rank.TWO, Suit.CLUBS)])
        is_correct, correct = single_deck_strategy.check_action(
            "H", "8", "5", hand=hand
        )
        assert is_correct
        assert correct == "H"

    def test_check_action_composition_incorrect(self, single_deck_strategy):
        """Doubling (6,2) vs 5 should be wrong with exception active."""
        hand = Hand([Card(Rank.SIX, Suit.HEARTS), Card(Rank.TWO, Suit.CLUBS)])
        is_correct, correct = single_deck_strategy.check_action(
            "D", "8", "5", hand=hand
        )
        assert not is_correct
        assert correct == "H"

    def test_check_action_rule_dependent(self, single_deck_strategy):
        """check_action should respect rule-dependent exceptions."""
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SEVEN, Suit.CLUBS)])
        rules = Rules(num_decks=1, dealer_hits_soft_17=True)
        is_correct, correct = single_deck_strategy.check_action(
            "H", "A7", "A", hand=hand, rules=rules
        )
        assert is_correct
        assert correct == "H"


class TestTrainerIntegration:
    def test_trainer_passes_hand_for_composition(self, data_dir):
        """Trainer should pass hand to strategy for composition checks."""
        rules = Rules(num_decks=1)
        trainer = Trainer(rules, data_dir)

        # Manually set up a (6,2) hand vs dealer 5
        hand = Hand([Card(Rank.SIX, Suit.HEARTS), Card(Rank.TWO, Suit.CLUBS)])
        trainer._current_hand = hand
        trainer._current_dealer_card = Card(Rank.FIVE, Suit.DIAMONDS)

        result = trainer.check_answer("H")
        assert result.is_correct
        assert result.correct_action == "H"

    def test_trainer_passes_rules_for_h17(self, data_dir):
        """Trainer should pass rules to strategy for rule-dependent checks."""
        rules = Rules(num_decks=1, dealer_hits_soft_17=True)
        trainer = Trainer(rules, data_dir)

        # Manually set up A7 vs dealer Ace
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SEVEN, Suit.CLUBS)])
        trainer._current_hand = hand
        trainer._current_dealer_card = Card(Rank.ACE, Suit.DIAMONDS)

        result = trainer.check_answer("H")
        assert result.is_correct
        assert result.correct_action == "H"

    def test_trainer_s17_no_exception(self, data_dir):
        """With S17, A7 vs Ace should still be Stand."""
        rules = Rules(num_decks=1, dealer_hits_soft_17=False)
        trainer = Trainer(rules, data_dir)

        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SEVEN, Suit.CLUBS)])
        trainer._current_hand = hand
        trainer._current_dealer_card = Card(Rank.ACE, Suit.DIAMONDS)

        result = trainer.check_answer("S")
        assert result.is_correct
        assert result.correct_action == "S"
