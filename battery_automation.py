
import ctypes
import sys
from ctypes import wintypes


# ---------------------------------------
# WINDOWS BATTERY DATA STRUCTURE
# ---------------------------------------

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", wintypes.BYTE),
        ("BatteryFlag", wintypes.BYTE),
        ("BatteryLifePercent", wintypes.BYTE),
        ("SystemStatusFlag", wintypes.BYTE),
        ("BatteryLifeTime", wintypes.DWORD),
        ("BatteryFullLifeTime", wintypes.DWORD),
    ]


# ---------------------------------------
# READ LAPTOP BATTERY INFORMATION
# ---------------------------------------

def get_battery_status():
    """Read battery information from Windows."""

    if sys.platform != "win32":
        return "ERROR: Battery monitoring requires Windows."

    try:
        status = SYSTEM_POWER_STATUS()

        kernel32 = ctypes.WinDLL(
            "kernel32",
            use_last_error=True
        )

        get_power_status = kernel32.GetSystemPowerStatus

        get_power_status.argtypes = [
            ctypes.POINTER(SYSTEM_POWER_STATUS)
        ]

        get_power_status.restype = wintypes.BOOL

        success = get_power_status(
            ctypes.byref(status)
        )

        if not success:
            return "ERROR: Could not read battery status."

        # Windows reports 255 when percentage is unknown.
        if status.BatteryLifePercent == 255:
            return "INFO: Battery percentage is unavailable."

        # Windows uses battery flag 128 for no battery.
        if status.BatteryFlag & 128:
            return "INFO: No battery detected."

        percentage = status.BatteryLifePercent

        # Determine power connection status.
        if status.BatteryFlag & 8:
            power_state = "Charging"

        elif status.ACLineStatus == 1:
            if percentage == 100:
                power_state = "Fully charged"
            else:
                power_state = "Plugged in"

        elif status.ACLineStatus == 0:
            power_state = "On battery power"

        else:
            power_state = "Power state unknown"

        return (
            f"SUCCESS: Battery level is {percentage}%. "
            f"Status: {power_state}."
        )

    except (OSError, AttributeError, ValueError) as error:
        return f"ERROR: {error}"


# ---------------------------------------
# SUPPORTED VOICE COMMANDS
# ---------------------------------------

BATTERY_COMMANDS = {
    # English
    "battery status",
    "check battery",
    "battery percentage",
    "how much battery is left",

    # Hindi
    "बैटरी कितनी है",
    "बैटरी स्टेटस बताओ",
    "बैटरी चेक करो",

    # Telugu
    "బ్యాటరీ ఎంత ఉంది",
    "బ్యాటరీ స్టేటస్ చెప్పు",
    "బ్యాటరీ చెక్ చెయ్యి",
}


# ---------------------------------------
# RECOGNIZE KYRA COMMANDS
# ---------------------------------------

def handle_battery_command(command):
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

    if command in BATTERY_COMMANDS:
        return get_battery_status()

    return None


# ---------------------------------------
# TERMINAL TEST
# ---------------------------------------

if __name__ == "__main__":
    print("=== KYRA BATTERY MONITOR TEST ===")

    command = input("Enter command: ")

    result = handle_battery_command(command)

    if result is None:
        print("Command not recognized.")
    else:
        print(result)
