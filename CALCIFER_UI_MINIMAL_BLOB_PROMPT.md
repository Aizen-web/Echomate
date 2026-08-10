# Calcifer — Minimal Companion UI + Functional Expansion Prompt

**Read `CURRENT_STATE.md` first**, plus the two prior UI prompts
(`CALCIFER_UI_VISUAL_PROMPT.md`, `CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md`). This prompt
**supersedes the face-animation ambitions of both** — full facial expression rigging is now
**out of scope**. Everything else those documents established (glassmorphism material,
layered colour depth, layout regions, public API stability) still applies unless this document
says otherwise.

**If you get stuck or are unsure about any decision below, stop and ask rather than guessing.**
That applies especially to Sections 2 and 5, where some choices are intentionally left open.

---

## 0. What Changed

Facial rigging (eyes, mouth, expression shape library) was consistently the weakest part of
every previous attempt and is not worth further iteration right now. Replace it with something
simpler and easier to get right: **a single glowing blob/orb** that reacts to what's happening
and changes colour with emotion — no face, no eyes, no mouth. In exchange, put the saved effort
into (a) actually nailing the visual polish of that simpler element, and (b) meaningfully
expanding what the app *does*, surfacing the tool capabilities that already exist in
`actions/*` (see `CURRENT_STATE.md` Section 2) but aren't yet visible anywhere in the UI.

---

## 1. Scope for This Pass

Keep the three-region layout and material system from `CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md`
(sidebar / companion stage / chat panel, glassmorphism throughout, deep layered colour). On top
of that:

1. Replace the current face widget (`calcifer_face.py`) with a minimal animated blob.
2. Add a clock to the companion stage.
3. Keep the companion stage otherwise uncluttered — the brief word for this pass is **minimal**:
   the blob, its glow, and the clock are the only things living in that central region.
4. Expand functionality elsewhere in the UI (Section 5) — this is where the added value of this
   pass lives, not in the visual complexity of the companion stage.

---

## 2. The Blob — Design Spec

1. **Shape:** a soft, rounded, organic blob — think a glowing liquid/plasma orb, not a
   geometric circle and not a face. It can have gentle irregularity to its edge (a soft, slowly
   shifting outline) so it reads as alive rather than a static disc — but keep the irregularity
   subtle; this should look premium, not lava-lamp kitsch.
2. **Idle state:** slow, gentle breathing motion (soft scale/size pulsing) plus a very slow
   drifting shimmer across its surface — calm, not busy.
3. **Speaking/talking state:** the blob visibly reacts while Calcifer is talking — pulsing,
   rippling, or gently morphing in sync with speech output. If you have access to real-time
   audio amplitude from the outgoing speech stream, drive the reaction off that for a genuine
   "talking" feel; if that's not feasible in this pass, use a convincing rhythmic animated
   pattern that reads as "actively speaking" even without true audio-reactivity, and note in
   your implementation notes which approach you used.
4. **Listening state:** a distinct, calmer animated treatment from speaking — e.g. a slow
   inward pull or gentle ripple-toward-center — so listening and speaking are visually
   distinguishable at a glance without needing to read the status text.
5. **Thinking/processing state:** its own distinct motion — e.g. a slow internal swirl — again
   distinguishable from both idle and speaking.
6. **Colour behaviour — important:** the blob's colour is driven by the current emotion (reuse
   the existing `EMOTION_COLORS` table and emotion protocol from `CURRENT_STATE.md` Sections 4.3
   –4.4 — no changes needed to that system). **The colour must hold steady once set and must
   not drift, fade, or reset until the next emotion update arrives** — i.e. if Calcifer responds
   with "excited" and then goes idle waiting for the next prompt, the blob stays the excited
   colour at idle, it does not fall back to a default resting colour. Only a new incoming
   emotion value changes the colour, and that change still eases smoothly rather than snapping
   (matching the ~300ms ease already used for the glow in `CompanionArea`).
7. **Glow:** keep the soft radial glow behind the blob from the current `CompanionArea`
   implementation, synced to the same colour and easing behaviour as the blob itself, so the
   blob and its glow always read as one light source, not two independently coloured layers.
8. **Size and placement:** the blob is the clear focal point of the companion stage, centred,
   large enough to read clearly from a normal viewing distance, with room around it so it never
   feels cramped against the clock or the stage edges.

---

## 3. Clock

1. Add a clock to the companion stage — minimal, glass-styled, consistent with the rest of the
   material system (Section 2 of `CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md`).
2. Keep it visually quiet: it should support the stage, not compete with the blob for attention.
   A small digital time readout in a restrained, modern typeface is the safe default; a subtle
   glass-ring analog treatment is also reasonable if it stays minimal and doesn't add visual
   noise.
3. Placement: somewhere that doesn't crowd the blob or the status line beneath it — for example
   a corner of the companion stage, or integrated quietly into a thin top strip if one exists
   from the prior rehaul pass.
4. Updates live, naturally, with no jarring re-render each tick.

---

## 4. Visual Bar for This Pass

Everything here still applies and is not being relaxed:

- **Glassmorphism** — blur, translucency, layered edge light, exactly as specified in
  `CALCIFER_UI_GLASSMORPHISM_REHAUL_PROMPT.md` Section 2.
- **Soft glows** — the blob's glow, hover states, active highlights — nothing should ever be a
  hard-edged flat colour fill.
- **Minimalist** — resist the urge to add decorative elements to the companion stage beyond the
  blob, its glow, and the clock. Functional richness belongs in the sidebar/chat expansion
  (Section 5), not in the companion stage.
- **Futuristic** — consistent with the detailing guidance already given (thin glowing dividers,
  restrained geometric iconography, tasteful shimmer on interaction).
- **"4K UHD" crispness** — every asset, gradient, and animated element must render perfectly
  smooth and sharp at high resolution: no visible banding in gradients, no pixelation on the
  blob's edge or glow falloff, no aliasing on any curved shape. Test at a large window size
  specifically to confirm nothing that looked fine small starts looking rough when scaled up.

---

## 5. Functional Expansion — Think Like Tony Stark

The companion stage is now intentionally minimal, so this is where the app should feel more
capable, not less. Calcifer already has real tool capability sitting unused in `actions/*`
(17 modules — see the full list in `CURRENT_STATE.md` Section 2: apps, web search, weather,
messaging, reminders, YouTube, screen/webcam analysis, computer settings, browser automation,
file management, desktop control, code help, multi-file project building, computer
control, game updates, flight search, file processing) plus a background task queue
(`agent/task_queue.py`) that currently has no visible presence in the UI at all. Surface this.
You have real latitude here — build the version of this that feels most like a capable,
unobtrusive assistant a person would actually want running quietly in the background. Some
concrete directions to consider, use judgement on which combination fits best:

1. **A quick-command palette or launcher.** A fast, keyboard-triggerable overlay (e.g. a single
   shortcut opens it) listing common actions — open an app, run a web search, check weather,
   set a reminder — so frequent tool use doesn't require typing a full sentence into chat every
   time.
2. **A live activity feed for background tasks.** Since `agent/task_queue.py` already tracks
   queued/running work, give it a small, unobtrusive glass panel or drawer (collapsed by
   default) showing what Calcifer is currently doing or has just finished — e.g. "Downloading
   game update," "Reminder set for 6 PM," "Searching the web" — so multi-step tool use isn't
   invisible.
3. **Lightweight contextual chips near the companion stage or sidebar** — for example a compact
   weather chip, or an upcoming-reminder chip — surfaced quietly when relevant, not as permanent
   dashboard clutter, matching the minimal companion-stage rule from Section 4.
4. **Quick status toggles** for things that are currently only keyboard shortcuts (mute is F4
   today) — small, glassy icon toggles for mic mute, and indicators for when browser automation,
   screen/webcam analysis, or computer-control actions are actively running, so the user always
   knows when Calcifer has an active hand on their system.
5. **Notification toasts** for completed background actions (reminder fired, file operation
   finished, download complete) — small, glass-styled, auto-dismissing, non-blocking.
6. **A settings expansion** beyond the current colour-palette/reduced-motion toggle — surface
   controls for things like default voice confirmation, per-tool permission toggles (e.g.
   confirm before computer-control or browser-automation actions run), and notification
   preferences.

Pick and implement the set of these that gives the most real functional value without violating
the "minimal companion stage" rule — most of this belongs in the sidebar, a collapsible drawer,
or lightweight overlays, not the center stage.

---

## 6. Non-Regression

- Every public API entry point in `CURRENT_STATE.md` Section 3.4 keeps working exactly as
  documented.
- Every existing feature (conversation switching/rename/delete, file attach, settings, mute,
  emotion protocol, voice) keeps working through this pass.
- The emotion → colour mapping logic itself is unchanged — this pass only changes what visual
  element that colour is applied to (the blob instead of a face) and reinforces that the colour
  must persist between prompts rather than reset.

---

## 7. QA Checklist

- Blob is clearly distinguishable in idle, listening, thinking, and speaking states through
  motion alone.
- Blob colour changes only on a new emotion value, eases smoothly, and holds steady afterward —
  confirm it does **not** drift back to a default colour while idle.
- Clock is legible, unobtrusive, and updates smoothly.
- Companion stage still reads as minimal — nothing beyond blob, glow, clock, and status line.
- Whatever functional expansion features you implement from Section 5 are fully functional, not
  decorative, and don't clutter the companion stage.
- No banding, pixelation, or aliasing on the blob or its glow at large window sizes.
- All non-regression items in Section 6 verified.

---

## 8. Definition of Done

This pass is complete when: the companion stage shows only a polished, smoothly animated
glowing blob (with distinguishable idle/listening/thinking/speaking motion and emotion-persistent
colour) plus a minimal clock, the glassmorphism/soft-glow/futuristic/high-resolution visual bar
from prior passes is fully met, at least one meaningful piece of functional expansion from
Section 5 is implemented and genuinely useful, and every item in the QA checklist passes.
