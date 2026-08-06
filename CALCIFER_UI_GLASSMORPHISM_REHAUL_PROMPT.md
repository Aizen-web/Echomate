# Calcifer — Final UI Rehaul: Glassmorphism, Depth & Layout Swap

**Read `CURRENT_STATE.md` first.** It is the ground truth for what exists today — exact files,
classes, line numbers, and the public backend API. This prompt describes the next and final UI
pass on top of that: it does **not** ask you to rebuild the app from scratch, only to rework its
visual system and reflow its layout. Every public API entry point listed in `CURRENT_STATE.md`
Section 3.4 (`write_log`, `set_state`, `set_emotion`, `on_text_command`, `muted`, `current_file`,
`wait_for_api_key`, `start_speaking`, `stop_speaking`, `root.mainloop`) must keep working
unchanged after this pass. This is a visual/layout rehaul, not a backend rewrite.

---

## 0. What's Wrong Right Now (read this before touching anything)

Based on the current screenshots and `CURRENT_STATE.md`:

1. **Everything is one flat colour.** Sidebar, chat panel, and companion area currently share
   the same near-black chrome (`#0a0a0c`) with no separation between them beyond faint borders —
   the eye can't tell where one region ends and the next begins. This must be fixed with real
   layered depth, not just a slightly different shade.
2. **The face reads as unfinished, not "professional."** Right now it is two flat orange
   ellipses and a thin line beneath them (see the current screenshot in this task). It needs a
   genuine redesign: proper shape language, housing/frame, and polish — not just recolouring the
   same two circles.
3. **No sense of depth, glass, or material.** The current UI is flat colour fields on flat
   colour fields. This pass introduces true glassmorphism: translucency, blur, layered
   elevation, and light response.
4. **Layout order needs to flip.** Today: sidebar → chat → companion (face on the far right).
   Target: **sidebar stays left, the animated companion/face moves to the center as the primary
   visual stage, and the chat panel moves to the right** as a supporting panel.

---

## 1. New Layout Order

```
┌───────────┬──────────────────────────────────┬───────────────────┐
│  Sidebar  │     Companion stage (center)      │   Chat panel      │
│  (glass,  │     face + glow, largest region,  │   (glass, right,  │
│  left)    │     primary focal point           │   narrower)       │
└───────────┴──────────────────────────────────┴───────────────────┘
```

1. **Sidebar** (`Sidebar` in `ui.py:390`) stays on the left, keeps its existing functionality
   (identity, new chat, conversation list, clock, settings, collapse) — only its *material* and
   *contrast* change in this pass (Section 3).
2. **Companion stage** (`CompanionArea`, `ui.py:566`) moves from the right edge to the **center**
   and becomes the largest, most visually dominant region — it is the thing your eye lands on
   first when the window opens.
3. **Chat panel** (`ChatView` + `ChatInputBar`, `ui.py:132` / `ui.py:296`) moves from the
   center-left to the **right side**, as a narrower supporting glass panel — conversation is now
   secondary to the living face, not sandwiched in the middle.
4. Keep all existing behaviour intact through this move: auto-scroll rules, 200-message cap,
   hero empty state, file-attach chip, drag-and-drop — only the *position on screen* changes,
   not the mechanics.
5. Re-check responsiveness after the swap: at narrower window widths, decide and implement a
   sensible collapse order (recommend: chat panel is the first thing allowed to narrow/collapse
   behind a toggle before the companion stage or sidebar ever shrink, since the face is now the
   focal point and must stay legible at all sizes).

---

## 2. Material System — Real Glassmorphism

Define one consistent glass material and reuse it everywhere a panel needs to read as "floating
glass," rather than inventing a different translucency per panel.

1. **Layered blur + translucency.** Every glass panel (sidebar, chat panel, settings dialog,
   conversation rows on hover) should sit on a semi-transparent, background-blurred surface — so
   whatever glow/gradient is behind it visibly (but softly) shows through, rather than the panel
   being a solid opaque block.
2. **Edge treatment.** Give every glass panel a thin, soft-glowing top/inner edge highlight — as
   if light is catching the top rim of the glass — plus a very subtle outer drop shadow so the
   panel visibly separates from what's behind it. This edge light is what will finally make the
   sidebar and chat panel read as distinct floating surfaces instead of blending into the
   background.
3. **Elevation tiers.** Establish at least three distinct depth levels and apply them
   consistently:
   - **Base layer:** the deep background gradient behind everything (Section 4).
   - **Panel layer:** sidebar and chat panel glass surfaces.
   - **Raised layer:** anything sitting on top of a panel — the active conversation row, the
     send button, hover states, the settings dialog — should read as one step more elevated
     again (slightly brighter glass, slightly stronger edge glow).
4. **Don't overdo the blur.** Text inside glass panels must stay perfectly crisp and readable —
   only the panel background blurs what's behind it, never the panel's own content.
5. Apply this same glass treatment to the **settings dialog** and any modal/overlay so the whole
   app feels like one consistent material system, not just the sidebar and chat panel.

---

## 3. Colour System — Deeper, More Vivid, Clearly Separated

This directly fixes the "everything is one colour" problem.

1. **Background base gets real depth**, not a flat hex. Build the base layer as a rich, dark
   gradient with subtle colour movement across it (for example: deep charcoal blending toward a
   near-black warm ember tone in one corner and a cooler near-black in another) — this alone
   will make the window feel less like a flat rectangle.
2. **Each elevation tier gets a distinguishable tone**, not just a different opacity of the same
   grey. Sidebar glass, chat panel glass, and the companion stage background should each be
   *readably* different from one another at a glance — through a combination of tint, blur
   strength, and edge glow — while still clearly belonging to the same palette family.
3. **Push saturation and depth on the accent colour**, not just brightness. The existing warm
   amber accent (`#FFB347` in `EMOTION_COLORS`, `ui.py:52`) and its emotion-family siblings
   (violet/blue for thinking, teal/indigo for calm, red for anger/error — see the table in
   `CURRENT_STATE.md` Section 4.4) should be deepened and enriched for this pass — think rich
   jewel-tone glow rather than pastel — while keeping the same emotional colour-family logic
   already implemented.
4. **Use gradients, not flat fills, for every accent surface** — buttons, the active
   conversation highlight, the send button, the mute pill — so even small UI elements pick up
   the same "glass catching coloured light" feeling as the big panels.
5. **Increase contrast where legibility currently suffers.** Text, icons, and borders that are
   currently low-contrast against the same-toned chrome need to be re-evaluated against the new,
   deeper backgrounds so nothing gets harder to read as a side effect of the richer colours.

---

## 4. Companion Stage (Center) — Make It the Centrepiece

1. Now that the companion stage is centered and enlarged, give its background more presence than
   the current simple radial glow: consider a deeper layered glow (multiple soft concentric
   light layers rather than one blob), a very subtle ambient texture (fine grain, soft mesh, or
   faint radial rings) behind the glow for a futuristic "energy field" feel — kept subtle enough
   that it never distracts from the face itself.
2. Keep the existing behaviour from `CompanionArea` (glow eases ~300 ms on emotion change,
   gently pulses while speaking, dims when muted, status line below, mute pill nearby) — this
   pass elevates the *material and visual richness* of the stage, not its underlying logic.
3. Since the stage is now the largest region and the primary focal point, make sure the face
   itself scales up proportionally and stays perfectly centered at every window size.
4. This is the right place to add the futuristic details the user wants: a faint glass "housing"
   or frame concept around the face (like it's being displayed inside a piece of glass
   technology rather than floating loose on a plain background), subtle rim lighting that
   echoes the current emotion colour, and gentle light bloom around the brightest parts of the
   face during speaking/excited states.

---

## 5. Face Redesign — From Placeholder to Eilik-Grade

`calcifer_face.py` currently renders two flat coloured ellipses and a line for a mouth. This is
the single biggest thing holding back the "professional" feeling and must be rebuilt, not just
recoloured.

1. **Give the face real shape language.** Replace the flat ellipse eyes with expressive,
   rounded, slightly glossy shapes that have visible depth (a soft highlight/gradient within
   each eye shape, not a flat fill) — the goal is something that reads like a polished LED/glass
   character face (in the spirit of expressive desktop-robot displays), not two paint splotches.
2. **Rebuild the expression set with intent**, covering the existing 10 modes (speaking, happy,
   mad, sad, surprised, sleepy, thinking, confused, excited, love — `calcifer_face.py:82`) so
   each one is distinguishable by shape alone, not just colour:
   - eye shape/width/curve changes per emotion (e.g. narrowed and curved for happy, wide and
     round for surprised, drooping for sleepy/sad, angled for mad/confused),
   - the mouth becomes an actual expressive shape (curve, not just a static flat line) that
     changes with emotion and animates while speaking rather than staying static,
   - keep transitions between expressions smooth (this pass is a good place to finally add the
     crossfade between expression states noted as outstanding polish in `CURRENT_STATE.md`
     Section 6).
3. **Add a subtle "housing" or frame concept** around the face if it strengthens the futuristic,
   professional read — for example a soft glass bezel or faint containing shape — but keep it
   restrained; the face's own expressiveness should still be the star.
4. **Keep the existing idle motion system** (gaze drift, blink, gentle bob — `calcifer_face.py`)
   but refine its timing/easing so it reads as more organic and less mechanical, matching the
   more polished shape work.
5. **Verify legibility at the new, larger centered size** — since the face is now the largest
   element on screen, every rendering artifact or hard edge that was easy to miss at its old
   smaller size will now be obvious, so this is worth an explicit visual QA pass at full size.

---

## 6. Chat Panel (Now on the Right) — Restyle for Its New Role

1. Since it moved from the center to a narrower right-hand panel, tighten its proportions:
   slightly more compact message bubbles, comfortably readable at a narrower width without
   feeling cramped.
2. Apply the new glass material (Section 2) and deeper colour system (Section 3) to the panel
   background, message bubbles, and input bar — bubbles should feel like they're sitting on
   glass, with a soft elevated look for the user's own messages vs. Calcifer's replies.
3. Keep all existing mechanics unchanged: instant message rendering, auto-scroll-respects-manual
   -scroll behaviour, the serif hero empty state, the file-attach chip, and the
   attach/input/send controls in `ChatInputBar`.
4. Give the send button and attach button the same "raised glass with coloured glow" treatment
   described in Section 3.4 so small controls feel consistent with the big panels.

---

## 7. Sidebar — Glass Treatment Without Losing Function

1. Apply the glass material system to the sidebar so it visibly separates from the background —
   this is the direct fix for it currently blending into everything else.
2. Strengthen the active-conversation highlight so it's unmistakable at a glance: a filled glass
   "pill" or panel behind the selected row with a soft coloured glow, versus the current subtle
   tint.
3. Keep every existing interaction intact: new chat, select conversation, rename (double-click
   or right-click), delete (hover-× or right-click), collapse-to-icons, clock, settings entry.
4. In the collapsed/icon-only state, make sure the glass treatment and active-state highlight
   still read clearly at the smaller icon size.

---

## 8. Futuristic Detailing (use judgment, keep it tasteful)

You have latitude here — the request is explicitly for a more futuristic feel. Reasonable ways
to add that without tipping into clutter:

- Thin, glowing accent lines or dividers between regions instead of plain flat borders.
- A very subtle animated shimmer or light sweep across glass surfaces on hover/focus (kept
  fast and subtle, not a constant distracting animation).
- Slightly geometric, modern iconography throughout the sidebar and controls, consistent in
  stroke weight and style.
- Consider a thin, unobtrusive top strip spanning the full window width above all three regions
  if it helps establish hierarchy (e.g. a minimal wordmark/status readout) — optional, only add
  it if it clearly improves the "hard to tell regions apart" problem rather than adding clutter.
- Keep any of this subtle enough that it never competes with the face for attention — the face
  is still the emotional centrepiece of the product.

---

## 9. Explicit Don'ts

- Don't change or break any entry point in the public API list from `CURRENT_STATE.md`
  Section 3.4 — this is purely a visual/layout rehaul.
- Don't lose any existing functionality during the reflow (conversation switching, rename,
  delete, file attach, mute, settings, reduced-motion toggle) — everything currently working
  must still work after the layout swap.
- Don't make glass panels so translucent or blurred that text becomes hard to read.
- Don't reintroduce a flat, single-tone look anywhere — every region must be visually
  distinguishable from its neighbours at a glance.
- Don't leave the face as simple flat ellipses — this must be a genuine shape/material redesign,
  not a recolour of the existing primitives.
- Don't let the futuristic detailing from Section 8 become busy or distracting — restraint over
  excess.

---

## 10. QA Checklist for This Pass

- Sidebar, companion stage, and chat panel are each instantly distinguishable from one another
  at a glance, with no flat single-colour blending.
- The face is centered, larger, and visibly more polished/expressive than the current two-ellipse
  version, at every one of its 10 emotion modes.
- Chat panel functions identically to before, just relocated to the right and restyled.
- All glass panels stay legible: no text readability regressions anywhere.
- Emotion colour changes still ease smoothly and now read as richer/deeper, not just brighter.
- Every item in the public API list and every existing interactive feature still works after
  the reflow.
- Reduced-motion/lite mode still disables the heavier motion additions from this pass
  appropriately (shimmer sweeps, extra glow pulsing, etc.).

---

## 11. Definition of Done

This rehaul is complete when: the layout reads sidebar → centered companion stage → chat panel
(right), every region is clearly separated through real glassmorphism and layered colour depth
rather than one flat tone, the face has been genuinely redesigned into an expressive,
professional, Eilik-grade character rather than flat ellipses, the whole UI feels vivid, deep,
and futuristic without sacrificing legibility or any existing functionality, and the full QA
checklist above passes.
