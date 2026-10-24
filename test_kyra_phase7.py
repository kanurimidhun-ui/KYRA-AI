
import unittest
from unittest.mock import patch

from automation import handle_automation_command
from web_automation import handle_website_command
from search_automation import handle_search_command
from folder_automation import handle_folder_command
from datetime_automation import handle_datetime_command
from battery_automation import handle_battery_command
from ram_automation import handle_ram_command
from cpu_automation import handle_cpu_command


class TestKYRAPhase7(unittest.TestCase):

    # ----------------------------------
    # 1. APPLICATION COMMANDS
    # ----------------------------------

    def test_unrelated_app_command(self):
        result = handle_automation_command(
            "tell me about artificial intelligence"
        )
        self.assertIsNone(result)

    # ----------------------------------
    # 2. WEBSITE COMMANDS
    # ----------------------------------

    def test_unrelated_website_command(self):
        result = handle_website_command(
            "explain python variables"
        )
        self.assertIsNone(result)

    # ----------------------------------
    # 3. GOOGLE SEARCH COMMANDS
    # ----------------------------------

    def test_unrelated_search_command(self):
        result = handle_search_command(
            "what is machine learning"
        )
        self.assertIsNone(result)

    # ----------------------------------
    # 4. FOLDER COMMANDS
    # ----------------------------------

    def test_unrelated_folder_command(self):
        result = handle_folder_command(
            "what is a folder"
        )
        self.assertIsNone(result)

    # ----------------------------------
    # 5. DATE AND TIME
    # ----------------------------------

    def test_telugu_time_command(self):
        result = handle_datetime_command(
            "కైరా, ఇప్పుడు టైమ్ ఎంత?"
        )
        self.assertIsNotNone(result)
        self.assertTrue(
            result.startswith(
                "SUCCESS: Current time is "
            )
        )

    def test_english_date_command(self):
        result = handle_datetime_command(
            "KYRA, today's date"
        )
        self.assertIsNotNone(result)
        self.assertTrue(
            result.startswith(
                "SUCCESS: Today's date is "
            )
        )

    # ----------------------------------
    # 6. BATTERY MONITORING
    # ----------------------------------

    @patch(
        "battery_automation.get_battery_status",
        return_value=(
            "SUCCESS: Battery level is 80%. "
            "Status: Charging."
        )
    )
    def test_telugu_battery_command(self, mock_battery):
        result = handle_battery_command(
            "కైరా, బ్యాటరీ ఎంత ఉంది"
        )

        self.assertEqual(
            result,
            "SUCCESS: Battery level is 80%. "
            "Status: Charging."
        )

        mock_battery.assert_called_once()

    # ----------------------------------
    # 7. RAM MONITORING
    # ----------------------------------

    @patch(
        "ram_automation.get_ram_status",
        return_value=(
            "SUCCESS: RAM usage is 50.0%. "
            "Used: 8.0 GB. "
            "Available: 8.0 GB. "
            "Total: 16.0 GB."
        )
    )
    def test_telugu_ram_command(self, mock_ram):
        result = handle_ram_command(
            "కైరా, ర్యామ్ ఎంత వాడుతోంది"
        )

        self.assertIsNotNone(result)
        self.assertTrue(
            result.startswith("SUCCESS: RAM usage")
        )

        mock_ram.assert_called_once()

    # ----------------------------------
    # 8. CPU MONITORING
    # ----------------------------------

    @patch(
        "cpu_automation.get_cpu_status",
        return_value="SUCCESS: CPU usage is 25.0%."
    )
    def test_telugu_cpu_command(self, mock_cpu):
        result = handle_cpu_command(
            "కైరా, సీపీయూ ఎంత వాడుతోంది"
        )

        self.assertEqual(
            result,
            "SUCCESS: CPU usage is 25.0%."
        )

        mock_cpu.assert_called_once()

    # ----------------------------------
    # 9. UNKNOWN COMMANDS
    # ----------------------------------

    def test_unknown_battery_command(self):
        result = handle_battery_command(
            "explain cybersecurity"
        )
        self.assertIsNone(result)

    def test_unknown_ram_command(self):
        result = handle_ram_command(
            "what is python"
        )
        self.assertIsNone(result)

    def test_unknown_cpu_command(self):
        result = handle_cpu_command(
            "tell me a joke"
        )
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main(verbosity=2)
