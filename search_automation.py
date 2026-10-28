
import re
import webbrowser
from urllib.parse import quote_plus


SEARCH_ENGINES = {
    "google": "https://www.google.com/search?q=",
    "youtube": "https://www.youtube.com/results?search_query=",
    "bing": "https://www.bing.com/search?q=",
    "duckduckgo": "https://duckduckgo.com/?q=",
}


def handle_search_command(command):
    """Recognize natural-language web search commands."""

    if not isinstance(command, str):
        return None

    command = command.strip()

    # Remove optional KYRA wake word.
    command = re.sub(
        r"^(?:kyra|कायरा|కైరా)[\s,!:]+",
        "",
        command,
        flags=re.IGNORECASE,
    ).strip()

    command = command.rstrip(" ?.!।").strip()

    patterns = [
        # search google for Python tutorials
        r"^search\s+(google|youtube|bing|duckduckgo)\s+for\s+(.+)$",

        # search Python tutorials on Google
        r"^search\s+(.+?)\s+on\s+(google|youtube|bing|duckduckgo)$",

        # search for Python tutorials
        r"^search\s+for\s+(.+)$",

        # google Python tutorials
        r"^(google|youtube|bing|duckduckgo)\s+(.+)$",

        # Hindi
        r"^गूगल पर\s+(.+?)\s+खोजो$",

        # Telugu
        r"^గూగుల్‌లో\s+(.+?)\s+వెతుకు$",
    ]

    engine = "google"
    query = None

    for index, pattern in enumerate(patterns):
        match = re.fullmatch(
            pattern,
            command,
            flags=re.IGNORECASE,
        )

        if not match:
            continue

        if index == 0:
            engine, query = match.groups()

        elif index == 1:
            query, engine = match.groups()

        elif index == 2:
            query = match.group(1)

        elif index == 3:
            engine, query = match.groups()

        else:
            query = match.group(1)

        break

    if query is None:
        return None

    engine = engine.lower()
    query = query.strip()

    if not query:
        return "ERROR: Search topic is empty."

    if len(query) > 200:
        return "ERROR: Search topic is too long."

    search_url = SEARCH_ENGINES[engine] + quote_plus(query)

    try:
        opened = webbrowser.open(search_url)

        if opened:
            return (
                f"SUCCESS: Searching {engine.title()} "
                f"for {query}."
            )

        return "ERROR: Could not open the browser."

    except Exception as error:
        return f"ERROR: Web search failed: {error}"


if __name__ == "__main__":
    print("=== KYRA AI v3.0 WEB SEARCH ===")

    while True:
        command = input("Enter search command (or EXIT): ").strip()

        if command.lower() == "exit":
            break

        result = handle_search_command(command)

        if result is None:
            print("Command not recognized.")
        else:
            print(result)
