# Calcifer — Current State Reference

This document describes everything in the project **as it exists right now**: the file
structure, the UI, and the logic. It is the shared reference for the UI redesign work
(see `CALCIFER_UI_VISUAL_PROMPT.md` and `CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md`
for the target design). The latest pass (glassmorphism rehaul) is reflected here.

---

## 1. What This Project Is

A cross-platform desktop AI assistant (voice-first) called **Calcifer** (rebranded from
JARVIS). It is a PyQt6 desktop app that talks to **Google Gemini Live** for real-time
voice conversation, vision, and tool routing, plus **OpenRouter** for heavy text tasks
(memory extraction, planning, helpers).

---

## 2. File Structure

```
/workspace
├── main.py                   # Entry point. JarvisLive: Gemini Live session, mic/speaker,
│                             #   tool dispatcher, emotion-tag parsing. Boots the UI.
├── ui.py                     # PyQt6 UI. MainWindow (sidebar + chat + companion) + all widgets,
│                             #   conversation store, settings, setup overlay.
├── ui_face_avatar.py         # FaceAvatar: OLD procedural face engine (currently UNUSED —
│                             #   superseded by calcifer_face.py).
├── calcifer_face.py          # CalciferFace: ACTIVE procedural face widget (warm amber, emotion-
│                             #   synced colour, 10 emotion modes, blink/gaze/bob idle motion).
├── or_client.py              # OpenRouter HTTP client with free-model fallback pool.
├── setup.py                  # pip + playwright install helper.
├── requirements.txt          # Python dependencies.
├── .gitignore                # Ignores config/api_keys.json, conversations.json, settings.json.
│
├── core/
│   └── prompt.txt            # System personality + tool rules + emotion-tag instructions.
│
├── config/
│   ├── __init__.py           # Config package.
│   ├── api_keys.json         # API keys (gitignored, created at runtime).
│   ├── conversations.json    # Chat history (gitignored, created at runtime).
│   └── settings.json         # Reduced-motion flag (gitignored, created at runtime).
│
├── memory/
│   ├── __init__.py
│   ├── config_manager.py     # Legacy config helpers.
│   ├── memory_manager.py     # Load/save/extract long-term memory (long_term.json).
│   └── long_term.json        # Stored user facts (gitignored, created at runtime).
│
├── agent/
│   ├── planner.py            # Breaks goals into <=5 steps (OpenRouter).
│   ├── executor.py           # Runs each plan step by calling action modules.
│   ├── task_queue.py         # Background task queue with priorities.
│   └── error_handler.py      # Plan-failure handling.
│
├── actions/                  # One module per tool (17 files):
│   ├── open_app.py           #   Launch applications
│   ├── web_search.py         #   Web search (Gemini + DuckDuckGo fallback)
│   ├── weather_report.py     #   Weather by city
│   ├── send_message.py       #   WhatsApp / Telegram
│   ├── reminder.py           #   Scheduled reminders
│   ├── youtube_video.py      #   Play / summarize / trending
│   ├── screen_processor.py   #   Screenshot / webcam + voice analysis (Leda voice)
│   ├── computer_settings.py  #   Volume, brightness, WiFi, shutdown, etc.
│   ├── browser_control.py    #   Playwright browser automation
│   ├── file_controller.py    #   File/folder CRUD
│   ├── desktop.py            #   Wallpaper, organize desktop
│   ├── code_helper.py        #   Write/edit/run code
│   ├── dev_agent.py          #   Multi-file project builder
│   ├── computer_control.py   #   Mouse, keyboard, screen clicks
│   ├── game_updater.py       #   Steam / Epic install & update
│   ├── flight_finder.py      #   Google Flights search
│   └── file_processor.py     #   Uploaded-file processing
│
├── FaceEngine/               # Original C++ reference (Xiaozhi OLED face engine) — kept for
│   ├── Display code.cc       #   design inspiration only, not used by the Python app.
│   ├── face_engine.cc
│   └── face_engine.h
│
├── test_emotion_system.py    # Smoke test for emotion parsing / face modes.
│
├── README.md                 # Original "Face engine for Xiaozhi" readme.
├── HOW_IT_WORKS.md           # Architecture documentation.
├── GUI_REDESIGN_PLAN.md      # Original redesign roadmap (debloat + face).
├── IMPLEMENTATION_PLAN.md    # 11-phase implementation plan.
├── CALCIFER_REDESIGN_AGENT_PROMPT.md   # Redesign brief (animation, emotion, rebrand).
├── CALCIFER_REDESIGN_COMPLETE.md       # Completed-implementation report.
└── CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md  # Final visual rehaul brief (glass, depth, layout swap).
```

---

## 3. The Current UI

### 3.1 Entry point

`main.py:893` creates `JarvisUI("face.png")`, then a background thread runs
`JarvisLive(ui).run()`, and `ui.root.mainloop()` runs the Qt event loop.

### 3.2 Layout (what you see today)

```
┌───────────────────────────────────────────────────────────────────────────┐
│ TopStrip (34px, full-width): ◆ CALCIFER wordmark + LIVE status LED        │
├────────────┬──────────────────────────────────┬───────────────────────────┤
│ Sidebar    │  Companion stage (CENTER)        │  Chat panel (RIGHT)       │
│ (210px,    │  - largest region, primary focal │  - narrower glass panel   │
│ collapsible│  point, glowing divider edges    │  - ChatView bubbles        │
│ to icons)  │  - layered concentric glow +     │  - hero empty state        │
│ · identity │    ambient rings                 │  - file chip               │
│ · New chat │  - CalciferFace in glass housing │  - ChatInputBar (attach +  │
│ · conv list│    (rim light, bloom, glossy     │    input + Send)           │
│ · clock    │    eyes, per-emotion mouths)     │  - collapse toggle (›)     │
│ · Settings │  - status line + mute pill       │  - chat panel collapses    │
│ · collapse │  - face scales up with region    │    FIRST when window is    │
│            │                                  │    narrow (auto)           │
└────────────┴──────────────────────────────────┴───────────────────────────┘
```

Glassmorphism material system: deep gradient base (`_BasePane`, warm ember bottom-left +
cool top-right), three elevation tiers — base gradient → translucent glass panels
(sidebar/chat, ~160 alpha fills + top edge light + glowing amber divider lines) → raised
items (active conversation pill, send button, dialogs). Deepened jewel-tone accents
(`#FFB020` amber, `#FF5E6E` coral, `#8B7CFF` violet, `#4FC6E8` teal, `#FF4B5C` red,
`#FF8FB3` rose) on a deep charcoal base (`#0a0a0d`).

### 3.3 Widget inventory (ui.py)

| Class | Role |
|-------|------|
| `MainWindow` | Owns the top-strip + 3-region layout (sidebar | companion center | chat right), conversation store + persistence, file attach, shortcuts (F4 mute, F11 fullscreen), setup overlay, settings, chat collapse toggle + auto-collapse-on-narrow. |
| `TopStrip` | 34 px full-width glass wordmark strip: "◆ CALCIFER" + live state LED/readout (synced via `_apply_state`). |
| `_BasePane` | Paints the deep gradient background (charcoal → ember bottom-left → cool top-right) behind all translucent glass panels. |
| `Sidebar` | Collapsible glass nav: serif identity, gradient "New chat", conversation list (select / double-click rename / right-click or hover-× delete), clock, Settings, collapse toggle; translucent fill + top edge light + right glowing divider. |
| `_ConvRow` | A single conversation row (title + meta) with hover delete button. |
| `ChatView` | Glass bubble transcript with auto-scroll that respects manual scroll-up; hero empty state; 200-bubble render cap; accepts file drops. |
| `ChatInputBar` | Glass attach (＋) button, rounded "Message Calcifer…" field, gradient Send button with soft amber glow that enables only with text. |
| `_GlassPanel` | Glass chat-panel container: translucent fill + top edge light + left glowing divider; hosts header (collapse toggle ›), chat body, file chip. |
| `CompanionArea` | Center stage: layered concentric glow (eases ~300 ms, pulses while speaking, dims when muted), faint ambient rings, edge rim light; status line + gradient mute pill; face scales up to fill the enlarged region. |
| `CalciferFace` (calcifer_face.py) | Eilik-grade procedural glass face: glass housing bezel + rim light + bloom, glossy gradient eyes with highlights, per-emotion eye/mouth shapes, animated speaking mouth, crossfade between expressions (~230 ms), eased gaze/blink/bob idle motion. ~22 FPS. |
| `SettingsDialog` | Frameless glass modal: emotion palette swatches (jewel tones) + "Reduced motion (lite mode)" toggle persisted to `config/settings.json`. |
| `SetupOverlay` | First-run glass modal: Gemini key + OpenRouter key + OS picker → writes `config/api_keys.json`. |
| `_RootShim` | Wraps QApplication so backend can call `mainloop()` / `protocol()`. |
| `JarvisUI` | Public backend-facing API shim over MainWindow. |

Legacy classes (`HudCanvas`, `MetricBar`, `_SysMetrics`, `LogWidget`, `FileDropZone`,
`FaceAvatar`/`ui_face_avatar.py`) are no longer referenced by the UI.

### 3.4 Public backend-facing API (must keep working)

```python
ui.write_log(text)            # → MainWindow._log_sig → _append_log → active conversation
ui.set_state(state)           # → _state_sig → CompanionArea.set_state (status line colour)
ui.set_emotion(emotion)       # → _emotion_sig → CompanionArea.set_emotion (glow + face colour/expression)
ui.on_text_command = cb       # text commands (chat input) → cb(text) on a thread
ui.muted (get/set)            # toggles MainWindow._muted + companion mute pill
ui.current_file               # → MainWindow._current_file (attached file path)
ui.wait_for_api_key()         # blocks until SetupOverlay submits config
ui.start_speaking()           # = set_state("SPEAKING")
ui.stop_speaking()            # = set_state("LISTENING") (unless muted)
ui.root.mainloop()            # run Qt event loop
```

Backend calls from main.py: `write_log`, `set_state`, `set_emotion`, `on_text_command`,
`muted`, `current_file`, `wait_for_api_key`, `start_speaking`, `stop_speaking`, `root.mainloop`.

---

## 4. The Logic

### 4.1 Startup

1. `python main.py` → `JarvisUI("face.png")` builds the window.
2. If `config/api_keys.json` is missing/incomplete → `SetupOverlay` shows; `wait_for_api_key()` blocks the backend thread.
3. `JarvisLive.run()` loads `core/prompt.txt` + long-term memory, connects to Gemini Live with tools + voice, and starts 4 async tasks: `_send_realtime`, `_listen_audio`, `_receive_audio`, `_play_audio`.
4. On disconnect → waits 3 s → reconnects automatically.

### 4.2 Conversation loop

```
User speaks → mic (16 kHz PCM) → Gemini Live (STT + reasoning)
  → optional tool_call → tool runs locally (actions/*)
  → FunctionResponse sent back → Gemini generates AUDIO (24 kHz PCM)
  → speakers + transcript via ui.write_log
```

- States driven by `ui.set_state()`: `INITIALISING`, `LISTENING`, `THINKING`, `PROCESSING`, `SPEAKING`, `MUTED`.
- Echo prevention: mic callback does not send while `_is_speaking`.
- Mute: F4 or button → `ui._toggle_mute()` → stops sending audio.

### 4.3 Emotion protocol

- `core/prompt.txt` instructs the model to begin every reply with `[emotion: name]`.
- `main.py` `_receive_audio()` parses it with regex, strips it from visible/spoken text, and calls `ui.set_emotion(emotion)`; missing/unknown → `"playful"`.
- `CompanionArea.set_emotion()` picks a target colour from `EMOTION_COLORS` (ui.py) and eases the glow over ~300 ms, plus calls `face.setEmotion()`.

### 4.4 Colour families

| Emotion family | Glow colour |
|---|---|
| happy / proud / playful | deep warm gold `#FFB020` |
| love | warm rose `#FF8FB3` |
| excited / surprised | vivid coral `#FF5E6E` |
| thinking / curious / focused | rich violet `#8B7CFF` |
| calm / sleepy / sad | jewel teal `#4FC6E8` |
| angry / annoyed / error | ember red `#FF4B5C` |

### 4.5 Face expression modes (CalciferFace)

0 speaking · 1 happy · 2 mad · 3 sad · 4 surprised · 5 sleepy · 6 thinking · 7 confused · 8 excited · 9 love.
Emotion → mode map lives in `calcifer_face.py:82`.

### 4.6 Voice

- Gemini Live native audio; no local TTS/STT stack.
- `voice_name="Leda"` in `main.py` (~line 580) and `actions/screen_processor.py` (~line 195).

### 4.7 Conversation persistence

- Conversations are stored in `config/conversations.json` (gitignored user data): each has
  `id`, `title`, `created`, `updated`, and a `messages` list of `{role, text, time}`.
- `ui.write_log()` routes each line to the **active** conversation via `_route_line()`
  (`you:` / `calcifer:` / `file:` / `err` → `you` / `ai` / `sys` / `err`), strips the
  `You:` / `Calcifer:` prefixes for clean bubbles, caps at 200 messages, and auto-titles
  the chat from the first user message.
- Sidebar: **New chat** creates a conversation; click switches; double-click or right-click
  renames; hover-× or right-click deletes (falls back to a fresh chat if the last is deleted).
- `config/settings.json` holds the reduced-motion flag (`lite`).

---

## 5. Key Files & Line References

| What | Where |
|------|-------|
| Emotion colour table | `ui.py:54` (`EMOTION_COLORS`) |
| Deep glass chrome palette `class C` | `ui.py:78` |
| Top strip | `ui.py:139` (`TopStrip`) |
| Conversation routing | `ui.py:132` (`_route_line`) |
| Chat transcript view | `ui.py:197` (`ChatView`) |
| Chat input bar | `ui.py:390` (`ChatInputBar`) |
| Sidebar | `ui.py:534` (`Sidebar`), rows `_ConvRow` at `ui.py:488` |
| Companion stage | `ui.py:752` (`CompanionArea`) |
| Settings dialog | `ui.py:920` (`SettingsDialog`) |
| Setup overlay | `ui.py:1014` (`SetupOverlay`) |
| Base gradient background | `ui.py:1169` (`_BasePane`) |
| Glass chat panel | `ui.py:1205` (`_GlassPanel`) |
| Main window + conversations | `ui.py:1238` (`MainWindow`) |
| Public API shim | `ui.py:1707` (`JarvisUI`) |
| Face widget (active) | `calcifer_face.py:34` (`CalciferFace`, `setColor` + `setEmotion` + `set_lite`) |
| Face widget (legacy/unused) | `ui_face_avatar.py` |
| Emotion parsing (backend) | `main.py:779-784` |
| UI wiring (backend) | `main.py:505-515`, `main.py:893` |

---

## 6. Design Gaps — Resolved in the UI Redesign

| Target (`CALCIFER_UI_VISUAL_PROMPT.md` / glassmorphism rehaul) | Status |
|--------|---------|
| Sidebar: identity + new chat + conversation list + settings, collapsible to icons | ✅ Done (glass material, active amber pill) |
| Chat panel: full transcript, hero serif empty state, input with attach + send | ✅ Done (now a narrower right-hand glass panel, collapsible) |
| Companion area = visual centrepiece | ✅ Center region, largest, layered glow + rings |
| Layout swap: sidebar → companion (center) → chat (right) | ✅ Done |
| Real glassmorphism: translucency, layered elevation, edge light, glowing dividers | ✅ Done (3 elevation tiers, top edge highlights, amber divider lines) |
| Base background has real depth (gradient, not flat hex) | ✅ Done (`_BasePane` ember/cool gradient) |
| Deepened jewel-tone accents, gradients on all accent surfaces | ✅ Done (deeper `EMOTION_COLORS` + qlineargradient buttons/pills) |
| Face redesigned, Eilik-grade (shape language, glossy eyes, per-emotion mouths) | ✅ Done (glass housing, rim light, bloom, crossfade) |
| Chat panel restyled for its new supporting role | ✅ Done (compact glass bubbles, elevated user vs. AI) |
| Futuristic detailing, restrained | ✅ Done (top strip, glowing dividers, corner notches, sparkles) |
| Responsive: chat collapses first | ✅ Done (toggle + auto-collapse below `_CHAT_AUTO_COLLAPSE_W`) |
| Glow is the only emotion-shifting surface | ✅ Sidebar/chat chrome stays stable; face colour synced |
| Mute near the face, small & quiet | ✅ Gradient pill under the status line |
| Eased colour transitions, gentle motion | ✅ Glow eases ~300 ms; crossfaded face expressions; eased gaze/blink/bob |
| No system/resource-monitor surface | ✅ Removed (`_SysMetrics`, bars, HUD, badges) |
| Conversation switching functional | ✅ Persisted, switchable, rename/delete |
| Everything functional, not decorative | ✅ Verified offscreen (API + layout + face-mode + visual sanity) |
| Reduced-motion (lite) still disables heavier motion | ✅ Slows glow easing, kills bloom/ring pulse, shortens face crossfade |

**Remaining polish (out of scope for this pass):** message fade/slide-in animation.
