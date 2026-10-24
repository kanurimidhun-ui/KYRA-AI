
import unittest
from unittest.mock import patch

from app import (
    app,
    conversation_history,
    history_lock,
)


# ==========================================
# KYRA PHASE 7 - STEP 2
# FLASK API REGRESSION TESTS
# ==========================================

class TestKYRAAPI(unittest.TestCase):

    def setUp(self):
        # Create a test client.
        self.client = app.test_client()

        # Clear test conversation history.
        with history_lock:
            conversation_history.clear()

    # ----------------------------------
    # TEST 1: BACKEND HEALTH
    # ----------------------------------

    def test_health_endpoint(self):
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["status"],
            "online"
        )

    # ----------------------------------
    # TEST 2: KYRA STATUS
    # ----------------------------------

    def test_status_endpoint(self):
        response = self.client.get("/api/status")

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["assistant"], "KYRA")
        self.assertEqual(data["phase"], 6)

    # ----------------------------------
    # TEST 3: INVALID JSON
    # ----------------------------------

    def test_invalid_json(self):
        response = self.client.post(
            "/api/ask",
            data="invalid-json",
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)

    # ----------------------------------
    # TEST 4: EMPTY QUESTION
    # ----------------------------------

    def test_empty_question(self):
        response = self.client.post(
            "/api/ask",
            json={"message": ""},
        )

        self.assertEqual(response.status_code, 400)

    # ----------------------------------
    # TEST 5: CPU - TELUGU
    # ----------------------------------

    @patch(
        "cpu_automation.get_cpu_status",
        return_value="SUCCESS: CPU usage is 25.0%."
    )
    def test_cpu_telugu(self, mock_cpu):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "కైరా, సీపీయూ ఎంత వాడుతోంది",
                "language": "te",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "cpu_status")
        self.assertIn("25.0", data["reply"])
        self.assertIn("సీపీయూ", data["reply"])

        mock_cpu.assert_called_once()

    # ----------------------------------
    # TEST 6: RAM - HINDI
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
    def test_ram_hindi(self, mock_ram):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "कायरा, रैम स्टेटस बताओ",
                "language": "hi",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "ram_status")
        self.assertIn("50.0", data["reply"])
        self.assertIn("रैम", data["reply"])

        mock_ram.assert_called_once()

    # ----------------------------------
    # TEST 7: BATTERY - ENGLISH
    # ----------------------------------

    @patch(
        "battery_automation.get_battery_status",
        return_value=(
            "SUCCESS: Battery level is 80%. "
            "Status: Charging."
        )
    )
    def test_battery_english(self, mock_battery):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "KYRA, battery status",
                "language": "en",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "battery_status")
        self.assertIn("80%", data["reply"])
        self.assertIn("Charging", data["reply"])

        mock_battery.assert_called_once()

    # ----------------------------------
    # TEST 8: DATE AND TIME - TELUGU
    # ----------------------------------

    def test_datetime_telugu(self):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "కైరా, ఇప్పుడు టైమ్ ఎంత?",
                "language": "te",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "date_time")
        self.assertIn("సమయం", data["reply"])

    # ----------------------------------
    # TEST 9: FOLDER AUTOMATION
    # ----------------------------------

    @patch(
        "app.handle_folder_command",
        return_value="SUCCESS: Opened downloads."
    )
    def test_folder_automation(self, mock_folder):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "KYRA, open downloads",
                "language": "en",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "open_folder")
        self.assertIn("Downloads", data["reply"])

        mock_folder.assert_called_once()

    # ----------------------------------
    # TEST 10: WEBSITE AUTOMATION
    # ----------------------------------

    @patch(
        "app.handle_website_command",
        return_value="SUCCESS: Opened youtube."
    )
    def test_website_automation(self, mock_website):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "KYRA, open youtube",
                "language": "en",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(data["action"], "open_website")
        self.assertIn("YouTube", data["reply"])

        mock_website.assert_called_once()

    # ----------------------------------
    # TEST 11: AI CHAT FALLBACK
    # ----------------------------------

    @patch(
        "app.ollama_request",
        return_value={
            "message": {
                "content": "Recursion is when a function calls itself."
            }
        }
    )
    def test_ai_chat(self, mock_ollama):
        response = self.client.post(
            "/api/ask",
            json={
                "message": "Explain recursion in one sentence",
                "language": "en",
            },
        )

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertIn("Recursion", data["reply"])

        mock_ollama.assert_called_once()

    # ----------------------------------
    # TEST 12: AI MODEL STATUS
    # ----------------------------------

    @patch(
        "app.ollama_request",
        return_value={
            "models": [
                {"name": "llama3.2:3b"}
            ]
        }
    )
    def test_ai_status(self, mock_ollama):
        response = self.client.get("/api/ai-status")

        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["ready"])
        self.assertEqual(data["status"], "online")

        mock_ollama.assert_called_once()

    # ----------------------------------
    # TEST 13: INVALID TTS LANGUAGE
    # ----------------------------------

    def test_invalid_tts_language(self):
        response = self.client.post(
            "/api/tts",
            json={
                "text": "Hello",
                "language": "en",
            },
        )

        self.assertEqual(response.status_code, 400)


# ==========================================
# RUN TESTS
# ==========================================

if __name__ == "__main__":
    unittest.main(verbosity=2)
