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
        """All 34 strategy keys are covered across levels 1-5."""
        combined = set()
        for keys in LEVEL_KEYS.values():
            combined.update(keys)
        assert combined == ALL_STRATEGY_KEYS

    def test_no_unexpected_duplicates_across_levels(self):
        """Only intentional keys appear in more than one level."""
        allowed_duplicates = {"77"}  # appears in both Splits and Expert
        seen: set[str] = set()
        for level, keys in LEVEL_KEYS.items():
            overlap = seen & set(keys) - allowed_duplicates
            assert not overlap, f"Level {level} has duplicates: {overlap}"
            seen.update(keys)

    def test_level_1_count(self):
        assert len(LEVEL_KEYS[1]) == 13

    def test_level_2_count(self):
        assert len(LEVEL_KEYS[2]) == 7

    def test_level_3_count(self):
        assert len(LEVEL_KEYS[3]) == 6

    def test_level_4_count(self):
        assert len(LEVEL_KEYS[4]) == 6

    def test_level_5_count(self):
        assert len(LEVEL_KEYS[5]) == 3


class TestGetKeysForLevel:
    def test_level_0_returns_all_keys(self):
        keys = get_keys_for_level(0)
        assert keys == ALL_STRATEGY_KEYS

    def test_level_1_returns_correct_keys(self):
        keys = get_keys_for_level(1)
        assert keys == set(LEVEL_KEYS[1])

    def test_level_3_returns_splits_without_aa_88_tt_55(self):
        keys = get_keys_for_level(3)
        assert keys == {"22", "33", "44", "66", "77", "99"}

    def test_level_5_returns_correct_keys(self):
        keys = get_keys_for_level(5)
        assert keys == {"A6", "A7", "77"}

    def test_invalid_level_raises(self):
        with pytest.raises(ValueError, match="Invalid level: 6"):
            get_keys_for_level(6)

    def test_negative_level_raises(self):
        with pytest.raises(ValueError, match="Invalid level: -1"):
            get_keys_for_level(-1)


class TestLevelNames:
    def test_all_levels_have_names(self):
        for level in [0, 1, 2, 3, 4, 5]:
            assert level in LEVEL_NAMES

    def test_level_0_name(self):
        assert LEVEL_NAMES[0] == "All Hands"

    def test_level_3_name(self):
        assert LEVEL_NAMES[3] == "Splits"

    def test_level_5_name(self):
        assert LEVEL_NAMES[5] == "Expert"
