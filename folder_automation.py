
import os
from pathlib import Path


# -----------------------------------
# FIND WINDOWS USER FOLDERS
# -----------------------------------

def find_user_folder(folder_name):
    """Find a folder, including common OneDrive locations."""

    home = Path.home()

    candidates = [
        home / folder_name,
    ]

    # Some Windows laptops store folders in OneDrive.
    for env_name in (
        "OneDrive",
        "OneDriveConsumer",
        "OneDriveCommercial",
    ):
        onedrive = os.environ.get(env_name)

        if onedrive:
            candidates.append(
                Path(onedrive) / folder_name
            )

    candidates.append(
        home / "OneDrive" / folder_name
    )

    for path in candidates:
        if path.is_dir():
            return path

    return None


# -----------------------------------
# APPROVED FOLDERS
# -----------------------------------

ALLOWED_FOLDERS = {
    "downloads": "Downloads",
    "documents": "Documents",
}


# -----------------------------------
# MULTILINGUAL COMMANDS
# -----------------------------------

FOLDER_COMMANDS = {
    # English
    "open downloads": "downloads",
    "downloads open": "downloads",
    "open documents": "documents",
    "documents open": "documents",

    # Hindi
    "डाउनलोड्स खोलो": "downloads",
    "डाउनलोड खोलो": "downloads",
    "डॉक्यूमेंट्स खोलो": "documents",
    "डॉक्यूमेंट खोलो": "documents",

    # Telugu
    "డౌన్‌లోడ్స్ తెరువు": "downloads",
    "డౌన్‌లోడ్స్ ఓపెన్ చెయ్యి": "downloads",
    "డాక్యుమెంట్స్ తెరువు": "documents",
    "డాక్యుమెంట్స్ ఓపెన్ చెయ్యి": "documents",
}


# -----------------------------------
# OPEN APPROVED FOLDER
# -----------------------------------

def open_folder(folder_name):
    """Open an approved Windows folder."""

    if not isinstance(folder_name, str):
        return "ERROR: Invalid folder name."

    folder_name = folder_name.strip().lower()

    if folder_name not in ALLOWED_FOLDERS:
        return "ERROR: Folder not supported."

    actual_name = ALLOWED_FOLDERS[folder_name]

    folder_path = find_user_folder(actual_name)

    if folder_path is None:
        return f"ERROR: {actual_name} folder not found."

    try:
        os.startfile(str(folder_path))

        return f"SUCCESS: Opened {folder_name}."

    except OSError as error:
        return f"ERROR: Could not open folder: {error}"


# -----------------------------------
# RECOGNIZE KYRA COMMAND
# -----------------------------------

def handle_folder_command(command):
    """Recognize English, Hindi and Telugu commands."""

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

    folder_name = FOLDER_COMMANDS.get(command)

    if folder_name is None:
        return None

    return open_folder(folder_name)


# -----------------------------------
# TERMINAL TEST
# -----------------------------------

if __name__ == "__main__":
    print("=== KYRA FOLDER AUTOMATION TEST ===")

    command = input("Enter command: ")

    result = handle_folder_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
