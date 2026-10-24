
import ctypes
import sys
import time
from ctypes import wintypes


# ==========================================
# WINDOWS CPU TIME STRUCTURE
# ==========================================

class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


# ==========================================
# CONVERT WINDOWS CPU TIME
# ==========================================

def filetime_to_int(value):
    """Convert Windows FILETIME to an integer."""

    return (
        (value.dwHighDateTime << 32)
        | value.dwLowDateTime
    )


# ==========================================
# READ CPU TIME SNAPSHOT
# ==========================================

def get_cpu_times():
    """Read system CPU times from Windows."""

    kernel32 = ctypes.WinDLL(
        "kernel32",
        use_last_error=True
    )

    get_system_times = kernel32.GetSystemTimes

    get_system_times.argtypes = [
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
        ctypes.POINTER(FILETIME),
    ]

    get_system_times.restype = wintypes.BOOL

    idle_time = FILETIME()
    kernel_time = FILETIME()
    user_time = FILETIME()

    success = get_system_times(
        ctypes.byref(idle_time),
        ctypes.byref(kernel_time),
        ctypes.byref(user_time),
    )

    if not success:
        raise OSError(
            "Could not read Windows CPU times."
        )

    return (
        filetime_to_int(idle_time),
        filetime_to_int(kernel_time),
        filetime_to_int(user_time),
    )


# ==========================================
# MEASURE CPU USAGE
# ==========================================

def get_cpu_status():
    """Measure CPU usage over a short interval."""

    if sys.platform != "win32":
        return "ERROR: CPU monitoring requires Windows."

    try:
        # First CPU measurement
        idle1, kernel1, user1 = get_cpu_times()

        # Wait half a second
        time.sleep(0.5)

        # Second CPU measurement
        idle2, kernel2, user2 = get_cpu_times()

        idle_delta = idle2 - idle1

        kernel_delta = kernel2 - kernel1
        user_delta = user2 - user1

        # Windows kernel time includes idle time.
        total_delta = kernel_delta + user_delta

        if total_delta <= 0:
            return "ERROR: CPU usage unavailable."

        busy_delta = total_delta - idle_delta

        usage_percent = (
            busy_delta / total_delta
        ) * 100

        # Keep percentage within 0-100.
        usage_percent = max(
            0.0,
            min(100.0, usage_percent)
        )

        return (
            f"SUCCESS: CPU usage is "
            f"{usage_percent:.1f}%."
        )

    except (OSError, AttributeError, ValueError) as error:
        return f"ERROR: {error}"


# ==========================================
# SUPPORTED COMMANDS
# ==========================================

CPU_COMMANDS = {
    # English
    "cpu usage",
    "cpu status",
    "check cpu",
    "how much cpu is being used",

    # Hindi
    "सीपीयू कितना इस्तेमाल हो रहा है",
    "सीपीयू स्टेटस बताओ",
    "सीपीयू चेक करो",

    # Telugu
    "సీపీయూ ఎంత వాడుతోంది",
    "సీపీయూ స్టేటస్ చెప్పు",
    "సీపీయూ చెక్ చెయ్యి",
}


# ==========================================
# COMMAND RECOGNITION
# ==========================================

def handle_cpu_command(command):
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

    if command in CPU_COMMANDS:
        return get_cpu_status()

    return None


# ==========================================
# TERMINAL TEST
# ==========================================

if __name__ == "__main__":
    print("=== KYRA CPU MONITOR TEST ===")

    command = input("Enter command: ")

    result = handle_cpu_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
