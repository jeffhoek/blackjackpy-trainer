"""Tests for strategy module."""

from pathlib import Path

import pytest

from blackjack.strategy import Action, Strategy


@pytest.fixture
def multi_deck_strategy():
    data_dir = Path(__file__).parent.parent / "data"
    return Strategy(data_dir / "multi-deck.csv")


@pytest.fixture
def single_deck_strategy():
    data_dir = Path(__file__).parent.parent / "data"
    return Strategy(data_dir / "single-deck.csv")


class TestAction:
    def test_action_constants(self):
        assert Action.STAND == "S"
        assert Action.HIT == "H"
        assert Action.DOUBLE == "D"
        assert Action.SPLIT == "P"
        assert Action.SURRENDER == "R"

    def test_get_name(self):
        assert Action.get_name("S") == "Stand"
        assert Action.get_name("H") == "Hit"
        assert Action.get_name("D") == "Double"
        assert Action.get_name("P") == "Split"
        assert Action.get_name("R") == "Surrender"
        assert Action.get_name("s") == "Stand"  # Case insensitive


class TestStrategyMultiDeck:
    def test_hard_16_vs_10_surrender(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("16", "10")
        assert action == "R"

    def test_hard_16_vs_6_stand(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("16", "6")
        assert action == "S"

    def test_hard_11_vs_10_double(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("11", "10")
        assert action == "D"  # Multi-deck: Double vs 10

    def test_hard_11_vs_6_double(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("11", "6")
        assert action == "D"

    def test_soft_17_vs_3_double(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("A6", "3")
        assert action == "D"

    def test_soft_18_vs_9_hit(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("A7", "9")
        assert action == "H"

    def test_pair_88_vs_10_split(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("88", "10")
        assert action == "P"

    def test_pair_88_vs_A_surrender(self, multi_deck_strategy):
        action = multi_deck_strategy.get_correct_action("88", "A")
        assert action == "R"

    def test_pair_AA_always_split(self, multi_deck_strategy):
        for dealer in Strategy.DEALER_CARDS:
            action = multi_deck_strategy.get_correct_action("AA", dealer)
            assert action == "P"

    def test_pair_TT_always_stand(self, multi_deck_strategy):
        for dealer in Strategy.DEALER_CARDS:
            action = multi_deck_strategy.get_correct_action("TT", dealer)
            assert action == "S"


class TestStrategySingleDeck:
    def test_hard_11_vs_ace_double(self, single_deck_strategy):
        action = single_deck_strategy.get_correct_action("11", "A")
        assert action == "D"  # Single deck: Double vs A

    def test_hard_9_vs_2_double(self, single_deck_strategy):
        action = single_deck_strategy.get_correct_action("9", "2")
        assert action == "D"  # Single deck: Double

    def test_soft_A8_vs_5_double(self, single_deck_strategy):
        action = single_deck_strategy.get_correct_action("A8", "5")
        assert action == "D"


class TestCheckAction:
    def test_correct_action(self, multi_deck_strategy):
        is_correct, correct = multi_deck_strategy.check_action("S", "20", "10")
        assert is_correct
        assert correct == "S"

    def test_incorrect_action(self, multi_deck_strategy):
        is_correct, correct = multi_deck_strategy.check_action("H", "20", "10")
        assert not is_correct
        assert correct == "S"

    def test_case_insensitive(self, multi_deck_strategy):
        is_correct, _ = multi_deck_strategy.check_action("s", "20", "10")
        assert is_correct


class TestStrategyErrors:
    def test_unknown_hand(self, multi_deck_strategy):
        with pytest.raises(KeyError):
            multi_deck_strategy.get_correct_action("21", "10")  # 21 is not a valid row

    def test_unknown_dealer_card(self, multi_deck_strategy):
        with pytest.raises(KeyError):
            multi_deck_strategy.get_correct_action("16", "X")
