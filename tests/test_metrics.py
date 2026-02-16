"""Tests for metrics module and streak tracking."""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from blackjack.cards import Card, Rank, Suit
from blackjack.metrics import NoOpMetricsClient, create_metrics_client
from blackjack.rules import Rules
from blackjack.trainer import Trainer, TrainingStats


@pytest.fixture
def data_dir():
    return Path(__file__).parent.parent / "data"


@pytest.fixture
def mock_statsd():
    """Inject a fake statsd module into sys.modules so MetricsClient can import it."""
    mock_mod = MagicMock()
    with patch.dict(sys.modules, {"statsd": mock_mod}):
        yield mock_mod


class TestNoOpMetricsClient:
    def test_methods_dont_raise(self):
        client = NoOpMetricsClient()
        client.card_dealt("A")
        client.shoe_shuffled()
        client.answer(True, "hard", "10", "16", 1, 1)
        client.answer(False, "soft", "A", "A6", 0, 1)
        client.end_session(10)


class TestCreateMetricsClient:
    def test_none_host_returns_noop(self):
        client = create_metrics_client(None)
        assert isinstance(client, NoOpMetricsClient)

    def test_none_host_with_port_returns_noop(self):
        client = create_metrics_client(None, 9999)
        assert isinstance(client, NoOpMetricsClient)

    def test_host_returns_metrics_client(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        client = create_metrics_client("localhost", 8125)
        assert isinstance(client, MetricsClient)
        mock_statsd.StatsClient.assert_called_once_with(
            "localhost", 8125, prefix="blackjack"
        )


class TestMetricsClient:
    def test_card_dealt(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.card_dealt("A")

        mock_inner.incr.assert_any_call("cards.dealt.total")
        mock_inner.incr.assert_any_call("cards.dealt.a")

    def test_card_dealt_ten(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.card_dealt("T")

        mock_inner.incr.assert_any_call("cards.dealt.t")

    def test_shoe_shuffled(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.shoe_shuffled()

        mock_inner.incr.assert_called_once_with("shoe.shuffle")

    def test_answer_correct(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.answer(True, "hard", "10", "16", 3, 5)

        mock_inner.incr.assert_any_call("answer.correct")
        mock_inner.incr.assert_any_call("answer.hand_type.hard.correct")
        mock_inner.incr.assert_any_call("answer.dealer.10.correct")
        mock_inner.gauge.assert_any_call("streak.correct", 3)
        mock_inner.gauge.assert_any_call("streak.best", 5)

    def test_answer_wrong(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.answer(False, "soft", "A", "A6", 0, 5)

        mock_inner.incr.assert_any_call("answer.wrong")
        mock_inner.incr.assert_any_call("answer.hand_type.soft.wrong")
        mock_inner.incr.assert_any_call("answer.dealer.A.wrong")
        mock_inner.incr.assert_any_call("answer.hand.A6_vs_A.wrong")

    def test_answer_correct_no_wrong_hand_metric(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        client = MetricsClient("localhost")
        client.answer(True, "hard", "10", "16", 1, 1)

        # Should NOT emit the per-hand wrong metric
        wrong_calls = [
            c for c in mock_inner.incr.call_args_list if "hand." in str(c) and "wrong" in str(c)
        ]
        assert len(wrong_calls) == 0

    def test_end_session(self, mock_statsd):
        from blackjack.metrics import MetricsClient

        mock_inner = MagicMock()
        mock_statsd.StatsClient.return_value = mock_inner

        with patch("blackjack.metrics.time") as mock_time:
            mock_time.monotonic.side_effect = [100.0, 220.0]  # 120 seconds
            client = MetricsClient("localhost")
            client.end_session(30)

        mock_inner.gauge.assert_any_call("session.duration", 120)
        mock_inner.gauge.assert_any_call("session.total_hands", 30)
        mock_inner.gauge.assert_any_call("session.hands_per_minute", 15.0)


class TestTrainingStatsStreak:
    def test_initial_streak(self):
        stats = TrainingStats()
        assert stats.current_streak == 0
        assert stats.best_streak == 0

    def test_correct_increments_streak(self):
        stats = TrainingStats()
        stats.record(True)
        assert stats.current_streak == 1
        assert stats.best_streak == 1

    def test_wrong_resets_streak(self):
        stats = TrainingStats()
        stats.record(True)
        stats.record(True)
        stats.record(False)
        assert stats.current_streak == 0
        assert stats.best_streak == 2

    def test_best_streak_preserved(self):
        stats = TrainingStats()
        stats.record(True)
        stats.record(True)
        stats.record(True)  # streak = 3
        stats.record(False)  # reset
        stats.record(True)
        stats.record(True)  # streak = 2
        assert stats.current_streak == 2
        assert stats.best_streak == 3


class TestTrainerMetricsIntegration:
    def test_deal_hand_emits_card_dealt(self, data_dir):
        mock_metrics = MagicMock()
        rules = Rules(num_decks=6)
        trainer = Trainer(rules, data_dir, metrics=mock_metrics)

        trainer.deal_hand()

        # 3 cards dealt: 2 player + 1 dealer
        assert mock_metrics.card_dealt.call_count == 3

    def test_deal_hand_emits_shuffle(self, data_dir):
        mock_metrics = MagicMock()
        rules = Rules(num_decks=6)
        trainer = Trainer(rules, data_dir, metrics=mock_metrics)

        # Force a reshuffle by depleting the shoe
        trainer.shoe._cards = []
        trainer.deal_hand()

        assert mock_metrics.shoe_shuffled.call_count >= 1

    def test_check_answer_emits_metrics(self, data_dir):
        mock_metrics = MagicMock()
        rules = Rules(num_decks=6)
        trainer = Trainer(rules, data_dir, metrics=mock_metrics)

        trainer.deal_hand()
        trainer.check_answer("S")

        mock_metrics.answer.assert_called_once()
        call_kwargs = mock_metrics.answer.call_args
        # Verify all expected keyword args are present
        assert "is_correct" in call_kwargs.kwargs
        assert "hand_type" in call_kwargs.kwargs
        assert "dealer_key" in call_kwargs.kwargs
        assert "strategy_key" in call_kwargs.kwargs
        assert "current_streak" in call_kwargs.kwargs
        assert "best_streak" in call_kwargs.kwargs

    def test_default_metrics_is_noop(self, data_dir):
        rules = Rules(num_decks=6)
        trainer = Trainer(rules, data_dir)
        assert isinstance(trainer.metrics, NoOpMetricsClient)
