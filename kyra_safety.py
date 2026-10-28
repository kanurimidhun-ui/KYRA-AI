
# ==========================================
# KYRA AI v3.9 - ACTION SAFETY ENGINE
# ==========================================

import re


# Destructive or sensitive commands are blocked.
BLOCKED_ACTIONS = [
    r"\bdelete\b",
    r"\bremove\b",
    r"\berase\b",
    r"\bformat\b",
    r"\bshutdown\b",
    r"\brestart\b",
    r"\breboot\b",
    r"\bpower\s*off\b",
    r"\block\b",
    r"\bexecute\b",
    r"\binstall\b",
    r"\buninstall\b",
]

# Commands eligible for voice confirmation.
CONFIRMABLE_ACTIONS = [
    r"^(please\s+)?open\b",
    r"^(please\s+)?launch\b",
    r"^(please\s+)?search\b",
    r"^(please\s+)?google\b",
    r"^(please\s+)?play\b",
    r"^(please\s+)?start\b",
    r"^(can|could|would|will)\s+you\s+"
    r"(please\s+)?(open|launch|search|play|start)\b",
]


def assess_action(command):
    """
    Returns:
        blocked  - never execute
        confirm  - requires user confirmation
        blocked  - also used for unknown actions
    """

    if not isinstance(command, str):
        return "blocked"

    text = " ".join(command.lower().split())

    if not text:
        return "blocked"

    # Allow only explicit PC lock requests with confirmation.
    if re.fullmatch(
        r"(?:please\s+)?lock\s+(?:my\s+)?(?:pc|computer|laptop)",
        text,
    ):
        return "confirm"

    # First check dangerous operations.
    for pattern in BLOCKED_ACTIONS:
        if re.search(pattern, text):
            return "blocked"

    # Then check explicitly permitted action types.
    for pattern in CONFIRMABLE_ACTIONS:
        if re.search(pattern, text):
            return "confirm"

    # Fail closed for unknown actions.
    return "blocked"


if __name__ == "__main__":

    tests = [
        "Open calculator",
        "Search Python tutorials",
        "Play music",
        "Delete my files",
        "Restart my computer",
        "Format my drive",
        "Open calculator and delete files",
        "Do something",
    ]

    print("=== KYRA ACTION SAFETY TEST ===")

    for command in tests:
        result = assess_action(command)
        print(f"{command} -> {result.upper()}")
