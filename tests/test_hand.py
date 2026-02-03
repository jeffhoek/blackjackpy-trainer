"""Tests for hand module."""

from blackjack.cards import Card, Rank, Suit
from blackjack.hand import Hand


class TestHandValue:
    def test_simple_hand(self):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        assert hand.value == 16

    def test_soft_hand(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        assert hand.value == 17
        assert hand.is_soft

    def test_hard_hand_with_ace(self):
        hand = Hand([
            Card(Rank.ACE, Suit.HEARTS),
            Card(Rank.SIX, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
        ])
        assert hand.value == 15
        assert not hand.is_soft

    def test_multiple_aces(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.CLUBS)])
        assert hand.value == 12
        assert hand.is_soft

    def test_blackjack(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS)])
        assert hand.value == 21
        assert hand.is_blackjack

    def test_21_not_blackjack(self):
        hand = Hand([
            Card(Rank.SEVEN, Suit.HEARTS),
            Card(Rank.SEVEN, Suit.CLUBS),
            Card(Rank.SEVEN, Suit.DIAMONDS),
        ])
        assert hand.value == 21
        assert not hand.is_blackjack

    def test_bust(self):
        hand = Hand([
            Card(Rank.TEN, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.FIVE, Suit.DIAMONDS),
        ])
        assert hand.value == 23


class TestHandPair:
    def test_is_pair(self):
        hand = Hand([Card(Rank.EIGHT, Suit.HEARTS), Card(Rank.EIGHT, Suit.CLUBS)])
        assert hand.is_pair

    def test_ten_value_pair(self):
        hand = Hand([Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS)])
        assert hand.is_pair

    def test_mixed_ten_value_not_pair(self):
        hand = Hand([Card(Rank.KING, Suit.HEARTS), Card(Rank.QUEEN, Suit.CLUBS)])
        assert not hand.is_pair

    def test_three_cards_not_pair(self):
        hand = Hand([
            Card(Rank.EIGHT, Suit.HEARTS),
            Card(Rank.EIGHT, Suit.CLUBS),
            Card(Rank.EIGHT, Suit.DIAMONDS),
        ])
        assert not hand.is_pair


class TestStrategyKey:
    def test_hard_total(self):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        assert hand.get_strategy_key() == "16"

    def test_soft_hand(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.SEVEN, Suit.CLUBS)])
        assert hand.get_strategy_key() == "A7"

    def test_pair(self):
        hand = Hand([Card(Rank.EIGHT, Suit.HEARTS), Card(Rank.EIGHT, Suit.CLUBS)])
        assert hand.get_strategy_key() == "88"

    def test_ace_pair(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.ACE, Suit.CLUBS)])
        assert hand.get_strategy_key() == "AA"

    def test_ten_pair(self):
        hand = Hand([Card(Rank.KING, Suit.HEARTS), Card(Rank.KING, Suit.CLUBS)])
        assert hand.get_strategy_key() == "TT"

    def test_soft_hand_A2(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.TWO, Suit.CLUBS)])
        assert hand.get_strategy_key() == "A2"

    def test_soft_hand_A9(self):
        hand = Hand([Card(Rank.ACE, Suit.HEARTS), Card(Rank.NINE, Suit.CLUBS)])
        assert hand.get_strategy_key() == "A9"


class TestAddCard:
    def test_add_card(self):
        hand = Hand()
        hand.add_card(Card(Rank.TEN, Suit.HEARTS))
        assert len(hand) == 1
        hand.add_card(Card(Rank.SIX, Suit.CLUBS))
        assert len(hand) == 2
        assert hand.value == 16

    def test_cards_property_returns_copy(self):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS)])
        cards = hand.cards
        cards.append(Card(Rank.SIX, Suit.CLUBS))
        assert len(hand) == 1
