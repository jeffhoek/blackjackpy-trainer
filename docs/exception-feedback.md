# Strategy Exception Feedback

## Overview

When a player answers incorrectly and the correct action comes from a strategy exception
(not the base CSV table), the trainer surfaces the exception's description as an additional
hint. This explains *why* the play differs from the strategy chart — particularly important
for composition-dependent single-deck plays that aren't visible in the base table.

## Example

> Incorrect. The correct play is H (Hit).
> Exception: Composition exception — (6,2) hard 8 hits vs 5–6 in single deck.

## Implementation

`blackjack/strategy.py`:
- `_find_exception()` return type changed from `str | None` to `StrategyException | None`
- `check_action()` return signature changed from `tuple[bool, str]` to `tuple[bool, str, StrategyException | None]`
- `get_correct_action()` unchanged externally — internally uses the matched exception's `.action`

`blackjack/trainer.py`:
- `TrainingResult` gains `exception_description: str | None = None`
- `check_answer()` unpacks the new third return value and populates `exception_description`

`blackjack/ui.py`:
- `display_result()` prints the exception description below the wrong-answer message when present

## Verification

```bash
# Single-deck game, get dealt (6,2) vs dealer 5, choose D (double) — should see exception note
uv run python main.py

# Run tests
uv run pytest tests/test_exceptions.py
uv run pytest
```
