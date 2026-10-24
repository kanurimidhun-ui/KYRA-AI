
import webbrowser

# Only approved websites can be opened.
ALLOWED_WEBSITES = {
    "youtube": "https://www.youtube.com",
    "google": "https://www.google.com",
    "github": "https://github.com",
}

WEBSITE_COMMANDS = {
    # English
    "open youtube": "youtube",
    "open google": "google",
    "open github": "github",

    # Hindi
    "यूट्यूब खोलो": "youtube",
    "गूगल खोलो": "google",
    "गिटहब खोलो": "github",

    # Telugu
    "యూట్యూబ్ తెరువు": "youtube",
    "గూగుల్ తెరువు": "google",
    "గిట్‌హబ్ తెరువు": "github",
}


def open_website(website_name):
    """Open a website from the approved list."""

    if not isinstance(website_name, str):
        return "ERROR: Invalid website name."

    website_name = website_name.strip().lower()

    if website_name not in ALLOWED_WEBSITES:
        return "ERROR: Website not supported."

    url = ALLOWED_WEBSITES[website_name]

    try:
        opened = webbrowser.open(url)

        if opened:
            return f"SUCCESS: Opened {website_name}."

        return f"ERROR: Browser could not open {website_name}."

    except Exception as error:
        return f"ERROR: {error}"


def handle_website_command(command):
    """Recognize website commands in three languages."""

    if not isinstance(command, str):
        return None

    command = command.strip().lower()

    for wake_word in ("kyra", "कायरा", "కైరా"):
        if command.startswith(wake_word):
            command = command[len(wake_word):]
            command = command.lstrip(" ,:!?।")

    command = command.rstrip(" .?!।")

    website_name = WEBSITE_COMMANDS.get(command)

    if website_name is None:
        return None

    return open_website(website_name)


if __name__ == "__main__":
    print("=== KYRA WEBSITE AUTOMATION TEST ===")

    command = input(
        "Enter website command: "
    )

    result = handle_website_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
