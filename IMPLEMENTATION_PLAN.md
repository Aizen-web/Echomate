# Calcifer Redesign — Implementation Plan

Rebuild the Jarvis desktop assistant into **Calcifer** — a warm, expressive, colour-shifting desktop companion. This plan covers all 11 phases from the design documents, drawing inspiration from the C++ FaceEngine for the procedural face.

---

## User Decisions & Review

- **Internal identifier renaming:** Leave them as-is (e.g., `JarvisUI`, `JarvisLive`) to avoid unnecessary churn across action modules. Only user-visible strings get rebranded.
- **System monitor tab:** Drop the System tab entirely per the newer visual prompt (`CALCIFER_UI_VISUAL_PROMPT.md`) to debloat the UI for faster run times.
- **Sidebar with conversation history:** Build the sidebar UI shell with placeholder items. Display the mute button, time, and agent name in the sidebar. Ensure the GUI is premium, clean, yet beautiful.
- **Log / text streaming:** Do not use the typewriter effect, but stream the text/transcription smoothly as chunks arrive.
- **Face Engine:** Implement a premium procedural QPainter face engine inspired by the C++ `FaceEngine` (eyes, mouth, blink, idle motion, eyebrows, and expressions).

---

## Proposed Changes

### Phase 1 — Rebrand to Calcifer

#### [core/prompt.txt](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/core/prompt.txt)
- Replace with the Calcifer personality prompt from [prompt.txt](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/prompt.txt) (root level), which already has the emotion signal instructions.

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)
- Window title: `"J.A.R.V.I.S — MARK XXXIX"` → `"Calcifer"`
- Header title: `"J.A.R.V.I.S"` → `"Calcifer"`
- Header subtitle: → `"Your Fiery Desktop Companion"`
- All user-visible "JARVIS" / "J.A.R.V.I.S" strings → "Calcifer"
- Footer branding update.
- Setup overlay text: `"Configure J.A.R.V.I.S."` → `"Configure Calcifer"`.
- File dialog title & file hint text.
- Log tag detection: `"jarvis:"` → `"calcifer:"`.

#### [main.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/main.py)
- Fallback system prompt: `"You are JARVIS"` → `"You are Calcifer"`.
- User-visible log: `"Jarvis: {text}"` → `"Calcifer: {text}"`.
- `"SYS: JARVIS online."` → `"SYS: Calcifer online."`.
- Console debug prints: leave `[JARVIS]` prefix as-is (developer-only).

#### [setup.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/setup.py)
- `"start JARVIS"` → `"start Calcifer"`.

---

### Phase 2 — Debloat the Existing Interface

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)

**LogWidget changes:**
- Kill the character-by-character typewriter timer entirely.
- Replace `_step()` / `_next()` with instant full-line append using `append()` + colour formatting, but allow text streaming as chunks arrive.
- Add line cap: 100 lines max for chat, 5 for status strip.
- Drop oldest lines when cap exceeded.

**HudCanvas changes (interim):**
- Timer from 16ms → 50ms (~20 FPS) as interim step.
- Pause timer when window minimized/unfocused.
- These elements will be fully replaced by FaceAvatar in Phase 4.

**System metrics:**
- Poll interval: 1.5s → 5s.
- Skip GPU/temp subprocess when metrics panel not visible.

**FileDropZone:**
- Stop constant dash animation timer.
- Animate only on `dragEnterEvent` / `dragLeaveEvent`.

---

### Phase 3 — Layout Split (Three-Region Premium Layout)

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)

Complete rebuild of `MainWindow.__init__` and layout methods:

```
┌───────────┬──────────────────────────┬──────────────────────────┐
│  Sidebar  │   Chat panel             │   Companion area         │
│ (nav)     │   (transcript + input)   │   (face + glow + mute)   │
└───────────┴──────────────────────────┴──────────────────────────┘
```

**New components:**
- `SidebarWidget` — collapsible nav with app identity, "new chat" button, conversation list (placeholder), settings entry, mute button, time, and agent name.
- `ChatPanel` — full instant-append transcript + chat input box with send button, file attach, empty state with serif hero text.
- `CompanionArea` — large region for face + glow background + status text.
- Remove the old left panel (sys monitor), old right panel (log + file drop + input).

**Design tokens (new colour class):**
- Deep charcoal base (not pure black): `#0a0a0f` with warm tint.
- Warm amber/orange default accent.
- Refined serif font for hero moments.
- Clean sans-serif for UI text.

**Log routing rules:**
| Content | Chat panel | Companion status |
|---------|-----------|-----------------|
| `You: …` | ✅ full | One-liner |
| `Calcifer: …` | ✅ full | One-liner |
| `SYS:` / `ERR:` | ✅ full | ✅ short |
| Tool progress | ✅ full | Short status |

---

### Phase 4 — Face Animation Engine (FaceAvatar)

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)

Build `FaceAvatar(QWidget)` — a procedural face engine **inspired by the C++ FaceEngine** but rendered via QPainter:

**Core design (from C++ FaceEngine inspiration):**
- Two eyes (rounded rects with variable width/height for expression).
- Mouth (rounded rect with variable size for speech animation).
- Procedural blink cycle (3-phase: closing → closed → opening).
- Random idle eye movement offsets.
- Speaking mouth animation (random target heights, smooth interpolation).
- Listening pose (asymmetric eyes, small mouth).

**Enhancements beyond the C++ version:**
- Soft glow halo behind the face that shifts colour with emotion.
- Smooth easing on all property changes (eye size, position, mouth).
- Eyebrow-like lines above eyes for expression (raised = surprised, angled = angry).
- Rounded, soft aesthetic matching the "warm spirit/orb" character.
- 12 FPS animation timer (8 FPS in lite mode).
- Timer pauses when window minimized or companion area not visible.
- Crossfade transitions between states (150-300ms alpha blend).

**State machine:**
| `set_state()` | Face behaviour |
|---------------|---------------|
| `INITIALISING` | Slow blink open |
| `LISTENING` | Calm idle with occasional blink, subtle eye drift |
| `THINKING` | Eyes looking up/side, gentle "searching" movement |
| `SPEAKING` | Mouth cycling, eyes engaged |
| `PROCESSING` | Same as thinking |
| `MUTED` | Eyes half-closed, mouth small/flat, dimmed colours |
| Error | Brief wide-eye shock → return to previous |

**Exposed API:**
```python
face.set_state(state: str)      # Operating state
face.set_emotion(emotion: str)  # Emotion-driven colour/expression
face.set_palette(r, g, b)      # Direct colour override
```

#### [assets/face/manifest.json](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/assets/face/manifest.json)
- Reserve the sprite-pack contract for future PNG sequence art.
- Procedural face is the v1 implementation; manifest enables future sprite swap.

---

### Phase 5 — Expression Set & State Mapping

Defined inline in the FaceAvatar class — each emotion maps to eye shape, brow angle, and mouth shape parameters:

| Expression | Eyes | Brows | Mouth | Idle motion |
|-----------|------|-------|-------|-------------|
| Happy/Playful | Wide, bright | Neutral/raised | Slight smile curve | Gentle bob |
| Excited/Surprised | Very wide | Raised high | Open "O" | Quick movements |
| Thinking/Curious | Looking up/side | Slightly furrowed | Small, closed | Slow drift |
| Calm/Sleepy | Half-lidded | Relaxed | Neutral line | Slow breathing |
| Angry/Annoyed | Narrowed | Angled inward | Tight frown | Slight shake |
| Sad | Droopy | Slightly raised center | Down curve | Very slow |
| Error | Very wide briefly | Raised | Open shock | Quick shake |

---

### Phase 6 — Emotion Tag Protocol

#### [main.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/main.py)
- In `_receive_audio()`, parse `[emotion: X]` tag from output transcription.
- Strip tag before displaying in UI log.
- Pass emotion to UI via new `ui.set_emotion(emotion)` method.
- Fallback to "playful" for unknown/missing tags.

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)
- Add `set_emotion(emotion: str)` to `JarvisUI` class.
- Route emotion to both FaceAvatar and glow colour system.
- Supported emotions: `happy`, `excited`, `playful`, `proud`, `curious`, `thinking`, `focused`, `calm`, `sad`, `angry`, `annoyed`, `surprised`, `sleepy`, `error`.

#### [core/prompt.txt](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/core/prompt.txt)
- Already handled in Phase 1 — the root `prompt.txt` has emotion signal instructions.

---

### Phase 7 — Emotion-Driven Colour System

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)

Emotion → colour family mapping:

| Emotion family | Glow colour (RGB target) |
|---|---|
| happy / proud / playful | Warm gold `#FFB347` |
| excited / surprised | Hot orange/pink `#FF6B6B` |
| thinking / curious / focused | Violet/blue `#7B68EE` |
| calm / sleepy / sad | Teal/indigo `#4A90D9` |
| angry / annoyed / error | Red `#FF4444` |

**Implementation:**
- Smooth HSL interpolation between old and new colour (300ms ease-in-out).
- Glow is a large soft radial gradient behind the face in CompanionArea.
- Small accent touches on sidebar active item and button hovers.
- Sidebar and chat panel chrome stays stable.

---

### Phase 8 — Voice Swap to Leda

#### [main.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/main.py#L580)
- `voice_name="Charon"` → `voice_name="Leda"`.

#### [actions/screen_processor.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/actions/screen_processor.py#L195)
- `voice_name="Charon"` → `voice_name="Leda"`.

---

### Phase 9 — Motion Polish

#### [ui.py](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/ui.py)
- All transitions use ease-in-out.
- Crossfade between expression states (except boot and error flash).
- 150-300ms blend duration.
- Gentle hover/press states on buttons (brightness lift, not colour swap).
- New chat messages ease in with short fade/slide-up.
- Panel/tab switches with soft fade.
- `ui_lite` config flag support: reduces animation FPS to 8, disables idle personality extras.

---

### Phase 10 — QA (Verification)

Manual verification checklist:
- Idle CPU usage lower than pre-redesign baseline.
- No frame drops during 30+ second speech.
- Chat scrolls smoothly with 200+ lines.
- Quick commands work from both chat panel and companion area.
- Mute shows muted expression + stops mic.
- Every state triggers correct face animation.
- File drop works.
- Emotion tags parsed correctly, never visible/spoken.
- Voice is Leda in both main and vision module.
- No leftover HUD rings/scanners/waveform.
- Idle personality motion runs autonomously.

---

### Phase 11 — Documentation

#### [HOW_IT_WORKS.md](file:///c:/Users/DELL/OneDrive/Desktop/Vs%20Code/Calcifer/HOW_IT_WORKS.md)
- Update architecture section for new layout.
- Document FaceAvatar engine and manifest format.
- Document emotion tag protocol and parsing.
- Document colour system and emotion-family mapping.
- Update voice name to Leda.
- Note that all face artwork is original.
