---
name: lead-magnet-builder
description: Turn an existing asset into a high-converting lead magnet. Use this whenever the user wants to create a lead magnet, freebie, opt-in, downloadable, guide, checklist, or PDF to grow their email list or capture leads, or has an existing asset (a YouTube video, a newsletter, a blog post, a PDF, a webinar, a slide deck, a transcript) they want to repurpose into one. Triggers on things like "make a lead magnet from this," "turn this video into a freebie," "create an opt-in from my newsletter," "I need a downloadable for my content," or "build me a guide I can give away." It extracts the single most valuable, self-contained win from the source, reshapes it into a lean premium guide or checklist, and produces a clean PDF the user can promote. Trigger it any time the user wants to convert content or expertise into a lead-capturing asset.
---

# Lead Magnet Builder

A lead magnet is not a content dump. It is one sharp, complete win that solves a single specific problem for a specific person, fast. The best ones are made from something the user already has: a video, a newsletter, a talk. This skill finds the win inside an existing asset and turns it into a clean, promotable PDF.

## Step 1 — Get the source, the goal, and the branding

Ask for three things (or pull them from context):

1. **The source asset to repurpose.** Most commonly one of:
   - a **YouTube video transcript** (paste it, or give the link and the transcript if you can't read the video),
   - a **newsletter** issue, or
   - an **Instagram post / caption** (or a short series of them).

   A blog post, slide deck, webinar transcript, or just their expertise also work. Accept files or pasted text.
2. **Who it is for and what it should get them.** The ideal person and the one outcome the magnet delivers. If they are unsure, infer it from the source and confirm.
3. **Branding context** so the PDF looks like theirs, not a generic template. Read `brand-config.md` if it exists; otherwise ask for: brand colors (one accent + light/dark), a display and body font (Google Fonts), their name/handle, and a one-line tone. Save it to `assets/brand-config-template.md` → `brand-config.md` so future magnets reuse it. If they have nothing, use a clean default (one accent color, Inter, plenty of whitespace) and tell them.

## Step 2 — Find the one win

Resist the urge to include everything. Read the source and identify the **single most valuable, self-contained takeaway** the reader can act on without anything else. A good lead magnet promises one clear result ("the 5-step X," "the checklist I use for Y," "the exact Z framework"), not "everything about a topic."

Pick the format that delivers that win fastest:
- **Checklist** — for a process they can follow step by step
- **Mini-guide** — for a framework or method that needs a little teaching
- **Template / swipe file** — for something they can copy and fill in
- **Cheat sheet** — for rules, examples, or quick reference

If the source is rich, it is better to make one tight magnet than a bloated one. Offer to spin a second magnet from the leftovers later.

## Step 3 — Write it

Keep it lean and premium. Structure:

- **Title:** names the specific outcome and who it is for. ("The 20-Minute Content System for Busy Coaches")
- **One-line promise:** what they will be able to do after reading it.
- **A short intro:** 2 to 4 sentences. Why this matters, and what they are about to get. No long backstory.
- **The body:** the actual win, delivered as clean steps, a checklist, or a framework. Concrete, specific, usable. This is 70% of the document.
- **A soft next step:** one line pointing to the user's offer, call, or follow, framed as the natural next move, not a hard pitch.

Write in the user's voice (read a `brand.md` / `voice.md` if present, or mirror the source's tone). No fluff, no filler, no AI-tell words. Make every line earn its place, premium means tight, not long.

## Step 4 — Produce the PDF

Build the document as a single clean HTML file, then render it to PDF. This gives full control over layout and looks far better than a plain text export.

1. Write `lead-magnet.html` styled from the **branding context in Step 1**: pull the colors, accent, and the display/body fonts from `brand-config.md` (load fonts from Google Fonts). Generous spacing, clear headings, one accent color used sparingly, a title page with their name/handle. Keep it to a clean A4/Letter-friendly width.
2. Render to PDF with headless Chrome:

```bash
# macOS
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --print-to-pdf="lead-magnet.pdf" --print-to-pdf-no-header --no-pdf-header-footer \
  "file://$PWD/lead-magnet.html"
```

If Chrome is not available, fall back to a Markdown-to-PDF tool the user has, or deliver a clean Markdown file and tell them how to export it. Always show the user the final file path.

## Step 5 — Help them promote it (optional but valuable)

Offer to write the promo: a one-line "comment [KEYWORD] and I'll send it" CTA, a short caption, and an email to their list announcing it. The magnet only works if people know it exists.

## Distribution note

Deliver the magnet as a file the user can host wherever they collect emails (their email tool, a link in bio, a simple landing page). Keep any API keys or form IDs in a `.env` file, never hard-coded into the document.
