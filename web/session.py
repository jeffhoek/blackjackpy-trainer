"""Async game session for the web interface.

Mirrors the flow of blackjack/ui.py but uses asyncio queues instead of
termios-based getch() and blocking print()/input() calls.
"""

import asyncio
from pathlib import Path

from blackjack.levels import LEVEL_NAMES, get_keys_for_level
from blackjack.rules import Rules
from blackjack.strategy import Action, Strategy
from blackjack.trainer import Trainer


class Disconnected(Exception):
    """Raised when the WebSocket client disconnects."""


class WebSession:
    """Runs a training session over send/recv asyncio queues.

    The server puts received characters into recv_queue and reads
    outgoing text from send_queue.
    """

    def __init__(
        self,
        send_queue: asyncio.Queue,
        recv_queue: asyncio.Queue,
        data_dir: Path,
    ) -> None:
        self._send_q = send_queue
        self._recv_q = recv_queue
        self._data_dir = data_dir

    # ------------------------------------------------------------------
    # Low-level I/O helpers
    # ------------------------------------------------------------------

    async def send(self, text: str) -> None:
        """Send text to the terminal."""
        await self._send_q.put(text)

    async def recv_char(self) -> str:
        """Read the next character from the terminal.

        Raises:
            Disconnected: If the client disconnects (None sentinel received).
        """
        ch = await self._recv_q.get()
        if ch is None:
            raise Disconnected
        return ch

    async def recv_line(self) -> str:
        """Read a line of text, echoing input and handling backspace.

        Returns on Enter (\\r or \\n). Backspace removes the last character.
        """
        buf: list[str] = []
        while True:
            ch = await self.recv_char()
            if ch in ("\r", "\n"):
                await self.send("\r\n")
                return "".join(buf)
            elif ch in ("\x7f", "\x08"):  # DEL or BS
                if buf:
                    buf.pop()
                    await self.send("\b \b")  # erase last char in terminal
            else:
                buf.append(ch)
                await self.send(ch)  # echo

    # ------------------------------------------------------------------
    # Config phase (mirrors ui.get_rules)
    # ------------------------------------------------------------------

    async def _get_rules(self) -> Rules:
        await self.send("\r\n=== Game Configuration ===\r\n\r\n")

        # Number of decks
        while True:
            await self.send("Number of decks (1/6) [1]: ")
            deck_input = (await self.recv_line()).strip()
            if deck_input == "":
                num_decks = 1
                break
            if deck_input in ("1", "6"):
                num_decks = int(deck_input)
                break
            await self.send("Please enter 1 or 6\r\n")

        # Dealer hits soft 17
        while True:
            await self.send("Dealer hits soft 17? (y/n) [y]: ")
            h17_input = (await self.recv_line()).strip().lower()
            if h17_input == "":
                dealer_hits_soft_17 = True
                break
            if h17_input in ("y", "yes"):
                dealer_hits_soft_17 = True
                break
            if h17_input in ("n", "no"):
                dealer_hits_soft_17 = False
                break
            await self.send("Please enter y or n\r\n")

        # Skill level
        await self.send("\r\nSkill levels:\r\n")
        for lvl, name in sorted(LEVEL_NAMES.items()):
            await self.send(f"  {lvl} - {name}\r\n")
        while True:
            await self.send("Skill level (0-7) [0]: ")
            level_input = (await self.recv_line()).strip()
            if level_input == "":
                level = 0
                break
            if level_input in ("0", "1", "2", "3", "4", "5", "6", "7"):
                level = int(level_input)
                break
            await self.send("Please enter 0-7\r\n")

        return Rules(
            num_decks=num_decks,
            dealer_hits_soft_17=dealer_hits_soft_17,
            level=level,
        )

    # ------------------------------------------------------------------
    # Strategy chart display
    # ------------------------------------------------------------------

    async def _show_table(self, rules: Rules) -> None:
        """Render the strategy chart for the chosen level and wait for a keypress."""
        table_name = rules.strategy_file.replace(".csv", "").replace("-", " ").title()
        level_name = LEVEL_NAMES.get(rules.level, f"Level {rules.level}")
        title = f"{table_name} Basic Strategy \u2014 Level {rules.level}: {level_name}"
        row_keys = get_keys_for_level(rules.level)
        strategy = Strategy(self._data_dir / rules.strategy_file)
        lines = strategy.format_table(title, row_keys=row_keys)
        await self.send("\r\n" + "\r\n".join(lines) + "\r\n")
        await self.send("\r\nPress any key to begin training...\r\n")
        await self.recv_char()

    # ------------------------------------------------------------------
    # Training loop (mirrors ui.run_training_loop)
    # ------------------------------------------------------------------

    async def _run_training_loop(self, trainer: Trainer) -> None:
        await self.send(f"\r\nRules: {trainer.rules}\r\n")
        await self.send("\r\nStarting training session... (Q to quit)\r\n\r\n")

        while True:
            player_hand, dealer_card = trainer.deal_hand()
            await self.send(
                f"\r\nYour hand: {player_hand}  Dealer shows: {dealer_card}\r\n"
            )

            await self.send(
                "\r\n[S]tand  [H]it  [D]ouble  s[P]lit  su[R]render  [Q]uit\r\n"
            )
            await self.send("Your action: ")

            # Single-keypress input
            action: str | None = None
            while True:
                ch = await self.recv_char()
                upper = ch.upper()
                if upper == "Q":
                    await self.send(upper + "\r\n")
                    action = None
                    break
                if upper in Action.ALL:
                    await self.send(upper + "\r\n")
                    action = upper
                    break
                # Ignore unrecognised keys silently

            if action is None:
                break

            result = trainer.check_answer(action)
            if result.is_correct:
                feedback = f"\033[32m{result.feedback}\033[0m"
            else:
                feedback = f"\033[31m{result.feedback}\033[0m"
            await self.send(f"\r\n{feedback}\r\n")
            await self.send(f"Session: {trainer.stats}\r\n")

        trainer.metrics.end_session(trainer.stats.total)

        # Final stats (mirrors ui.display_final_stats)
        await self.send("\r\n" + "=" * 50 + "\r\n")
        await self.send("          SESSION COMPLETE\r\n")
        await self.send("=" * 50 + "\r\n")
        await self.send(f"\r\nFinal Score: {trainer.stats}\r\n")
        if trainer.stats.total > 0:
            if trainer.stats.percentage >= 90:
                await self.send("Excellent! You've mastered basic strategy!\r\n")
            elif trainer.stats.percentage >= 70:
                await self.send("Good job! Keep practicing to improve.\r\n")
            else:
                await self.send("Keep studying the strategy charts.\r\n")
        await self.send("\r\nThanks for practicing!\r\n")

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Run the full session: welcome → config → training → stats."""
        # Welcome (mirrors ui.display_welcome)
        await self.send("\033[2J\033[H")  # clear screen
        await self.send("=" * 50 + "\r\n")
        await self.send("     BLACKJACK BASIC STRATEGY TRAINER\r\n")
        await self.send("=" * 50 + "\r\n")
        await self.send("\r\nLearn perfect basic strategy through practice!\r\n")
        await self.send(
            "You'll be shown a hand and must choose the correct action.\r\n"
        )

        rules = await self._get_rules()

        await self.send("\r\nView strategy chart for this level? (y/n) [y]: ")
        show = (await self.recv_line()).strip().lower()
        if show in ("", "y", "yes"):
            await self._show_table(rules)

        trainer = Trainer(rules, self._data_dir)
        await self._run_training_loop(trainer)
