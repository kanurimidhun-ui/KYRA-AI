
import json
import os
import re
import subprocess
from functools import lru_cache


# ---------------------------------------
# KYRA AI - WINDOWS APPLICATION AUTOMATION
# ---------------------------------------

# Existing supported applications.
ALLOWED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
}

# Windows apps that need a special launcher.
SPECIAL_APPS = {
    "camera",
}

# Common application name alternatives.
APP_ALIASES = {
    "calc": "calculator",
    "ms paint": "paint",
    "windows camera": "camera",
    "camera app": "camera",
    "vscode": "visual studio code",
    "vs code": "visual studio code",
    "code": "visual studio code",
}

# Supported direct commands.
APP_COMMANDS = {
    # Notepad
    "open notepad": "notepad",
    "notepad open": "notepad",
    "నోట్‌ప్యాడ్ తెరువు": "notepad",
    "नोटपैड खोलो": "notepad",

    # Calculator
    "open calculator": "calculator",
    "calculator open": "calculator",
    "కాలిక్యులేటర్ తెరువు": "calculator",
    "कैलकुलेटर खोलो": "calculator",

    # Paint
    "open paint": "paint",
    "paint open": "paint",
    "పెయింట్ తెరువు": "paint",
    "पेंट खोलो": "paint",

    # Camera - NEW
    "open camera": "camera",
    "camera open": "camera",
    "launch camera": "camera",
    "start camera": "camera",
    "open windows camera": "camera",
    "కెమెరా తెరువు": "camera",
    "कैमरा खोलो": "camera",
}


def normalize_name(value):
    """Normalize application names for matching."""
    return " ".join(value.casefold().strip().split())


@lru_cache(maxsize=1)
def discover_installed_apps():
    """
    Discover applications registered in Windows Start menu.
    Does not install software or scan private files.
    """

    powershell_command = (
        "[Console]::OutputEncoding = "
        "[System.Text.Encoding]::UTF8; "
        "Get-StartApps | "
        "Select-Object Name, AppID | "
        "ConvertTo-Json -Compress -Depth 3"
    )

    try:
        result = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-Command",
                powershell_command,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=True,
        )

        if not result.stdout.strip():
            return []

        apps = json.loads(result.stdout)

        if isinstance(apps, dict):
            apps = [apps]

        return [
            app
            for app in apps
            if isinstance(app, dict)
            and isinstance(app.get("Name"), str)
            and isinstance(app.get("AppID"), str)
            and app["Name"].strip()
            and app["AppID"].strip()
        ]

    except (
        OSError,
        subprocess.SubprocessError,
        ValueError,
    ):
        return []


def find_installed_app(app_name):
    """Find a Windows application by its display name."""

    target = normalize_name(app_name)
    apps = discover_installed_apps()

    exact_matches = [
        app
        for app in apps
        if normalize_name(app["Name"]) == target
    ]

    if len(exact_matches) == 1:
        return exact_matches[0]

    if len(exact_matches) > 1:
        return None

    partial_matches = [
        app
        for app in apps
        if normalize_name(app["Name"]).startswith(target + " ")
    ]

    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


def open_application(app_name):
    """Launch an explicitly supported or registered application."""

    if not isinstance(app_name, str):
        return "ERROR: Invalid application name."

    app_name = normalize_name(app_name)

    if not app_name:
        return "ERROR: Empty application name."

    app_name = APP_ALIASES.get(app_name, app_name)

    # ---------------------------------------
    # NEW - WINDOWS CAMERA
    # ---------------------------------------
    if app_name == "camera":
        try:
            os.startfile("microsoft.windows.camera:")
            return "SUCCESS: Opened Camera."

        except OSError as error:
            return f"ERROR: Could not open Camera: {error}"

    # ---------------------------------------
    # EXISTING APPLICATIONS
    # ---------------------------------------
    if app_name in ALLOWED_APPS:
        try:
            subprocess.Popen(
                [ALLOWED_APPS[app_name]],
                shell=False,
            )

            return f"SUCCESS: Opened {app_name}."

        except OSError as error:
            return f"ERROR: Could not open {app_name}: {error}"

    # ---------------------------------------
    # REGISTERED WINDOWS APPLICATIONS
    # ---------------------------------------
    installed_app = find_installed_app(app_name)

    if installed_app is None:
        return (
            f"ERROR: Application '{app_name}' was not found "
            "in the Windows Start menu."
        )

    try:
        app_id = installed_app["AppID"]

        subprocess.Popen(
            [
                "explorer.exe",
                "shell:AppsFolder\\" + app_id,
            ],
            shell=False,
        )

        return (
            "SUCCESS: Launch requested for "
            f"{installed_app['Name']}."
        )

    except OSError as error:
        return f"ERROR: Could not launch application: {error}"


def handle_automation_command(command):
    """Recognize application-opening commands."""

    if not isinstance(command, str):
        return None

    command = normalize_name(command)

    # Remove optional KYRA wake word.
    command = re.sub(
        r"^(kyra|కైరా|कायरा)[\s,!:]+",
        "",
        command,
    ).strip()

    command = command.rstrip(" .?!।")

    # ---------------------------------------
    # EXACT COMMAND MATCHING
    # ---------------------------------------
    if command in APP_COMMANDS:
        return open_application(APP_COMMANDS[command])

    # ---------------------------------------
    # FLEXIBLE COMMAND MATCHING
    # ---------------------------------------
    patterns = [
        # English
        r"^(?:open|launch|start|run)\s+(.+)$",
        r"^(.+?)\s+open$",

        # Telugu
        r"^(.+?)\s+తెరువు$",
        r"^(.+?)\s+ఓపెన్ చెయ్యి$",
        r"^(.+?)\s+ఓపెన్ చేయి$",

        # Hindi
        r"^(.+?)\s+खोलो$",
        r"^(.+?)\s+खोलिए$",
    ]

    for pattern in patterns:
        match = re.match(pattern, command)

        if not match:
            continue

        app_name = match.group(1).strip()

        if not app_name:
            return None

        # Avoid intercepting websites and URLs.
        if (
            app_name.startswith(
                ("http://", "https://", "www.")
            )
            or "." in app_name
        ):
            return None

        app_name = APP_ALIASES.get(app_name, app_name)

        # Only launch supported or registered apps.
        if (
            app_name in ALLOWED_APPS
            or app_name in SPECIAL_APPS
            or find_installed_app(app_name) is not None
        ):
            return open_application(app_name)

    # Allow other KYRA modules to handle the command.
    return None


# ---------------------------------------
# DIRECT MODULE TEST
# ---------------------------------------
if __name__ == "__main__":
    print("=== KYRA AI v4.2 ===")
    print("Windows Application Automation")
    print()

    apps = discover_installed_apps()

    print(f"Registered applications found: {len(apps)}")
    print("Supported: Notepad, Calculator, Paint, Camera")
    print()

    while True:
        command = input(
            "Enter command (or EXIT): "
        ).strip()

        if command.casefold() == "exit":
            break

        result = handle_automation_command(command)

        if result is None:
            print("Command not recognized by app launcher.")
        else:
            print(result)

        print()
