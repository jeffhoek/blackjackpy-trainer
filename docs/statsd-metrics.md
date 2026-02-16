# StatsD Metrics Integration

The blackjack trainer supports optional [StatsD](https://github.com/statsd/statsd) metrics for monitoring training sessions in real time. When enabled, metrics are emitted for card dealing, shoe shuffles, strategy accuracy breakdowns, streaks, and session summaries. A pre-built Grafana dashboard is included.

Metrics are disabled by default and have zero impact on normal usage. Enable them by passing `--statsd-host` on the command line.

## Quick Start

### 1. Install the metrics dependency

```bash
uv pip install -e ".[metrics]"
```

### 2. Start a StatsD-compatible stack

You need a StatsD receiver, a time-series database, and a dashboard tool. The easiest way is to use the **TIG stack** (Telegraf + InfluxDB + Grafana):

> **[github.com/jeffhoek/tig-stack](https://github.com/jeffhoek/tig-stack)** -- Docker Compose setup to spin up Telegraf, InfluxDB, and Grafana in seconds.

### 3. Run the trainer with metrics enabled

```bash
uv run python main.py --statsd-host localhost
```

By default, metrics are sent to UDP port 8125. Use `--statsd-port` to override:

```bash
uv run python main.py --statsd-host localhost --statsd-port 9125
```

## Grafana Dashboard

A ready-made Grafana dashboard is included at [`grafana/dashboard.json`](../grafana/dashboard.json). Import it into your Grafana instance to visualize:

- Answer accuracy (correct vs. wrong over time)
- Accuracy by hand type (hard, soft, pair)
- Accuracy by dealer upcard
- Current and best streaks
- Cards dealt and shoe shuffles
- Session duration and pace (hands per minute)

## Metrics Reference

All metrics are prefixed with `blackjack.`.

### Card / Shoe

| Metric | Type | Description |
|--------|------|-------------|
| `cards.dealt.total` | counter | Every card dealt |
| `cards.dealt.{rank}` | counter | Per rank (`2`..`10`, `a`) |
| `shoe.shuffle` | counter | Each shoe reshuffle |

### Strategy Accuracy

| Metric | Type | Description |
|--------|------|-------------|
| `answer.correct` | counter | Correct answers |
| `answer.wrong` | counter | Wrong answers |
| `answer.hand_type.{hard\|soft\|pair}.correct` | counter | Correct, by hand type |
| `answer.hand_type.{hard\|soft\|pair}.wrong` | counter | Wrong, by hand type |
| `answer.dealer.{upcard}.correct` | counter | Correct, by dealer upcard |
| `answer.dealer.{upcard}.wrong` | counter | Wrong, by dealer upcard |
| `answer.hand.{key}_vs_{dealer}.wrong` | counter | Wrong answers for a specific hand matchup |
| `streak.correct` | gauge | Current correct-answer streak |
| `streak.best` | gauge | Best streak this session |

### Session (sent when the training loop exits)

| Metric | Type | Description |
|--------|------|-------------|
| `session.duration` | gauge | Session length in seconds |
| `session.total_hands` | gauge | Total hands played |
| `session.hands_per_minute` | gauge | Pace of play |

## Architecture Notes

- **`blackjack/metrics.py`** contains `MetricsClient` (real) and `NoOpMetricsClient` (stub). A factory function `create_metrics_client(host, port)` returns the appropriate one.
- When `--statsd-host` is not provided, the `NoOpMetricsClient` is used and the `statsd` package does not need to be installed.
- The `statsd` package is an optional dependency declared under `[project.optional-dependencies]` in `pyproject.toml`.
