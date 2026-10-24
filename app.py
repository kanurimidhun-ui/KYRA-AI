
import asyncio
import json
import re
from datetime import datetime
from threading import Lock
from urllib import error, request as url_request

import edge_tts
from flask import Flask, Response, jsonify, render_template, request

# ==========================================
# KYRA AUTOMATION MODULES
# ==========================================

from automation import handle_automation_command
from web_automation import handle_website_command
from search_automation import handle_search_command
from system_info import handle_system_command
from folder_automation import handle_folder_command
from datetime_automation import handle_datetime_command
from battery_automation import handle_battery_command
from ram_automation import handle_ram_command

# STEP 23: CPU monitoring
from cpu_automation import handle_cpu_command


# ==========================================
# KYRA CONFIGURATION
# ==========================================

app = Flask(__name__)

OLLAMA_URL = "http://127.0.0.1:11434"
AI_MODEL = "llama3.2:3b"

conversation_history = []
history_lock = Lock()
MAX_HISTORY = 20

LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English only.",
    "hi": "Respond in Hindi only, using Devanagari script.",
    "te": "Respond in Telugu only, using Telugu script.",
}

TELUGU_VOICE = "te-IN-ShrutiNeural"


# ==========================================
# HOME PAGE AND STATUS
# ==========================================

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/health")
@app.route("/api/status")
def status():
    return jsonify(
        assistant="KYRA",
        status="online",
        phase=6,
        checked_at=datetime.now().astimezone().isoformat(
            timespec="seconds"
        ),
    )


# ==========================================
# OLLAMA CONNECTION
# ==========================================

def ollama_request(endpoint, payload=None, timeout=30):
    url = OLLAMA_URL + endpoint

    if payload is None:
        http_request = url_request.Request(
            url,
            method="GET",
        )
    else:
        http_request = url_request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    with url_request.urlopen(
        http_request,
        timeout=timeout,
    ) as response:
        return json.loads(
            response.read().decode("utf-8")
        )


@app.route("/api/ai-status")
def ai_status():
    try:
        data = ollama_request("/api/tags", timeout=5)

        installed = any(
            model.get("name") == AI_MODEL
            or model.get("model") == AI_MODEL
            for model in data.get("models", [])
        )

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="online" if installed else "offline",
            available=installed,
            ready=installed,
            online=installed,
            installed=installed,
        )

    except (
        error.URLError,
        TimeoutError,
        ValueError,
        OSError,
    ):
        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="offline",
            available=False,
            ready=False,
            online=False,
            installed=False,
            message="Ollama is not reachable.",
        )


# ==========================================
# CONVERSATION MEMORY
# ==========================================

def remember_exchange(question, answer):
    with history_lock:
        conversation_history.append({
            "role": "user",
            "content": question,
        })

        conversation_history.append({
            "role": "assistant",
            "content": answer,
        })

        if len(conversation_history) > MAX_HISTORY:
            del conversation_history[:-MAX_HISTORY]


def extract_user_command(question):
    marker = "\nUSER QUESTION: "

    if (
        question.startswith("IMPORTANT LANGUAGE REQUIREMENT:")
        and marker in question
    ):
        return question.rsplit(marker, 1)[1].strip()

    return question.strip()


# ==========================================
# WINDOWS APPLICATION REPLIES
# ==========================================

def automation_reply(result, language):
    if result.startswith("SUCCESS:"):
        app_name = (
            result.replace("SUCCESS: Opened ", "")
            .rstrip(".")
            .strip()
        )

        app_names = {
            "notepad": {
                "en": "Notepad",
                "hi": "नोटपैड",
                "te": "నోట్‌ప్యాడ్",
            },
            "calculator": {
                "en": "Calculator",
                "hi": "कैलकुलेटर",
                "te": "కాలిక్యులేటర్",
            },
            "paint": {
                "en": "Paint",
                "hi": "पेंट",
                "te": "పెయింట్",
            },
        }

        translated_name = app_names.get(
            app_name, {}
        ).get(language, app_name)

        if language == "hi":
            return f"मैंने {translated_name} खोल दिया है।"

        if language == "te":
            return f"నేను {translated_name} తెరిచాను."

        return f"I opened {translated_name} successfully."

    if language == "hi":
        return "माफ़ कीजिए, मैं एप्लिकेशन नहीं खोल पाई।"

    if language == "te":
        return "క్షమించండి, నేను అప్లికేషన్ తెరవలేకపోయాను."

    return "Sorry, I couldn't open the application."


# ==========================================
# WEBSITE REPLIES
# ==========================================

def website_reply(result, language):
    if result.startswith("SUCCESS:"):
        website_name = (
            result.replace("SUCCESS: Opened ", "")
            .rstrip(".")
            .strip()
        )

        website_names = {
            "youtube": {
                "en": "YouTube",
                "hi": "यूट्यूब",
                "te": "యూట్యూబ్",
            },
            "google": {
                "en": "Google",
                "hi": "गूगल",
                "te": "గూగుల్",
            },
            "github": {
                "en": "GitHub",
                "hi": "गिटहब",
                "te": "గిట్‌హబ్",
            },
        }

        translated_name = website_names.get(
            website_name, {}
        ).get(language, website_name)

        if language == "hi":
            return f"मैंने {translated_name} खोल दिया है।"

        if language == "te":
            return f"నేను {translated_name} వెబ్‌సైట్ తెరిచాను."

        return f"I opened {translated_name} successfully."

    if language == "hi":
        return "माफ़ कीजिए, वेबसाइट नहीं खुल पाई।"

    if language == "te":
        return "క్షమించండి, వెబ్‌సైట్ తెరవలేకపోయాను."

    return "Sorry, I couldn't open the website."


# ==========================================
# GOOGLE SEARCH REPLIES
# ==========================================

def search_reply(result, language):
    if result.startswith("SUCCESS:"):
        if language == "hi":
            return "मैंने गूगल पर खोज परिणाम खोल दिए हैं।"

        if language == "te":
            return "నేను గూగుల్‌లో సెర్చ్ ఫలితాలను తెరిచాను."

        return "I opened your Google search results."

    if language == "hi":
        return "माफ़ कीजिए, गूगल खोज नहीं खुल पाई।"

    if language == "te":
        return "క్షమించండి, గూగుల్ సెర్చ్ తెరవలేకపోయాను."

    return "Sorry, I couldn't open Google search."


# ==========================================
# SYSTEM INFORMATION REPLIES
# ==========================================

SYSTEM_LABELS = {
    "hi": {
        "Operating System": "ऑपरेटिंग सिस्टम",
        "Logical CPU Cores": "सीपीयू के लॉजिकल कोर",
        "Drive Checked": "जाँची गई ड्राइव",
        "Total Disk Space": "कुल डिस्क स्थान",
        "Free Disk Space": "खाली डिस्क स्थान",
        "Current Time": "वर्तमान समय",
    },
    "te": {
        "Operating System": "ఆపరేటింగ్ సిస్టమ్",
        "Logical CPU Cores": "సీపీయూ లాజికల్ కోర్లు",
        "Drive Checked": "పరిశీలించిన డ్రైవ్",
        "Total Disk Space": "మొత్తం డిస్క్ స్థలం",
        "Free Disk Space": "ఖాళీ డిస్క్ స్థలం",
        "Current Time": "ప్రస్తుత సమయం",
    },
}


def system_reply(result, language):
    if language == "en":
        return result

    if language == "hi":
        heading = "यह आपके कंप्यूटर की जानकारी है:"
    else:
        heading = "ఇవి మీ కంప్యూటర్ వివరాలు:"

    labels = SYSTEM_LABELS.get(language, {})
    output_lines = [heading]

    for line in result.splitlines():
        if line.startswith("==="):
            continue

        if ": " in line:
            key, value = line.split(": ", 1)

            translated_key = labels.get(key, key)

            output_lines.append(
                f"{translated_key}: {value}"
            )
        else:
            output_lines.append(line)

    return "\n".join(output_lines)


# ==========================================
# FOLDER AUTOMATION REPLIES
# ==========================================

FOLDER_NAMES = {
    "downloads": {
        "en": "Downloads",
        "hi": "डाउनलोड्स",
        "te": "డౌన్‌లోడ్స్",
    },
    "documents": {
        "en": "Documents",
        "hi": "डॉक्यूमेंट्स",
        "te": "డాక్యుమెంట్స్",
    },
}


def folder_reply(result, language):
    if result.startswith("SUCCESS: Opened "):
        folder_name = (
            result.replace("SUCCESS: Opened ", "", 1)
            .rstrip(".")
            .strip()
            .lower()
        )

        translated_name = FOLDER_NAMES.get(
            folder_name, {}
        ).get(language, folder_name)

        if language == "hi":
            return f"मैंने {translated_name} फ़ोल्डर खोल दिया है।"

        if language == "te":
            return f"నేను {translated_name} ఫోల్డర్ తెరిచాను."

        return f"I opened your {translated_name} folder."

    if language == "hi":
        return "माफ़ कीजिए, फ़ोल्डर नहीं खुल पाया।"

    if language == "te":
        return "క్షమించండి, ఫోల్డర్ తెరవలేకపోయాను."

    return "Sorry, I couldn't open the folder."


# ==========================================
# DATE AND TIME REPLIES
# ==========================================

def datetime_reply(result, language):
    time_prefix = "SUCCESS: Current time is "
    date_prefix = "SUCCESS: Today's date is "

    if result.startswith(time_prefix):
        time_value = (
            result[len(time_prefix):]
            .rstrip(".")
            .strip()
        )

        if language == "hi":
            return f"अभी समय {time_value} है।"

        if language == "te":
            return f"ఇప్పుడు సమయం {time_value}."

        return f"The current time is {time_value}."

    if result.startswith(date_prefix):
        date_value = (
            result[len(date_prefix):]
            .rstrip(".")
            .strip()
        )

        if language == "hi":
            return f"आज की तारीख {date_value} है।"

        if language == "te":
            return f"ఈరోజు తేదీ {date_value}."

        return f"Today's date is {date_value}."

    if language == "hi":
        return "माफ़ कीजिए, समय या तारीख नहीं मिल पाई।"

    if language == "te":
        return "క్షమించండి, సమయం లేదా తేదీ తెలుసుకోలేకపోయాను."

    return "Sorry, I couldn't get the date or time."


# ==========================================
# BATTERY REPLIES
# ==========================================

BATTERY_STATUS_TRANSLATIONS = {
    "Charging": {
        "en": "Charging",
        "hi": "चार्ज हो रही है",
        "te": "ఛార్జ్ అవుతోంది",
    },
    "Fully charged": {
        "en": "Fully charged",
        "hi": "पूरी तरह चार्ज है",
        "te": "పూర్తిగా ఛార్జ్ అయింది",
    },
    "Plugged in": {
        "en": "Plugged in",
        "hi": "चार्जर जुड़ा हुआ है",
        "te": "ఛార్జర్ కనెక్ట్ అయి ఉంది",
    },
    "On battery power": {
        "en": "On battery power",
        "hi": "बैटरी पर चल रहा है",
        "te": "బ్యాటరీ పవర్‌తో పనిచేస్తోంది",
    },
    "Power state unknown": {
        "en": "Power state unknown",
        "hi": "पावर की स्थिति अज्ञात है",
        "te": "పవర్ స్థితి తెలియదు",
    },
}


def battery_reply(result, language):
    pattern = (
        r"SUCCESS: Battery level is (\d{1,3})%\. "
        r"Status: (.+)\."
    )

    match = re.fullmatch(pattern, result)

    if match:
        percentage = match.group(1)
        power_state = match.group(2)

        translated_status = BATTERY_STATUS_TRANSLATIONS.get(
            power_state, {}
        ).get(language, power_state)

        if language == "hi":
            return (
                f"आपकी बैटरी {percentage}% है। "
                f"स्थिति: {translated_status}।"
            )

        if language == "te":
            return (
                f"మీ బ్యాటరీ {percentage}% ఉంది. "
                f"స్థితి: {translated_status}."
            )

        return (
            f"Your battery is at {percentage}%. "
            f"Status: {translated_status}."
        )

    if result.startswith("INFO: No battery detected."):
        if language == "hi":
            return "आपके कंप्यूटर में बैटरी नहीं मिली।"

        if language == "te":
            return "మీ కంప్యూటర్‌లో బ్యాటరీ గుర్తించబడలేదు."

        return "No battery was detected on your computer."

    if result.startswith(
        "INFO: Battery percentage is unavailable."
    ):
        if language == "hi":
            return "बैटरी प्रतिशत की जानकारी उपलब्ध नहीं है।"

        if language == "te":
            return "బ్యాటరీ శాతం సమాచారం అందుబాటులో లేదు."

        return "Battery percentage information is unavailable."

    if language == "hi":
        return "माफ़ कीजिए, बैटरी की जानकारी नहीं मिल पाई।"

    if language == "te":
        return "క్షమించండి, బ్యాటరీ వివరాలు తెలుసుకోలేకపోయాను."

    return "Sorry, I couldn't read the battery information."


# ==========================================
# RAM MONITORING REPLIES
# ==========================================

def ram_reply(result, language):
    pattern = (
        r"SUCCESS: RAM usage is (\d+(?:\.\d+)?)%\. "
        r"Used: (\d+(?:\.\d+)?) GB\. "
        r"Available: (\d+(?:\.\d+)?) GB\. "
        r"Total: (\d+(?:\.\d+)?) GB\."
    )

    match = re.fullmatch(pattern, result)

    if match:
        usage = match.group(1)
        used = match.group(2)
        available = match.group(3)
        total = match.group(4)

        if language == "hi":
            return (
                f"आपकी रैम का उपयोग {usage} प्रतिशत है। "
                f"इस्तेमाल हो रही रैम {used} जीबी है। "
                f"उपलब्ध रैम {available} जीबी है। "
                f"कुल रैम {total} जीबी है।"
            )

        if language == "te":
            return (
                f"మీ ర్యామ్ వినియోగం {usage} శాతం. "
                f"ఉపయోగిస్తున్నది {used} జీబీ. "
                f"అందుబాటులో ఉన్నది {available} జీబీ. "
                f"మొత్తం ర్యామ్ {total} జీబీ."
            )

        return (
            f"Your RAM usage is {usage}%. "
            f"Used: {used} GB. "
            f"Available: {available} GB. "
            f"Total: {total} GB."
        )

    if language == "hi":
        return "माफ़ कीजिए, रैम की जानकारी नहीं मिल पाई।"

    if language == "te":
        return "క్షమించండి, ర్యామ్ వివరాలు తెలుసుకోలేకపోయాను."

    return "Sorry, I couldn't read the RAM information."


# ==========================================
# STEP 23: CPU MONITORING REPLIES
# ==========================================

def cpu_reply(result, language):
    """
    Example:
    SUCCESS: CPU usage is 23.5%.
    """

    pattern = (
        r"SUCCESS: CPU usage is "
        r"(\d+(?:\.\d+)?)%\."
    )

    match = re.fullmatch(pattern, result)

    if match:
        usage = match.group(1)

        if language == "hi":
            return (
                f"आपके सीपीयू का उपयोग "
                f"{usage} प्रतिशत है।"
            )

        if language == "te":
            return (
                f"మీ సీపీయూ వినియోగం "
                f"{usage} శాతం ఉంది."
            )

        return f"Your CPU usage is {usage}%."

    if language == "hi":
        return "माफ़ कीजिए, सीपीयू की जानकारी नहीं मिल पाई।"

    if language == "te":
        return "క్షమించండి, సీపీయూ వివరాలు తెలుసుకోలేకపోయాను."

    return "Sorry, I couldn't read the CPU information."


# ==========================================
# MAIN AI AND AUTOMATION API
# ==========================================

@app.route("/api/ask", methods=["POST"])
def ask_ai():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify(
            error="Please send a valid JSON object."
        ), 400

    question = (
        data.get("message")
        or data.get("prompt")
        or data.get("question")
        or data.get("command")
    )

    if not isinstance(question, str) or not question.strip():
        return jsonify(
            error="Please enter a question for KYRA."
        ), 400

    question = question.strip()

    if len(question) > 4000:
        return jsonify(
            error="Your question is too long."
        ), 400

    language = data.get("language", "en")

    if language not in LANGUAGE_INSTRUCTIONS:
        language = "en"

    actual_command = extract_user_command(question)

    # -----------------------------------
    # STEP 23: CPU MONITORING
    # -----------------------------------

    try:
        cpu_result = handle_cpu_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "CPU monitoring failed."
        )

        return jsonify(
            error="Could not read CPU information."
        ), 500

    if cpu_result is not None:
        answer = cpu_reply(
            cpu_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = cpu_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="cpu_status",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # RAM MONITORING
    # -----------------------------------

    try:
        ram_result = handle_ram_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "RAM monitoring failed."
        )

        return jsonify(
            error="Could not read RAM information."
        ), 500

    if ram_result is not None:
        answer = ram_reply(
            ram_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = ram_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="ram_status",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # BATTERY MONITORING
    # -----------------------------------

    try:
        battery_result = handle_battery_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Battery monitoring failed."
        )

        return jsonify(
            error="Could not read battery information."
        ), 500

    if battery_result is not None:
        answer = battery_reply(
            battery_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = (
            battery_result.startswith("SUCCESS:")
            or battery_result.startswith("INFO:")
        )

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="battery_status",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # DATE AND TIME
    # -----------------------------------

    try:
        datetime_result = handle_datetime_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Date and time automation failed."
        )

        return jsonify(
            error="Could not read date or time."
        ), 500

    if datetime_result is not None:
        answer = datetime_reply(
            datetime_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success",
            action="date_time",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # FOLDER AUTOMATION
    # -----------------------------------

    try:
        folder_result = handle_folder_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Folder automation failed."
        )

        return jsonify(
            error="Folder automation encountered an error."
        ), 500

    if folder_result is not None:
        answer = folder_reply(
            folder_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = folder_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="open_folder",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # SYSTEM INFORMATION
    # -----------------------------------

    try:
        system_result = handle_system_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "System information lookup failed."
        )

        return jsonify(
            error="Could not read system information."
        ), 500

    if system_result is not None:
        answer = system_reply(
            system_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success",
            action="system_information",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # GOOGLE SEARCH
    # -----------------------------------

    try:
        search_result = handle_search_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Google search automation failed."
        )

        return jsonify(
            error="Google search automation encountered an error."
        ), 500

    if search_result is not None:
        answer = search_reply(
            search_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = search_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="google_search",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # WEBSITE AUTOMATION
    # -----------------------------------

    try:
        website_result = handle_website_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Website automation failed."
        )

        return jsonify(
            error="Website automation failed."
        ), 500

    if website_result is not None:
        answer = website_reply(
            website_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = website_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="open_website",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # WINDOWS APPLICATION AUTOMATION
    # -----------------------------------

    try:
        automation_result = handle_automation_command(
            actual_command
        )

    except Exception:
        app.logger.exception(
            "Windows automation failed."
        )

        return jsonify(
            error="Windows automation failed."
        ), 500

    if automation_result is not None:
        answer = automation_reply(
            automation_result,
            language,
        )

        remember_exchange(
            actual_command,
            answer,
        )

        succeeded = automation_result.startswith("SUCCESS:")

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success" if succeeded else "error",
            action="open_application",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

    # -----------------------------------
    # OLLAMA AI CHAT
    # -----------------------------------

    system_instruction = (
        "You are KYRA, a friendly and intelligent personal "
        "AI voice assistant. Answer clearly and accurately. "
        "Keep answers concise and easy to understand. "
        + LANGUAGE_INSTRUCTIONS[language]
        + " Use previous conversation messages when relevant. "
        "Never invent memories that were not provided."
    )

    with history_lock:
        previous_messages = list(conversation_history)

    messages = [
        {
            "role": "system",
            "content": system_instruction,
        }
    ]

    messages.extend(previous_messages)

    messages.append({
        "role": "user",
        "content": question,
    })

    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.7,
            "num_predict": 180,
        },
    }

    try:
        result = ollama_request(
            "/api/chat",
            payload=payload,
            timeout=120,
        )

        answer = (
            result.get("message", {})
            .get("content", "")
            .strip()
        )

        if not answer:
            return jsonify(
                error="The AI model returned an empty answer."
            ), 502

        remember_exchange(
            question,
            answer,
        )

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success",
            reply=answer,
            response=answer,
            answer=answer,
        )

    except error.HTTPError as exc:
        return jsonify(
            error=f"Ollama returned HTTP {exc.code}."
        ), 502

    except (
        error.URLError,
        TimeoutError,
        OSError,
    ):
        return jsonify(
            error=(
                "Cannot contact Ollama. "
                "Check that Ollama is running."
            )
        ), 503

    except (ValueError, KeyError, AttributeError):
        return jsonify(
            error="Ollama returned an invalid response."
        ), 502


# ==========================================
# TELUGU TEXT TO SPEECH
# ==========================================

async def generate_telugu_audio(text):
    communicate = edge_tts.Communicate(
        text=text,
        voice=TELUGU_VOICE,
    )

    audio_chunks = []

    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    return b"".join(audio_chunks)


@app.route("/api/tts", methods=["GET", "POST"])
def text_to_speech():
    if request.method == "POST":
        data = request.get_json(silent=True)

        if not isinstance(data, dict):
            return jsonify(
                error="Please send a valid JSON object."
            ), 400
    else:
        data = request.args

    text = data.get("text", "")
    language = data.get("language", "te")

    if not isinstance(text, str) or not text.strip():
        return jsonify(
            error="Please provide text to speak."
        ), 400

    text = text.strip()

    if len(text) > 2000:
        return jsonify(
            error="Speech text is too long."
        ), 400

    if language != "te":
        return jsonify(
            error="This endpoint currently supports Telugu only."
        ), 400

    try:
        audio = asyncio.run(
            generate_telugu_audio(text)
        )

        if not audio:
            return jsonify(
                error="No Telugu audio was generated."
            ), 502

        return Response(
            audio,
            mimetype="audio/mpeg",
            headers={
                "Cache-Control": "no-store",
            },
        )

    except Exception:
        app.logger.exception(
            "Telugu speech generation failed."
        )

        return jsonify(
            error=(
                "Telugu speech could not be generated. "
                "Check your internet connection."
            )
        ), 502


# ==========================================
# START KYRA AI
# ==========================================

if __name__ == "__main__":
    print("=" * 45)
    print("KYRA AI - PHASE 6")
    print("WINDOWS APPLICATION AUTOMATION ENABLED")
    print("WEBSITE AUTOMATION ENABLED")
    print("GOOGLE SEARCH AUTOMATION ENABLED")
    print("SYSTEM INFORMATION ENABLED")
    print("DOWNLOADS AND DOCUMENTS ENABLED")
    print("DATE AND TIME AUTOMATION ENABLED")
    print("BATTERY MONITORING ENABLED")
    print("RAM MONITORING ENABLED")
    print("CPU MONITORING ENABLED")
    print("ENGLISH / HINDI / TELUGU")
    print("SHORT-TERM CONVERSATION MEMORY")
    print("TELUGU EDGE TTS ENABLED")
    print("MODEL:", AI_MODEL)
    print("DASHBOARD: http://127.0.0.1:5050")
    print("=" * 45)

    app.run(
        host="127.0.0.1",
        port=5050,
        debug=True,
    )
