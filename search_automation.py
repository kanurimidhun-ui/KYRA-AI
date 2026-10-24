
import webbrowser
from urllib.parse import quote_plus


def handle_search_command(command):
    """Search Google using approved command patterns."""

    if not isinstance(command, str):
        return None

    command = command.strip()

    # Remove optional KYRA wake word
    for wake_word in ("kyra", "कायरा", "కైరా"):
        if command.lower().startswith(wake_word):
            command = command[len(wake_word):]
            command = command.lstrip(" ,:!?।")

    lower_command = command.lower()

    # English command
    if lower_command.startswith("search google for "):
        query = command[len("search google for "):]

    # Hindi command
    elif command.startswith("गूगल पर ") and command.endswith(" खोजो"):
        query = command[len("गूगल पर "):-len(" खोजो")]

    # Telugu command
    elif command.startswith("గూగుల్‌లో ") and command.endswith(" వెతుకు"):
        query = command[len("గూగుల్‌లో "):-len(" వెతుకు")]

    else:
        return None

    query = query.strip().rstrip("?.!।").strip()

    if not query:
        return "ERROR: Search topic is empty."

    if len(query) > 200:
        return "ERROR: Search topic is too long."

    search_url = (
        "https://www.google.com/search?q="
        + quote_plus(query)
    )

    try:
        opened = webbrowser.open(search_url)

        if opened:
            return f"SUCCESS: Searching Google for {query}."

        return "ERROR: Could not open the browser."

    except Exception:
        return "ERROR: Google search could not start."


if __name__ == "__main__":
    print("=== KYRA GOOGLE SEARCH TEST ===")

    command = input("Enter search command: ")

    result = handle_search_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
