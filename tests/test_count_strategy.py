"""Tests for Omega II count-based strategy (TC -6 / +6 tables)."""

from pathlib import Path

import pytest

from blackjack.cards import Card, Rank, Suit
from blackjack.hand import Hand
from blackjack.rules import Rules
from blackjack.strategy import Band, CountStrategy
from blackjack.trainer import Trainer, TrainingResult, format_true_count


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def count_strategy(data_dir):
    return CountStrategy(data_dir)


class TestBand:
    @pytest.mark.parametrize(
        "tc, band",
        [
            (-12, Band.MINUS6),
            (-6, Band.MINUS6),
            (-5, Band.BASIC),
            (0, Band.BASIC),
            (5, Band.BASIC),
            (6, Band.PLUS6),
            (12, Band.PLUS6),
        ],
    )
    def test_band_edges(self, tc, band):
        assert Band.for_true_count(tc) == band


class TestCountStrategy:
    def test_change_counts_match_book(self, count_strategy):
        # Table 5.1 lists 48 changes. Table 5.3 lists 12, but 4 of those are
        # footnote changes on cells whose letter matches basic.
        assert len(count_strategy.deviations(Band.MINUS6)) == 48
        assert len(count_strategy.deviations(Band.PLUS6)) == 8
        assert count_strategy.deviations(Band.BASIC) == set()

    def test_tables_cover_same_rows(self, count_strategy):
        basic_keys = count_strategy.tables[Band.BASIC].row_keys()
        for band in Band.ALL:
            assert count_strategy.tables[band].row_keys() == basic_keys

    @pytest.mark.parametrize(
        "row, dealer, tc, expected",
        [
            # Hard 16 vs 10: surrender in basic and +6, hit at -6
            ("16", "10", -6, "H"),
            ("16", "10", -5, "R"),
            ("16", "10", 6, "R"),
            # Hard 12 vs 2: stand only at +6
            ("12", "2", 5, "H"),
            ("12", "2", 6, "S"),
            # Hard 11 vs A: double except at -6
            ("11", "A", -6, "H"),
            ("11", "A", 0, "D"),
            # A,8 vs 4: double at +6
            ("A8", "4", 5, "S"),
            ("A8", "4", 6, "D"),
            # 9,9 vs 2: stand at -6
            ("99", "2", -6, "S"),
            ("99", "2", -5, "P"),
            # 3,3 vs 3: split at +6, hit otherwise
            ("33", "3", 0, "H"),
            ("33", "3", 6, "P"),
            # A,A vs A: hit at -6
            ("AA", "A", -7, "H"),
        ],
    )
    def test_known_cells(self, count_strategy, row, dealer, tc, expected):
        _, correct, _ = count_strategy.check_action("S", row, dealer, tc)
        assert correct == expected

    def test_book_basic_is_no_das(self, count_strategy):
        # The book's basic doesn't split these, unlike data/single-deck.csv
        assert count_strategy.basic_action("44", "5") == "D"
        assert count_strategy.basic_action("22", "2") == "H"


class TestOmega2Trainer:
    def test_true_count_drawn(self, data_dir):
        trainer = Trainer(Rules(omega2=True), data_dir)
        for _ in range(50):
            trainer.deal_hand()
            assert -12 <= trainer.current_true_count <= 12

    def test_no_true_count_without_omega2(self, data_dir):
        trainer = Trainer(Rules(), data_dir)
        trainer.deal_hand()
        assert trainer.current_true_count is None

    def test_deviations_only_deals_deviations(self, data_dir):
        trainer = Trainer(Rules(omega2=True, deviations_only=True), data_dir)
        cs = trainer.count_strategy
        for _ in range(30):
            hand, dealer = trainer.deal_hand()
            key = hand.get_strategy_key()
            dealer_key = "10" if dealer.strategy_symbol() == "T" else dealer.strategy_symbol()
            band = Band.for_true_count(trainer.current_true_count)
            assert (key, dealer_key) in cs.deviations(band)

    def test_check_answer_uses_count_table(self, data_dir):
        trainer = Trainer(Rules(omega2=True), data_dir)
        trainer._current_hand = Hand(
            [Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)]
        )
        trainer._current_dealer_card = Card(Rank.TEN, Suit.SPADES)
        trainer._current_true_count = -8
        result = trainer.check_answer("H")
        assert result.is_correct
        assert result.is_deviation
        assert result.basic_action == "R"


class TestFeedback:
    def _result(self, **kwargs):
        hand = Hand([Card(Rank.TEN, Suit.HEARTS), Card(Rank.SIX, Suit.CLUBS)])
        defaults = dict(
            player_hand=hand,
            dealer_card=Card(Rank.TEN, Suit.SPADES),
            player_action="R",
            correct_action="H",
            is_correct=False,
            true_count=-8,
            basic_action="R",
        )
        defaults.update(kwargs)
        return TrainingResult(**defaults)

    def test_wrong_deviation(self):
        assert self._result().feedback == "Wrong. At TC -8 the play is Hit (basic: Surrender)"

    def test_correct_deviation(self):
        result = self._result(player_action="H", is_correct=True)
        assert result.feedback == "Correct! At TC -8 the play is Hit (basic: Surrender)"

    def test_wrong_same_as_basic(self):
        result = self._result(true_count=2, correct_action="R", player_action="H")
        assert result.feedback == "Wrong. At TC +2 the play is Surrender, same as basic"

    def test_format_true_count(self):
        assert format_true_count(8) == "+8"
        assert format_true_count(-7) == "-7"
        assert format_true_count(0) == "0"
