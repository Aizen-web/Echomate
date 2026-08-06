# GUI Redesign Plan — Debloat + Eilik-Style Face

This document is the implementation roadmap for two related UI changes:

1. **Performance debloat** — lighter main screen, instant logging, separate Chat tab  
2. **Visual redesign** — remove HUD rings/circles; replace with **Eilik-style expressive face animations**

---

## Goals

| Goal | Success looks like |
|------|---------------------|
| **Faster, smoother UI** | Lower idle CPU; no stutter while Jarvis speaks |
| **Cleaner main view** | Voice-first dashboard — face + status + quick command + file drop |
| **Readable chat elsewhere** | Full transcript on a dedicated Chat tab (instant text, no typewriter) |
| **Eilik-like companion feel** | Animated face reacts to state (idle, listening, thinking, speaking, muted, errors) |
| **Minimal backend churn** | `main.py` and action modules keep using `ui.write_log()` / `set_state()` |

---

## Why We're Doing This

The current UI spends most of its budget on **decoration**, not function:

- `HudCanvas` repaints at **~60 FPS** with rings, scanners, grid, particles, waveform
- `LogWidget` types **one character every 6 ms** — expensive for long replies
- Sys metrics poll subprocesses every **1.5–2 s**

Debloating frees CPU/GPU headroom so **face animations** can run smoothly without fighting the old HUD effects.

---

## Current UI Architecture (baseline)

```
MainWindow (PyQt6)
├── Header (clock, title)
├── Left panel — Sys Monitor (CPU/MEM/NET/GPU/TMP)     ← heavy
├── Center — HudCanvas (rings, face.png, waveform)     ← heaviest
├── Right panel — Activity log (typewriter), file drop, input, mute
└── Footer
```

**Key files:** `ui.py` (~1500 lines), `main.py` (calls `write_log`, `set_state`)

**State signals today:** `INITIALISING`, `LISTENING`, `THINKING`, `SPEAKING`, `PROCESSING`, `MUTED`

---

## Target UI Architecture

```
MainWindow (PyQt6)
├── Header (clock, title, tab bar)
├── QStackedWidget / QTabWidget
│   ├── [VOICE] tab  ← default, lightweight
│   │   ├── FaceAvatar (Eilik-style animations)
│   │   ├── Status strip (1–3 lines, instant)
│   │   ├── Quick command input
│   │   ├── File drop zone
│   │   └── Mute + fullscreen
│   ├── [CHAT] tab
│   │   ├── Full transcript (instant append)
│   │   └── Chat input (same backend as voice commands)
│   └── [SYSTEM] tab (optional / collapsible)
│       └── CPU, MEM, NET, GPU, TMP (slow poll)
└── Footer
```

---

# Part A — GUI Debloat Plan

## Phase A1 — Quick wins (1–2 days)

### A1.1 Remove typewriter logging

**Current:** `LogWidget._step()` inserts one char every 6 ms.  
**Change:** Append full lines instantly with colored HTML or `append()` + line cap.

| Item | Detail |
|------|--------|
| Max lines | 100 on Chat tab; 5–8 on Voice status strip |
| Trim | Drop oldest lines when over cap |
| Color tags | Keep `you` / `ai` / `sys` / `err` / `file` coloring |

**Files:** `ui.py` — refactor `LogWidget` → `ChatLogWidget` (instant) + `StatusStrip` (minimal)

### A1.2 Throttle HUD before removal

Interim step if face swap takes longer:

- Idle: timer **50 ms** (~20 FPS) instead of 16 ms
- Pause animation when window minimized / unfocused
- Disable particles + grid dots when not `SPEAKING`

### A1.3 Slow sys monitor

- Move metrics to **System tab**
- Poll every **5 s** instead of 1.5–2 s
- Skip GPU/temp subprocess calls if tab not visible

### A1.4 Stop file-drop border animation on Voice tab

- Static border when idle; animate only on drag-over

**Expected gain:** ~40–60% less UI thread work before Eilik face lands.

---

## Phase A2 — Tab split (2–3 days)

### A2.1 Routing rules

| Log content | Voice tab | Chat tab |
|-------------|-----------|----------|
| `You: …` | Optional one-liner | ✅ full line |
| `Jarvis: …` | Optional one-liner | ✅ full line |
| `SYS:` / `FILE:` / `ERR:` | ✅ status strip | ✅ full log |
| Tool progress | Short status | ✅ if long |

### A2.2 API changes (backward compatible)

Keep public `JarvisUI` API stable:

```python
ui.write_log(text)      # routes to Chat + status strip
ui.set_state(state)     # drives face animation FSM
ui.on_text_command      # unchanged
```

Optional new helpers:

```python
ui.write_status(text)   # Voice tab only, 1 line
ui.set_expression(name) # future: manual emotion override
```

### A2.3 Command input

- **Voice tab:** quick test box (keep current behavior)
- **Chat tab:** full chat input; same `on_text_command` callback
- Both can be active; dedupe is not required (user chooses tab)

**Files:** `ui.py` only — `main.py` unchanged unless we add expression hooks later.

---

## Phase A3 — Lite mode flag (optional, 0.5 day)

Add to `config/api_keys.json`:

```json
"ui_lite": true
```

When enabled:

- No System tab polling
- Face animations at reduced FPS
- No drag-over animation on file zone

---

# Part B — Eilik-Style Face (replace rings & circle HUD)

## What “Eilik-like” means for Jarvis

[Eilik](https://www.eilikrobot.com/) is a desktop companion with an **OLED expressive face** — not a sci-fi HUD. Key traits we want to borrow:

| Eilik trait | Jarvis adaptation |
|-------------|-------------------|
| Rich facial expressions | Sprite/clip per mood: idle, curious, focused, happy, annoyed, sleepy |
| Reacts to interaction | Map `set_state()` → expression + animation clip |
| Idle self-amusement | Loop subtle idle clips when listening with no speech |
| Smooth transitions | Crossfade or 2–4 frame blend between expressions (not instant pop) |
| Compact “desk pet” frame | Face centered; **no rings, scanners, crosshairs, or waveform bars** |
| Personality | Matches `core/prompt.txt` (Calcifer gremlin) — cheeky idle, dramatic when thinking |

We are **not** copying Eilik assets or firmware — we build **original** face art/animations inspired by the same *feel*.

---

## What gets removed from `HudCanvas`

Delete entirely from `paintEvent` / `_step`:

- Grid dots
- Halo glow ellipses (10 layers)
- Pulse rings
- Spinning arc rings (3)
- Scanner arcs (2)
- Tick marks (36 lines)
- Crosshair
- Corner brackets
- Particle system
- Bottom waveform bars (36 rects × random)

**Keep (simplified):**

- Dark background panel
- Face animation widget (center)
- Small status label under face (`LISTENING`, etc.)

---

## Animation system design

### Recommended approach: **Frame-based sprite player** (best perf in PyQt6)

Replace `HudCanvas` with `FaceAvatar(QWidget)`:

```
assets/face/
├── idle/
│   ├── 001.png … 024.png      # subtle blink/bob loop
├── listening/
│   └── 001.png … 012.png
├── thinking/
│   └── 001.png … 016.png      # eyes dart, curious
├── speaking/
│   └── 001.png … 020.png      # mouth/expression cycle (loop while speaking)
├── muted/
│   └── 001.png                # static or slow blink
├── error/
│   └── 001.png … 008.png
└── manifest.json              # fps, loop, transition rules
```

**Why sprites over live QPainter animation:**

- One `drawPixmap` per frame vs dozens of vector draws
- Timer at **12–15 FPS** is enough for Eilik feel
- Easy to swap art without touching logic
- Can author in Aseprite, Pixelorama, or export from Blender

### Alternative options (ranked)

| Option | Pros | Cons |
|--------|------|------|
| **PNG sequence** ✅ | Fast, simple, full control | Need to create frames |
| **GIF / APNG** | Easy preview | Less control over timing; scaling artifacts |
| **QMediaPlayer + WebM** | Smooth loops | Heavier; sync with state harder |
| **Live2D / Rive** | Professional motion | New deps, overkill for v1 |
| **Single face.png + code morph** | No new assets | Hard to match Eilik quality |

**Recommendation:** PNG sequences + `manifest.json` for v1.

---

## State machine → expression mapping

```
                    ┌─────────────┐
         startup ──►│ INITIALISING│──► idle clip once ──► LISTENING
                    └─────────────┘
                           │
     ┌─────────────────────┼─────────────────────┐
     ▼                     ▼                     ▼
  MUTED               LISTENING              THINKING
 (muted clip)    (idle / listening loop)   (thinking loop)
     │                     │                     │
     │                     │                     ▼
     │                     │                 SPEAKING
     │                     │              (speaking loop)
     │                     │                     │
     └─────────────────────┴─────────────────────┘
                           │
                      PROCESSING
                   (thinking or focused)
                           │
                         ERR:*
                      (error flash → idle)
```

| `set_state()` | Animation clip | Notes |
|---------------|----------------|-------|
| `INITIALISING` | `boot` or first `idle` frame | One-shot |
| `LISTENING` | `idle` loop | Random idle variant every 30–60 s (Eilik “self-amusement”) |
| `THINKING` | `thinking` loop | Start when tool called |
| `SPEAKING` | `speaking` loop | Driven by `hud.speaking` / `set_state("SPEAKING")` |
| `PROCESSING` | `thinking` or `focused` | Long tasks |
| `MUTED` | `muted` | Dim palette optional |
| Error (log contains `ERR:`) | `error` one-shot | Return to previous state after clip |

### Transitions (Eilik 2.0.7-style blending)

- **Blend duration:** 150–300 ms between clips (crossfade alpha or 2–3 intermediate frames)
- **No hard cuts** except boot and error flash
- **Idle micro-motion:** even in calm mode, blink every 4–8 s

---

## `FaceAvatar` class sketch

New class in `ui.py` (or split `ui/face_avatar.py` if file grows):

```python
class FaceAvatar(QWidget):
    def __init__(self, assets_dir: Path):
        self._clips: dict[str, Clip] = load_manifest(assets_dir)
        self._state = "idle"
        self._frame_idx = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._advance_frame)

    def set_state(self, state: str):
        clip = self._map_state_to_clip(state)
        if clip != self._current_clip:
            self._transition_to(clip)

    def _advance_frame(self):
        # advance frame index, draw single pixmap, update() once
        ...

    def paintEvent(self, event):
        # draw background + current frame only
        ...
```

**Performance target:**

- ≤ **15 FPS** animation timer
- ≤ **2 ms** per `paintEvent` on mid-range laptop
- **0** random calls in paint loop
- Pause timer when tab hidden or window minimized

---

## Asset pipeline

### v1 — Placeholder pack (ship the system)

Use simple placeholder sprites (colored emoji-style or minimal pixel face) so code works before final art.

### v2 — Character art pass

Align with Calcifer personality from `core/prompt.txt`:

| Clip | Visual idea |
|------|-------------|
| `idle` | Half-lidded eyes, slight smirk, occasional blink |
| `listening` | Eyes open, subtle head tilt |
| `thinking` | Eyes up/side, flame flicker (if robot has “fire” motif) |
| `speaking` | Mouth/expression cycles; can sync loosely to audio (optional v3) |
| `muted` | Zipper mouth / turned away |
| `error` | Dramatic shock → annoyed |

### Authoring workflow

1. Design base face at **512×512** (scale down in UI)
2. Export PNG sequences per clip
3. Update `assets/face/manifest.json`:

```json
{
  "idle":       { "fps": 8,  "loop": true,  "frames": "idle/%03d.png" },
  "listening":  { "fps": 10, "loop": true,  "frames": "listening/%03d.png" },
  "thinking":   { "fps": 12, "loop": true,  "frames": "thinking/%03d.png" },
  "speaking":   { "fps": 15, "loop": true,  "frames": "speaking/%03d.png" },
  "muted":      { "fps": 4,  "loop": true,  "frames": "muted/%03d.png" },
  "error":      { "fps": 10, "loop": false, "frames": "error/%03d.png" }
}
```

4. Replace `face.png` reference in `main.py` → `assets/face/` directory

### Legal note

Do not use official Eilik artwork, firmware dumps, or trademarked character art. Original assets only.

---

## Optional v3 enhancements (later)

| Feature | Description |
|---------|-------------|
| **Audio-reactive mouth** | Amplitude from playback buffer scales mouth frame index |
| **Random idle events** | 5% chance every minute: yawn, glance, gremlin smirk |
| **Touch reactions** | Click face → playful clip (Eilik head-touch analog) |
| **Expression from memory** | If user name known, warmer idle variant |
| **Calm / Lite animation profile** | Fewer frames, no random idle (like Eilik Quiet mode) |

---

# Part C — Combined implementation schedule

## Milestone 1 — Debloat foundation (Week 1)

- [ ] Refactor `LogWidget` → instant append + line cap
- [ ] Add `QTabWidget`: Voice | Chat | System
- [ ] Route `write_log()` to Chat + short status on Voice
- [ ] Move sys metrics to System tab; slow poll
- [ ] Remove typewriter timer entirely

**Deliverable:** Faster UI, same look (rings still there temporarily).

## Milestone 2 — Face avatar core (Week 2)

- [ ] Create `assets/face/` + `manifest.json`
- [ ] Implement `FaceAvatar` sprite player
- [ ] Wire `set_state()` / `speaking` to animation FSM
- [ ] Add placeholder sprite clips (all states)
- [ ] Replace `HudCanvas` in Voice tab center panel

**Deliverable:** Rings gone; placeholder face animates by state.

## Milestone 3 — Remove old HUD code (Week 2)

- [ ] Delete dead `HudCanvas` ring/scanner/particle code
- [ ] Remove waveform + grid from codebase
- [ ] Tune timer FPS (12–15) and document CPU usage

**Deliverable:** Clean `ui.py`; no legacy HUD paths.

## Milestone 4 — Art & polish (Week 3+)

- [ ] Final face sprites matching Calcifer / Jarvis tone
- [ ] Expression transitions (crossfade)
- [ ] Random idle variety loops
- [ ] `ui_lite` config flag
- [ ] Update `HOW_IT_WORKS.md` with new UI section

**Deliverable:** Shippable Eilik-inspired companion UI.

---

# Part D — File change checklist

| File | Changes |
|------|---------|
| `ui.py` | Tabs, instant logs, `FaceAvatar`, remove `HudCanvas` effects |
| `ui/face_avatar.py` | *(optional split)* animation engine |
| `assets/face/**` | **New** — sprites + manifest |
| `main.py` | Change `JarvisUI("face.png")` → `JarvisUI("assets/face")` (or keep compat shim) |
| `config/api_keys.json` | Optional `ui_lite` |
| `HOW_IT_WORKS.md` | Document new UI after ship |
| `.gitignore` | Ensure large asset exports handled if needed |

**No changes required:** `actions/*`, `memory/*`, `or_client.py`, Gemini Live loop.

---

# Part E — Testing plan

## Performance

- [ ] Task Manager: UI process CPU **idle < 5%** (was often 10–25% with old HUD)
- [ ] No frame drops when Jarvis speaks for 30+ seconds
- [ ] Chat tab with 200+ lines scrolls smoothly

## Functional

- [ ] Voice commands still work from Voice tab input
- [ ] Chat tab input sends to same Live session
- [ ] Mute (F4) → muted face clip + mic stops
- [ ] `THINKING` during tool call → thinking animation
- [ ] `SPEAKING` during TTS → speaking loop
- [ ] File drop still works on Voice tab
- [ ] System tab metrics update when visible only

## Visual

- [ ] No rings, scanners, or waveform on Voice tab
- [ ] State changes feel smooth (blend, not snap)
- [ ] Idle animation runs without user input

---

# Part F — Open decisions (pick before coding)

| # | Question | Recommendation |
|---|----------|----------------|
| 1 | Split `ui.py` into modules? | Yes, after Milestone 2: `ui/main_window.py`, `ui/face_avatar.py`, `ui/chat_log.py` |
| 2 | Keep `face.png` fallback? | Yes — if manifest missing, show static PNG |
| 3 | Chat tab default on startup? | No — **Voice tab** default |
| 4 | Remove command input from Voice tab? | **Keep** quick input for tests |
| 5 | Character style | Original gremlin/desktop pet; not Iron Man HUD |
| 6 | Animation FPS cap | 15 FPS default; 8 FPS in `ui_lite` |

---

# Summary

**Debloat** removes the typewriter log, moves heavy monitoring off the main view, and splits Chat into its own tab so the voice screen stays light.

**Eilik-style face** replaces the entire ring/scanner HUD with a **sprite-based expression system** driven by Jarvis state — idle loops, thinking, speaking, muted — with smooth transitions and optional random idle variety.

Build order: **debloat + tabs first** (immediate speed win), then **FaceAvatar + placeholders**, then **final art polish**.

When ready to implement, start with **Milestone 1** in `ui.py` — no backend changes required.

Change the name from jarvis to calcifer and when the ai replies have it send some emotional values such as (happy angry sad excited and many more) so based on that value the screen will glow in different color based on emotions  and its facial ecpressions (add this in the md file too) change the voice to Leda

---

# Calcifer Identity + Emotion Extension

The visible assistant is **Calcifer**: header, window title, transcript speaker, and face identity use that name. Compatibility class/function names may remain temporarily so the existing voice backend does not need a broad migration.

Each reply begins with one compact machine-readable emotion tag:

```text
[emotion: excited] I found it. Try to look surprised.
```

The UI removes this tag before displaying the reply and maps it to Calcifer's glow and face. Initial supported values are `happy`, `excited`, `playful`, `proud`, `curious`, `thinking`, `focused`, `calm`, `sad`, `angry`, `annoyed`, `surprised`, `sleepy`, and `error`; unknown values fall back to `playful`.

| Emotion family | Glow colour | Expression direction |
|---|---|---|
| happy / proud / playful | gold / orange | bright eyes, smirk |
| excited / surprised | hot orange / pink | wide eyes, open mouth |
| thinking / curious / focused | violet / blue | attentive eyes |
| calm / sleepy / sad | teal / indigo | relaxed or lowered eyes |
| angry / annoyed / error | red | angled brows, frown |

The configured Gemini Live voice is **Leda**.
