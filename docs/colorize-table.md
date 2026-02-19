# Colorize Strategy Table by Action Frequency

## Overview

The `--table` CLI flag prints the basic strategy table with ANSI color coding. Rarer actions
get more visually prominent colors so players can quickly spot exceptional decisions.

## Color Scheme

| Action | Color | ANSI Code |
|--------|-------|-----------|
| R (Surrender) | Bold bright magenta | `\033[1;95m` |
| D (Double) | Bright yellow | `\033[93m` |
| P (Split) | Bright cyan | `\033[96m` |
| S (Stand) | Default white | — |
| H (Hit) | Default white | — |

## Dynamic Frequency Counting

Colors are assigned based on action frequency within the **displayed rows only** (respects
`--level` filter). Actions are sorted ascending by count; the rarest get color tiers.

This means at filtered levels the coloring adapts automatically — e.g. at `--level 3`
(splits only), S becomes rarer than H and picks up a color tier.

## Implementation

Only `blackjack/strategy.py` was modified:

- Two module-level constants: `_COLOR_RESET` and `_ACTION_COLOR_TIERS`
- `print_table` counts frequencies, sorts ascending, builds `color_map`, applies color with
  padding inside the color span so invisible escape bytes don't shift column widths

## Verification

```bash
uv run python main.py --table multi-deck           # R=magenta, D=yellow, P=cyan, S/H=white
uv run python main.py --table single-deck          # similar
uv run python main.py --table multi-deck --level 3 # splits only: dynamic coloring
uv run python main.py --table multi-deck --level 5 # S=magenta, D=yellow, H/P lower tiers
uv run pytest                                       # all tests pass
```
