
import sqlite3
from pathlib import Path

# KYRA AI - DAY 6
# Long-Term Memory Engine

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "kyra_long_memory.db"


def connect_db():
    return sqlite3.connect(DB_PATH)


def initialize_memory():
    with connect_db() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)


def remember(key, value):
    key = str(key).strip().lower()
    value = str(value).strip()

    if not key or not value:
        return False

    with connect_db() as connection:
        connection.execute("""
            INSERT INTO memories (key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
        """, (key, value))

    return True


def recall(key):
    key = str(key).strip().lower()

    with connect_db() as connection:
        result = connection.execute(
            "SELECT value FROM memories WHERE key = ?",
            (key,)
        ).fetchone()

    return result[0] if result else None


def forget(key):
    key = str(key).strip().lower()

    with connect_db() as connection:
        cursor = connection.execute(
            "DELETE FROM memories WHERE key = ?",
            (key,)
        )
        return cursor.rowcount > 0


if __name__ == "__main__":
    initialize_memory()

    print("=== KYRA LONG-TERM MEMORY TEST ===")

    remember("test_color", "Blue")

    print("Saved memory:", recall("test_color"))

    if recall("test_color") == "Blue":
        print("LONG-TERM MEMORY TEST SUCCESS!")
    else:
        print("LONG-TERM MEMORY TEST FAILED!")
