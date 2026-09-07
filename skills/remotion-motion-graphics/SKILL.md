---
name: remotion-motion-graphics
description: Scaffold and drive a Remotion (React) motion-graphics studio for making animated titles, lower thirds, callouts, and transparent overlays that export into any video editor (Premiere, Final Cut, CapCut, DaVinci). Use when the user asks for Remotion specifically, wants reusable branded graphics as code, or needs transparent-alpha overlay exports for an external editor. For rendering finished videos inside Claude, prefer /hyperframes; this skill is the React/Remotion alternative.
---

# Remotion Motion-Graphics Studio

Source: "The Motion-Graphics Starter Kit" by Pouya Eti (Rangy AI). Two parts: a starter scaffold, then pro-prompt principles applied whenever a graphic feels flat.

## Part 1: The starter scaffold

Set up in an empty folder. Keep the visual design simple and neutral: a clean working starting point the user takes in their own direction, not a finished style.

1. **Scaffold.** Initialize a Remotion + TypeScript project (latest Remotion) in the current folder. Install and verify it runs.
2. **Canvas.** Shared video settings in one place: default 1920x1080 at 30fps, with resolution and fps trivial to change (user may switch to 4K / 60fps).
3. **Structure.** `src/Root.tsx` registers compositions; `src/compositions/` one file per graphic; `public/` fonts, images, audio; `out/` renders.
4. **Starter compositions.** Four minimal examples, each with a clean enter AND exit so nothing pops or cuts mid-animation, using `useCurrentFrame`, `interpolate`, `spring`, and `Easing`:
   a) Title card, b) Lower third, c) Kinetic text, d) Transparent overlay demo (badge on a TRANSPARENT background). Give each a zod schema + defaultProps so it is editable live in the Studio.
5. **Transparency + export.** Overlays must render with a real alpha channel. Put these in the README:
   - MP4: `npx remotion render <id> out/<id>.mp4 --codec=h264 --crf=18`
   - Transparent: `npx remotion render <id> out/<id>.mov --codec=prores --prores-profile=4444 --pixel-format=yuva444p10le --image-format=png`
   - PNG sequence: `npx remotion render <id> out/<id>/frame-%04d.png --image-format=png`
   Add an npm `studio` script for the live preview.
6. **README.** How to preview (`npm run studio`); how to add a new graphic (component + register in Root.tsx with id, fps/size, zod schema, defaultProps); the render commands; tips (keep text in the title-safe area; always give animations a full enter and exit; trim leading silence on sound effects).
7. **Nice to have.** Load a Google font via `@remotion/google-fonts`; show how to add a sound effect with `<Audio src={staticFile("...")} />` inside a `<Sequence>`.

When done, launch the Studio and summarize what was built and the commands the user will use most.

## Part 2: Pro-prompt principles (level up any graphic)

Apply these whenever a graphic feels flat; they work for any style or topic.

**Animation and motion**
- Every element animates in (from off-screen or opacity 0), holds, then animates fully out before the clip ends. Nothing pops in abruptly or gets cut off mid-motion. This is the single biggest upgrade separating polished from amateur.
- No robotic linear motion: add anticipation (a tiny wind-up), a little overshoot, then a settle. Spring or eased curves.
- Stagger elements so they enter one after another a few frames apart, not all at once. Cascading reveals feel intentional.
- While a graphic holds on screen, add subtle life: a gentle float, a soft glow pulse, a slow shine sweep.
- If it demonstrates a click or tap, animate a cursor moving in, pressing with a small ripple, then leaving, so the action reads as real.

**Effects and style**
- Clean and modern: prefer geometric light (a flash, an expanding ring, thin light streaks, soft glints, glow/bloom) over emoji or clip-art particles.
- One tasteful animated accent (light traveling around a border, a slow gradient shift) for a premium feel without clutter.
- Give results a payoff moment: the winner or key number gets a brief celebration (scale pop, glow, a few particles, a sound) so it lands.

**Readability and layout**
- Key text inside the title-safe area (about 10 percent margins) and legible over busy footage: subtle shadow, a scrim, or a backing shape.
- Auto-fit text: shrink long text and wrap cleanly so nothing overflows or clips.
- Clear hierarchy: one bold focal element, supporting text smaller and lower-contrast.

**Sound design**
- Synced sound: soft whoosh on entrance, click/pop on key actions, chime on success, swish on exit. Trim silence at the start of each file so the hit lands on its frame; keep levels balanced (no clipping).
- For typing or counting, one continuous soft sound over the whole duration instead of a harsh effect repeated per character.

**Reusable and on-brand**
- Fully data-driven: expose text, colors, numbers, and images as props with a schema, so it restyles without editing code.
- Define the brand once (accent colors, font, corner radius) and apply consistently to every graphic.
- Support a real image via a prop with a clean placeholder fallback.

**Workflow**
- Render a still at a key frame first to check the look before rendering the whole clip.
- Show 2 to 3 style variations before polishing one.
- Match timing to content: about a second per short line to read; keep the whole graphic within the requested length.

**Export for any editor**
- Overlays: transparent ProRes 4444 .mov (with alpha) for NLEs, or a PNG sequence for CapCut. Full scenes: MP4 (H.264, crf 18).

**Things this builds well:** title cards, lower thirds (name + role), animated logo / intro sting, Like/Subscribe/Comment/Share reminders, "watch this" card, "link in description" pop-up, comparison scoreboard, before/after reveal, animated chart, stat callout, "new / just dropped" badge, prompt box, countdown / timer, end screen, captions.

## House rules

House standards apply on top: no emojis and no em or en dashes in any on-screen text; SVG or geometric shapes over clip-art; load `high-end-visual-design` for overall look decisions.
