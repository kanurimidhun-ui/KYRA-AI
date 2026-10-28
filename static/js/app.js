
"use strict";

// KYRA AI v4.2 — JARVIS Day 9
// English, Hindi and Telugu Voice Assistant
// Secure sequential execution for Notepad and Calculator.

const $ = id => document.getElementById(id);

const statusDot = $("statusDot");
const statusText = $("statusText");
const commandForm = $("commandForm");
const commandInput = $("commandInput");
const consoleLog = $("consoleLog");
const micButton = $("micButton");
const micButtonText = $("micButtonText");
const voiceToggle = $("voiceToggle");
const voiceTest = $("voiceTest");
const voiceSelect = $("voiceSelect");
const voiceStatus = $("voiceStatus");
const voiceModuleState = $("voiceModuleState");
const replyLanguage = $("replyLanguage");
const voiceAvailability = $("voiceAvailability");
const aiModuleState = $("aiModuleState");

const SpeechRecognitionClass =
  window.SpeechRecognition || window.webkitSpeechRecognition;

const speaker =
  "speechSynthesis" in window ? window.speechSynthesis : null;

const LANGUAGES = {
  en: {
    label: "English",
    locale: "en-IN",
    instruction: "English only"
  },
  hi: {
    label: "हिंदी (Hindi)",
    locale: "hi-IN",
    instruction: "Hindi only, written in Devanagari script"
  },
  te: {
    label: "తెలుగు (Telugu)",
    locale: "te-IN",
    instruction: "Telugu only, written in Telugu script"
  }
};

const STORAGE_LANGUAGE = "kyra.replyLanguage.v2";
const STORAGE_VOICES = "kyra.voicePreferences.v2";

let language = "en";
let recognition = null;
let listening = false;
let recognizedText = "";
let recognitionFailed = false;
let repliesEnabled = true;
let availableVoices = [];
let currentVoiceKey = "auto";
let activeUtterance = null;
let activeTeluguAudio = null;
let activeTeluguAudioUrl = null;
let activeTeluguRequest = null;
let speechSequence = 0;
let isBusy = false;
let aiReady = false;
let conversation = [];

// =======================================
// SAVE USER PREFERENCES
// =======================================

function loadPreference(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch {
    return fallback;
  }
}

function savePreference(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch {
    // Browser storage may be unavailable.
  }
}

function savedVoiceMap() {
  try {
    return JSON.parse(
      loadPreference(STORAGE_VOICES, "{}")
    ) || {};
  } catch {
    return {};
  }
}

// =======================================
// DASHBOARD MESSAGES
// =======================================

function addMessage(sender, text, type = "kyra") {
  if (!consoleLog) return;

  const card = document.createElement("div");
  card.className = `message message--${type}`;

  const name = document.createElement("span");
  name.textContent = sender;

  const body = document.createElement("p");
  body.textContent = String(text);

  card.append(name, body);
  consoleLog.appendChild(card);
  consoleLog.scrollTop = consoleLog.scrollHeight;
}

function setVoiceStatus(message, isError = false) {
  if (!voiceStatus) return;

  voiceStatus.textContent = message;
  voiceStatus.classList.toggle("is-error", isError);
}

// =======================================
// LIVE CLOCK
// =======================================

function refreshClock() {
  const now = new Date();

  if ($("liveClock")) {
    $("liveClock").textContent = now.toLocaleTimeString();
  }

  if ($("liveDate")) {
    $("liveDate").textContent = now.toLocaleDateString(
      undefined,
      {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric"
      }
    );
  }
}

// =======================================
// FLASK BACKEND STATUS
// =======================================

async function checkBackend() {
  try {
    const response = await fetch("/api/status", {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error("Backend not reachable");
    }

    const data = await response.json();

    if (
      data.assistant !== "KYRA" ||
      data.status !== "online"
    ) {
      throw new Error("Unexpected backend response");
    }

    if (statusText) {
      statusText.textContent = "BACKEND ONLINE";
    }

    if (statusDot) {
      statusDot.className = "status-dot";
    }

    return true;
  } catch {
    if (statusText) {
      statusText.textContent = "BACKEND OFFLINE";
    }

    if (statusDot) {
      statusDot.className =
        "status-dot status-dot--offline";
    }

    return false;
  }
}

// =======================================
// OLLAMA AI STATUS
// =======================================

async function checkAI() {
  try {
    const response = await fetch("/api/ai-status", {
      cache: "no-store"
    });

    if (!response.ok) {
      throw new Error("AI unavailable");
    }

    const data = await response.json();
    aiReady = Boolean(data.ready);

    if (aiModuleState) {
      aiModuleState.textContent = aiReady
        ? "READY"
        : "OPTIONAL";

      aiModuleState.classList.toggle(
        "module-state--later",
        !aiReady
      );

      aiModuleState.title = data.message || "";
    }
  } catch {
    aiReady = false;

    if (aiModuleState) {
      aiModuleState.textContent = "OPTIONAL";
    }
  }
}

// =======================================
// LANGUAGE SELECTION
// =======================================

function configureLanguageSelector() {
  if (
    replyLanguage &&
    replyLanguage.tagName === "SELECT"
  ) {
    replyLanguage.replaceChildren(
      new Option("English", "en"),
      new Option("हिंदी (Hindi)", "hi"),
      new Option("తెలుగు (Telugu)", "te")
    );
  }

  const stored = loadPreference(
    STORAGE_LANGUAGE,
    "en"
  );

  setLanguage(
    Object.hasOwn(LANGUAGES, stored)
      ? stored
      : "en",
    false
  );

  if (replyLanguage) {
    replyLanguage.addEventListener("change", () => {
      setLanguage(replyLanguage.value, true);
    });
  }
}

function setLanguage(next, announce = false) {
  if (!Object.hasOwn(LANGUAGES, next)) {
    next = "en";
  }

  language = next;

  if (replyLanguage) {
    replyLanguage.value = language;
  }

  savePreference(STORAGE_LANGUAGE, language);

  if (recognition) {
    recognition.lang = LANGUAGES[language].locale;
  }

  stopSpeech();
  updateVoiceChoices();

  if (announce) {
    kyraReply(localText("languageChanged"));
  }
}

// =======================================
// VOICE SELECTION
// =======================================

function voiceKey(voice) {
  return `${voice.voiceURI}|${voice.lang}|${voice.name}`;
}

function matchingVoices() {
  return availableVoices.filter(voice => {
    const voiceLanguage = voice.lang
      .toLowerCase()
      .split(/[-_]/)[0];

    return voiceLanguage === language;
  });
}

function preferredVoice() {
  const candidates = matchingVoices();

  const feminine =
    /female|zira|jenny|aria|hazel|susan|samantha|heera|swara|kalpana/i;

  return (
    candidates.find(voice =>
      feminine.test(voice.name)
    ) ||
    candidates[0] ||
    null
  );
}

function chooseVoice() {
  const voices = matchingVoices();

  if (currentVoiceKey !== "auto") {
    return (
      voices.find(voice =>
        voiceKey(voice) === currentVoiceKey
      ) ||
      preferredVoice()
    );
  }

  return preferredVoice();
}

function updateVoiceChoices() {
  if (!voiceSelect) return;

  availableVoices = speaker
    ? speaker.getVoices()
    : [];

  const saved = savedVoiceMap();
  const desired = saved[language] || "auto";

  voiceSelect.replaceChildren(
    new Option(
      `Auto: ${LANGUAGES[language].label} voice`,
      "auto"
    )
  );

  // Telugu voice is available through Flask Edge TTS.
  if (language === "te") {
    voiceSelect.add(
      new Option(
        "Microsoft Telugu - Edge TTS (online)",
        "edge-tts-te"
      )
    );
  }

  for (const voice of matchingVoices()) {
    voiceSelect.add(
      new Option(
        `${voice.name} (${voice.lang})`,
        voiceKey(voice)
      )
    );
  }

  const exists = [...voiceSelect.options].some(
    option => option.value === desired
  );

  currentVoiceKey = exists ? desired : "auto";
  voiceSelect.value = currentVoiceKey;

  const count = matchingVoices().length;

  if (voiceAvailability) {
    if (language === "te") {
      voiceAvailability.textContent =
        "Telugu voice available via Microsoft Edge TTS (internet required).";
    } else {
      voiceAvailability.textContent = count
        ? `${count} ${LANGUAGES[language].label} voice(s) available.`
        : `No ${LANGUAGES[language].label} speech voice installed. Text replies still work.`;
    }

    voiceAvailability.classList.toggle(
      "is-error",
      language !== "te" && count === 0
    );
  }
}

// =======================================
// STOP SPEECH
// =======================================

function stopSpeech() {
  speechSequence += 1;

  if (speaker) {
    speaker.cancel();
  }

  if (activeTeluguRequest) {
    activeTeluguRequest.abort();
    activeTeluguRequest = null;
  }

  if (activeTeluguAudio) {
    activeTeluguAudio.pause();
    activeTeluguAudio.removeAttribute("src");
    activeTeluguAudio.load();
    activeTeluguAudio = null;
  }

  if (activeTeluguAudioUrl) {
    URL.revokeObjectURL(activeTeluguAudioUrl);
    activeTeluguAudioUrl = null;
  }

  activeUtterance = null;
  document.body.classList.remove("is-speaking");
}

// =======================================
// TELUGU EDGE TTS
// =======================================

async function speakTeluguWithEdgeTTS(text, sequence) {
  const controller = new AbortController();

  activeTeluguRequest = controller;

  setVoiceStatus(
    "Generating Telugu voice via Edge TTS..."
  );

  try {
    const response = await fetch("/api/tts", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        text: String(text).slice(0, 2000),
        language: "te"
      }),
      signal: controller.signal
    });

    if (!response.ok) {
      const details = await response
        .json()
        .catch(() => ({}));

      throw new Error(
        details.error ||
        `Telugu voice HTTP ${response.status}`
      );
    }

    const blob = await response.blob();

    if (
      sequence !== speechSequence ||
      controller.signal.aborted
    ) {
      return;
    }

    if (!blob.size) {
      throw new Error("The Telugu audio was empty.");
    }

    activeTeluguAudioUrl =
      URL.createObjectURL(blob);

    const audio = new Audio(activeTeluguAudioUrl);

    activeTeluguAudio = audio;

    audio.onended = () => {
      if (sequence !== speechSequence) return;

      stopSpeech();

      setVoiceStatus(
        "Telugu voice finished. MIC READY."
      );
    };

    audio.onerror = () => {
      if (sequence !== speechSequence) return;

      stopSpeech();

      setVoiceStatus(
        "Could not play Telugu audio.",
        true
      );
    };

    await audio.play();

    if (sequence === speechSequence) {
      document.body.classList.add("is-speaking");

      setVoiceStatus(
        "Speaking Telugu via Edge TTS..."
      );
    }
  } catch (err) {
    if (
      sequence !== speechSequence ||
      controller.signal.aborted
    ) {
      return;
    }

    console.error(
      "KYRA Telugu TTS error:",
      err
    );

    setVoiceStatus(
      "Telugu voice failed: " +
      err.message +
      ". Check internet and browser audio permission.",
      true
    );
  } finally {
    if (activeTeluguRequest === controller) {
      activeTeluguRequest = null;
    }
  }
}

// =======================================
// MAIN TEXT-TO-SPEECH ENGINE
// =======================================

function say(text, force = false) {
  if (!repliesEnabled && !force) {
    return;
  }

  stopSpeech();

  const sequence = speechSequence;

  if (
    language === "te" &&
    (
      currentVoiceKey === "auto" ||
      currentVoiceKey === "edge-tts-te"
    )
  ) {
    void speakTeluguWithEdgeTTS(
      text,
      sequence
    );
    return;
  }

  if (!speaker) {
    setVoiceStatus(
      "Browser speech is unavailable. Answer shown as text.",
      true
    );
    return;
  }

  const selectedVoice = chooseVoice();

  if (!selectedVoice) {
    setVoiceStatus(
      `No ${LANGUAGES[language].label} browser voice installed. Answer shown as text.`,
      true
    );
    return;
  }

  const utterance = new SpeechSynthesisUtterance(
    String(text)
  );

  utterance.voice = selectedVoice;
  utterance.lang = LANGUAGES[language].locale;
  utterance.rate = 0.94;
  utterance.pitch = 1.04;

  utterance.onstart = () => {
    document.body.classList.add("is-speaking");
  };

  utterance.onend = () => {
    activeUtterance = null;
    document.body.classList.remove(
      "is-speaking"
    );
  };

  utterance.onerror = event => {
    activeUtterance = null;

    document.body.classList.remove(
      "is-speaking"
    );

    if (
      !["canceled", "interrupted"].includes(
        event.error
      )
    ) {
      setVoiceStatus(
        "Speech output failed. Try another voice.",
        true
      );
    }
  };

  activeUtterance = utterance;
  speaker.speak(utterance);
}

function kyraReply(text, speak = true) {
  addMessage("KYRA", text);

  if (speak) {
    say(text);
  }
}

// =======================================
// MULTILINGUAL RESPONSES
// =======================================

const MESSAGES = {
  languageChanged: [
    "English mode enabled.",
    "हिंदी मोड चालू है।",
    "తెలుగు మోడ్ ప్రారంభమైంది."
  ],
  cleared: [
    "Console cleared. Awaiting your next command.",
    "कंसोल साफ़ हो गया।",
    "కన్సోల్ క్లియర్ అయింది."
  ],
  help: [
    "Ask me about time, date, status, jokes, motivation, calculations, or anything using local AI. Say 'speak Hindi' or 'speak Telugu' to change languages.",
    "समय, तारीख, सिस्टम स्थिति, चुटकुले, गणित या कोई भी सवाल पूछें।",
    "సమయం, తేదీ, సిస్టమ్ స్థితి, జోకులు, లెక్కలు లేదా ఏ ప్రశ్నైనా అడగండి."
  ],
  hello: [
    "Hello! I'm KYRA. How can I help you?",
    "नमस्ते! मैं कायरा हूँ। आपकी क्या मदद करूँ?",
    "నమస్కారం! నేను కైరా. మీకు ఎలా సహాయం చేయగలను?"
  ],
  intro: [
    "I'm KYRA, your JARVIS-inspired voice assistant, built with Python and JavaScript.",
    "मैं कायरा हूँ, पायथन और जावास्क्रिप्ट से बना आपका वॉइस असिस्टेंट।",
    "నేను కైరా, పైథాన్ మరియు జావास्क्रिप్ట్‌తో రూపొందించిన మీ వాయిస్ అసిస్టెంట్‌ని."
  ],
  fine: [
    "I'm doing great! My systems are ready.",
    "मैं ठीक हूँ! मेरे सिस्टम तैयार हैं।",
    "నేను బాగున్నాను! నా సిస్టమ్‌లు సిద్ధంగా ఉన్నాయి."
  ],
  joke: [
    "Why do programmers prefer dark mode? Because light attracts bugs!",
    "प्रोग्रामर डार्क मोड क्यों पसंद करते हैं? क्योंकि रोशनी में बग आते हैं!",
    "ప్రోగ్రామర్లు డార్క్ మోడ్ ఎందుకు ఇష్టపడతారు? వెలుతురు బగ్‌లను ఆకర్షిస్తుంది కాబట్టి!"
  ],
  motivation: [
    "Every expert was once a beginner. Keep learning and building!",
    "हर विशेषज्ञ कभी शुरुआती था। सीखते रहिए और आगे बढ़िए!",
    "ప్రతి నిపుణుడూ ఒకప్పుడు ప్రారంభకుడే. నేర్చుకుంటూ ముందుకు సాగండి!"
  ],
  thanks: [
    "You're welcome! Ready for the next mission.",
    "आपका स्वागत है! अगले काम के लिए तैयार हूँ।",
    "పర్వాలేదు! తదుపరి పనికి సిద్ధంగా ఉన్నాను."
  ],
  stopped: [
    "Speech stopped.",
    "बोलना बंद कर दिया।",
    "మాట్లాడటం ఆపాను."
  ],
  thinking: [
    "Let me think...",
    "मैं सोच रही हूँ...",
    "నేను ఆలోచిస్తున్నాను..."
  ],
  offline: [
    "My local AI is not connected. Please check Ollama.",
    "लोकल एआई कनेक्ट नहीं है। ओलामा जाँचें।",
    "లోకల్ ఏఐ కనెక్ట్ కాలేదు. ఒల్లామాను తనిఖీ చేయండి."
  ],
  error: [
    "Something went wrong. Please try again.",
    "कुछ गड़बड़ हुई। फिर कोशिश करें।",
    "ఏదో సమస్య వచ్చింది. మళ్లీ ప్రయత్నించండి."
  ],
  online: [
    "All systems operational. KYRA is online.",
    "सभी सिस्टम ठीक हैं। कायरा ऑनलाइन है।",
    "అన్ని సిస్టమ్‌లు సరిగ్గా పనిచేస్తున్నాయి. కైరా ఆన్‌లైన్‌లో ఉంది."
  ],
  backendOffline: [
    "The Flask backend is offline.",
    "फ्लास्क बैकएंड ऑफ़लाइन है।",
    "ఫ్లాస్క్ బ్యాకెండ్ ఆఫ్‌లైన్‌లో ఉంది."
  ],
  test: [
    "Hello! I'm KYRA. My English voice is ready.",
    "नमस्ते! मैं कायरा हूँ। मेरी हिंदी आवाज़ तैयार है।",
    "నమస్కారం! నేను కైరా. నా తెలుగు వాయిస్ సిద్ధంగా ఉంది."
  ]
};

function localText(key) {
  const index = {
    en: 0,
    hi: 1,
    te: 2
  }[language];

  return (
    MESSAGES[key]?.[index] ||
    MESSAGES.error[index]
  );
}

function localizedNumberAnswer(value) {
  if (language === "hi") {
    return `उत्तर ${value} है।`;
  }

  if (language === "te") {
    return `సమాధానం ${value}.`;
  }

  return `The answer is ${value}.`;
}

// =======================================
// COMMAND PROCESSING
// =======================================

function normalizeCommand(command) {
  return String(command)
    .trim()
    .replace(
      /^(?:(?:hey|hi|hello|ok|okay)\s+)?(?:kyra|kira|keira|ciara|cara)\s*[,.:!?-]?\s*/i,
      ""
    )
    .toLowerCase()
    .replace(/[?.!,]+$/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

function matchesAny(text, patterns) {
  return patterns.some(
    pattern => pattern.test(text)
  );
}

function smallMath(input) {
  const match = input.match(
    /(?:calculate|what(?:'s| is)|solve|compute)\s+(-?\d+(?:\.\d+)?)\s*(plus|minus|times|multiplied by|divided by|\+|-|\*|\/|x)\s*(-?\d+(?:\.\d+)?)/i
  );

  if (!match) return null;

  const a = Number(match[1]);
  const b = Number(match[3]);
  const operator = match[2].toLowerCase();

  if (["plus", "+"].includes(operator)) {
    return a + b;
  }

  if (["minus", "-"].includes(operator)) {
    return a - b;
  }

  if (
    ["times", "multiplied by", "*", "x"].includes(operator)
  ) {
    return a * b;
  }

  if (b === 0) {
    if (language === "hi") return "अपरिभाषित";
    if (language === "te") return "నిర్వచించబడలేదు";
    return "undefined";
  }

  return a / b;
}

// =======================================
// LOCAL OLLAMA AI + DAY 9 JARVIS EXECUTION
// =======================================

async function askLocalAI(command) {
  if (!aiReady) {
    kyraReply(localText("offline"));
    return;
  }

  kyraReply(localText("thinking"), false);

  const languageRule =
    `IMPORTANT LANGUAGE REQUIREMENT: Respond in ${LANGUAGES[language].instruction}. ` +
    "Use no Italian. Reply in the selected language regardless of the question's language. " +
    `Keep the answer clear and concise.\nUSER QUESTION: ${command}`;

  const payload = {
    question: languageRule,
    language: language,
    history: conversation
  };

  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(payload)
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(
        data.error || "AI unavailable"
      );
    }

    // =======================================
    // DAY 9: SECURE SEQUENTIAL EXECUTION
    // =======================================
    // Only Notepad and Calculator are allowed
    // in this first version.
    //
    // Each step gets its own server-issued,
    // single-use confirmation token.
    //
    // The browser cannot bypass Flask's
    // existing action authorization.

    if (data.status === "plan_ready") {
      const steps = data.steps;

      const allowedAppCommand = /^open .+$/i;

      if (
        !Array.isArray(steps) ||
        steps.length < 2 ||
        steps.length > 3 ||
        !steps.every(step =>
          step &&
          typeof step.command === "string" &&
          allowedAppCommand.test(
            step.command.trim()
          ) &&
          step.requires_confirmation === true
        )
      ) {
        kyraReply(
          "KYRA prepared a plan, but automatic execution is currently limited to opening Notepad and Calculator. No actions were executed."
        );
        return;
      }

      kyraReply(
        "KYRA has prepared the plan. Each step will ask for separate approval.",
        false
      );

      const completed = [];

      for (
        let index = 0;
        index < steps.length;
        index++
      ) {
        const stepCommand =
          steps[index].command.trim();

        const stepPayload = {
          question: stepCommand,
          language: language,
          history: conversation
        };

        // Request a confirmation token for
        // this exact command from Flask.

        const stepResponse = await fetch(
          "/api/ask",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(stepPayload)
          }
        );

        const stepData =
          await stepResponse.json();

        if (
          !stepResponse.ok ||
          stepData.status !==
            "confirmation_required" ||
          typeof stepData.confirmation_token !==
            "string" ||
          !stepData.confirmation_token
        ) {
          kyraReply(
            `Plan stopped at Step ${index + 1}: confirmation could not be requested. No further steps were executed.`
          );
          return;
        }

        const approved = window.confirm(
          `KYRA JARVIS — Step ${index + 1} of ${steps.length}\n\n` +
          `${stepCommand}\n\n` +
          "OK = Approve this step; Cancel = Stop the plan"
        );

        // Submit approval OR cancellation
        // so the server consumes and audits
        // the one-time confirmation token.

        const confirmResponse = await fetch(
          "/api/ask",
          {
            method: "POST",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify({
              ...stepPayload,
              confirmation_token:
                stepData.confirmation_token,
              confirmation: approved
            })
          }
        );

        const result =
          await confirmResponse.json();

        // Stop if the user cancelled.
        if (!approved) {
          if (
            confirmResponse.ok &&
            result.status === "cancelled"
          ) {
            kyraReply(
              `Plan cancelled at Step ${index + 1}. Remaining steps were not executed.`
            );
          } else {
            kyraReply(
              `Plan stopped at Step ${index + 1}. Cancellation could not be confirmed by the server.`
            );
          }
          return;
        }

        // Stop if Flask did not report a
        // successful application launch.
        if (
          !confirmResponse.ok ||
          result.status !== "success" ||
          result.automation !== true ||
          result.action !== "open_application"
        ) {
          kyraReply(
            `Plan stopped at Step ${index + 1}: ` +
            (
              result.error ||
              result.reply ||
              "The action did not succeed."
            )
          );
          return;
        }

        completed.push(stepCommand);
      }

      // All steps succeeded.
      const finalAnswer =
        "JARVIS plan completed successfully!\n" +
        completed.map(
          (item, index) =>
            `Step ${index + 1}: ${item} — Success`
        ).join("\n");

      conversation.push(
        {
          role: "user",
          content: command
        },
        {
          role: "assistant",
          content: finalAnswer
        }
      );

      conversation =
        conversation.slice(-6);

      kyraReply(finalAnswer);
      return;
    }

    // =======================================
    // EXISTING SINGLE-ACTION CONFIRMATION
    // =======================================

    let result = data;

    if (
      data.status === "confirmation_required"
    ) {
      if (
        typeof data.confirmation_token !==
        "string"
      ) {
        throw new Error(
          "Missing action confirmation token"
        );
      }

      const promptText =
        language === "te"
          ? "KYRA ఈ చర్యను అమలు చేయాలా?\n" +
            command +
            "\nOK = నిర్ధారించు; Cancel = రద్దు"
          : "Allow KYRA to perform this action?\n" +
            command +
            "\nOK = Confirm; Cancel = Cancel";

      const approved =
        window.confirm(promptText);

      const confirmationResponse =
        await fetch("/api/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json"
          },
          body: JSON.stringify({
            ...payload,
            confirmation_token:
              data.confirmation_token,
            confirmation: approved
          })
        });

      result =
        await confirmationResponse.json();

      if (!confirmationResponse.ok) {
        throw new Error(
          result.error ||
          "Action confirmation failed"
        );
      }
    }

    const answer =
      result.reply ||
      result.answer ||
      result.response;

    if (
      typeof answer !== "string" ||
      !answer.trim()
    ) {
      throw new Error("Empty AI answer");
    }

    conversation.push(
      {
        role: "user",
        content: command
      },
      {
        role: "assistant",
        content: answer
      }
    );

    conversation =
      conversation.slice(-6);

    kyraReply(answer);

  } catch (error) {
    console.error(
      "KYRA AI error:",
      error
    );

    kyraReply(localText("error"));
  }
}

// =======================================
// MAIN KYRA COMMAND ENGINE
// =======================================

async function executeCommand(rawCommand) {
  const command =
    String(rawCommand || "").trim();

  if (!command || isBusy) return;

  const normalized =
    normalizeCommand(command);

  if (
    matchesAny(normalized, [
      /^clear(?: (?:the )?(?:console|screen|terminal))?$/,
      /^clean console$/
    ])
  ) {
    if (consoleLog) {
      consoleLog.replaceChildren();
    }

    kyraReply(localText("cleared"));
    return;
  }

  addMessage("YOU", command, "user");

  isBusy = true;

  try {
    // ENGLISH MODE
    if (
      matchesAny(normalized, [
        /\bspeak english\b/,
        /\benglish (?:mode|please)\b/,
        /अंग्रेजी में बोलो/
      ])
    ) {
      setLanguage("en", true);

    // HINDI MODE
    } else if (
      matchesAny(normalized, [
        /\bspeak hindi\b/,
        /\bhindi (?:mode|please)\b/,
        /हिंदी में बोलो/,
        /हिन्दी में बोलो/
      ])
    ) {
      setLanguage("hi", true);

    // TELUGU MODE
    } else if (
      matchesAny(normalized, [
        /\bspeak telugu\b/,
        /\btelugu (?:mode|please)\b/,
        /తెలుగులో మాట్లాడు/,
        /తెలుగులో మాట్లాడండి/
      ])
    ) {
      setLanguage("te", true);

    // HELP
    } else if (
      matchesAny(normalized, [
        /^(help|commands|show commands)$/,
        /what (?:can|do) you do/,
        /list .*commands/
      ])
    ) {
      kyraReply(localText("help"));

    // STATUS
    } else if (
      matchesAny(normalized, [
        /\b(system|backend|core)\s+(?:status|check)\b/,
        /\bcheck\s+(?:the\s+)?(?:system\s+)?status\b/,
        /^status$/,
        /are you (?:online|working|connected)/
      ])
    ) {
      const online = await checkBackend();

      kyraReply(
        localText(
          online
            ? "online"
            : "backendOffline"
        )
      );

    // TIME
    } else if (
      matchesAny(normalized, [
        /^time$/,
        /^clock$/,
        /what.*time/,
        /tell me the time/,
        /current time/
      ])
    ) {
      const value =
        new Date().toLocaleTimeString(
          LANGUAGES[language].locale
        );

      const message =
        language === "hi"
          ? `समय ${value} है।`
          : language === "te"
            ? `ఇప్పుడు సమయం ${value}.`
            : `The time is ${value}.`;

      kyraReply(message);

    // DATE
    } else if (
      matchesAny(normalized, [
        /^date$/,
        /what.*date/,
        /today.s date/,
        /tell me the date/,
        /what day is it/
      ])
    ) {
      const value =
        new Date().toLocaleDateString(
          LANGUAGES[language].locale,
          { dateStyle: "full" }
        );

      const message =
        language === "hi"
          ? `आज ${value} है।`
          : language === "te"
            ? `ఈ రోజు ${value}.`
            : `Today is ${value}.`;

      kyraReply(message);

    // GREETINGS
    } else if (
      matchesAny(normalized, [
        /^(hello|hi|hey|greetings|good morning|good evening|good afternoon)$/
      ])
    ) {
      kyraReply(localText("hello"));

    // INTRODUCTION
    } else if (
      matchesAny(normalized, [
        /who are you/,
        /introduce yourself/,
        /your name/,
        /tell me about yourself/
      ])
    ) {
      kyraReply(localText("intro"));

    // HOW ARE YOU
    } else if (
      matchesAny(normalized, [
        /how are you/,
        /how.s it going/,
        /are you okay/
      ])
    ) {
      kyraReply(localText("fine"));

    // JOKE
    } else if (
      matchesAny(normalized, [
        /tell (?:me )?a joke/,
        /make me laugh/,
        /say something funny/,
        /^joke$/
      ])
    ) {
      kyraReply(localText("joke"));

    // MOTIVATION
    } else if (
      matchesAny(normalized, [
        /motivate me/,
        /inspire me/,
        /give me motivation/
      ])
    ) {
      kyraReply(localText("motivation"));

    // THANK YOU
    } else if (
      matchesAny(normalized, [
        /thank you/,
        /^thanks$/,
        /धन्यवाद/,
        /ధన్యవాదాలు/
      ])
    ) {
      kyraReply(localText("thanks"));

    // STOP SPEAKING
    } else if (
      matchesAny(normalized, [
        /stop speaking/,
        /be quiet/,
        /silence/,
        /stop talking/
      ])
    ) {
      stopSpeech();

      kyraReply(
        localText("stopped"),
        false
      );

    // CALCULATIONS
    } else if (
      smallMath(normalized) !== null
    ) {
      kyraReply(
        localizedNumberAnswer(
          smallMath(normalized)
        )
      );

    // AI QUESTIONS AND ACTIONS
    } else {
      await askLocalAI(command);
    }

  } catch (error) {
    console.error(
      "KYRA command error:",
      error
    );

    kyraReply(localText("error"));

  } finally {
    isBusy = false;
  }
}

// =======================================
// MICROPHONE STATUS
// =======================================

function setListening(active) {
  listening = active;

  if (micButton) {
    micButton.classList.toggle(
      "is-listening",
      active
    );

    micButton.setAttribute(
      "aria-pressed",
      String(active)
    );

    micButton.setAttribute(
      "aria-label",
      active
        ? "Stop microphone"
        : "Start microphone"
    );
  }

  document.body.classList.toggle(
    "is-listening",
    active
  );

  if (micButtonText) {
    micButtonText.textContent = active
      ? "STOP MIC"
      : "START MIC";
  }
}

function microphoneErrorMessage(error) {
  const messages = {
    "not-allowed":
      "Microphone permission denied.",
    "service-not-allowed":
      "Speech recognition is blocked.",
    "audio-capture":
      "No microphone detected.",
    "network":
      "Speech recognition needs network access.",
    "no-speech":
      "No speech detected. Try again.",
    "language-not-supported":
      `${LANGUAGES[language].label} recognition is not supported in this browser.`,
    "aborted":
      "Listening stopped."
  };

  return (
    messages[error] ||
    `Microphone error: ${error}.`
  );
}

// =======================================
// SPEECH RECOGNITION
// =======================================

function initializeRecognition() {
  if (!SpeechRecognitionClass) {
    if (micButton) {
      micButton.disabled = true;
    }

    if (voiceModuleState) {
      voiceModuleState.textContent =
        "LIMITED";
    }

    setVoiceStatus(
      "Speech recognition unavailable. Try Chrome or Edge.",
      true
    );

    return;
  }

  recognition =
    new SpeechRecognitionClass();

  recognition.lang =
    LANGUAGES[language].locale;

  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    setListening(true);

    setVoiceStatus(
      `LISTENING IN ${LANGUAGES[language].label.toUpperCase()}...`
    );
  };

  recognition.onresult = event => {
    const result = event.results[0];

    if (result && result[0]) {
      recognizedText =
        result[0].transcript.trim();

      setVoiceStatus(
        `Heard: ${recognizedText}`
      );
    }
  };

  recognition.onerror = event => {
    recognitionFailed = true;

    setVoiceStatus(
      microphoneErrorMessage(
        event.error
      ),
      event.error !== "aborted"
    );
  };

  recognition.onend = () => {
    setListening(false);

    const words = recognizedText;
    recognizedText = "";

    if (words) {
      setVoiceStatus(
        "MIC READY. Tap to speak again."
      );

      void executeCommand(words);

    } else if (!recognitionFailed) {
      setVoiceStatus(
        "No speech recognized. Try again."
      );
    }
  };

  setVoiceStatus(
    "MIC READY. Select English, Hindi, or Telugu and speak."
  );
}

// =======================================
// MICROPHONE BUTTON
// =======================================

if (micButton) {
  micButton.addEventListener(
    "click",
    () => {
      if (!recognition) return;

      if (listening) {
        recognition.stop();
        return;
      }

      recognizedText = "";
      recognitionFailed = false;

      stopSpeech();

      try {
        recognition.start();

        setVoiceStatus(
          "Microphone starting..."
        );
      } catch {
        setVoiceStatus(
          "Microphone busy. Try again.",
          true
        );
      }
    }
  );
}

// =======================================
// VOICE ON / OFF
// =======================================

if (voiceToggle) {
  voiceToggle.addEventListener(
    "click",
    () => {
      repliesEnabled =
        !repliesEnabled;

      voiceToggle.setAttribute(
        "aria-pressed",
        String(repliesEnabled)
      );

      voiceToggle.textContent =
        repliesEnabled
          ? "🔊 REPLIES ON"
          : "🔇 REPLIES OFF";

      if (!repliesEnabled) {
        stopSpeech();
      }
    }
  );
}

// =======================================
// TEST VOICE BUTTON
// =======================================

if (voiceTest) {
  voiceTest.addEventListener(
    "click",
    () => {
      say(
        localText("test"),
        true
      );

      if (language !== "te") {
        const selectedVoice =
          chooseVoice();

        setVoiceStatus(
          selectedVoice
            ? `Selected voice: ${selectedVoice.name}`
            : `No ${LANGUAGES[language].label} speech voice installed.`,
          !selectedVoice
        );
      }
    }
  );
}

// =======================================
// VOICE DROPDOWN
// =======================================

if (voiceSelect) {
  voiceSelect.addEventListener(
    "change",
    () => {
      currentVoiceKey =
        voiceSelect.value;

      const preferences =
        savedVoiceMap();

      preferences[language] =
        currentVoiceKey;

      savePreference(
        STORAGE_VOICES,
        JSON.stringify(preferences)
      );

      if (
        language === "te" &&
        (
          currentVoiceKey === "auto" ||
          currentVoiceKey === "edge-tts-te"
        )
      ) {
        setVoiceStatus(
          "Telugu Edge TTS selected (internet required)."
        );
      } else {
        const selectedVoice =
          chooseVoice();

        setVoiceStatus(
          selectedVoice
            ? `Selected: ${selectedVoice.name}`
            : "No matching voice available.",
          !selectedVoice
        );
      }
    }
  );
}

// =======================================
// TEXT COMMAND FORM
// =======================================

if (commandForm) {
  commandForm.addEventListener(
    "submit",
    async event => {
      event.preventDefault();

      if (!commandInput) return;

      const command =
        commandInput.value;

      commandInput.value = "";

      await executeCommand(command);

      commandInput.focus();
    }
  );
}

// =======================================
// QUICK COMMAND BUTTONS
// =======================================

document
  .querySelectorAll("[data-command]")
  .forEach(button => {
    button.addEventListener(
      "click",
      () => {
        void executeCommand(
          button.dataset.command
        );
      }
    );
  });

// =======================================
// INITIALIZE KYRA
// =======================================

configureLanguageSelector();

updateVoiceChoices();

if (
  speaker &&
  typeof speaker.addEventListener ===
    "function"
) {
  speaker.addEventListener(
    "voiceschanged",
    updateVoiceChoices
  );
}

initializeRecognition();

refreshClock();

setInterval(refreshClock, 1000);

void checkBackend();
void checkAI();

console.log(
  "KYRA AI v4.2 JARVIS Day 9 loaded: English / Hindi / Telugu + secure sequential execution."
);
