---
name: premium-funnel-page
description: Build premium, conversion-focused landing pages and funnel pages (opt-in, post-optin confirmation, post-call booking). Editorial dark luxury aesthetic with serif headlines, gold gradients, animated mesh gradient background, cursor spotlight, magnetic buttons, parallax photos, scroll reveals, ticker strips, glassmorphic cards, and rotating testimonials. Inspired by nekter.ai. Use when user asks for premium landing page, opt-in page, sales funnel page, VSL landing page, post-optin / call-confirmed pages, or wants a "luxury / expensive feeling" page that converts.
---

# Premium Funnel Page Builder

Builds dark, editorial, conversion-focused funnel pages. The aesthetic is "expensive" without being cliché — Playfair Display + Inter, near-black background, slow-drifting gold mesh gradient, no static blocks. Every page has motion. Every element has reason.

**Core principle:** A landing page is not a website. There is one goal — convert. Strip out navigation. Strip out distracting links. Repeat the form/CTA strategically. Everything else exists to support the conversion.

## When to use this skill

Trigger on requests like:
- "Build a landing page for [creator/offer]"
- "Build the opt-in page"
- "Build a post-call booking page"
- "Build a confirmation/thank-you page"
- "Make this page feel more premium / expensive"
- "Build a VSL funnel"
- User shares a creator's Instagram and wants a funnel
- User explicitly asks for "the same style" as a previous premium page

Do NOT use for:
- Multi-page websites (use a different skill)
- Dashboards / app UI (use design-taste-frontend with sans-serif)
- Marketing sites with multiple navigation destinations

## Design System (NON-NEGOTIABLE)

### Typography
- **Headlines:** `Playfair Display`, weight **600** (NOT 700/800/900 — that's the cheap-looking trap), letter-spacing `-0.025em` to `-0.035em`, line-height `0.95` to `1.05`
- **Italic accent words:** italicized + gold gradient text-fill — this is the signature look
- **Body:** `Inter`, weight 400-500
- **Eyebrow / label:** `Inter`, weight 600, 11px, letter-spacing `0.16em` to `0.28em`, uppercase, gold-2 color
- **Italic captions on photos:** `Playfair Display` italic, 13-14px

### Colors
```css
--bg:        #09090C;   /* near-black, NEVER #000 */
--bg-soft:   #0F0F14;
--surface:   #14141A;   /* card backgrounds */
--surface-2: #1A1A22;
--line:      rgba(255,255,255,0.06);
--line-mid:  rgba(255,255,255,0.10);
--white:     #F5F5F7;   /* warm white, NEVER #FFFFFF */
--text:      #C8C8CE;
--muted:     #8A8A92;
--muted-2:   #5A5A62;
--gold-1:    #F2D27A;   /* light gold */
--gold-2:    #D9A741;   /* mid gold */
--gold-3:    #B8782A;   /* deep amber */
--gold-soft: rgba(217,167,65,0.10);
--green:     #34D399;   /* live status pill */
--red:       #ef4444;   /* urgency badges */
```

For brand variants (e.g. blue / purple), substitute the gold trio but keep the same gradient pattern.

### The Gold Gradient (signature element)
```css
background: linear-gradient(108deg,
  var(--gold-1) 0%,
  var(--gold-2) 45%,
  var(--gold-3) 100%);
-webkit-background-clip: text;
        background-clip: text;
-webkit-text-fill-color: transparent;
font-style: italic;
font-weight: 500;
```
Apply to: italic accent words in H1s, big numbers, italic CTA hooks, the giant `"` quote marks.

## Required Animated Layers

These four overlays go on EVERY page in this order (z-index 0 → 2):

1. **Animated mesh gradient** (4 large blurred gold blobs, each on independent 32-44s ease-in-out infinite drift loops)
2. **Subtle grain texture** (SVG fractalNoise, opacity 0.04, mix-blend overlay)
3. **Vignette** (radial gradient ellipse darkening edges)
4. **Page content** (z-index 2, position relative)

**CSS pattern:**
```css
.mesh { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.mesh-blob {
  position: absolute;
  border-radius: 50%;
  filter: blur(120px);
  opacity: 0.32;
  will-change: transform;
}
.mesh-blob-1 { width: 700px; height: 700px; top: -200px; left: -150px;
  background: radial-gradient(circle, rgba(242,210,122,0.40), transparent 60%);
  animation: drift-1 32s ease-in-out infinite; }
/* ... 3 more blobs at different positions, sizes, durations */

@keyframes drift-1 {
  0%,100% { transform: translate(0,0) scale(1); }
  33%     { transform: translate(120px,80px) scale(1.15); }
  66%     { transform: translate(-60px,140px) scale(0.95); }
}
```

Use 4 blobs minimum. Each with different durations (32s/38s/44s/36s) and different keyframe positions so they never sync.

## Required Interactive Behaviors

Every premium funnel page MUST have these JS behaviors:

### 1. Cursor-tracking gold spotlight on hero
```js
const hero = document.getElementById('hero');
hero.addEventListener('mousemove', (e) => {
  const r = hero.getBoundingClientRect();
  hero.style.setProperty('--mx', ((e.clientX - r.left) / r.width * 100) + '%');
  hero.style.setProperty('--my', ((e.clientY - r.top) / r.height * 100) + '%');
});
```
Paired with:
```css
.hero::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(500px circle at var(--mx, 50%) var(--my, 30%),
              rgba(217,167,65,0.06), transparent 65%);
  transition: background 0.18s ease-out;
}
```

### 2. Magnetic CTA buttons
```js
document.querySelectorAll('.magnetic').forEach(btn => {
  btn.addEventListener('mousemove', (e) => {
    const r = btn.getBoundingClientRect();
    const x = e.clientX - r.left - r.width / 2;
    const y = e.clientY - r.top - r.height / 2;
    btn.style.transform = `translate(${x * 0.12}px, ${y * 0.20}px)`;
  });
  btn.addEventListener('mouseleave', () => { btn.style.transform = ''; });
});
```
Apply `.magnetic` class to all primary CTAs.

### 3. Scroll-triggered reveals (with stagger)
```js
const observer = new IntersectionObserver((entries) => {
  entries.forEach(e => {
    if (e.isIntersecting) { e.target.classList.add('in'); observer.unobserve(e.target); }
  });
}, { threshold: 0.10, rootMargin: '0px 0px -40px 0px' });
document.querySelectorAll('.reveal').forEach(el => observer.observe(el));
```
```css
.reveal { opacity: 0; transform: translateY(28px);
  transition: opacity 0.7s cubic-bezier(0.16,1,0.3,1), transform 0.7s cubic-bezier(0.16,1,0.3,1); }
.reveal.in { opacity: 1; transform: translateY(0); }
.reveal[data-delay="1"] { transition-delay: 0.05s; }
.reveal[data-delay="2"] { transition-delay: 0.10s; }
.reveal[data-delay="3"] { transition-delay: 0.15s; }
.reveal[data-delay="4"] { transition-delay: 0.20s; }
```
Add `class="reveal" data-delay="N"` to every section/element you want to animate in.

### 4. Parallax hero photo (only if hero has a photo)
```js
let scrollY = 0, ticking = false;
function updateParallax() {
  if (heroPhoto) heroPhoto.style.transform = `translateY(${scrollY * 0.10}px) scale(1.05)`;
  ticking = false;
}
window.addEventListener('scroll', () => {
  scrollY = window.scrollY;
  if (!ticking && scrollY < 1200) { requestAnimationFrame(updateParallax); ticking = true; }
}, { passive: true });
```

### 5. Typewriter (in pre-headline pill, optional)
Cycles 4-5 short identity phrases. Pill format: `"For people who want to [TYPE]"`. Speed: 88ms type / 38ms delete / 2200ms pause / 420ms between phrases.

### 6. Rotating testimonial card (if testimonials section exists)
Single quote-card cycles 3-5 quotes every 5500ms with fade transition + dot indicators.

### 7. Live ticker strip (between sections, especially for finance/trading niches)
Marquee with `animation: ticker 40s linear infinite` translating `0` to `-50%`. Items duplicated 2x for seamless loop. Each ticker item has gold italic Playfair symbol + monospace price + colored arrow (green up / red down).

### 8. Animated shine on submit buttons
```css
.submit-btn::after {
  content: ''; position: absolute; top: 0; left: -100%;
  width: 60%; height: 100%;
  background: linear-gradient(90deg, transparent, rgba(255,255,255,0.5), transparent);
  animation: shine 4s ease-in-out infinite;
}
@keyframes shine { 0%,60% { left: -100%; } 100% { left: 200%; } }
```

## Component Library

### Live Pill (top of hero)
Green-tinted pill with pulsing green dot. `Inter` 11px, `0.18em` letter-spacing, uppercase. Used to communicate active members count or status.

### Form Card (glassmorphic)
```css
background: rgba(20,20,26,0.7);
border: 1px solid var(--line-mid);
border-radius: 16px;
padding: 18px;
backdrop-filter: blur(20px);
box-shadow: 0 20px 60px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.05);
```
Inputs: `rgba(9,9,12,0.6)` bg, gold border-color on focus, gold ring shadow on focus.

### Gold gradient submit button
```css
background: linear-gradient(180deg, var(--gold-1) 0%, var(--gold-2) 60%, var(--gold-3) 100%);
color: #0A0A0A;
box-shadow:
  0 12px 40px rgba(184,120,42,0.35),
  inset 0 1px 0 rgba(255,255,255,0.45),
  inset 0 -1px 0 rgba(0,0,0,0.10);
```
Always paired with shine animation. ALWAYS magnetic.

### Inline stats row (3 stats with hairline dividers)
Three columns separated by `1px` `--line-mid` borders. Numbers in Playfair Display 32px weight 600 with italic gold accent on suffix (e.g., `5,241+` where `+` is gold italic).

### Photo treatment
- 4:5 aspect ratio
- 20px border radius
- 1px solid `--line-mid` border
- Big shadow: `0 50px 100px rgba(0,0,0,0.6), 0 0 0 1px rgba(217,167,65,0.10)`
- Gradient ring border via `::before` mask-composite trick (1px gradient border inset)
- Bottom gradient overlay: `linear-gradient(to top, rgba(9,9,12,0.6) 0%, transparent 35%)`
- Italic Playfair caption bottom-left in gold or white

### Floating stat badges (on hero photo)
Two badges absolutely positioned on the photo edges. Glassmorphic cards with icon + number + uppercase label. Each has independent gentle float animation (6-7s ease-in-out infinite, 8-10px translate).

### Numbered list (premium "what's inside")
NOT cards. Use line-divider format:
- Border-top + border-bottom on `<ul>`
- Each `<li>`: grid `64px 1fr auto`, gap 28px, padding 28px 0
- Number column: Playfair italic 36px in gold-1
- Title: Playfair 24px weight 600
- Tag pill on right: gold-soft bg, gold-1 text, uppercase 10px, 0.14em tracking, rounded-full
- Hover: `padding-left: 12px` with cubic-bezier transition

### FAQ accordion
`<details>` / `<summary>` glassmorphic cards. `+` rotating to `×` (rotate 45deg) on open. Gold border tint when open. Background gets slightly lighter on open.

### Step tracker (for booking/multi-step pages)
Horizontal row of dots with hairline connector. Active dots filled with gold gradient + glow shadow. Labels uppercase 10px tracking 0.14em underneath.

### Rotating testimonial card
Glassmorphic card centered, max-width 800px. Big italic Playfair quote (20-26px clamp). Author in `Inter` 13px gold-1 uppercase tracking 0.10em. Dot indicators below. Decorative `"` mark in top-left at 120px gold gradient with 0.5 opacity.

### Personal message card
Same glassmorphic + `"` decoration. Italic Playfair quote on top. Body text in muted. Signature row at bottom with gradient logo-mark, italic name, muted handle. Always lowercase voice for the creator's personal message.

### Live forex ticker (trading niches)
```html
<div class="ticker">
  <div class="ticker-track">
    <span class="ticker-item"><span class="symbol">XAUUSD</span> 2,387.45 <span class="arrow-up">▲ +1.84%</span></span>
    <!-- ...repeat 12+ items, then duplicate the whole sequence for seamless loop -->
  </div>
</div>
```
40s linear infinite scroll. Symbols in italic Playfair gold. Prices monospace-feeling. Arrows green/red.

## Layout Principles

1. **No top navigation.** This is a landing page, not a website.
2. **Asymmetric desktop hero**: text/form left (1.15fr), photo right (1fr), gap 80px. Stack on mobile, photo first.
3. **Wide max-widths**: 1280px hero, 1100px features, 880px focused sections, 760px CTA.
4. **Single-page flow**: hero → ticker → "what's inside" → about → testimonial → final CTA → minimal footer.
5. **Repeat the form**: top of page (hero) and bottom (final CTA). Ideally a third in middle if page is long.
6. **Minimal footer**: just brand mark + copyright. No nav links. Maybe Privacy/Terms inline if legally required.
7. **Generous padding**: sections 96-120px vertical on desktop, 64-72px on mobile.

## Page Types

### A. Opt-in / VSL Landing Page (`index.html`)
Goal: capture email/name → confirmed page.
Sections: hero (form #1) → ticker → what's inside → about (with photo gallery) → rotating testimonial → final CTA (form #2) → footer.

### B. Post-Optin Confirmation (`confirmed.html`)
Goal: get them to take next step (DM on Instagram, watch first email, etc).
Sections: hero with massive `YOU'RE IN.` (italic gold accent on `IN`) → 3 numbered step cards → primary CTA → personal message card → footer.

### C. Post-Call Booking (`call-booked.html`)
Goal: prevent no-shows. Make them prep for the call.
Sections: hero with urgency badge ("Call Pending — Complete Steps Below") + booking-info card showing date/time → step tracker → ticker → step 1 video → step 2 calendar buttons → step 3 homework cards → step 4 FAQ → proof grid → personal message → footer.

The "call is not yet confirmed until you complete these steps" framing is the conversion mechanic — copy from Alex Eubank / TJR Trades references.

## Copywriting Principles

- **Headlines as story**: "From dead-end jobs to two Lamborghinis. Here's the system." NOT "Become a profitable trader."
- **Italic accent does the work**: keep main headline white, then italic gold finisher line. Creates rhythm.
- **Lowercase personal voice**: when the creator speaks directly ("you made the right call. most people sat on the fence."), use lowercase. Feels human.
- **Specific numbers**: "5,241 members" not "thousands." "5,241+ already inside" not "join us."
- **Real specifics**: "XAUUSD" not "Gold." "£412 in three hours" not "made some money."
- **Forms**: First name + email. Two fields. Ever. Phone optional only for SMS-heavy funnels.
- **Risk disclaimers**: bottom of page in muted-2 small text if niche is regulated (trading/finance/health).

## Anti-Patterns (NEVER DO)

- ❌ Inter for headlines
- ❌ Playfair at weight 700-900 (looks fake luxury)
- ❌ Pure black `#000`
- ❌ Pure white `#FFF`
- ❌ Centered hero with no photo (boring)
- ❌ 3-column feature card grid (generic AI tell)
- ❌ Top nav with menu links (this is a landing page)
- ❌ Multiple CTAs going to different places
- ❌ Static gradients (must be animated mesh)
- ❌ Emojis in production copy
- ❌ Generic stock photos (always use creator's real photos when possible)
- ❌ Lorem ipsum / placeholder copy in final builds

## Required Files

For a creator's full funnel, build these in `[name]-funnel/`:
- `index.html` — opt-in landing page
- `confirmed.html` — post-optin confirmation
- `call-booked.html` — post-call booking (only if their funnel includes a call)
- `emails.md` — opt-in + post-call email sequences (3-6 emails)
- `photos/` — directory with creator's real photos (download from their Instagram via Apify)

## Workflow

1. **Research the creator** — scrape Instagram (and TikTok if relevant), identify niche, brand voice, top-engaging content
2. **Determine the offer** — what's the destination? (signal group, mentorship call, course, brokerage referral)
3. **Download real photos** — minimum 4-6 from their Instagram via Apify scraper, save to `photos/`
4. **Build index.html** — full design system, all animations, real photos, real copy in their voice
5. **Build confirmed.html** — match style, single goal (next step), personal message
6. **Build call-booked.html** — only if there's a call in the funnel; use 4-step engagement structure
7. **Write emails.md** — opt-in sequence (welcome / story / pitch) + post-call sequence (confirm / homework / day-of)
8. **Serve locally** — `npx live-server [folder] --port=5500` for live preview with auto-reload
9. **Iterate on user feedback** — be willing to rebuild if "feels cheap" — usually means more motion / better hierarchy / better photo placement

## Reference Pages (study these)

- **nekter.ai** — the design language we're stealing. Playfair Display 600 + Inter, lab-color gradients, near-black bg
- **harrygunter.com** — trading influencer offer structure (free trial → Telegram)
- **ai-advertiser.com/training-c** — minimal opt-in page, story headline
- **ai-advertiser.com/training/confirmed** — "YOU GOT IN. HERE'S WHAT TO DO NEXT." structure
- **lp.tjrtrades.com/booking** — 4-step post-call booking flow
- **pathway.alexeubankcoaching.com/call-confirmed-pm** — "YOUR CALL IS NOT CONFIRMED" urgency framing

## Known Pitfalls

- **Heavy backdrop-filter on iOS Safari**: glassmorphic cards may stutter. Test on mobile and reduce blur radius if needed (8-12px instead of 20px).
- **Mesh gradient performance**: 4 large blurred elements can chug on low-end Android. Add `@media (prefers-reduced-motion: reduce)` fallback that disables all animations.
- **Ticker on mobile**: keep ticker visible but speed it up (30s instead of 40s) — small screens make it feel slow.
- **Letter-spacing on headlines**: at very large sizes (>80px), `-0.035em` is correct. At smaller sizes, dial back to `-0.025em`. Don't reuse the same value at all sizes.
- **Photo CDN URLs from Instagram expire** in 24-48 hours. Always download to local `photos/` folder. Use Apify `instagram-scraper/fast-instagram-post-scraper` (~$0.001/post).
- **Don't use `Playwright`/`Chromium` MCP** if the user already has Chrome open with Playwright — it'll error "browser already in use." Either kill it or use `--isolated` mode.
- **Local dev port 5500** is the default `live-server` port. Check if user already has something there before starting.
