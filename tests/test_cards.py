"""Tests for cards module."""

import pytest

from blackjack.cards import Card, Rank, Shoe, Suit


class TestRank:
    def test_rank_values(self):
        assert Rank.TWO.value == 2
        assert Rank.TEN.value == 10
        assert Rank.JACK.value == 10
        assert Rank.QUEEN.value == 10
        assert Rank.KING.value == 10
        assert Rank.ACE.value == 11

    def test_rank_symbols(self):
        assert Rank.TWO.symbol == "2"
        assert Rank.TEN.symbol == "10"
        assert Rank.JACK.symbol == "J"
        assert Rank.ACE.symbol == "A"

    def test_is_ten_value(self):
        assert Rank.TEN.is_ten_value
        assert Rank.JACK.is_ten_value
        assert Rank.QUEEN.is_ten_value
        assert Rank.KING.is_ten_value
        assert not Rank.ACE.is_ten_value
        assert not Rank.NINE.is_ten_value


class TestCard:
    def test_card_creation(self):
        card = Card(Rank.ACE, Suit.SPADES)
        assert card.rank == Rank.ACE
        assert card.suit == Suit.SPADES

    def test_card_value(self):
        assert Card(Rank.TWO, Suit.HEARTS).value == 2
        assert Card(Rank.KING, Suit.DIAMONDS).value == 10
        assert Card(Rank.ACE, Suit.CLUBS).value == 11

    def test_card_str(self):
        card = Card(Rank.ACE, Suit.SPADES)
        assert str(card) == "A♠"

    def test_card_is_ace(self):
        assert Card(Rank.ACE, Suit.HEARTS).is_ace
        assert not Card(Rank.KING, Suit.HEARTS).is_ace

    def test_strategy_symbol(self):
        assert Card(Rank.ACE, Suit.HEARTS).strategy_symbol() == "A"
        assert Card(Rank.TEN, Suit.HEARTS).strategy_symbol() == "T"
        assert Card(Rank.JACK, Suit.HEARTS).strategy_symbol() == "T"
        assert Card(Rank.QUEEN, Suit.HEARTS).strategy_symbol() == "T"
        assert Card(Rank.KING, Suit.HEARTS).strategy_symbol() == "T"
        assert Card(Rank.NINE, Suit.HEARTS).strategy_symbol() == "9"

    def test_card_immutable(self):
        card = Card(Rank.ACE, Suit.SPADES)
        with pytest.raises(AttributeError):
            card.rank = Rank.KING


class TestShoe:
    def test_shoe_creation(self):
        shoe = Shoe(num_decks=1)
        assert shoe.num_decks == 1
        assert shoe.cards_remaining == 52

    def test_shoe_multi_deck(self):
        shoe = Shoe(num_decks=6)
        assert shoe.cards_remaining == 312

    def test_deal_card(self):
        shoe = Shoe(num_decks=1)
        card = shoe.deal()
        assert isinstance(card, Card)
        assert shoe.cards_remaining == 51

    def test_deal_all_cards(self):
        shoe = Shoe(num_decks=1)
        cards = [shoe.deal() for _ in range(52)]
        assert len(cards) == 52
        # Dealing from empty shoe triggers reshuffle
        card = shoe.deal()
        assert isinstance(card, Card)

    def test_shuffle_restores_cards(self):
        shoe = Shoe(num_decks=1)
        for _ in range(10):
            shoe.deal()
        assert shoe.cards_remaining == 42
        shoe.shuffle()
        assert shoe.cards_remaining == 52

    def test_needs_shuffle(self):
        shoe = Shoe(num_decks=1)
        assert not shoe.needs_shuffle()
        # Deal 80% of cards
        for _ in range(42):
            shoe.deal()
        assert shoe.needs_shuffle()
