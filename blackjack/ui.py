"""Console user interface for the trainer."""

import sys
from pathlib import Path

from .levels import LEVEL_NAMES
from .rules import Rules
from .strategy import Action
from .trainer import Trainer


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


def clear_screen() -> None:
    """Clear the terminal screen."""
    print("\033[2J\033[H", end="")


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
        level_input = input("Skill level (0-5) [0]: ").strip()
        if level_input == "":
            level = 0
            break
        if level_input in ("0", "1", "2", "3", "4", "5"):
            level = int(level_input)
            break
        print("Please enter 0-5")

    return Rules(num_decks=num_decks, dealer_hits_soft_17=dealer_hits_soft_17, level=level)


def display_hand(player_hand, dealer_card) -> None:
    """Display the current hand situation."""
    print(f"\nYour hand: {player_hand}  Dealer shows: {dealer_card}")


def get_action() -> str | None:
    """Prompt user for their action.

    Returns:
        The action string, or None to quit
    """
    print("\n[S]tand  [H]it  [D]ouble  s[P]lit  su[R]render  [Q]uit")
    print("Your action: ", end="", flush=True)
    while True:
        action = getch().upper()
        if action == "Q":
            print(action)
            return None
        if action in Action.ALL:
            print(action)
            return action
        # Ignore invalid keys silently


def display_result(result, stats) -> None:
    """Display the result and current stats."""
    if result.is_correct:
        feedback = f"\033[32m{result.feedback}\033[0m"  # green
    else:
        feedback = f"\033[31m{result.feedback}\033[0m"  # red
    print(f"\n{feedback}")
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
    print(f"\nRules: {trainer.rules}")
    print("\nStarting training session... (Q to quit)\n")

    while True:
        # Deal a new hand
        player_hand, dealer_card = trainer.deal_hand()
        display_hand(player_hand, dealer_card)

        # Get player's action
        action = get_action()
        if action is None:
            break

        # Check and display result
        result = trainer.check_answer(action)
        display_result(result, trainer.stats)

    display_final_stats(trainer.stats)


def main(data_dir: Path | None = None) -> None:
    """Main entry point for the UI."""
    if data_dir is None:
        data_dir = Path(__file__).parent.parent / "data"

    display_welcome()
    rules = get_rules()
    trainer = Trainer(rules, data_dir)
    run_training_loop(trainer)
