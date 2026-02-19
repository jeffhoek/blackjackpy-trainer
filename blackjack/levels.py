"""Skill level definitions for progressive training."""

LEVEL_NAMES: dict[int, str] = {
    0: "All Hands",
    1: "Hard Hands",
    2: "Soft Hands",
    3: "Splits",
    4: "Always",
    5: "Fundamentals",
    6: "Advanced",
    7: "Expert",
}

LEVEL_KEYS: dict[int, list[str]] = {
    1: [
        # Hard 5-20
        "5", "6", "7", "8", "9", "10", "11", "12",
        "13", "14", "15", "16", "17", "18", "19", "20",
    ],
    2: [
        # Soft A2-A9
        "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9",
    ],
    3: [
        # All pairs 22-AA
        "22", "33", "44", "55", "66", "77", "88", "99", "TT", "AA",
    ],
    4: [
        # Hard: always hit
        "5", "6", "7",
        # Hard: always double
        "11",
        # Hard: always stand
        "17", "18", "19", "20",
        # Soft: always stand (soft 20)
        "A9",
        # Pairs: always split
        "AA", "88",
        # Pairs: always stand / never split
        "TT",
    ],
    5: [
        # Hard: almost always / learnable thresholds
        "8", "10", "13", "14",
        # Soft: almost always stand
        "A8",
        # Pairs: never split (treat as hard 10)
        "55",
        # Pairs: split vs low dealer cards
        "22", "33", "66",
    ],
    6: [
        # Hard: learnable patterns
        "9", "12",
        # Soft: lower soft doubles
        "A2", "A3", "A4", "A5",
    ],
    7: [
        # Hard: surrender decisions, most complex
        "15", "16",
        # Soft: multi-action, most counter-intuitive
        "A6", "A7",
        # Pairs: restrictive split / classic gotchas
        "44", "77", "99",
    ],
}


def get_keys_for_level(level: int) -> set[str]:
    """Return the set of allowed strategy keys for a given level.

    Args:
        level: Skill level (0 = all hands, 1-7 = specific subsets)

    Returns:
        Set of strategy row keys for that level

    Raises:
        ValueError: If level is not 0-7
    """
    if level == 0:
        # All keys from all levels combined
        all_keys: set[str] = set()
        for keys in LEVEL_KEYS.values():
            all_keys.update(keys)
        return all_keys
    if level not in LEVEL_KEYS:
        raise ValueError(f"Invalid level: {level}. Must be 0-7.")
    return set(LEVEL_KEYS[level])
