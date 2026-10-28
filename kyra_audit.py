
import json
from datetime import datetime
from pathlib import Path

AUDIT_FILE = Path(__file__).resolve().parent / "kyra_audit.jsonl"

ALLOWED_DECISIONS = {
    "blocked",
    "approved",
    "cancelled",
    "confirmation_failed"
}


def log_security_event(command, decision):

    if decision not in ALLOWED_DECISIONS:
        raise ValueError("Invalid security decision")

    if not isinstance(command, str):
        command = ""

    event = {
        "timestamp": datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
        "command": command[:200],
        "decision": decision
    }

    with AUDIT_FILE.open("a", encoding="utf-8") as file:
        file.write(
            json.dumps(event, ensure_ascii=False) + "\n"
        )

    return event


if __name__ == "__main__":

    event = log_security_event(
        "Open calculator",
        "approved"
    )

    print("Security event saved:")
    print(json.dumps(event, indent=2))
