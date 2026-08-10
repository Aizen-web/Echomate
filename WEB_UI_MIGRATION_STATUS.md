# Web UI Migration — Status Report

Date: 2026-08-10

Status of the `CALCIFER_WEB_UI_MIGRATION_PROMPT.md` migration: the native PyQt6 widget UI has been fully replaced with an embedded web frontend (`QWebEngineView` + `QWebChannel` bridge). The Python backend (`main.py`, `agent/*`, `actions/*`, `memory/*`, `or_client.py`) is untouched.

## What Has Been Done

### Frontend (`web/`)
- `index.html` — Top strip, sidebar, companion stage (concentric rings + `#glow` layer + SVG face + housing), chat panel, Ctrl+K command palette, settings modal, setup modal, toasts, file chip, mute pill.
- `style.css` — Glassmorphism panels, layered colour depth, `@property`-registered `--glow-color` / `--face-color` / `--feature-color` custom properties that **transition on `.3s` so colours glide instead of snapping**. `speaking` / `muted` / `lite` / `collapsed` state classes.
- `face.js` — Parametric SVG face engine: 9 expression presets (eyes = morphable path anchors, mouth = cubic path). Per-frame easing toward a target (`D=0.15`), blink with variable interval (2.2–5.4 s), gaze drift, speaking mouth ripple. Driven by a persistent 30 ms `setInterval` (NOT `requestAnimationFrame`, which silently stops in offscreen/headless mode). Exposes `window.CalciferFace`.
- `app.js` — Bridge wiring, chat rendering + autoscroll, sidebar conversations with inline rename + context menu, task feed, fading toasts, palette with 11 commands incl. `{arg}` sub-prompts, setup/settings modals, chat auto-collapse at narrow widths, Ctrl+K / Esc shortcuts. Exposes `window.bridge`.
- `qwebchannel.js` — Vendored official Qt WebChannel client.

### Backend host (`ui.py`, rewritten)
- `_WebView(QWebEngineView)` with a custom `file_dropped` signal and Chromium flags for root users.
- `Bridge(QObject)` registered as `bridge` on the `QWebChannel`; signals `onReady/onState/onEmotion/onMuted/onFile/onTasks/onConvs/onMessages/onSetup/onLite/onToast/onOpenSettings`; slots forward to `MainWindow` handlers.
- `MainWindow` re-implements the old logic: conversations (`config/conversations.json`), log routing / auto-titling, threaded `on_text_command`, 1 s task poller with toast-on-completion, settings lite flag, setup flow writing `config/api_keys.json`, F4 mute / F11 fullscreen shortcuts, native `QFileDialog` picker, custom drag-and-drop.
- The 10-item public API is preserved identically: `write_log`, `set_state`, `set_emotion`, `on_text_command`, `muted`, `current_file`, `wait_for_api_key`, `start_speaking`, `stop_speaking`, `root.mainloop`.

## What Works (Verified by Automated Tests)

Two headless smoke suites (`/tmp/opencode/web_smoke.py` and `web_smoke2.py`) run offscreen; **54/54 checks pass**.

- Page loads; face.js/app.js/bridge all initialise; zero JS console errors.
- Face engine: eye/mouth morph paths are rendered and animate; blink + gaze drift run.
- **Colour easing verified by sampling intermediate values** (`rgb(139,124,255)` → `rgb(189,132,222)` → … → `rgb(255,143,179)`), so glow and face colours glide rather than snap.
- Rapid back-to-back emotion changes still end on the correct colour and expression.
- Glow is a **separate `#glow` element** (independent layer, own animation) tinted from the same eased colour; pixel scan confirms the warm gold glow renders during `happy`.
- State machine: Initialising → Listening → Thinking → Speaking; `start_speaking()` / `stop_speaking()` drive the DOM; speaking ripple toggles on/off; `lite` mode disables motion.
- Mute: palette action toggles, pill reflects state, `muted` getter/setter works from Python.
- Setup: overlay shows when `config/api_keys.json` is missing, hides after save, `wait_for_api_key()` returns.
- Chat: bubbles render, empty-state toggles, messages persist across conversation switching, sidebar rows, rename/delete apply, new chat works.
- Tasks: sidebar feed populates from the real `agent/task_queue.py`.
- File chip + `current_file` property work.

## What Does NOT Work / Limitations

- **Full `main.py` boot cannot be exercised in this environment**: it needs a real Gemini API key and a microphone. The backend `JarvisLive` path (`asyncio.run(jarvis.run())`) was not run end-to-end here; the public-API surface it depends on was verified directly.
- **The task executor fails on real tool goals here** (`No module named 'google'`): the downloaded executor's deps aren't installed in this sandbox. This is an environment limitation, not an app bug — the task feed/list/status plumbing itself is proven.
- **Headless requirements**: offscreen needs `QT_QPA_PLATFORM=offscreen`; QtWebEngine as root needs `QTWEBENGINE_CHROMIUM_FLAGS="--no-sandbox --disable-gpu --disable-dev-shm-usage"`. Chromium noise (`dbus... bus.cc`, `QRhiGles2`) is benign.
- `calcifer_blob.py` (old minimal-blob widget) is now **unused but still present** (not deleted).
- Page is served via `file://` from the bundled `web/` dir (no local dev server needed).

## What's Left To Do

1. **Human visual/UX review** on a real display (offscreen pixel tests pass, but a human should confirm the glassmorphism/layout polish).
2. **Full end-to-end run** with a real API key + mic via `python3 main.py` to validate the complete backend loop against the new UI.
3. Optional: drop the now-unused `calcifer_blob.py`.
4. The migration prompt's deliverable (boot-sequence explanation) — covered below.

## App Boot Sequence (as implemented)

1. `python3 main.py` → `main()` (main.py:892) constructs `JarvisUI("face.png")` (ui.py).
2. `JarvisUI.__init__` builds the `QApplication`, `MainWindow`, and `_WebView`; sets up the `QWebChannel` + `Bridge`, then loads `web/index.html` from the local file system. The page registers its JS handlers and notifies `onReady` back to Python.
3. `main()` spawns a daemon thread that calls `ui.wait_for_api_key()`: if `config/api_keys.json` is missing, the bridge shows the setup modal in the page; saving it writes the file and unblocks `wait_for_api_key`.
4. The thread then creates `JarvisLive(ui)`, wires `ui.on_text_command = self._on_text_command`, and runs `asyncio.run(jarvis.run())` (agents, mic, etc.).
5. Meanwhile `ui.root.mainloop()` runs the Qt event loop. The backend calls `ui.write_log` / `ui.set_state` / `ui.set_emotion` from its threads; the bridge turns those into signals that the web page renders. `on_text_command` results and `[emotion: X]` tags flow back into the UI via the same bridge.
