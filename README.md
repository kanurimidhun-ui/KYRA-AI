# KYRA AI — Phase 3: Voice Engine

JARVIS-inspired voice command dashboard, built with VS Code, Flask, HTML/CSS and JavaScript.
This is a working, rule-based command assistant, not a trained AI model or a fully autonomous agent.

## What's new

- **Push-to-talk** (click START MIC; one command at a time) via the browser's Web Speech API.
- **Spoken replies** using browser speech synthesis. Toggle replies on/off, change voice, test speakers.
- Wake-prefix support: "Hey KYRA, ..." or "KYRA, ...".
- Phase 2 command console, live clock, animated HUD, and real backend status retained.
- Handles microphone denial, missing microphones, recognition not supported, offline speech services.
- No new Python dependencies or paid APIs needed; `Flask>=3.0,<4.0` remains the only Python dependency.

## Safe Windows / VS Code installation

1. Stop the Phase 2 server with Ctrl+C.
2. In the VS Code terminal opened at your existing `KYRA-AI` folder, back up Phase 2:

```powershell
Compress-Archive -Path app.py,templates,static,requirements.txt,README.md -DestinationPath KYRA-Phase2-Backup.zip -Force
```

3. Extract the contents of `KYRA-Phase3-VSCode.zip` **into the existing `KYRA-AI` folder**, overwriting the four source files plus README. Do **not** create a nested `KYRA-AI` directory. This zip has root-level app.py, templates, static, etc.

```powershell
Expand-Archive -LiteralPath "$HOME\Downloads\KYRA-Phase3-VSCode.zip" -DestinationPath "." -Force
```

4. Install requirements (already installed if Phase 2 works):

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

5. Open http://127.0.0.1:5050 and do a hard refresh (Ctrl+Shift+R).
6. Click **TEST VOICE** to verify speaker output, then click **START MIC**, allow microphone permission in the browser, and say **"Hey KYRA, what time is it?"**.
7. Try `status`, `date`, `hello`, `introduce yourself`, `help`, `clear` from mic or typed console.

## Troubleshooting

- Use a recent **Google Chrome or Microsoft Edge** browser on `http://127.0.0.1:5050`. Speech recognition is not supported equally in all browsers.
- If mic permission is denied, click the site permission icon next to the address bar, allow microphone and refresh.
- Check Windows **Settings > Privacy & security > Microphone** and enable mic access for desktop apps.
- If KYRA can speak but not hear you, check for `Speech recognition needs network access` and try an internet connection. On some browsers, speech audio is sent to the browser provider's speech service for recognition; this is **not a fully offline / private speech recognition solution**.
- If KYRA hears you but is silent, check speaker volume, click TEST VOICE, select a different voice in the dropdown, and turn REPLIES ON.
- If new controls are not visible, refresh with Ctrl+Shift+R and confirm files were copied to correct folder.
- If mic unavailable, typed commands still work. Voice synthesis can work even where mic recognition is unsupported.

## Scope and safety

This phase DOES NOT open applications, run shell commands or access laptop files. Phase 4 will introduce safe, explicitly allowlisted actions. No background listening or keyword activation: recognition starts only when you press START MIC and stops after one command.
