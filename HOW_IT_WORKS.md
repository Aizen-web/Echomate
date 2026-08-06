# Calcifer — How It Works

> **Current UI note:** Calcifer now uses Voice, Chat, and System tabs rather than the former HUD. See the Calcifer UI redesign section at the end of this document for the current architecture.

## Calcifer UI redesign (current implementation)

- **Identity:** UI and transcript output use **Calcifer**. Internal backend names such as `JarvisUI` and `JarvisLive` remain for compatibility.
- **Views:** the default **Voice** tab contains the companion face, a three-line status strip, quick command input, file drop, mute, and fullscreen. **Chat** contains the full instant transcript and command input. **System** refreshes resource values only while selected.
- **Face engine:** `FaceAvatar` is an original procedural placeholder driven at 12 FPS (8 FPS with `ui_lite: true` in `config/api_keys.json`). It pauses when hidden, inactive, or minimized. `assets/face/manifest.json` reserves the original sprite-pack contract; missing artwork never blocks the UI.
- **States:** `INITIALISING`, `LISTENING`, `THINKING`, `PROCESSING`, `SPEAKING`, and `MUTED` control the pose. Speaking animates the mouth; muted, thinking, and errors have distinct treatment.
- **Emotion protocol:** replies begin with `[emotion: name]`. The UI strips the marker before appending text, falls back safely to `playful`, then updates face and glow together. Supported names are `happy`, `excited`, `playful`, `proud`, `curious`, `thinking`, `focused`, `calm`, `sad`, `angry`, `annoyed`, `surprised`, `sleepy`, and `error`.
- **Palette:** warm gold/orange for happy/playful, hot orange/pink for excited/surprised, violet/blue for thinking/focused, teal/indigo for calm/sad, and red for angry/error. Palette changes interpolate smoothly.
- **Voice:** both main and screen/camera Gemini Live sessions use the prebuilt **Leda** voice. Restart after a voice change.
- **Customization:** add emotions in `EMOTIONS` in `ui.py`, update prompt vocabulary, and add only original artwork metadata under `assets/face/`. No Eilik assets, firmware, or sounds are used.

This document explains the full architecture of this project: how voice input and output work, which AI models are used, how tools and memory fit together, and how you can customize the assistant’s voice.

---

## Table of Contents

1. [What This Project Is](#what-this-project-is)
2. [Voice & Audio — Quick Answers](#voice--audio--quick-answers)
3. [Voice Input (Speech Recognition)](#voice-input-speech-recognition)
4. [Voice Output (Text-to-Speech)](#voice-output-text-to-speech)
5. [Can You Change the Voice?](#can-you-change-the-voice)
6. [AI Models Used in This Project](#ai-models-used-in-this-project)
7. [High-Level Architecture](#high-level-architecture)
8. [Startup Flow](#startup-flow)
9. [Real-Time Conversation Loop](#real-time-conversation-loop)
10. [Tool System (Actions)](#tool-system-actions)
11. [Autonomous Agent (Multi-Step Tasks)](#autonomous-agent-multi-step-tasks)
12. [Memory System](#memory-system)
13. [User Interface (`ui.py`)](#user-interface-uipy)
14. [Screen & Camera Vision](#screen--camera-vision)
15. [Configuration & API Keys](#configuration--api-keys)
16. [Project File Structure](#project-file-structure)
17. [Dependencies](#dependencies)
18. [Running the Project](#running-the-project)
19. [Customization Tips](#customization-tips)

---

## What This Project Is

**JARVIS (MARK XXXIX-OR)** is a cross-platform desktop AI assistant inspired by Tony Stark’s JARVIS. It runs locally on your machine and connects to cloud AI APIs for intelligence and voice.

You can:

- Talk to it in real time (microphone) or type commands in the UI
- Have it control your computer (apps, files, browser, settings, games)
- Upload files for analysis (PDF, images, code, audio, video, etc.)
- Ask it to see your screen or webcam
- Give it complex multi-step goals that it plans and executes
- Store long-term facts about you across sessions

The personality and behavior are defined in `core/prompt.txt` (currently configured as a sarcastic “Calcifer”-style gremlin, not a classic polite JARVIS).

---

## Voice & Audio — Quick Answers

| Question | Answer |
|----------|--------|
| **What voice / speech model is used?** | **Google Gemini Live** — model `models/gemini-2.5-flash-native-audio-preview-12-2025` |
| **What TTS library is used?** | **None locally.** Speech is generated **natively by Gemini** over the Live API. There is no pyttsx3, gTTS, ElevenLabs, or Edge TTS in this project. |
| **What handles listening (STT)?** | Also **Gemini Live** — your microphone audio is streamed to the API; transcription comes back as `input_audio_transcription`. |
| **What plays the audio?** | **`sounddevice`** — PCM audio chunks from Gemini are written to your speakers at 24 kHz. |
| **Current voice name** | **`Charon`** (Google prebuilt voice — described as “Informative”) |
| **Can you change the voice?** | **Yes** — change `voice_name` in `main.py` and `actions/screen_processor.py` (see below). |

---

## Voice Input (Speech Recognition)

Voice input is **not** handled by Whisper, Vosk, or Windows Speech Recognition. It works like this:

1. **`sounddevice`** opens a microphone stream at **16 kHz**, mono, 16-bit PCM.
2. Audio chunks (~1024 samples) are sent to Gemini via `session.send_realtime_input()` with MIME type `audio/pcm`.
3. Gemini’s Live session transcribes your speech and returns text in `response.server_content.input_transcription`.
4. That text is shown in the UI activity log as `You: ...`.

**Echo prevention:** While Jarvis is speaking (`_is_speaking == True`), the mic callback **does not** send audio — so the assistant doesn’t hear itself.

**Mute:** Press **F4** or click the microphone button. When muted, no audio is sent to Gemini.

**Text input:** You can also type in the right panel; text is injected into the same Live session via `send_client_content()`.

---

## Voice Output (Text-to-Speech)

There is **no separate TTS step**. Gemini’s native-audio model produces speech directly:

1. Live config sets `response_modalities=["AUDIO"]`.
2. Gemini streams raw PCM audio back in `response.data`.
3. **`sounddevice.RawOutputStream`** plays it at **24 kHz**, mono, 16-bit.
4. A parallel transcription (`output_audio_transcription`) is used for the UI log (`Jarvis: ...`) and memory extraction — not for generating speech.

So “TTS” in this project = **Gemini 2.5 Flash Native Audio** built into the Live API.

Relevant configuration in `main.py`:

```python
LIVE_MODEL = "models/gemini-2.5-flash-native-audio-preview-12-2025"

speech_config=types.SpeechConfig(
    voice_config=types.VoiceConfig(
        prebuilt_voice_config=types.PrebuiltVoiceConfig(
            voice_name="Charon"
        )
    )
),
```

The **screen/camera vision module** (`actions/screen_processor.py`) uses the **same model and voice** in its own Live session when describing what it sees.

---

## Can You Change the Voice?

**Yes.** Gemini Live exposes **30 prebuilt HD voices**. You pick one by changing the `voice_name` string.

### Where to edit

1. **`main.py`** — inside `JarvisLive._build_config()` (~line 572)
2. **`actions/screen_processor.py`** — inside `_LiveSession._main()` (~line 195)

Change `"Charon"` to any supported name in **both files** if you want the main assistant and the vision module to sound the same.

### Example voices (not exhaustive)

| Voice | Character (per Google docs) |
|-------|-----------------------------|
| **Charon** | Informative *(current default in this repo)* |
| **Puck** | Upbeat *(Gemini default if unspecified)* |
| **Kore** | Firm |
| **Fenrir** | Excitable |
| **Aoede** | Breezy |
| **Leda** | Youthful |
| **Orus** | Firm |
| **Zephyr** | Bright |
| **Sulafat** | Warm |

Full list: [Google Cloud — Configure language and voice](https://cloud.google.com/gemini-enterprise-agent-platform/models/live-api/configure-language-voice)

### Example change

```python
voice_name="Puck"   # or "Fenrir", "Kore", "Aoede", etc.
```

Restart the app after editing. There is **no UI setting** for voice today — code change only.

### What you *cannot* easily do

- Clone your own voice or use custom TTS (ElevenLabs, etc.) without rewriting the audio pipeline
- Adjust pitch/speed independently — those are tied to the prebuilt voice profile
- Use offline TTS — voice requires the Gemini API and internet

---

## AI Models Used in This Project

This project uses **two AI backends**:

### 1. Google Gemini (primary — voice + some tools)

| Use case | Model |
|----------|--------|
| Real-time voice conversation | `gemini-2.5-flash-native-audio-preview-12-2025` (Live API) |
| Screen/camera vision narration | Same Live model |
| Web search (primary path) | `gemini-2.5-flash` with Google Search tool |
| Tool orchestration | Live model decides which function to call |

### 2. OpenRouter (secondary — text tasks)

Many action modules call **`or_client.py`**, which tries free OpenRouter models in order (Llama, Gemma, Nemotron, Qwen, etc.) for:

- Memory extraction and relevance checks
- Flight search summarization
- Desktop/browser/file helper logic
- Agent planner steps
- Code helper / dev agent text generation

This split saves Gemini quota: **Live handles voice and tool routing**; **OpenRouter handles heavy text work**.

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        PyQt6 UI (ui.py)                          │
│  HUD · Activity log · File drop · Text input · Mute · Metrics   │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                     main.py — JarvisLive                         │
│  Gemini Live session · Mic in · Speaker out · Tool dispatcher   │
└─────┬───────────────────┬───────────────────┬───────────────────┘
      │                   │                   │
      ▼                   ▼                   ▼
 sounddevice         Google Gemini         actions/*.py
 (16k in / 24k out)   Live API              (17 tool modules)
                      + tool calls
                             │
                             ▼
                      or_client.py
                      (OpenRouter fallback)
                             │
                             ▼
                      agent/ (planner,
                      executor, task queue)
```

---

## Startup Flow

1. **`python main.py`** starts the PyQt6 window (`JarvisUI`).
2. First launch shows a setup overlay: **Gemini API key**, **OpenRouter API key**, and **OS** (Windows / macOS / Linux). Saved to `config/api_keys.json`.
3. A background thread runs `JarvisLive.run()`:
   - Loads system prompt from `core/prompt.txt`
   - Loads long-term memory from `memory/long_term.json`
   - Connects to Gemini Live with tools + voice config
4. Four async tasks start:
   - `_send_realtime` — mic → API
   - `_listen_audio` — captures microphone
   - `_receive_audio` — API responses, tool calls, transcriptions
   - `_play_audio` — API audio → speakers

If the connection drops, it waits 3 seconds and reconnects automatically.

---

## Real-Time Conversation Loop

```
User speaks → mic (16 kHz PCM)
    → Gemini Live (STT + reasoning)
    → optional tool_call (function)
    → tool executes locally
    → FunctionResponse sent back
    → Gemini generates AUDIO response (24 kHz PCM)
    → speakers + transcript in UI log
```

**States shown on the HUD:** `INITIALISING`, `LISTENING`, `THINKING`, `SPEAKING`, `MUTED`.

When a tool finishes, Jarvis usually speaks a short summary based on the tool result — unless the tool is `screen_process` (vision speaks directly) or `save_memory` (silent).

---

## Tool System (Actions)

The Live model has **20+ declared tools** in `main.py` (`TOOL_DECLARATIONS`). When Gemini calls a function, `_execute_tool()` runs the matching Python module.

| Tool name | Module | Purpose |
|-----------|--------|---------|
| `open_app` | `actions/open_app.py` | Launch applications |
| `web_search` | `actions/web_search.py` | Web search (Gemini + DuckDuckGo fallback) |
| `weather_report` | `actions/weather_report.py` | Weather by city |
| `send_message` | `actions/send_message.py` | WhatsApp / Telegram messaging |
| `reminder` | `actions/reminder.py` | Scheduled reminders (Task Scheduler) |
| `youtube_video` | `actions/youtube_video.py` | Play, summarize, trending |
| `screen_process` | `actions/screen_processor.py` | Screenshot or webcam + voice analysis |
| `computer_settings` | `actions/computer_settings.py` | Volume, brightness, WiFi, shutdown, etc. |
| `browser_control` | `actions/browser_control.py` | Playwright browser automation |
| `file_controller` | `actions/file_controller.py` | File/folder CRUD |
| `desktop_control` | `actions/desktop.py` | Wallpaper, organize desktop |
| `code_helper` | `actions/code_helper.py` | Write/edit/run code |
| `dev_agent` | `actions/dev_agent.py` | Multi-file project builder |
| `agent_task` | `agent/task_queue.py` | Complex multi-step goals |
| `computer_control` | `actions/computer_control.py` | Mouse, keyboard, screen clicks |
| `game_updater` | `actions/game_updater.py` | Steam / Epic install & update |
| `flight_finder` | `actions/flight_finder.py` | Google Flights search |
| `file_processor` | `actions/file_processor.py` | Uploaded file processing |
| `save_memory` | `memory/memory_manager.py` | Silent long-term memory write |
| `shutdown_jarvis` | `main.py` | Exit the application |

Tools run on thread pool or background threads so the Live session stays responsive.

---

## Autonomous Agent (Multi-Step Tasks)

When you ask for something that needs **many steps** (e.g. “research X and save to a file”), Gemini calls `agent_task`.

Flow:

1. **`agent/task_queue.py`** — queues goals with priority
2. **`agent/planner.py`** — OpenRouter breaks the goal into ≤5 steps
3. **`agent/executor.py`** — runs each step by calling action modules
4. **`agent/error_handler.py`** — handles failures

The agent reports progress via the `speak()` callback so Jarvis can voice updates.

---

## Memory System

**File:** `memory/long_term.json`

**Categories:** `identity`, `preferences`, `projects`, `relationships`, `wishes`, `notes`

**Two ways memory is updated:**

1. **Explicit:** Gemini calls `save_memory` during conversation (silent)
2. **Automatic:** After each turn, a background thread may extract facts via OpenRouter (`should_extract_memory` → `extract_memory`)

Memory is injected into the system prompt on each Live session connect so Jarvis “remembers” you across restarts (within a ~2200 character budget).

---

## User Interface (`ui.py`)

Built with **PyQt6**:

- **Center:** Animated HUD with face image (`face.png`), status, waveform
- **Left:** CPU, RAM, network, GPU, temperature monitors
- **Right:** Activity log (typewriter effect), file upload zone, text command box, mute button
- **Shortcuts:** `F4` mute, `F11` fullscreen

The UI thread stays separate from the asyncio Live loop; callbacks bridge them with `asyncio.run_coroutine_threadsafe`.

---

## Screen & Camera Vision

`screen_process` tool:

1. Captures **screenshot** (`mss`) or **webcam frame** (`opencv`)
2. Compresses to JPEG
3. Opens a **separate** Gemini Live session (no microphone)
4. Sends image + your question
5. Speaks the answer with the same **Charon** voice

Main Jarvis stays silent during this — the vision module talks directly.

---

## Configuration & API Keys

**File:** `config/api_keys.json`

```json
{
    "gemini_api_key": "AIza...",
    "openrouter_api_key": "sk-or-...",
    "os_system": "windows",
    "camera_index": 0
}
```

| Key | Required for |
|-----|----------------|
| `gemini_api_key` | Voice, Live tools, vision, Gemini search |
| `openrouter_api_key` | Memory, planner, many action backends |
| `os_system` | OS-specific behavior in actions |
| `camera_index` | Auto-detected on first camera use |

**System prompt:** edit `core/prompt.txt` to change personality and tool rules.

---

## Project File Structure

```
Jarvis/
├── main.py                 # Entry point, Live session, tool routing
├── ui.py                   # PyQt6 interface
├── or_client.py            # OpenRouter client + model pools
├── setup.py                # pip + playwright install helper
├── requirements.txt
├── readme.md               # Original project readme
├── HOW_IT_WORKS.md         # This file
├── core/
│   └── prompt.txt          # System personality & tool rules
├── config/
│   └── api_keys.json       # API keys (created on first run)
├── memory/
│   ├── memory_manager.py   # Load/save/extract memory
│   ├── config_manager.py   # Legacy config helpers
│   └── long_term.json      # Stored user facts
├── agent/
│   ├── planner.py          # Multi-step plan generation
│   ├── executor.py         # Plan execution
│   ├── task_queue.py       # Background task queue
│   └── error_handler.py
├── actions/                # One module per tool (17 files)
└── documents/              # Sample notes / HTML
```

---

## Dependencies

Key packages from `requirements.txt`:

| Package | Role |
|---------|------|
| `google-genai` | Gemini Live API + models |
| `sounddevice` / `pyaudio` | Microphone input & speaker output |
| `PyQt6` | Desktop UI |
| `playwright` | Browser automation |
| `pyautogui`, `pywinauto` | Mouse/keyboard/window control |
| `opencv-python`, `mss` | Camera & screenshots |
| `duckduckgo-search` | Web search fallback |
| `requests` | OpenRouter HTTP calls |

Run `playwright install` once after pip install (see `setup.py`).

---

## Running the Project

```bash
pip install -r requirements.txt
playwright install
python main.py
```

**Requirements:** Python 3.11 or 3.12, microphone, free Gemini + OpenRouter API keys, internet connection.

---

## Customization Tips

| Goal | What to change |
|------|----------------|
| **Change voice** | `voice_name` in `main.py` and `actions/screen_processor.py` |
| **Change personality** | `core/prompt.txt` |
| **Change Live model** | `LIVE_MODEL` constant in `main.py` / `screen_processor.py` |
| **Adjust mic/speaker** | `SEND_SAMPLE_RATE`, `RECEIVE_SAMPLE_RATE`, `CHUNK_SIZE` in `main.py` |
| **Add a new capability** | New function in `actions/`, add declaration to `TOOL_DECLARATIONS`, wire in `_execute_tool()` |
| **Face / branding** | Replace `face.png`, edit strings in `ui.py` |

---

## Summary

This project is a **Gemini Live-powered voice agent** with a **PyQt6 control panel** and **many local automation tools**. Speech recognition and speech synthesis are **one integrated pipeline** through Google’s native-audio model — not a separate STT + TTS stack. The assistant currently speaks with the **`Charon`** prebuilt voice, and you can swap it for any of Gemini’s other prebuilt voices by editing two lines of code.

For the original feature list and install video, see `readme.md`.
