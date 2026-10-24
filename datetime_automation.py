
from datetime import datetime


# ---------------------------------------
# SUPPORTED COMMANDS
# ---------------------------------------

TIME_COMMANDS = {
    # English
    "what time is it",
    "tell me the time",
    "current time",

    # Hindi
    "अभी कितने बजे हैं",
    "समय बताओ",

    # Telugu
    "ఇప్పుడు టైమ్ ఎంత",
    "సమయం చెప్పు",
}

DATE_COMMANDS = {
    # English
    "what is today's date",
    "what is the date today",
    "today's date",

    # Hindi
    "आज की तारीख बताओ",
    "आज कौन सी तारीख है",

    # Telugu
    "ఈరోజు తేదీ ఎంత",
    "ఈరోజు తేదీ చెప్పు",
}


# ---------------------------------------
# COMMAND HANDLER
# ---------------------------------------

def handle_datetime_command(command):
    """Recognize date and time commands."""

    if not isinstance(command, str):
        return None

    command = command.strip().lower()

    # Remove optional KYRA wake word.
    for wake_word in (
        "kyra",
        "कायरा",
        "కైరా",
    ):
        if command.startswith(wake_word):
            command = command[len(wake_word):]
            command = command.lstrip(" ,:!?।")

    command = command.rstrip(" .?!।")

    now = datetime.now()

    # Time commands
    if command in TIME_COMMANDS:
        current_time = now.strftime("%I:%M %p")
        return f"SUCCESS: Current time is {current_time}."

    # Date commands
    if command in DATE_COMMANDS:
        current_date = now.strftime("%d-%m-%Y")
        return f"SUCCESS: Today's date is {current_date}."

    return None


# ---------------------------------------
# TERMINAL TEST
# ---------------------------------------

if __name__ == "__main__":
    print("=== KYRA DATE AND TIME TEST ===")

    command = input("Enter command: ")

    result = handle_datetime_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
