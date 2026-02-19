"""Tests for levels module."""

import pytest

from blackjack.levels import LEVEL_KEYS, LEVEL_NAMES, get_keys_for_level


# All 34 strategy keys in a standard blackjack game
ALL_STRATEGY_KEYS = {
    # Hard hands: 5-20
    "5", "6", "7", "8", "9", "10", "11", "12",
    "13", "14", "15", "16", "17", "18", "19", "20",
    # Soft hands: A2-A9
    "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
    # Pairs: 22-AA
    "22", "33", "44", "55", "66", "77", "88", "99", "TT", "AA",
}


class TestLevelKeys:
    def test_all_34_keys_covered(self):
        """All 34 strategy keys are covered across levels 1-7."""
        combined = set()
        for keys in LEVEL_KEYS.values():
            combined.update(keys)
        assert combined == ALL_STRATEGY_KEYS

    def test_no_unexpected_duplicates_across_mixed_levels(self):
        """No key appears in more than one of the mixed levels (4, 5, 6, 7)."""
        mixed_levels = {4: LEVEL_KEYS[4], 5: LEVEL_KEYS[5], 6: LEVEL_KEYS[6], 7: LEVEL_KEYS[7]}
        seen: set[str] = set()
        for level, keys in mixed_levels.items():
            overlap = seen & set(keys)
            assert not overlap, f"Level {level} has duplicates with earlier mixed level: {overlap}"
            seen.update(keys)

    def test_mixed_levels_cover_all_34_keys(self):
        """Levels 4, 5, 6, 7 together cover all 34 strategy keys."""
        combined = set(LEVEL_KEYS[4]) | set(LEVEL_KEYS[5]) | set(LEVEL_KEYS[6]) | set(LEVEL_KEYS[7])
        assert combined == ALL_STRATEGY_KEYS

    def test_level_1_count(self):
        assert len(LEVEL_KEYS[1]) == 16

    def test_level_2_count(self):
        assert len(LEVEL_KEYS[2]) == 8

    def test_level_3_count(self):
        assert len(LEVEL_KEYS[3]) == 10

    def test_level_4_count(self):
        assert len(LEVEL_KEYS[4]) == 12

    def test_level_5_count(self):
        assert len(LEVEL_KEYS[5]) == 9

    def test_level_6_count(self):
        assert len(LEVEL_KEYS[6]) == 6

    def test_level_7_count(self):
        assert len(LEVEL_KEYS[7]) == 7


class TestGetKeysForLevel:
    def test_level_0_returns_all_keys(self):
        keys = get_keys_for_level(0)
        assert keys == ALL_STRATEGY_KEYS

    def test_level_1_returns_all_hard_hands(self):
        keys = get_keys_for_level(1)
        expected = {"5", "6", "7", "8", "9", "10", "11", "12",
                    "13", "14", "15", "16", "17", "18", "19", "20"}
        assert keys == expected

    def test_level_2_returns_all_soft_hands(self):
        keys = get_keys_for_level(2)
        expected = {"A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"}
        assert keys == expected

    def test_level_3_returns_all_pairs(self):
        keys = get_keys_for_level(3)
        expected = {"22", "33", "44", "55", "66", "77", "88", "99", "TT", "AA"}
        assert keys == expected

    def test_level_4_returns_always_keys(self):
        keys = get_keys_for_level(4)
        assert keys == {"5", "6", "7", "11", "17", "18", "19", "20", "A9", "AA", "88", "TT"}

    def test_level_5_returns_fundamentals_keys(self):
        keys = get_keys_for_level(5)
        assert keys == {"8", "10", "13", "14", "A8", "55", "22", "33", "66"}

    def test_level_6_returns_advanced_keys(self):
        keys = get_keys_for_level(6)
        assert keys == {"9", "12", "A2", "A3", "A4", "A5"}

    def test_level_7_returns_expert_keys(self):
        keys = get_keys_for_level(7)
        assert keys == {"15", "16", "A6", "A7", "44", "77", "99"}

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError, match="Invalid level: 8"):
            get_keys_for_level(8)

    def test_negative_level_raises(self):
        with pytest.raises(ValueError, match="Invalid level: -1"):
            get_keys_for_level(-1)


class TestLevelNames:
    def test_all_levels_have_names(self):
        for level in [0, 1, 2, 3, 4, 5, 6, 7]:
            assert level in LEVEL_NAMES

    def test_level_0_name(self):
        assert LEVEL_NAMES[0] == "All Hands"

    def test_level_1_name(self):
        assert LEVEL_NAMES[1] == "Hard Hands"

    def test_level_2_name(self):
        assert LEVEL_NAMES[2] == "Soft Hands"

    def test_level_3_name(self):
        assert LEVEL_NAMES[3] == "Splits"

    def test_level_4_name(self):
        assert LEVEL_NAMES[4] == "Always"

    def test_level_5_name(self):
        assert LEVEL_NAMES[5] == "Fundamentals"

    def test_level_6_name(self):
        assert LEVEL_NAMES[6] == "Advanced"

    def test_level_7_name(self):
        assert LEVEL_NAMES[7] == "Expert"
