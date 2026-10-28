
"""
KYRA AI - DAY 9
Multi-Step JARVIS Command Planner

This module ONLY plans commands.
It never executes Windows actions.
"""

import re


def split_commands(message):
    """Split explicit multi-step requests into separate commands."""

    if not isinstance(message, str):
        return []

    message = message.strip()

    if not message:
        return []

    # Remove the optional wake word.
    message = re.sub(
        r"^(?:hey\s+)?kyra[\s,:-]+",
        "",
        message,
        flags=re.IGNORECASE,
    ).strip()

    # Recognize explicit sequencing words.
    commands = re.split(
        r"\s+(?:and\s+then|and|then)\s+",
        message,
        flags=re.IGNORECASE,
    )

    return [
        command.strip()
        for command in commands
        if command.strip()
    ]


def create_plan(message, normalize, classify):
    """
    Prepare a plan using KYRA's existing security classifier.

    No actions are executed here.
    Every step must pass the existing action allowlist.
    """

    raw_commands = split_commands(message)

    if len(raw_commands) < 2:
        return {
            "status": "single_command",
            "steps": [],
            "message": "No multi-step request detected.",
        }

    if len(raw_commands) > 3:
        return {
            "status": "rejected",
            "steps": [],
            "message": "Maximum three commands per plan.",
        }

    steps = []

    for number, raw_command in enumerate(raw_commands, start=1):

        command = normalize(raw_command)
        decision = classify(command)

        if decision != "action":
            return {
                "status": "rejected",
                "steps": [],
                "message": (
                    f"Step {number} is not an allowed action: "
                    f"{command}"
                ),
            }

        steps.append({
            "number": number,
            "command": command,
            "requires_confirmation": True,
        })

    return {
        "status": "ready_for_confirmation",
        "steps": steps,
        "message": (
            "Plan prepared. Each action requires "
            "separate authorization and confirmation."
        ),
    }


if __name__ == "__main__":

    # Use the existing KYRA classifier.
    from app import (
        normalize_jarvis_command,
        classify_api_request,
    )

    test_command = (
        "KYRA, open Notepad and open Calculator"
    )

    result = create_plan(
        test_command,
        normalize_jarvis_command,
        classify_api_request,
    )

    print("=" * 45)
    print("KYRA AI - DAY 9 MULTI-STEP PLANNER")
    print("=" * 45)

    print("STATUS:", result["status"])

    for step in result["steps"]:
        print(
            f"STEP {step['number']}: "
            f"{step['command']}"
        )

    print("MESSAGE:", result["message"])
