import asyncio
import json
import hmac
import os
import secrets
import time
from kyra_threat_analysis import analyze_findings
from pathlib import Path
from urllib.parse import urlsplit
import re
from datetime import datetime
from threading import Lock
from urllib import error, request as url_request
import edge_tts
from flask import Flask, Response, jsonify, render_template, request, session
from kyra_safety import assess_action
from kyra_audit import log_security_event
from kyra_memory import ConversationMemory
from kyra_long_memory import initialize_memory, remember, recall, forget
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
# Browser sessions are signed, HttpOnly and same-site restricted.
app.secret_key = secrets.token_bytes(32)
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_SECURE=False,  # local HTTP only; never expose externally
)
def load_voice_api_token():
    """Create a random secret under the current Windows user's profile."""
    local_data = os.environ.get("LOCALAPPDATA")
    base = Path(local_data) if local_data else Path.home() / "AppData" / "Local"
    token_dir = base / "KYRA"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_path = token_dir / "api_token"
    if not token_path.is_file():
        # Only create when absent. Never print or send this token to the UI.
        token_path.write_text(secrets.token_urlsafe(32), encoding="utf-8")
    token = token_path.read_text(encoding="utf-8").strip()
    if len(token) < 32:
        raise RuntimeError("KYRA API token is invalid or too short.")
    return token
VOICE_API_TOKEN = load_voice_api_token()
# Browser calls must originate from this local dashboard.
DASHBOARD_ORIGINS = {
    "http://127.0.0.1:5050",
    "http://localhost:5050",
}
# Commands are deliberately narrow: no arbitrary paths, URLs or programs.
ACTION_ALLOWLIST = (
    re.compile(
        r"^(?:(?:please|can you|could you)\s+)?(?:open|launch)\s+"
        r"(?:calculator|camera|settings|personalization|this pc|TradingView|notepad|paint|youtube|google|google images|google drive|spotify|netflix|instagram|linked\.in|facebook|poki|github|downloads|documents)"
        r"(?:\s+(?:app|application|website|folder))?$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:(?:please|can you|could you)\s+)?"
        r"(?:search|google)(?:\s+(?:for|on google))?\s+.{1,180}$",
        re.IGNORECASE,
    ),
    # Laptop locking is allowed only after explicit confirmation.
    re.compile(
        r"^(?:please\s+)?lock\s+(?:my\s+)?(?:pc|computer|laptop)$",
        re.IGNORECASE,
    ),
)
# Only this exact laptop-lock intent is eligible for approval.
# Other uses of "lock" remain blocked by DANGEROUS_WORDS.
LOCK_PC_PATTERN = re.compile(
    r"^(?:please\s+)?lock\s+(?:my\s+)?(?:pc|computer|laptop)$",
    re.IGNORECASE,
)
# DAY 10: Screenshot voice command
SCREENSHOT_PATTERN = re.compile(
    r"^(?:please\s+)?(?:take|capture)\s+(?:a\s+)?screenshot$",
    re.IGNORECASE,
)
# This is a conservative action classifier, not a natural-language guarantee.
ACTION_START = re.compile(
    r"^(?:(?:please|can you|could you)\s+)?"
    r"(?:open|launch|search|google|play|start|delete|remove|erase|"
    r"format|shutdown|restart|reboot|lock|execute|install|uninstall|"
    r"run|create|write|edit|copy|move|rename|send|upload|download|"
    r"kill|stop|disable|enable)\b",
    re.IGNORECASE,
)
DANGEROUS_WORDS = re.compile(
    r"\b(?:delete|remove|erase|format|shutdown|restart|reboot|"
    r"power\s*off|lock|execute|install|uninstall)\b",
    re.IGNORECASE,
)
def classify_api_request(command):
    """Return 'action', 'blocked', or 'read_or_chat'."""
    if not isinstance(command, str) or not command.strip():
        return "blocked"

    normalized = " ".join(command.split())

    # Day 10: Screenshot command.
    if SCREENSHOT_PATTERN.fullmatch(normalized):
        return "action"

    # Keep the exact laptop-lock safety rules.
    if LOCK_PC_PATTERN.fullmatch(normalized):
        if assess_action(normalized) == "confirm" and any(
            pattern.fullmatch(normalized)
            for pattern in ACTION_ALLOWLIST
        ):
            return "action"
        return "blocked"

    # Dangerous commands must remain blocked.
    if DANGEROUS_WORDS.search(normalized):
        return "blocked"

    if ACTION_START.search(normalized):
        if assess_action(normalized) != "confirm":
            return "blocked"

        # Preserve existing allowed commands.
        if any(
            pattern.fullmatch(normalized)
            for pattern in ACTION_ALLOWLIST
        ):
            return "action"

        # Day 11: Allow registered Windows applications only.
        app_match = re.fullmatch(
            r"^(?:(?:please|can you|could you)\s+)?"
            r"(?:open|launch)\s+(.+?)(?:\s+(?:app|application))?$",
            normalized,
            re.IGNORECASE,
        )

        if app_match:
            app_name = app_match.group(1).strip()

            try:
                from automation import find_installed_app

                if find_installed_app(app_name) is not None:
                    return "action"
            except Exception:
                app.logger.exception(
                    "Installed-app classification failed."
                )
                return "blocked"

        return "blocked"

    return "read_or_chat"
def authorized_action_request():
    """Voice secret OR local same-origin dashboard session."""
    supplied_token = request.headers.get("X-KYRA-Token", "")
    if supplied_token and hmac.compare_digest(supplied_token, VOICE_API_TOKEN):
        return True
    if session.get("kyra_dashboard") is not True:
        return False
    origin = request.headers.get("Origin", "").rstrip("/")
    if origin:
        return origin in DASHBOARD_ORIGINS and origin == request.host_url.rstrip("/")
    referer = request.headers.get("Referer", "")
    if referer:
        parsed = urlsplit(referer)
        return f"{parsed.scheme}://{parsed.netloc}" == request.host_url.rstrip("/")
    return request.headers.get("Sec-Fetch-Site") == "same-origin"
# KYRA_CONFIRMATION_V42: server-side one-time dashboard action approval.
# The standalone voice client uses its own spoken confirmation and API token.
ACTION_CONFIRM_SECONDS = 60
ACTION_PENDING = {}
ACTION_PENDING_LOCK = Lock()
def confirm_dashboard_action(data, command):
    """Return a response until a one-time, same-session approval is verified."""
    client_id = session.get("kyra_action_client")
    if not isinstance(client_id, str) or not client_id:
        client_id = secrets.token_urlsafe(24)
        session["kyra_action_client"] = client_id
    now = time.monotonic()
    choice = data.get("confirmation")
    token = data.get("confirmation_token")
    with ACTION_PENDING_LOCK:
        # Remove expired tickets to avoid unbounded growth.
        for old_token, record in list(ACTION_PENDING.items()):
            if record["expires"] <= now:
                del ACTION_PENDING[old_token]
        if "confirmation" not in data and "confirmation_token" not in data:
            # Only one outstanding action per dashboard session.
            for old_token, record in list(ACTION_PENDING.items()):
                if record["client_id"] == client_id:
                    del ACTION_PENDING[old_token]
            new_token = secrets.token_urlsafe(32)
            ACTION_PENDING[new_token] = {
                "client_id": client_id,
                "command": command,
                "expires": now + ACTION_CONFIRM_SECONDS,
            }
            return jsonify(
                assistant="KYRA",
                status="confirmation_required",
                automation=False,
                confirmation_token=new_token,
                reply="Confirm or cancel this action before KYRA proceeds.",
            )
        # The ticket is consumed on the first approval/cancellation attempt.
        record = ACTION_PENDING.pop(token, None) if isinstance(token, str) else None
    if (
        type(choice) is not bool
        or record is None
        or record["expires"] <= now
        or not hmac.compare_digest(record["client_id"], client_id)
        or record["command"] != command
    ):
        return blocked_response("Invalid, expired, or already used action confirmation.", 403)
    decision = "approved" if choice else "cancelled"
    try:
        # Fail closed if an action approval cannot be audited.
        log_security_event(command, decision)
    except (OSError, ValueError, TypeError):
        app.logger.exception("Could not record dashboard action decision.")
        return blocked_response("Could not record action confirmation. Action stopped.", 503)
    if not choice:
        return jsonify(
            assistant="KYRA",
            status="cancelled",
            automation=False,
            reply=("చర్య రద్దు చేయబడింది. ఏ చర్య జరగలేదు."
                   if data.get("language") == "te"
                   else "Action cancelled. Nothing was executed."),
        )
    # Approved exactly once; continue to the existing automation handlers.
    return None
def blocked_response(message, code=403):
    return jsonify(
        assistant="KYRA", status="blocked", automation=False,
        reply=message, response=message, answer=message, error=message,
    ), code
@app.before_request
def require_local_request():
    # Defence in depth; server also binds to 127.0.0.1 only.
    if request.remote_addr not in {"127.0.0.1", "::1"}:
        return blocked_response("KYRA is only available locally.")
    if request.host not in {"127.0.0.1:5050", "localhost:5050"}:
        return blocked_response("Invalid local host.")
OLLAMA_URL = "http://127.0.0.1:11434"
AI_MODEL = "llama3.2:3b"
conversation_history = []
history_lock = Lock()
MAX_HISTORY = 20

# KYRA Day 5: load the last five saved conversations on server startup.
# Existing automation/security handlers are unchanged.
# KYRA Day 6: initialize long-term SQLite storage without altering existing JSON memory.
initialize_memory()
print("KYRA long-term SQLite memory initialized.")

permanent_memory = ConversationMemory(max_turns=5)
for saved_turn in permanent_memory.history:
    conversation_history.extend([
        {"role": "user", "content": saved_turn["user"]},
        {"role": "assistant", "content": saved_turn["assistant"]},
    ])
LANGUAGE_INSTRUCTIONS = {
    "en": "Respond in English only.",
    "te": "Respond in Telugu only, using Telugu script.",
}
TELUGU_VOICE = "te-IN-ShrutiNeural"
# ==========================================
# HOME PAGE AND STATUS
# ==========================================
@app.route("/")
def home():
    session["kyra_dashboard"] = True
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

        # Persist each completed exchange for the next server restart.
        # ConversationMemory saves to kyra_memory.json atomically.
        permanent_memory.add_turn(question, answer)
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
# ==========================================
# WINDOWS APPLICATION REPLIES
# ==========================================
def automation_reply(result, language):
    if not isinstance(result, str):
        result = str(result or "")

    if result.startswith("SUCCESS:"):
        prefixes = (
            "SUCCESS: Launch requested for ",
            "SUCCESS: Opened ",
        )

        app_name = result

        for prefix in prefixes:
            if result.startswith(prefix):
                app_name = result[len(prefix):].rstrip(".").strip()
                break

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
            app_name.casefold(), {}
        ).get(language, app_name)

        if language == "hi":
            return f"{translated_name} खोलने का अनुरोध भेज दिया है।"

        if language == "te":
            return f"{translated_name} తెరవడానికి అభ్యర్థన పంపించాను."

        return f"Launch request sent for {translated_name}."

    if language == "hi":
        return "माफ़ कीजिए, एप्लिकेशन खोलने का अनुरोध पूरा नहीं हो सका।"

    if language == "te":
        return "క్షమించండి, అప్లికేషన్ తెరవడానికి చేసిన అభ్యర్థన విజయవంతం కాలేదు."

    return "Sorry, I couldn't start the application."
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
# DAY 6: EXPLICIT LONG-TERM MEMORY COMMANDS
# ==========================================
def clear_recent_conversation_about(key):
    """Remove matching topic turns from JSON memory and active Ollama context.

    This does not erase unrelated chats, audit logs, or user-created backups.
    """
    topic = key.casefold()
    with history_lock:
        permanent_memory.history = [
            turn for turn in permanent_memory.history
            if topic not in str(turn.get("user", "")).casefold()
            and topic not in str(turn.get("assistant", "")).casefold()
        ]
        permanent_memory.save()

        # Both user and assistant messages form a completed exchange.
        # If either mentions the forgotten topic, discard the entire pair.
        kept_messages = []
        for start in range(0, len(conversation_history), 2):
            exchange = conversation_history[start:start + 2]
            if not any(
                topic in str(message.get("content", "")).casefold()
                for message in exchange
            ):
                kept_messages.extend(exchange)
        conversation_history[:] = kept_messages


def parse_long_memory_command(command):
    """Recognize explicit personal-memory requests, not arbitrary chat."""
    clean = re.sub(r"^(?:hey\s+)?kyra\s*[,!:]?\s*", "", command.strip(), flags=re.I)
    clean = re.sub(r"\s+", " ", clean).strip()

    save_match = re.fullmatch(
        r"(?:please\s+)?remember\s+(?:that\s+)?(my\s+.{1,120}?)\s+(?:is|=)\s+(.{1,500}?)\s*[.!]?",
        clean,
        flags=re.I,
    )
    if save_match:
        key = save_match.group(1).strip().lower()
        value = save_match.group(2).strip().rstrip(".! ")
        if key and value:
            return "save", key, value

    forget_match = re.fullmatch(
        r"(?:please\s+)?forget\s+(?:that\s+)?(my\s+.{1,120}?)\s*[.!]?",
        clean,
        flags=re.I,
    )
    if forget_match:
        key = forget_match.group(1).strip().rstrip(".! ").lower()
        if key:
            return "forget", key, None

    recall_match = re.fullmatch(
        r"(?:what\s+is|what's|tell\s+me|do\s+you\s+remember)\s+(my\s+.{1,120}?)\s*\??",
        clean,
        flags=re.I,
    )
    if not recall_match:
        recall_match = re.fullmatch(
            r"what\s+do\s+you\s+remember\s+about\s+(my\s+.{1,120}?)\s*[?]?",
            clean,
            flags=re.I,
        )
    if recall_match:
        return "recall", recall_match.group(1).strip().lower(), None
    return None


# ==========================================
# MAIN AI AND AUTOMATION API
# ==========================================

def normalize_jarvis_command(command):
    """Understand polite commands without bypassing security."""
    if not isinstance(command, str):
        return command

    command = command.strip()

    polite_patterns = [
        r"^(?:hey\s+)?kyra\s*[,\-:]?\s+",
        r"^(?:could|can|would)\s+you\s+(?:please\s+)?",
        r"^please\s+",
        r"^kindly\s+",
    ]

    for _ in range(4):
        previous = command

        for pattern in polite_patterns:
            command = re.sub(
                pattern,
                "",
                command,
                flags=re.IGNORECASE
            ).strip()

        if command == previous:
            break

    # Remove question punctuation only for explicit
    # application-opening requests.
    if re.match(
        r"^(?:open|launch|start)\s+\S",
        command,
        flags=re.IGNORECASE
    ):
        command = command.rstrip(" ?!")

    return command


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

    # ==========================================
    # DAY 9: SECURE MULTI-STEP PLANNING
    # ==========================================
    from day9_planner import create_plan

    multi_plan = create_plan(
    extract_user_command(question),
    normalize_jarvis_command,
    classify_api_request,
)

    if multi_plan["status"] == "ready_for_confirmation":
        # A plan must never bypass local authorization.
        if not authorized_action_request():
            return blocked_response(
                "Multi-step planning requires an authorized KYRA client.",
                403,
            )

        plan_lines = [
            f"Step {step['number']}: {step['command']}"
            for step in multi_plan["steps"]
        ]

        answer = (
    "I have prepared your JARVIS action plan:\n"
    + "\n".join(plan_lines)
    + "\n\nFor safety, send each step separately "
      "and approve its confirmation before proceeding "
      "to the next step."
)

        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="plan_ready",
            action="multi_step_plan",
            automation=False,
            steps=multi_plan["steps"],
            reply=answer,
            response=answer,
            answer=answer,
        )

    actual_command = normalize_jarvis_command(
        extract_user_command(question)
    )
    # Independent server-side safety: runs before any automation handler.
    security_decision = classify_api_request(actual_command)
    if security_decision == "blocked":
        app.logger.warning("Blocked an unsafe or unsupported action request.")
        return blocked_response(
            "For safety, KYRA cannot execute this command."
        )
    if security_decision == "action" and not authorized_action_request():
        app.logger.warning("Denied an action without local authorization.")
        return blocked_response(
            "This action needs an authorized local KYRA client."
        )
    # Browser actions require a server-verified, single-use confirmation.
    # A separately authenticated voice client has already asked verbally.
    supplied_token = request.headers.get("X-KYRA-Token", "")
    trusted_voice_client = bool(supplied_token) and hmac.compare_digest(
        supplied_token, VOICE_API_TOKEN
    )

# Approved non-destructive actions run without repeated prompts.
# Locking the PC still requires explicit confirmation.
    instant_action = (
        bool(SCREENSHOT_PATTERN.fullmatch(actual_command))
        or (
            security_decision == "action"
            and not bool(LOCK_PC_PATTERN.fullmatch(actual_command))
        )
    )

    if (
        security_decision == "action"
        and not trusted_voice_client
        and not instant_action
    ):
        confirmation_response = confirm_dashboard_action(
            data, actual_command
        )
        if confirmation_response is not None:
            return confirmation_response

    # DAY 6: SQLITE LONG-TERM PERSONAL MEMORY
    # -----------------------------------
    if security_decision == "read_or_chat":
        memory_command = parse_long_memory_command(actual_command)
        if memory_command is not None:
            # Personal memory is only available to the authorized local
            # dashboard or the authenticated voice assistant.
            if not authorized_action_request():
                return blocked_response(
                    "Personal memory requires your authorized KYRA dashboard or voice client.",
                    403,
                )
            intent, key, value = memory_command
            try:
                if intent == "save":
                    saved = remember(key, value)
                    if not saved:
                        return jsonify(error="Could not save that memory."), 400
                    answer = (
                        f"గుర్తుంచుకున్నాను: {key} = {value}."
                        if language == "te"
                        else f"I'll remember: {key} is {value}."
                    )
                elif intent == "forget":
                    deleted = forget(key)
                    clear_recent_conversation_about(key)
                    if language == "te":
                        answer = (
                            f"{key} గురించి సేవ్ చేసిన జ్ఞాపకాన్ని తొలగించాను."
                            if deleted else
                            f"{key} గురించి long-term memory లేదు. ఇటీవల chat history లో ఉన్న సంబంధిత messages తొలగించాను."
                        )
                    else:
                        answer = (
                            f"I've forgotten {key} and cleared matching recent chat turns."
                            if deleted else
                            f"No long-term fact was saved for {key}. I cleared matching recent chat turns."
                        )
                else:
                    saved_value = recall(key)
                    if saved_value is None:
                        answer = (
                            f"{key} గురించి ఇంకా సమాచారం సేవ్ చేయలేదు."
                            if language == "te"
                            else f"I don't have a saved memory for {key} yet."
                        )
                    else:
                        answer = (
                            f"{key}: {saved_value}."
                            if language == "te"
                            else f"{key.capitalize()} is {saved_value}."
                        )
            except Exception:
                app.logger.exception("Long-term memory operation failed.")
                return jsonify(error="Long-term memory is temporarily unavailable."), 500

            # A forget request must not itself be re-saved to chat history.
            if intent != "forget":
                remember_exchange(actual_command, answer)
            return jsonify(
                assistant="KYRA",
                model=AI_MODEL,
                status="success",
                reply=answer,
                response=answer,
                answer=answer,
            )

    # -----------------------------------
    # WINDOWS LOCK PC (AFTER CONFIRMATION)
    # -----------------------------------
        # DAY 10: Capture and save screenshot
    if security_decision == "action" and SCREENSHOT_PATTERN.fullmatch(actual_command):
        try:
            import pyautogui

            screenshot_folder = Path.home() / "Pictures" / "KYRA Screenshots"
            screenshot_folder.mkdir(parents=True, exist_ok=True)

            filename = "KYRA_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f") + ".png"
            screenshot_path = screenshot_folder / filename

            pyautogui.screenshot().save(str(screenshot_path))

            answer = f"Screenshot captured and saved successfully to {screenshot_path}"

            return jsonify(
                assistant="KYRA",
                model=AI_MODEL,
                status="success",
                action="take_screenshot",
                automation=True,
                reply=answer,
                response=answer,
                answer=answer,
            )

        except Exception:
            app.logger.exception("Screenshot capture failed.")
            return jsonify(
                assistant="KYRA",
                status="error",
                reply="Sorry, I could not capture the screenshot.",
            ), 500
    if security_decision == "action" and LOCK_PC_PATTERN.fullmatch(actual_command):
        try:
            if os.name != "nt":
                raise OSError("Lock PC is supported only on Windows.")

            # Lock the current Windows workstation, not shutdown or restart.
            import ctypes

            if ctypes.windll.user32.LockWorkStation() == 0:
                raise OSError("Windows did not accept the lock request.")
        except (OSError, AttributeError) as exc:
            app.logger.exception("Windows workstation lock failed.")
            return jsonify(
                assistant="KYRA",
                model=AI_MODEL,
                status="error",
                action="lock_pc",
                automation=False,
                reply=f"Could not lock the PC: {exc}",
            ), 500

        answer = (
            "మీ ల్యాప్‌టాప్ లాక్ చేయబడుతోంది."
            if language == "te"
            else "Your laptop is locking now."
        )
        return jsonify(
            assistant="KYRA",
            model=AI_MODEL,
            status="success",
            action="lock_pc",
            automation=True,
            reply=answer,
            response=answer,
            answer=answer,
        )

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
        folder_result = (
            handle_folder_command(actual_command)
            if security_decision == "action" else None
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
        search_result = (
            handle_search_command(actual_command)
            if security_decision == "action" else None
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
        website_result = (
            handle_website_command(actual_command)
            if security_decision == "action" else None
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
        automation_result = (
            handle_automation_command(actual_command)
            if security_decision == "action" else None
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
# ==========================================
# KYRA v4.1 - SECURITY AUDIT STATISTICS
# ==========================================
from kyra_audit_stats import get_audit_stats
@app.route("/api/security-stats", methods=["GET"])
def security_stats():
    """Read local audit decision totals without exposing command text."""
    if request.remote_addr not in ("127.0.0.1", "::1"):
        return jsonify({"error": "Access denied"}), 403
    return jsonify(get_audit_stats())
# ==========================================
# KYRA v4.2 - SECURITY EVENT HISTORY API
# ==========================================
from kyra_audit_history import get_recent_events
@app.route("/api/security-history", methods=["GET"])
def security_history():
    """Return recent audit events to an authorized local KYRA client."""
    if not authorized_action_request():
        return blocked_response("Unauthorized security history request.", 403)
    events = get_recent_events(10)
    response = jsonify({
        "events": events,
        "total_returned": len(events),
    })
    response.headers["Cache-Control"] = "no-store"
    return response

# KYRA Threat Analysis API
@app.route("/api/threat-analysis", methods=["POST"])
def threat_analysis_api():
    """Analyze supplied findings through KYRA's existing risk engine."""

    if not authorized_action_request():
        return blocked_response(
            "Unauthorized threat analysis request.", 403
        )

    if request.content_length and request.content_length > 100_000:
        return jsonify({"error": "Request body is too large."}), 413

    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({"error": "Send a JSON object."}), 400

    findings = data.get("findings", [])
    use_ai = data.get("use_ai", True)

    if not isinstance(findings, list):
        return jsonify({"error": "'findings' must be a list."}), 400

    if len(findings) > 50:
        return jsonify({"error": "Maximum 50 findings per request."}), 400

    if not all(isinstance(item, dict) for item in findings):
        return jsonify({"error": "Every finding must be a JSON object."}), 400

    if not isinstance(use_ai, bool):
        return jsonify({"error": "'use_ai' must be true or false."}), 400

    try:
        report = analyze_findings(findings, use_ai=use_ai)
    except Exception:
        app.logger.exception("Threat analysis request failed.")
        return jsonify({"error": "Threat analysis failed."}), 500

    response = jsonify(report)
    response.headers["Cache-Control"] = "no-store"
    return response

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
    print("ENGLISH / TELUGU")
    print("SHORT-TERM CONVERSATION MEMORY")
    print("TELUGU EDGE TTS ENABLED")
    print("V4.0 LOCAL API ACTION SECURITY ENABLED")
    print("MODEL:", AI_MODEL)
    print("DASHBOARD: http://127.0.0.1:5050")
    print("=" * 45)
    app.run(
    host=os.environ.get("HOST", "127.0.0.1"),
    port=int(os.environ.get("PORT", "5050")),
    debug=False,
)
