"""Console user interface for the trainer."""

import os
import sys
import time
from pathlib import Path

from .levels import LEVEL_NAMES
from .rules import Rules
from .strategy import Action
from .trainer import Trainer

# Number of lines reserved for the fixed top bar
_TOP_BAR_LINES = 2


def getch() -> str:
    """Read a single character from stdin without requiring Enter."""
    try:
        import termios
        import tty

        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch
    except ImportError:
        # Windows fallback
        import msvcrt

        return msvcrt.getch().decode("utf-8", errors="ignore")


def _get_terminal_rows() -> int:
    """Get terminal height in rows."""
    try:
        return os.get_terminal_size().lines
    except OSError:
        return 24


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


def _setup_top_bar() -> None:
    """Set up a fixed top bar with action commands and a scroll region below."""
    rows = _get_terminal_rows()
    # Clear screen and move to top
    print("\033[2J\033[H", end="")
    # Draw the top bar
    bar = "[S]tand  [H]it  [D]ouble  s[P]lit  su[R]render  [Q]uit"
    print(f"\033[7m {bar:<{os.get_terminal_size().columns - 1}}\033[0m")
    print("\033[90m" + "─" * os.get_terminal_size().columns + "\033[0m", end="")
    # Set scroll region to rows below the top bar
    print(f"\033[{_TOP_BAR_LINES + 1};{rows}r", end="")
    # Move cursor into the scroll region
    print(f"\033[{_TOP_BAR_LINES + 1};1H", end="", flush=True)


def _teardown_top_bar() -> None:
    """Reset the scroll region to full screen."""
    rows = _get_terminal_rows()
    print(f"\033[1;{rows}r", end="", flush=True)


def get_rules() -> Rules:
    """Prompt user to configure game rules."""
    print("\n=== Game Configuration ===\n")

    # Number of decks
    while True:
        deck_input = input("Number of decks (1/6) [1]: ").strip()
        if deck_input == "":
            num_decks = 1
            break
        if deck_input in ("1", "6"):
            num_decks = int(deck_input)
            break
        print("Please enter 1 or 6")

    # Dealer hits soft 17
    while True:
        h17_input = input("Dealer hits soft 17? (y/n) [y]: ").strip().lower()
        if h17_input == "":
            dealer_hits_soft_17 = True
            break
        if h17_input in ("y", "yes"):
            dealer_hits_soft_17 = True
            break
        if h17_input in ("n", "no"):
            dealer_hits_soft_17 = False
            break
        print("Please enter y or n")

    # Skill level
    print("\nSkill levels:")
    for lvl, name in sorted(LEVEL_NAMES.items()):
        print(f"  {lvl} - {name}")
    while True:
        level_input = input("Skill level (0-7) [0]: ").strip()
        if level_input == "":
            level = 0
            break
        if level_input in ("0", "1", "2", "3", "4", "5", "6", "7"):
            level = int(level_input)
            break
        print("Please enter 0-7")

    return Rules(num_decks=num_decks, dealer_hits_soft_17=dealer_hits_soft_17, level=level)


def display_hand(player_hand, dealer_card) -> None:
    """Display the current hand situation."""
    print(f"\nYour hand: {player_hand}  Dealer shows: {dealer_card}")


def get_action() -> str | None:
    """Prompt user for their action.

    Returns:
        The action string, or None to quit
    """
    print("Action: ", end="", flush=True)
    while True:
        action = getch().upper()
        if action == "Q":
            print(action)
            return None
        if action in Action.ALL:
            print(action)
            return action
        # Ignore invalid keys silently


def display_result(result, stats, response_time: float = 0.0) -> None:
    """Display the result and current stats."""
    if result.is_correct:
        feedback = f"\033[32m{result.feedback}\033[0m"  # green
    else:
        feedback = f"\033[31m{result.feedback}\033[0m"  # red
    time_str = f"  ({response_time:.1f}s)" if response_time > 0 else ""
    print(f"\n{feedback}{time_str}")
    if not result.is_correct and result.exception_description:
        print(f"  \033[33mException: {result.exception_description}\033[0m")  # yellow
    print(f"Session: {stats}")


def display_welcome() -> None:
    """Display welcome message."""
    clear_screen()
    print("=" * 50)
    print("     BLACKJACK BASIC STRATEGY TRAINER")
    print("=" * 50)
    print("\nLearn perfect basic strategy through practice!")
    print("You'll be shown a hand and must choose the correct action.")


def display_final_stats(stats) -> None:
    """Display final session statistics."""
    print("\n" + "=" * 50)
    print("          SESSION COMPLETE")
    print("=" * 50)
    print(f"\nFinal Score: {stats}")
    if stats.avg_time is not None:
        print(f"Avg correct response: {stats.avg_time:.1f}s  Best: {stats.best_time:.1f}s")
    if stats.total > 0:
        if stats.percentage >= 90:
            print("Excellent! You've mastered basic strategy!")
        elif stats.percentage >= 70:
            print("Good job! Keep practicing to improve.")
        else:
            print("Keep studying the strategy charts.")
    print("\nThanks for practicing!")


def run_training_loop(trainer: Trainer) -> None:
    """Run the main training loop."""
    _setup_top_bar()
    print(f"Rules: {trainer.rules}")
    print()

    try:
        while True:
            # Deal a new hand
            player_hand, dealer_card = trainer.deal_hand()
            display_hand(player_hand, dealer_card)

            # Get player's action (timed)
            start = time.monotonic()
            action = get_action()
            elapsed = time.monotonic() - start
            if action is None:
                break

            # Check and display result
            result = trainer.check_answer(action, response_time=elapsed)
            display_result(result, trainer.stats, response_time=elapsed)
            print()
    finally:
        _teardown_top_bar()

    trainer.metrics.end_session(trainer.stats.total)
    display_final_stats(trainer.stats)


def show_strategy_table(rules: "Rules", data_dir: Path) -> None:
    """Prompt user to view the strategy chart, then display it."""
    from .levels import get_keys_for_level

    choice = input("\nView strategy chart for this level? (y/n) [y]: ").strip().lower()
    if choice not in ("", "y", "yes"):
        return

    table_name = rules.strategy_file.replace(".csv", "").replace("-", " ").title()
    level_name = LEVEL_NAMES.get(rules.level, f"Level {rules.level}")
    title = f"{table_name} Basic Strategy \u2014 Level {rules.level}: {level_name}"
    row_keys = get_keys_for_level(rules.level)

    from .strategy import Strategy

    strategy = Strategy(data_dir / rules.strategy_file)
    strategy.print_table(title, row_keys=row_keys)

    print("\nPress any key to begin training...")
    getch()


def main(data_dir: Path | None = None, metrics=None) -> None:
    """Main entry point for the UI."""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data"

    display_welcome()
    rules = get_rules()
    show_strategy_table(rules, data_dir)
    trainer = Trainer(rules, data_dir, metrics=metrics)
    run_training_loop(trainer)
