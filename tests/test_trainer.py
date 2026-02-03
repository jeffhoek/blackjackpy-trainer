"""Tests for trainer module."""

from pathlib import Path

import pytest

from blackjack.cards import Card, Rank, Suit
from blackjack.hand import Hand
from blackjack.rules import Rules
from blackjack.trainer import Trainer, TrainingResult, TrainingStats


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def trainer(data_dir):
    rules = Rules(num_decks=6)
    return Trainer(rules, data_dir)


@pytest.fixture
def single_deck_trainer(data_dir):
    rules = Rules(num_decks=1)
    return Trainer(rules, data_dir)


class TestTrainingStats:
    def test_initial_stats(self):
        stats = TrainingStats()
        assert stats.correct == 0
        assert stats.total == 0
        assert stats.percentage == 0.0

    def test_record_correct(self):
        stats = TrainingStats()
        stats.record(True)
        assert stats.correct == 1
        assert stats.total == 1
        assert stats.percentage == 100.0

    def test_record_incorrect(self):
        stats = TrainingStats()
        stats.record(False)
        assert stats.correct == 0
        assert stats.total == 1
        assert stats.percentage == 0.0

    def test_multiple_records(self):
        stats = TrainingStats()
        stats.record(True)
        stats.record(True)
        stats.record(False)
        stats.record(True)
        assert stats.correct == 3
        assert stats.total == 4
        assert stats.percentage == 75.0

    def test_str(self):
        stats = TrainingStats()
        stats.record(True)
        stats.record(False)
        assert str(stats) == "1/2 correct (50%)"


class TestTrainingResult:
    def test_correct_feedback(self):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        result = TrainingResult(
            player_hand=hand,
            dealer_card=Card(Rank.SEVEN, Suit.DIAMONDS),
            player_action="H",
            correct_action="H",
            is_correct=True,
        )
        assert result.feedback == "Correct!"

    def test_incorrect_feedback(self):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        result = TrainingResult(
            player_hand=hand,
            dealer_card=Card(Rank.SIX, Suit.DIAMONDS),
            player_action="H",
            correct_action="S",
            is_correct=False,
        )
        assert result.feedback == "Wrong. Correct action: Stand"


class TestTrainer:
    def test_deal_hand(self, trainer):
        hand, dealer_card = trainer.deal_hand()
        assert len(hand) == 2
        assert isinstance(dealer_card, Card)

    def test_check_answer_correct(self, trainer):
        trainer.deal_hand()
        # We need to check what hand was dealt to know the correct answer
        # For this test, we'll just verify the mechanics work
        hand = trainer._current_hand
        dealer_card = trainer._current_dealer_card

        row_key = hand.get_strategy_key()
        dealer_key = dealer_card.strategy_symbol()
        if dealer_key == "T":
            dealer_key = "10"

        correct_action = trainer.strategy.get_correct_action(row_key, dealer_key)
        result = trainer.check_answer(correct_action)
        assert result.is_correct
        assert trainer.stats.correct == 1

    def test_check_answer_tracks_stats(self, trainer):
        trainer.deal_hand()
        trainer.check_answer("S")  # May or may not be correct
        assert trainer.stats.total == 1

    def test_check_answer_without_deal_raises(self, trainer):
        with pytest.raises(ValueError):
            trainer.check_answer("S")

    def test_reshuffles_when_needed(self, trainer):
        # Deal many hands to trigger reshuffle
        initial_cards = trainer.shoe.cards_remaining
        for _ in range(100):
            trainer.deal_hand()
        # The shoe should have reshuffled at some point
        # We verify by checking that hands can still be dealt
        hand, dealer = trainer.deal_hand()
        assert len(hand) == 2


class TestRules:
    def test_default_rules(self):
        rules = Rules()
        assert rules.num_decks == 1
        assert rules.dealer_hits_soft_17
        assert rules.strategy_file == "single-deck.csv"

    def test_single_deck_rules(self):
        rules = Rules(num_decks=1)
        assert rules.strategy_file == "single-deck.csv"

    def test_rules_str(self):
        rules = Rules(num_decks=6, dealer_hits_soft_17=True)
        assert str(rules) == "6 decks, H17"

        rules = Rules(num_decks=1, dealer_hits_soft_17=False)
        assert str(rules) == "1 deck, S17"
