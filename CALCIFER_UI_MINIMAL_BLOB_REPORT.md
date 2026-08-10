# Calcifer — Minimal Blob UI Pass: Implementation Report

This document explains exactly what was implemented in response to
`CALCIFER_UI_MINIMAL_BLOB_PROMPT.md`. It supersedes the face-animation ambitions
of the two prior UI passes (`CALCIFER_UI_VISUAL_PROMPT.md`,
`CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md`): the facial rig is gone, replaced
by a single glowing blob, and the saved effort went into surfacing the app's
existing (previously invisible) tool capability.

---

## 1. What Changed at a Glance

| Area | Before | After |
|------|--------|-------|
| Companion stage centrepiece | `CalciferFace` (procedural glass face: eyes, mouth, expressions) | `CalciferBlob` (single glowing plasma orb) |
| Emotion colour target | Face + stage glow | Blob + its own glow, eased ~300 ms, **holds steady** while idle |
| Companion stage content | Face + glow + status + mute pill | Blob + glow + **clock** + status + mute pill |
| Clock | Only in the sidebar | Added a second, glass, live clock in the companion stage |
| Background tasks | `agent/task_queue.py` ran with **zero UI presence** | Live activity feed in the sidebar + completion toasts |
| Quick tool use | Had to type a full sentence every time | **Ctrl+K command palette** launcher |

Files touched:

- **`calcifer_blob.py`** (new) — the minimal animated orb widget.
- **`ui.py`** — `CompanionArea` rewritten to host the blob + clock; new
  `CommandPalette`, `_Toast` widgets; `Sidebar` gains a live task feed;
  `MainWindow` wires palette / task polling / toasts.
- **`calcifer_face.py`** — left in the repo but is **no longer imported or
  used** by the UI (kept as reference, same as the legacy `ui_face_avatar.py`).

---

## 2. The Blob (`calcifer_blob.py`)

### 2.1 Shape

A soft, rounded, organic orb. The outline is **not a geometric circle**: it is a
smooth closed curve sampled from 36 radial points whose radius carries three
slow sinusoidal harmonics (`3θ`, `5θ`, `7θ`, with separate phases and drift
rates). That gives a gentle, slowly shifting edge so the orb reads as alive —
but the amplitudes are kept subtle so it looks premium, not lava-lamp.

### 2.2 Motion states (distinguishable by movement alone)

| State | Motion |
|-------|--------|
| **Idle** | Slow breathing (scale pulses at ~0.024 amplitude) + a white shimmer highlight slowly drifting across the surface |
| **Listening** | Calm inward pull: gentle contraction plus ripple rings that move **toward** the center |
| **Thinking / Processing** | Slow internal swirl: three rotating arc segments + an orbiting mote inside the orb |
| **Speaking** | Rhythmic pulse (two overlapping sines) + expanding ripple rings radiating outward |

> **Implementation note (per the prompt's Section 2.3):** real-time audio
> amplitude from the outgoing speech stream is **not** wired through to the UI
> in this pass (the audio path in `main.py` writes straight to the output
> device with no amplitude signal back to the UI thread). Speaking is therefore
> driven by a **convincing rhythmic animated pattern** — pulse + outward ripples
> at a speech-like cadence — exactly the fallback the prompt allowed. Wiring
> true amplitude reactivity would be a clean follow-up: expose a
> `blob.set_amplitude(float)` and feed it RMS from `_play_audio`.

### 2.3 Emotion colour behaviour (the important bit)

- Reuses the existing `EMOTION_COLORS` table in `ui.py` unchanged
  (`ui.py:54`). `CompanionArea.set_emotion()` maps emotion → `QColor` via
  `get_emotion_color()` and hands it to `blob.set_target_color()`.
- The colour eases from the current value to the new target over **~300 ms**
  (10 ticks at 30 ms), matching the old glow easing cadence.
- Once eased, **the colour holds steady**. It never drifts, fades, or falls
  back to a default while idle. Only a **new incoming emotion value** restarts
  an ease. Verified by test: `love → holds #FF8FB3` → `calm → #4FC6E8 → still
  #4FC6E8 after 1.5 s idle`.
- The blob paints its own radial glow **in the same paint pass, from the same
  eased colour**, so orb + glow always read as a single light source. The
  stage background now only adds a faint colour-synced ambient layer so it
  never fights the orb.

### 2.4 Glow, size, placement

- Blob radius ~ `0.235 × min(w,h)` of its widget; the glow extends ~2.5× that.
- The blob widget has an expanding size policy and is centred in the stage, so
  it scales up with the window and stays the focal point at every size.
- All gradients are smooth radial/linear fills with antialiasing enabled; the
  orb edge is a stroked rim light rather than a hard fill boundary, so there
  is no banding or aliasing at large window sizes (tested at 2200×1400).

### 2.5 Reduced-motion (lite)

`set_lite(True)` disables the swirl/ripple/shimmer effects, flattens the wobble
amplitude to near-static, and slows the animation timer — preserving the "calm,
quiet" promise of lite mode.

---

## 3. Clock (Companion Stage)

- A small, glass-styled digital readout (`HH:MM:SS`) sits in the **top-right
  corner** of the companion stage, visually quiet and separate from the blob.
- It is styled with the same translucent glass material as the rest of the app
  (subtle fill, hairline border, soft radius).
- Updated by its own 1-second `QTimer` inside `CompanionArea`; updates in place
  with no re-render jarring.

---

## 4. Functional Expansion (Section 5 of the prompt)

The companion stage is intentionally minimal, so the added capability lives in
the sidebar / overlays.

### 4.1 Quick-command palette — `Ctrl+K` (prompt item 1)

A frameless glass overlay that launches with **Ctrl+K** (toggle), centered over
the window.

- Lists 11 common actions: open an app, web search, weather, reminder, YouTube,
  message, screenshot, file management — plus local actions (new chat, mute,
  settings).
- Type to filter the list live; ↑/↓ navigate; Enter runs.
- Commands that need an argument (`Open {arg}`, `Search the web for {arg}`, …)
  switch into **argument mode**: the field prompts for the missing value, then
  Enter formats and sends the complete phrase.
- Text commands are sent down the **same pipeline as the chat input**
  (`MainWindow._send` → `on_text_command`), so they are genuinely functional —
  they reach Gemini Live and are routed to the existing `actions/*` tools.
- Local actions (new chat / mute / settings) execute immediately in the UI.

### 4.2 Live background-task activity feed (prompt item 2)

`agent/task_queue.py` had a working queue with **no visible UI**. Now:

- The sidebar has a **"▤ Tasks"** button showing a running/total badge
  (e.g. `▤ Tasks (2 running)`).
- Clicking it toggles a **glass panel** (collapsed by default) listing the
  most recent queued/running/completed tasks, colour-coded by status:
  pending = dim, running = amber, completed = green, failed = red.
- `MainWindow` polls `get_queue().get_all_statuses()` every second and refreshes
  the feed, so multi-step tool use is no longer invisible.
- The whole section collapses away cleanly when the sidebar is collapsed to
  icons.

### 4.3 Notification toasts (prompt item 5)

When a background task reaches a terminal state, a small glass toast slides in
at the top-right of the window — `Finished: …`, `Failed: …`, `Cancelled: …` —
coloured by outcome, and auto-dismisses after ~3.2 s. Non-blocking, stacked if
multiple complete at once, and safely cleaned up on dismissal.

### 4.4 Quick status toggles

Mute already had its F4 shortcut + companion pill; the palette now exposes the
same toggle as an entry point (`Mute / unmute mic`), so users don't need to
remember the key. The palette also exposes New chat and Settings.

### 4.5 What was deliberately **not** added

Per the "minimal companion stage" rule, none of the above lives in the center
stage — the stage contains only blob, glow, clock, status line, and mute pill.
No weather/reminder chips were added as permanent dashboard clutter.

---

## 5. Non-Regression (Section 6)

Every public backend-facing API is unchanged and verified:

| API | Status |
|-----|--------|
| `write_log(text)` | ✅ works |
| `set_state(state)` | ✅ works |
| `set_emotion(emotion)` | ✅ works (now drives the blob colour) |
| `on_text_command` get/set | ✅ works |
| `muted` get/set | ✅ works |
| `current_file` | ✅ works |
| `wait_for_api_key()` | ✅ works |
| `start_speaking()` / `stop_speaking()` | ✅ works |
| `root.mainloop()` | ✅ works |

Existing features kept working: conversation switching/rename/delete, file
attach, settings dialog (emotion palette + lite toggle), mute, emotion
protocol, voice pipeline. The emotion → colour mapping logic in `ui.py` was
**not changed** — this pass only redirected which visual element consumes that
colour (blob instead of face).

---

## 6. QA Results (Section 7 / 8)

Verification ran headless (`QT_QPA_PLATFORM=offscreen`) with PyQt6.

**Automated (19 + 10 + 11 checks, all passing):**

- All 11 public API entry points work.
- Blob animated through all states with no errors.
- Emotion colour holds steady at `love` while idle, eases correctly to `calm`,
  and does **not** drift back to default.
- `EMOTION_COLORS` mapping stable (`happy → #FFB020`, etc.).
- Palette: constructed, 11 commands, immediate command routes to chat,
  argument-mode command routes `"Open Chrome"`, mute action toggles.
- Task feed: sidebar shows running/completed tasks; toast fires on completion
  and dismisses cleanly.
- Companion clock shows `HH:MM:SS`.
- Sidebar collapse/expand preserves the tasks section.
- Chat auto-collapses on narrow windows; palette repositions on resize.
- Renders without errors at 2200×1400 (large-window crispness check).

**Visual (offscreen pixel sampling of rendered states):**

| State / emotion | Blob centre pixel | Reads as |
|-----------------|-------------------|----------|
| idle / happy | `(217,150,27)` | deep warm gold ✅ |
| listening / curious | `(119,106,218)` | rich violet ✅ |
| thinking / thinking | `(118,106,217)` | rich violet ✅ |
| speaking / excited | `(222,82,96)` | vivid coral ✅ |
| love | `(214,120,151)` | warm rose ✅ |
| calm | `(66,166,194)` | jewel teal ✅ |

The colour-persistence requirement (the headline behavioural fix of this pass)
was confirmed both by automated test and by the sampled frames: the orb keeps
its last emotion colour at idle instead of resetting.

---

## 7. Definition of Done — Met

- [x] Companion stage shows only a polished, smoothly animated glowing blob with
      distinguishable idle/listening/thinking/speaking motion, plus a clock.
- [x] Emotion-persistent colour (eases ~300 ms, holds steady while idle).
- [x] Glassmorphism / soft-glow / futuristic / high-res visual bar met (tested
      at large window size).
- [x] Functional expansion implemented and genuinely useful (Ctrl+K palette +
      background-task activity feed + completion toasts).
- [x] QA checklist passed; all non-regression items verified.
