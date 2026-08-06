# Calcifer Redesign — Implementation Prompt for CLI Coding Agent

**Paste this whole file to your CLI coding agent (Claude Code, etc.) as the task brief.**
It describes *what* to build and in *what order*, in plain language — no code included.
The agent should read `GUI_REDESIGN_PLAN.md` and `HOW_IT_WORKS.md` in the repo first, since
they contain the existing architecture this plan builds on top of.

---

## 0. Mission Statement

You are rebuilding the desktop assistant currently called **Jarvis** into a new character called
**Calcifer** — a small, expressive, colour-shifting desktop companion, visually and behaviourally
inspired by the *feel* of the Eilik desktop robot (rich facial expressions, snappy but smooth
reactions, idle personality quirks) — **not** a copy of Eilik's artwork or firmware.

Two systems must be delivered together and must feel like one coherent product:

1. **An animated expressive face** that replaces the current sci-fi HUD (rings, scanners,
   waveform bars, grid dots).
2. **An emotion → colour system**: every AI reply carries a machine-readable emotion value:
   the UI strips that value out of the visible text, and uses it to (a) pick a facial
   expression/animation clip and (b) recolour the glow/background/accent colours of the
   whole companion in real time.

Everything must run smoothly — no stutter, no dropped frames, no jarring pops between states.
Debloating the current UI is a prerequisite, not an afterthought, because the old HUD's constant
60 FPS repainting is what would make new animations feel janky.

Do not write any code yet in your first pass — first produce a short written implementation plan
per phase below, confirm the open decisions in Section 9, *then* begin implementation phase by
phase, committing/checkpointing after each phase.

---

## 1. Ground Rules (apply to every phase)

- Keep the public interface the backend (`main.py`, `actions/*`, `agent/*`, `memory/*`) uses to
  talk to the UI stable. Existing calls like "write a log line" and "set the current state"
  must keep working even after internal refactors — add new optional entry points rather than
  breaking old ones.
- Do not import, trace, decompile, or reference actual Eilik firmware, artwork, or sounds.
  All face art and animation must be original, only *inspired by* the same expressive-robot
  feeling.
- Every animation change must be interruptible and must never hard-freeze the interface thread.
  Long-running work (file I/O, network calls, image decoding) must never happen on the same
  thread that draws frames.
- Every new visual system needs an "off ramp": if new assets are missing or malformed, fall back
  to a simple static placeholder rather than crashing.
- Respect a hard performance budget: idle CPU usage for the interface should end up lower than
  it is today, not higher, even after adding face animation and colour theming.
- Rename the product from Jarvis to Calcifer everywhere it is user-visible (window title, header
  text, transcript speaker label, spoken self-references in the personality file) while leaving
  internal class/function names as-is wherever renaming them would create unnecessary churn.

---

## 2. Phase Overview

| Phase | Name | Goal |
|---|---|---|
| 1 | Rebrand | Jarvis → Calcifer everywhere user-visible |
| 2 | Debloat | Strip heavy, decorative rendering so there is CPU/GPU headroom |
| 3 | Layout split | Separate lightweight "companion" view from a full chat log view and a system-stats view |
| 4 | Face engine | Build the animation player that can show and blend between expression clips |
| 5 | Face art & state mapping | Define what each state/emotion looks like and wire it to real triggers |
| 6 | Emotion protocol | Define and parse the emotion tag the AI sends with every reply |
| 7 | Colour system | Drive glow/background/accent colour from the parsed emotion, in sync with the face |
| 8 | Voice swap | Switch the spoken voice to Leda |
| 9 | Motion polish | Crossfades, idle micro-motion, easing curves, no hard pops |
| 10 | QA pass | Performance, functional, and visual test checklist |
| 11 | Docs | Update project documentation to describe the new system |

Work through these in order. Do not start face art (Phase 5) before the animation engine
(Phase 4) can already display *something*, even a placeholder square that changes colour.

---

## 3. Phase 1 — Rebrand to Calcifer

Step by step:

1. Search the whole project for the word "Jarvis" (and casing variants) in anything the user
   actually sees: window title, header label, tab titles, transcript prefixes ("Jarvis: ..."),
   tray/notification text, any printed startup banner, and the personality/system prompt file.
   Replace with "Calcifer".
2. Leave purely internal identifiers (class names, file names, variable names, log tags meant
   for developers only) untouched unless renaming them is trivial and low-risk — a full symbol
   rename is optional cleanup, not required for this task.
3. Update the personality/system prompt so the assistant refers to itself as Calcifer and its
   tone matches a small, warm, slightly mischievous fire-spirit/companion character rather than
   a formal butler-style assistant.
4. Do a final pass with a search tool to confirm no user-facing "Jarvis" string remains.

---

## 4. Phase 2 — Debloat the Existing Interface

The current interface spends most of its per-frame budget on decoration rather than function.
Before any new animation work begins, strip this down.

1. **Kill the character-by-character log typing effect.** Replies should appear as complete
   lines instantly, not typed out over time. Preserve existing colour-coding for different kinds
   of log lines (user text, assistant text, system messages, errors, file events).
2. **Cap and cull scrollback.** Define a maximum number of retained lines for the always-visible
   status area (a handful of lines) and a larger cap for the full transcript view (on the order
   of a hundred), dropping oldest lines once the cap is hit.
3. **Throttle or remove the old animated HUD elements** — glow halos, spinning rings, scanner
   arcs, tick marks, crosshairs, corner brackets, particle effects, and the waveform bar strip.
   These are being replaced entirely by the face engine in later phases, so it is fine to delete
   this code once the face engine is functional; until then, throttle its refresh rate down
   drastically and pause it whenever the window is minimized or not focused.
4. **Slow down system-resource polling** (CPU/RAM/network/GPU/temperature). This does not need
   to update more than a few times per minute, and should not run subprocess calls at all when
   its view isn't currently visible.
5. **Stop idle animations on drag-and-drop zones** — animate the file-drop area only while a
   file is actively being dragged over it, not constantly.
6. Confirm, before moving on, that measured idle CPU usage of the interface has gone down
   compared to the pre-debloat baseline.

---

## 5. Phase 3 — Split the Layout Into Focused Views

Replace the single crowded main window with a small number of clearly separated views:

1. **Companion view (default on launch).** Shows only: the animated face, a one-to-few-line
   status strip, a small quick-command text box, a compact file-drop target, and mute/fullscreen
   controls. Nothing else. This is the view people leave open while talking to Calcifer.
2. **Chat view.** Shows the full instant-append transcript and a proper chat input box that
   drives the exact same backend command pathway as the companion view's quick box.
3. **System view** (can be collapsible or its own tab). Shows resource monitors, polled slowly,
   and only actively updates while this view is on screen.
4. Add simple navigation between these views (tabs or an equivalent) and make the companion view
   the one shown by default at startup.
5. Decide the routing rule for every kind of log line: does it show on the companion status
   strip, the full chat view, both, or neither. Write this rule down explicitly before
   implementing it (see the routing table pattern already sketched in `GUI_REDESIGN_PLAN.md`
   for a starting point) — long tool-progress output, for example, should not spam the compact
   status strip.

---

## 6. Phase 4 — Build the Face Animation Engine

This is the core new component. Build it as a self-contained module so the rest of the app
only ever calls two operations on it: "play this state" and "recolour to this palette."

1. **Choose an animation representation.** The recommended approach is a lightweight frame
   sequence player: each expression is a short ordered sequence of images played at a fixed
   low frame rate (roughly 8–15 frames per second is plenty for an expressive-but-not-busy
   character — do not aim for full video framerates, it wastes CPU for no visible benefit).
2. **Define a manifest format** describing, for every named clip: how many frames it has, what
   frame rate it plays at, and whether it loops continuously or plays once and then returns to
   whatever the previous looping state was.
3. **Build the player** so that:
   - only one clip is "active" at a time, plus an optional clip currently fading in/out during
     a transition,
   - advancing a frame and repainting is the *only* work done on every tick — no random number
     generation, no recomputation of layout, no unrelated work in the paint path,
   - the timer pauses completely when the window is minimized, unfocused, or the companion view
     is not the visible tab,
   - if a requested clip's assets are missing, it falls back to a safe default expression
     instead of erroring.
4. **Expose a simple state-setting entry point** other parts of the app call whenever the
   assistant's status changes (idle, listening, thinking, speaking, muted, error), and keep this
   separate from the emotion-driven expression override added in Phase 6, so both status-driven
   and emotion-driven expression changes can coexist without conflicting.
5. Ship with placeholder art first (simple shapes or a minimal sketch face) so the engine can be
   verified end-to-end before real character art exists.

---

## 7. Phase 5 — Define the Face's Expression Set and State Mapping

1. Define the full list of expression clips needed, at minimum: idle, listening, thinking,
   speaking, muted, and error, plus one clip per supported emotion family from Phase 6
   (see the table in Section 8). Some of these can share art with small variations rather than
   needing entirely separate clip sets — that's a design choice to make explicitly, not by
   accident.
2. For each clip, describe in writing (a design note, not code) what it should visually convey:
   eye shape/openness, any mouth or "expression line," head tilt, and any idle motion like
   blinking. Keep the character consistent — small, warm, expressive, a little mischievous —
   across every clip.
3. Map the assistant's operating states to clips:
   - idle → calm loop with occasional blink,
   - listening → alert/attentive loop,
   - thinking → searching/curious loop (this is a good place for a signature "flame flicker" or
     equivalent motif if the character has a fire/spark visual theme),
   - speaking → an expression cycle that loops for as long as speech audio is playing,
   - muted → a distinct "quieted" pose (dimmed, closed mouth, or similar),
   - error → a short one-shot reaction clip that automatically returns to whatever state was
     active beforehand once it finishes.
4. Add subtle idle personality: e.g., an occasional random blink or small idle gesture even when
   nothing is happening, so the character reads as "alive" rather than static between events.
5. Note explicitly: operating-state clips (idle/listening/thinking/speaking/muted/error) and
   emotion clips (Phase 6) both compete for "what does the face show right now" — decide and
   document the priority rule (for example: operating state controls the *pose/animation*,
   emotion controls the *palette and expression intensity/tint layered on top*, rather than two
   fully separate and conflicting animation sets).

---

## 8. Phase 6 — Emotion Tag Protocol

1. **Define the wire format.** Every AI reply should begin with one compact, machine-readable
   emotion marker before the human-readable reply text — something the UI can reliably detect
   and strip out before the reply is ever shown to the user or spoken aloud.
2. **Define the supported emotion vocabulary.** At minimum: happy, excited, playful, proud,
   curious, thinking, focused, calm, sad, angry, annoyed, surprised, sleepy, and an error state.
   Any emotion value the model sends that isn't recognized should fall back to a safe default
   (e.g. "playful") rather than breaking the UI.
3. **Update the assistant's instructions** (the personality/system prompt) so it is told, very
   explicitly, to always begin its response with exactly one emotion marker from the approved
   list, and that this marker will be removed before the user sees or hears the reply — so it
   should never be spoken aloud or shown as visible text.
4. **Parse defensively.** If a reply arrives with no marker, a malformed marker, or an
   unrecognized value, handle it gracefully (default emotion, log a warning, don't crash and
   don't leak the raw marker text into the visible transcript or spoken audio).
5. **Wire the parsed emotion into two places simultaneously**: the face engine's expression
   layer (Phase 5) and the colour system (Phase 7), so both update together the moment a reply
   arrives — they must never visibly drift out of sync (e.g., a happy-coloured glow with an
   angry-looking face).

---

## 9. Phase 7 — Emotion-Driven Colour System

1. **Group emotions into colour families** rather than giving all fourteen-plus emotions
   unrelated colours — this keeps the palette legible instead of chaotic. A reasonable starting
   grouping:

   | Emotion family | Glow colour direction |
   |---|---|
   | happy / proud / playful | warm gold / orange |
   | excited / surprised | hot orange / pink |
   | thinking / curious / focused | violet / blue |
   | calm / sleepy / sad | teal / indigo |
   | angry / annoyed / error | red |

2. **Decide what actually changes colour**: likely candidates are a glow/halo behind or around
   the face, the background panel of the companion view, and small accent elements (status text,
   borders). Keep the change tasteful and readable — this is a companion character, not a strobe
   light. Full-saturation flashing should be reserved for very short emotional spikes, not
   sustained states.
3. **Animate colour changes, don't snap them.** When the emotion changes, the colour should ease
   from the old palette to the new one over a short, smooth duration rather than jump instantly,
   matching the "flawless, smooth" requirement.
4. **Keep colour changes independent of expensive repaint work.** Recolouring should be cheap —
   ideally just a tint/overlay applied to already-rendered frames or a colour property change,
   not a full re-render of complex artwork per frame.
5. **Respect accessibility and taste**: make sure text and status labels remain readable against
   every possible glow colour (test the darkest and brightest combinations), and avoid colour
   combinations that could be uncomfortable to look at for extended periods.

---

## 10. Phase 8 — Voice Swap

1. Locate every place the spoken voice is configured for both the main conversation session and
   the screen/camera vision module (there are currently two separate places this is set).
2. Change the configured voice to **Leda** in both locations so the main assistant and the
   vision module sound consistent with each other.
3. Confirm the change takes effect after a full restart, since there is no in-app live setting
   for this today (unless you choose to add one — optional, not required).

---

## 11. Phase 9 — Motion Polish (do this after everything above works functionally)

1. **Crossfade, never hard-cut**, between expression clips — except for two intentional
   exceptions: the very first boot-up appearance, and a deliberate short "flash" for the error
   state, which is allowed to feel sudden because that's the point.
2. Use a short blend duration for transitions — long enough to feel smooth, short enough to
   still feel responsive (a small fraction of a second, not multiple seconds).
3. Add gentle easing (ease-in/ease-out rather than linear) to any moving element: colour
   transitions, glow intensity changes, and any positional motion.
4. Re-verify frame budget: confirm each redraw stays cheap and that nothing in the paint path
   allocates memory, hits disk, or does randomness-heavy work every frame.
5. Add a "lite" or reduced-motion mode toggle (config flag) that lowers animation frame rate and
   disables idle-personality extras, for lower-powered machines — this is optional polish but
   recommended.

---

## 12. Phase 10 — QA Checklist

Run through all of the following before calling this done:

**Performance**
- Idle CPU usage of the interface is measurably lower than before the redesign.
- No visible frame drops or stutter while the assistant is speaking continuously for 30+ seconds.
- The full chat transcript view scrolls smoothly with a couple hundred lines present.

**Functional**
- Quick commands still work from the companion view.
- Chat view input reaches the exact same backend pathway as companion-view input.
- Mute immediately shows the muted expression and stops the microphone.
- Every operating state (thinking/speaking/listening/muted/error) triggers the correct clip at
  the correct moment.
- File drop still works from the companion view.
- System stats only update while that view is visible.
- Every emotion tag in the approved vocabulary produces the correct face + colour combination,
  and an unrecognized/missing tag falls back safely without visible glitches or leaked raw tags.
- The spoken voice is confirmed as Leda in both the main session and the vision module.

**Visual**
- No leftover rings, scanners, grid dots, or waveform bars anywhere in the companion view.
- Every state and emotion change blends smoothly rather than popping.
- Idle personality motion (blinks, small gestures) runs on its own without user input.
- Text stays legible against every glow colour in the palette.

---

## 13. Phase 11 — Documentation

1. Update the project's architecture/how-it-works documentation to describe: the new view
   layout, the face animation engine and its manifest format, the emotion tag protocol and how
   it's parsed and stripped, the colour system and its emotion-family mapping, and the new voice
   name.
2. Note clearly, in the same document, that all face artwork is original and not derived from
   any third-party robot's actual assets.
3. Update any customization/tips section so a future maintainer knows where to add a new
   emotion, a new expression clip, or change the colour palette.

---

## 14. Open Decisions — Confirm Before Coding

The agent should ask the user (or state its chosen default and proceed) on each of these before
implementation, since they affect how much work each phase is:

1. Should internal code identifiers (class/function/file names still referencing the old name)
   be renamed too, or only user-visible strings?
2. Should there be a static fallback image if the animation asset pack is ever missing entirely?
3. Which view should be default on startup — confirmed as the companion view unless stated
   otherwise.
4. Should the quick-command box remain on the companion view, or move entirely to the chat view?
5. What is the target animation frame rate, and what is the reduced rate for "lite" mode?
6. Should colour changes apply only to the immediate glow around the face, or extend to the
   whole window background?
7. Should there be a manual override to force a specific expression for testing (a debug-only
   control), independent of both operating state and emotion?

---

## 15. Definition of Done

The redesign is complete when: the interface is measurably lighter than before, the old HUD
decoration is fully gone, the companion consistently identifies as Calcifer, every AI reply
carries a hidden emotion tag that is parsed reliably and never shown or spoken, the face and
background colour update together and smoothly for both operating state and emotion, the voice
is Leda everywhere it's configured, and the full QA checklist in Phase 10 passes.
