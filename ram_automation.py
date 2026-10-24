
import ctypes
import sys
from ctypes import wintypes


# ==========================================
# WINDOWS RAM INFORMATION STRUCTURE
# ==========================================

class MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", wintypes.DWORD),
        ("dwMemoryLoad", wintypes.DWORD),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


# ==========================================
# READ RAM USAGE
# ==========================================

def get_ram_status():
    """Read the laptop's RAM usage from Windows."""

    if sys.platform != "win32":
        return "ERROR: RAM monitoring requires Windows."

    try:
        memory = MEMORYSTATUSEX()

        memory.dwLength = ctypes.sizeof(
            MEMORYSTATUSEX
        )

        kernel32 = ctypes.WinDLL(
            "kernel32",
            use_last_error=True
        )

        get_memory_status = (
            kernel32.GlobalMemoryStatusEx
        )

        get_memory_status.argtypes = [
            ctypes.POINTER(MEMORYSTATUSEX)
        ]

        get_memory_status.restype = wintypes.BOOL

        success = get_memory_status(
            ctypes.byref(memory)
        )

        if not success:
            return "ERROR: Could not read RAM information."

        total_bytes = memory.ullTotalPhys
        available_bytes = memory.ullAvailPhys

        if total_bytes == 0:
            return "ERROR: Total RAM information unavailable."

        used_bytes = total_bytes - available_bytes

        # Convert bytes into gigabytes.
        gb = 1024 ** 3

        total_gb = total_bytes / gb
        used_gb = used_bytes / gb
        available_gb = available_bytes / gb

        usage_percent = (
            used_bytes / total_bytes
        ) * 100

        return (
            f"SUCCESS: RAM usage is {usage_percent:.1f}%. "
            f"Used: {used_gb:.1f} GB. "
            f"Available: {available_gb:.1f} GB. "
            f"Total: {total_gb:.1f} GB."
        )

    except (OSError, AttributeError, ValueError) as error:
        return f"ERROR: {error}"


# ==========================================
# SUPPORTED COMMANDS
# ==========================================

RAM_COMMANDS = {
    # English
    "ram usage",
    "ram status",
    "check ram",
    "how much ram is being used",

    # Hindi
    "रैम स्टेटस बताओ",
    "रैम कितनी इस्तेमाल हो रही है",
    "रैम चेक करो",

    # Telugu
    "ర్యామ్ ఎంత వాడుతోంది",
    "ర్యామ్ స్టేటస్ చెప్పు",
    "ర్యామ్ చెక్ చెయ్యి",
}


# ==========================================
# COMMAND RECOGNITION
# ==========================================

def handle_ram_command(command):
    """Recognize English, Hindi and Telugu RAM commands."""

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

    if command in RAM_COMMANDS:
        return get_ram_status()

    return None


# ==========================================
# TERMINAL TEST
# ==========================================

if __name__ == "__main__":
    print("=== KYRA RAM MONITOR TEST ===")

    command = input("Enter command: ")

    result = handle_ram_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
