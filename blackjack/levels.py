"""Skill level definitions for progressive training."""

LEVEL_NAMES: dict[int, str] = {
    0: "All Hands",
    1: "Fundamentals",
    2: "Standard Decisions",
    3: "Splits",
    4: "Doubles & Soft Hands",
    5: "Expert",
}

LEVEL_KEYS: dict[int, list[str]] = {
    1: [
        # Hard 5-8 (always hit)
        "5", "6", "7", "8",
        # Hard 17-20 (always stand)
        "17", "18", "19", "20",
        # Hard 10-11 (double)
        "10", "11",
        # Pairs AA/88 (always split), TT (never split)
        "AA", "88", "TT",
    ],
    2: [
        # Hard 13-16 (hit/stand threshold)
        "13", "14", "15", "16",
        # Soft A8/A9 (always stand)
        "A8", "A9",
        # Pair 55 (never split)
        "55",
    ],
    3: [
        # All pairs except AA/88/TT/55
        "22", "33", "44", "66", "77", "99",
    ],
    4: [
        # Hard 9/12
        "9", "12",
        # Soft A2-A5
        "A2", "A3", "A4", "A5",
    ],
    5: [
        # Soft A6/A7 (hardest!)
        "A6", "A7",
    ],
}


def get_keys_for_level(level: int) -> set[str]:
    """Return the set of allowed strategy keys for a given level.

    Args:
        level: Skill level (0 = all hands, 1-4 = specific subsets)

    Returns:
        Set of strategy row keys for that level

    Raises:
        ValueError: If level is not 0-4
    """
    if level == 0:
        # All keys from all levels combined
        all_keys: set[str] = set()
        for keys in LEVEL_KEYS.values():
            all_keys.update(keys)
        return all_keys
    if level not in LEVEL_KEYS:
        raise ValueError(f"Invalid level: {level}. Must be 0-5.")
    return set(LEVEL_KEYS[level])
