
import json
from collections import Counter
from pathlib import Path

AUDIT_FILE = Path(__file__).resolve().parent / "kyra_audit.jsonl"


def get_audit_stats():
    counts = Counter()
    total = 0

    if not AUDIT_FILE.exists():
        return {
            "total": 0,
            "approved": 0,
            "cancelled": 0,
            "blocked": 0,
            "confirmation_failed": 0
        }

    with AUDIT_FILE.open("r", encoding="utf-8") as file:
        for line in file:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue

            if not isinstance(event, dict):
                continue

            decision = event.get("decision")

            if decision in {
                "approved",
                "cancelled",
                "blocked",
                "confirmation_failed"
            }:
                counts[decision] += 1
                total += 1

    return {
        "total": total,
        "approved": counts["approved"],
        "cancelled": counts["cancelled"],
        "blocked": counts["blocked"],
        "confirmation_failed": counts["confirmation_failed"]
    }


if __name__ == "__main__":
    stats = get_audit_stats()

    print("=== KYRA SECURITY DASHBOARD ===")
    print("Total Actions:", stats["total"])
    print("Approved:", stats["approved"])
    print("Cancelled:", stats["cancelled"])
    print("Blocked:", stats["blocked"])
    print("Confirmation Failed:", stats["confirmation_failed"])
