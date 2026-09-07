---
name: carousel-builder
description: Turn one idea into a finished, on-brand Instagram carousel. Use this whenever the user wants to create a carousel, a multi-slide post, an Instagram/LinkedIn slide deck, or swipe post, or says things like "make a carousel about X," "turn this into slides," "build me a carousel from this idea/newsletter," or "I need a swipeable post." It reads the user's brand config (colors, fonts, handle), builds each slide from a bundled component library and templates, renders them to 1080x1350 PNGs, and checks them visually. Trigger it any time the user wants a designed multi-slide social post, even if they only have a rough idea or an existing piece of content to adapt.
---

# Carousel Builder

A carousel is the highest-leverage organic format: it earns saves, shares, and dwell time. This skill takes one idea and produces finished 1080x1350 PNG slides, designed from the user's brand and a real component library, rendered from HTML, and visually checked before hand-off. No Canva, no designer.

**What's bundled** (this is what makes the output look designed, not like a school project):
- `assets/base.css` — a component library: 4-corner chrome, numbered section heads, label/body spec rows, pills, CTA buttons, elevation shadows. All driven by your brand variables.
- `templates/cover.html`, `templates/body.html`, `templates/cta.html` — ready-made slide layouts that use the library.
- `scripts/render.py` — turns the HTML into crisp PNGs.

## Step 1 — Load or create the brand config

Look for `brand-config.md` in the project or skill folder. If it exists, read it. If not, create it with the user from `assets/brand-config-template.md`. You need: a **light** and a **dark** background color, **one accent** color, a **display** font and a **body** font (Google Fonts so anyone can use them), the **handle**, the **sign-off name**, and a **series label** for the top-left chrome. One accent color only — restraint is what makes it look designed.

## Step 2 — Plan the deck

Decide the slide count and arc. A strong default is 7 to 9 slides: a **cover**, 4 to 6 **body** slides, and a **CTA**. Pick a cover hook that stops the scroll (specific number + noun, a contrarian claim, or a clear promise). One idea per body slide, building an argument: problem → the turn → steps or proof. The CTA asks for one action (follow, save, or "comment [keyword]").

If adapting existing content (a newsletter, a transcript), pull the single throughline and the best 4 to 6 points; don't cram everything in.

## Step 3 — Build the slides from the templates

Make an `html/` folder. For each slide, copy the closest template into it and rename in order (`slide-01.html`, `slide-02.html`, …):
- **Cover** → `templates/cover.html`
- **Body slides** → `templates/body.html` (the label/body "spec rows" layout reads as premium; great for tips, steps, frameworks)
- **CTA** → `templates/cta.html`

In every copied file, do two things:
1. **Set the brand once** in the `<head>`: paste your chosen Google Fonts `<link>`, and fill the `:root` block with your colors and font names from `brand-config.md`. (Keep it identical across slides so the deck feels like one hand.)
2. **Write the content** into the existing classes. Don't invent new structure — use what the library gives you (`.head`, `.sub`, `.rows`/`.row`/`.rlabel`/`.rbody`, `.pills`, `.cta-btn`, `.display.h-cover`, `.lead`).

Design rules baked into the library, keep them intact:
- **Alternate backgrounds** — `.slide light` / `.slide dark`, never two of the same in a row. Give the cover and CTA the dark treatment for contrast.
- **One accent color**, on one or two things per slide (a key word, the page number, the CTA).
- **Vertically centered** content (`.main` does this) so no slide is top-heavy or half-empty.
- **Big, confident type.** If text is too long, cut words rather than shrink the font.
- Keep the 4-corner chrome consistent: series label top-left, page number top-right, name + swipe bottom.

## Step 4 — Render to PNG

```bash
python3 scripts/render.py
```

It turns every `html/slide-*.html` into a `slides/slide-*.png` at 1080x1350 (2x for crispness), auto-detecting the `html/` folder next to it. It uses headless Chrome (already on most machines); if Chrome is in a non-standard location it prints how to set the `CHROME` path.

## Step 5 — Check every slide, then hand off

Open each rendered PNG and actually look at it. Fix and re-render. Check for:
- Text cut off at the edges or overflowing
- Top-heavy or half-empty slides (let `.main` center them)
- Two adjacent slides with the same background
- The accent color used too much (pull it back to one or two elements)
- Headlines too small or body text too cramped

Don't call it done until every slide is clean. Then tell the user where the PNGs are (`slides/`), in order, ready to upload.

## Keep it yours

This is a starting system, not a straitjacket. Encourage the user to evolve `brand-config.md`, `assets/base.css`, and the templates over time so their carousels build a recognizable look — a fleet of slides that feel like one creator's hand.
