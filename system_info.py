
import os
import platform
import shutil
from datetime import datetime
from pathlib import Path


def get_system_information():
    """Read basic information about this computer."""

    # Detect operating system
    operating_system = platform.system()

    # Count logical CPU cores
    cpu_cores = os.cpu_count()

    # Check the drive containing the user's home folder
    drive = Path.home().anchor
    disk = shutil.disk_usage(drive)

    free_gb = disk.free / (1024 ** 3)
    total_gb = disk.total / (1024 ** 3)

    # Read local computer time
    current_time = datetime.now().strftime(
        "%d-%m-%Y %I:%M %p"
    )

    return (
        "=== KYRA SYSTEM INFORMATION ===\n"
        f"Operating System: {operating_system}\n"
        f"Logical CPU Cores: {cpu_cores}\n"
        f"Drive Checked: {drive}\n"
        f"Total Disk Space: {total_gb:.1f} GB\n"
        f"Free Disk Space: {free_gb:.1f} GB\n"
        f"Current Time: {current_time}"
    )


def handle_system_command(command):
    """Recognize system information commands."""

    if not isinstance(command, str):
        return None

    command = command.strip().lower()

    for wake_word in ("kyra", "कायरा", "కైరా"):
        if command.startswith(wake_word):
            command = command[len(wake_word):]
            command = command.lstrip(" ,:!?।")

    command = command.rstrip(" .?!।")

    supported_commands = {
        "system status",
        "show system information",
        "सिस्टम की जानकारी बताओ",
        "సిస్టమ్ వివరాలు చెప్పు",
    }

    if command not in supported_commands:
        return None

    return get_system_information()


if __name__ == "__main__":
    print("=== KYRA SYSTEM MONITOR TEST ===")

    command = input("Enter command: ")

    result = handle_system_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
