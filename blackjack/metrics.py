"""StatsD metrics integration for the blackjack trainer."""

import time


class MetricsClient:
    """Sends metrics to a StatsD server."""

    def __init__(self, host: str, port: int = 8125) -> None:
        try:
            import statsd
        except ImportError:
            raise SystemExit(
                "Error: statsd package not installed. "
                'Install it with: uv pip install -e ".[metrics]"'
            )

        self._client = statsd.StatsClient(host, port, prefix="blackjack")
        self._start_time = time.monotonic()

    def card_dealt(self, rank_symbol: str) -> None:
        """Record a card being dealt."""
        self._client.incr("cards.dealt.total")
        self._client.incr(f"cards.dealt.{rank_symbol.lower()}")

    def shoe_shuffled(self) -> None:
        """Record a shoe shuffle."""
        self._client.incr("shoe.shuffle")

    def answer(
        self,
        is_correct: bool,
        hand_type: str,
        dealer_key: str,
        strategy_key: str,
        current_streak: int,
        best_streak: int,
    ) -> None:
        """Record an answer result with all dimensions."""
        result = "correct" if is_correct else "wrong"
        self._client.incr(f"answer.{result}")
        self._client.incr(f"answer.hand_type.{hand_type}.{result}")
        self._client.incr(f"answer.dealer.{dealer_key}.{result}")

        if not is_correct:
            self._client.incr(f"answer.hand.{strategy_key}_vs_{dealer_key}.wrong")

        self._client.gauge("streak.correct", current_streak)
        self._client.gauge("streak.best", best_streak)

    def end_session(self, total_hands: int) -> None:
        """Send session summary metrics."""
        duration = time.monotonic() - self._start_time
        self._client.gauge("session.duration", round(duration))
        self._client.gauge("session.total_hands", total_hands)
        if duration > 0:
            hands_per_minute = round(total_hands / (duration / 60), 1)
            self._client.gauge("session.hands_per_minute", hands_per_minute)


class NoOpMetricsClient:
    """No-op metrics client used when StatsD is not configured."""

    def card_dealt(self, rank_symbol: str) -> None:
        pass

    def shoe_shuffled(self) -> None:
        pass

    def answer(
        self,
        is_correct: bool,
        hand_type: str,
        dealer_key: str,
        strategy_key: str,
        current_streak: int,
        best_streak: int,
    ) -> None:
        pass

    def end_session(self, total_hands: int) -> None:
        pass


def create_metrics_client(
    host: str | None, port: int = 8125
) -> MetricsClient | NoOpMetricsClient:
    """Factory: returns a real client if host is provided, otherwise no-op."""
    if host is None:
        return NoOpMetricsClient()
    return MetricsClient(host, port)
