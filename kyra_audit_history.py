
import json
from pathlib import Path

AUDIT_FILE = Path(__file__).resolve().parent / "kyra_audit.jsonl"

VALID_DECISIONS = {
    "approved",
    "cancelled",
    "blocked",
    "confirmation_failed"
}


def get_recent_events(limit=10):
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("Limit must be an integer")

    limit = max(1, min(limit, 50))

    if not AUDIT_FILE.exists():
        return []

    events = []

    with AUDIT_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            if event.get("decision") not in VALID_DECISIONS:
                continue

            events.append({
                "timestamp": str(event.get("timestamp", "")),
                "command": str(event.get("command", ""))[:200],
                "decision": event["decision"]
            })

    return events[-limit:][::-1]


if __name__ == "__main__":
    print("=== KYRA SECURITY EVENT HISTORY ===")

    for event in get_recent_events(10):
        print(
            event["timestamp"],
            "|",
            event["command"],
            "|",
            event["decision"].upper()
        )
