# Calcifer — UI Look & Feel Prompt for CLI Coding Agent

**Paste this alongside `CALCIFER_REDESIGN_AGENT_PROMPT.md`.** That file covers the animation
engine, emotion protocol, and rebrand logic. This file is purely about **layout, visual design,
and moment-to-moment functionality** — what the interface should look like and how someone
should be able to click through it. No code included — this is a design brief to implement
against.

Reference mood: a dark, premium, editorial-feeling product screen — soft ambient glow instead of
flat colour blocks, generous negative space, a calm neutral chrome with one warm accent colour
doing all the visual "talking," clean sans-serif UI text, and a large elegant serif moment
reserved for a hero/title state. Nothing about it should look like a generic dashboard or a
sci-fi HUD. It should look like a considered, expensive product — closer to a modern AI studio
tool than a gadget interface.

---

## 1. Overall Visual Direction

1. **Base palette:** near-black / deep charcoal chrome (not pure black — give it a very slight
   warm or cool tint so it doesn't look flat), with one primary accent colour family that the
   emotion system can shift (warm amber/orange as the resting default, per the emotion-colour
   plan in the other prompt).
2. **Depth through light, not borders.** Prefer soft glow, gentle gradients, and subtle blur
   over hard outlines. Panels should feel like they're floating in soft ambient light rather
   than being boxed in with visible strokes everywhere. Where borders are needed, keep them
   thin, low-contrast, and slightly translucent.
3. **One clear focal point at a time.** The animated face/orb is the emotional centre of the
   screen — everything else (sidebar, chat, buttons) should be visually quieter than it, using
   muted tones, so the face's colour is what draws the eye.
4. **Typography contrast.** Use a refined serif for any large hero/branding moment (app name,
   empty-state headline) and a clean modern sans-serif for all functional UI text (buttons,
   labels, chat, timestamps). Don't mix more than these two type families.
5. **No harsh, saturated, or clashing colour fields.** Avoid the flat/neon "weird colour"
   feeling of the old build entirely — every colour on screen, including emotion-driven glow,
   should read as part of one cohesive lighting scheme, like the whole window is lit by one
   warm light source rather than painted in disconnected blocks.
6. **Generous spacing.** Favour breathing room over density. It should feel calm to look at even
   when idle.

---

## 2. Layout Architecture

Three regions, matching the "sidebar + chat + companion" structure requested:

```
┌───────────┬─────────────────────────┬───────────────────────────┐
│  Sidebar  │   Chat panel            │   Companion area          │
│ (tabs /   │   (conversation list /  │   (face, glow background, │
│  nav)     │   active transcript)    │   mute + quick controls)  │
└───────────┴─────────────────────────┴───────────────────────────┘
```

- **Sidebar (left, narrow):** navigation only — no system stats, no resource monitors, nothing
  technical. This is a clean product, not a control panel.
- **Chat panel (left-center):** the actual conversation — message history and the input box.
- **Companion area (right, largest region):** the animated face sits here, roughly centred
  within its region, sitting on top of the ambient glow background, with a small mute control
  nearby and minimal supporting status text underneath it.

This mirrors the reference screenshot's split between a compact left conversation column and a
large, calm right-hand preview/stage area — except here the "stage" holds the living face
instead of a code preview.

---

## 3. Sidebar

1. **Purpose:** switch between conversations/contexts and access settings — nothing else.
   Explicitly **do not** include a system/resource-monitor tab or entry point in this build.
2. **Contents, top to bottom:**
   - App identity mark (small icon/wordmark for Calcifer) at the top.
   - A "new chat" action, clearly the most prominent item.
   - A scrollable list of past conversations/sessions, each with a short title and a subtle
     timestamp — collapse long titles rather than wrapping awkwardly.
   - A settings entry near the bottom (voice, theme, emotion/colour preferences,
     reduced-motion/lite-mode toggle from the other prompt).
3. **Behaviour:** the sidebar should be collapsible to icons-only for a narrower view, and the
   active/selected conversation should be clearly highlighted with the accent colour at low
   intensity — not a jarring full-colour block.
4. **Should feel optional to look at.** A user should be able to ignore it entirely while
   focused on the chat and the face.

---

## 4. Chat Panel

1. **Message list:** clean, readable message bubbles or a flat timeline (pick one consistent
   style) with clear visual distinction between the user's messages and Calcifer's replies —
   distinction through subtle background tone and alignment, not loud colour contrast.
2. **No emotion tag ever visible here.** The hidden emotion marker described in the other prompt
   must never leak into this view — only the clean reply text.
3. **Instant rendering.** Messages append immediately, no character-by-character typing effect,
   matching the debloat requirement from the other prompt.
4. **Input box** pinned to the bottom of this panel: a rounded, softly bordered text field with
   a placeholder like "Message Calcifer…", an attach/file button, and a send button that's
   disabled/dimmed until there's text to send.
5. **Empty state:** when there's no conversation yet, don't show a blank void — show a short,
   warm empty-state message (this is a good place for the large serif hero typography treatment
   from Section 1, similar in spirit to the reference screenshot's large heading).
6. **Scroll behaviour:** auto-scrolls to the latest message on new content, but stays put if the
   user has manually scrolled up to read history (don't yank their scroll position around).
7. **Everything here must be genuinely functional**, not decorative: sending updates the
   transcript immediately, the conversation list in the sidebar reflects new/renamed chats, and
   switching conversations swaps the visible transcript correctly.

---

## 5. Companion Area (Face + Background)

This is the region the user described as "the main area with the face" — make it the visual
centrepiece.

1. **Background glow, not a background colour.** Build this as a soft, large, blurred glow
   shape sitting behind/around the face — similar in spirit to the warm blurred orb glow in the
   reference screenshot — rather than a flat coloured rectangle. The glow's hue and intensity is
   what shifts with emotion (per the colour system in the other prompt); its shape and softness
   should stay consistent so only the colour and gentle intensity pulsing change.
2. **The face sits on top of, and reacts with, that glow** — for example, glow intensity can
   rise slightly while Calcifer is speaking and settle when idle, so the whole area feels alive
   together rather than the face and background being two unrelated layers.
3. **Face redesign requirement — this must look noticeably better than the previous version.**
   Concretely:
   - Replace whatever felt "off" about the old face (state this to the agent as: too static,
     too crude, or too literal — whichever applies once the old asset is reviewed) with a
     softer, more polished, more expressive design.
   - Expressions should read clearly at a glance — happy, thinking, listening, etc. should be
     distinguishable even at small size, using eye shape, subtle brow/mouth cues, and motion,
     not just colour.
   - Motion should feel organic: gentle bob/breathing motion at idle, natural blink timing (not
     metronomic), and smooth easing into and out of every expression change — never a stiff or
     mechanical snap between frames.
   - Keep the face relatively simple/abstract rather than trying to be photorealistic — an
     expressive, friendly, slightly stylized "spirit/orb" character reads better at small sizes
     and animates more believably than a detailed face would.
   - Scale and proportion the face so it feels like the natural centre of its region — not
     tiny and lost, not so large it feels cramped against the edges.
4. **Mute control:** a small, unobtrusive icon button placed near the face (for example, just
   below or to one side) — not part of a toolbar, not competing for attention. It should
   visually confirm mute state at a glance (e.g. a clear on/off icon swap) and respond instantly
   when clicked.
5. **Minimal status text beneath the face** — a single short line at most (e.g. "Listening…",
   "Thinking…") styled quietly, echoing the reference screenshot's small "Thinking…" caption
   under its main heading. No dense status blocks, no technical detail here.
6. **Quick command entry (optional, keep minimal if included):** if a quick-input affordance
   stays in this area at all, it should be a single unobtrusive field, visually much quieter
   than the main chat input in the chat panel, so it doesn't compete with it.

---

## 6. Colour & Emotion Integration in the UI

1. The **only** element that visibly shifts colour with emotion should be the companion area's
   glow (and, at low intensity, small accent touches like the active-chat highlight or button
   hover states) — the sidebar and chat panel chrome should stay visually stable so the
   interface doesn't feel chaotic when emotions change rapidly.
2. Every colour transition (glow included) eases smoothly rather than snapping, matching the
   motion-polish requirements in the other prompt.
3. Pick a small, deliberate accent palette per emotion family (see the table in the other
   prompt) and make sure every one of them still reads as "part of the same cohesive lighting
   scheme" at low intensity — test the full set side by side before committing to it, and reject
   any colour that looks disconnected or "neon" next to the others.

---

## 7. Motion & Micro-interactions

1. Buttons and interactive elements get a gentle hover/press state (slight brightness or glow
   lift) — never an abrupt colour swap.
2. Panel/tab switches (sidebar navigation, opening settings) should transition with a soft
   fade/slide rather than an instant cut.
3. New chat messages should ease in (a very short fade/slide-up) rather than popping into
   existence.
4. Keep every transition short — this should read as "polished," not "slow." Nothing should
   make the user wait to interact.

---

## 8. Functional Checklist (this must all actually work, not just look right)

- Sidebar: new chat, switch chats, delete/rename a chat (if included), open settings — all
  functional.
- Chat panel: send message, receive reply, scroll history, attach a file, auto-scroll behaviour
  as described in Section 4.
- Companion area: face reflects live operating state and emotion accurately, mute button toggles
  real mute state and updates instantly, background glow colour matches the current emotion.
- Resizing/collapsing the sidebar doesn't break the chat or companion layout.
- No system/resource-monitoring UI exists anywhere in this build.
- No emotion tag text is ever visible or spoken.
- Everything above still respects the performance and motion-polish rules from the other prompt
  — a beautiful UI that stutters is a failed UI.

---

## 9. Explicit Don'ts

- Don't reuse the old face art or animation logic as-is — it must be rebuilt to look and move
  better, not just recoloured.
- Don't bring back any system/CPU/RAM/network monitoring surface.
- Don't use flat, disconnected, "random" colour blocks anywhere — every colour choice should
  look like it belongs to the same warm ambient lighting scheme.
- Don't let the sidebar or chat panel compete visually with the companion area — they support
  it, they aren't equal partners in attention.
- Don't add borders, drop shadows, or dividers more heavily than necessary — lean on soft light
  and spacing to separate regions instead.

---

## 10. Definition of Done

The UI is complete when: the layout matches the sidebar / chat / companion three-region
structure, the sidebar has no system-check surface, the companion area's background is a soft
ambient glow (not a flat or clashing colour), the face is visibly improved — smoother, clearer,
better-animated — than the previous version, the mute button is small, clear, and instant, every
listed interaction is fully functional (not decorative), and the whole thing feels calm,
cohesive, and premium rather than busy or neon.
