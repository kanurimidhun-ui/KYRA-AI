
import subprocess

# Applications KYRA is allowed to open
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
}

# Supported voice commands in English, Hindi, Telugu
APP_COMMANDS = {
    "open notepad": "notepad",
    "notepad open": "notepad",
    "नोटपैड खोलो": "notepad",
    "नोटपैड खोलिए": "notepad",
    "నోట్‌ప్యాడ్ తెరువు": "notepad",
    "నోట్‌ప్యాడ్ ఓపెన్ చెయ్యి": "notepad",

    "open calculator": "calculator",
    "calculator open": "calculator",
    "कैलकुलेटर खोलो": "calculator",
    "కాలిక్యులేటర్ తెరువు": "calculator",

    "open paint": "paint",
    "paint open": "paint",
    "पेंट खोलो": "paint",
    "పెయింట్ తెరువు": "paint",
}


def open_application(app_name):
    """Open only approved Windows applications."""

    if not isinstance(app_name, str):
        return "ERROR: Invalid application name."

    app_name = app_name.strip().lower()

    if app_name not in ALLOWED_APPS:
        return f"ERROR: {app_name} is not supported."

    try:
        subprocess.Popen(
            [ALLOWED_APPS[app_name]],
            shell=False
        )

        return f"SUCCESS: Opened {app_name}."

    except OSError as error:
        return f"ERROR: Could not open {app_name}: {error}"


def handle_automation_command(command):
    """Recognize an approved command in three languages."""

    if not isinstance(command, str):
        return None

    command = command.strip().lower()

    # Remove optional assistant name
    for wake_word in ("kyra", "कायरा", "కైరా"):
        if command.startswith(wake_word):
            command = command[len(wake_word):]
            command = command.lstrip(" ,:!?।")

    command = command.rstrip(" .?!।")

    app_name = APP_COMMANDS.get(command)

    if app_name is None:
        return None

    return open_application(app_name)


if __name__ == "__main__":
    print("=== KYRA MULTILINGUAL AUTOMATION TEST ===")

    command = input(
        "Enter command (English / Hindi / Telugu): "
    )

    result = handle_automation_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
