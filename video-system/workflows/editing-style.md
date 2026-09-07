# House editing style (talking-head / VSL)

Codified from pro references (Hormozi caption guides, retention-editing breakdowns) plus the operator's notes. This document compounds: every note the operator gives becomes a rule here. Read BEFORE authoring any composition.

> **REELS (vertical) have their OWN grammar, captured in a reels autopsy you write yourself: nine of your own best reels pulled apart frame by frame.** Key divergences from this doc: reels are GRAPHICS-DRIVEN not cut-driven (persistent open-loop devices: blur-lists, progress trackers, slide decks; device mockups for proof); two text layers (big sparse structural slams + small constant one-word captions, never full-width Hormozi); audio is FLAT speech-first with a light bed, hook hottest, no film dips or risers. Where reels conflict with this doc, the autopsy wins.

## GROUND TRUTH: the operator's reference video (2026-07-02)

`references/new_vsl (360p).mp4` + full breakdown in `references/new_vsl_autopsy.md`. When a choice here conflicts with the reference, THE REFERENCE WINS. Its core lessons:

1. Structure = music-video sandwich: testimonial avalanche cold open (new face every 2-3s, split-screen grids) -> speaker entrance -> one loud LIFESTYLE MONTAGE on a music drop (0.7-0.8s per clip, ~4x talking loudness) -> long CLEAN talking body (jump-cut punch-ins every 2.5-7s, no captions, no cards) -> short full-screen proof flashes (1.4-2s, key number highlighted) -> framed proof cards on dark canvas -> QUIET intimate CTA (zero gimmicks, music decays to near-silence).
2. Proof density is FRONT-LOADED; the middle is restrained. Do not decorate the persuasion body.
3. Punch-ins are hard jump cuts between ~3 distinct levels (~1.15x apart), often with a small x shift. Not slow zooms.
4. Everything shown is REAL (their students, their trips, their Slack, their sheets). The material is the edit.

## The thesis 

"Well edited videos have pacing, they have music, they have zooms, pauses, they have sounds and visuals that pull the viewer in. It's not about what they see, it's about what they FEEL."

Editing is dynamics, not decoration. The tools only work through CONTRAST:
- A slam hits because the 5 seconds before it were still.
- A pause feels heavy because the music drops out right before it.
- A zoom creates tension because the frame was wide and calm first.
- Flat constant-medium energy = AI. Map the emotional arc of every chapter FIRST (hype, build, tension, hit, release), then assign visual/audio intensity to match. Leave deliberate BREATHING stretches (5-10s of just the speaker + captions + drift) between hits.

## The core diagnosis: why edits "look like AI"

AI edits put INFORMATION PANELS over a video and leave them there. Pro edits make the FRAME ITSELF keep transforming. Concretely:

- A glass panel with a kicker label sitting for 15s = AI slop. Kill it.
- The pro grammar is: big bold WORDS and NUMBERS slam on screen exactly as they are said, hold 0.8-2.5s, then leave. Proof imagery flashes in for 1-3s. The camera angle jumps. Captions punch along word by word.
- Panels are allowed ONLY for true lists (an agenda, a feature rundown) and even then: compact, fast, gone.

## Captions (Hormozi standard, adapted to 16:9)

- 2-4 words per page, ONE line, ALL CAPS.
- Font: Anton (or Montserrat Black / Bebas Neue). At 1920x1080: 58-68px. Thick black stroke (paint-order: stroke; ~8px) and drop shadow, NO pill/box background.
- Each page HOLDS UNTIL THE NEXT PAGE STARTS. Never a hard time cap (that causes visible "caption cut off" flashes during pauses). Cap only at very long silences (>2.5s), then fade.
- Active word: scale ~1.08 + brand accent. Money tokens (currency, prices) in green; power words (zero, free, result, minutes...) in orange/yellow.
- Position: bottom-center, clear of the mic and the speaker's hands. Suppress during full-width bottom moments.

## Scene changes beat everything 

"The most important is changing the SCENE, a different show every 2-3 seconds for reels and every 6-8 seconds for longer form. Not only overlays: actually SHOW different things: an operating system, a funnel run-through, a website, b-roll."

The hierarchy of visual change, strongest first:
1. **Cutaway scene** — the frame becomes the THING (website scrolling in a browser frame, product/OS screen recording, b-roll). Speaker shrinks to a corner PiP window (white ring, rounded, bottom-right) so the connection survives. Use whenever the script references something showable ("what you're seeing now is...", any named artifact). Capture method: full-page screenshot -> BrowserScroll component (engine/src/Broll.tsx) with smooth scroll; cap scrollEnd before empty footers. Screen recordings drop in the same slot.
2. **Angle cut** — simulated multi-cam reframe.
3. **Proof insert** — receipts/polaroids.
4. **Text slam** — the said word on screen.
5. **Overlay card** — LAST resort, true lists only.

Cadence: reels = a scene-level change every 2-3s. Long form = every 6-8s. Count only levels 1-3 as "scene changes"; slams and captions are seasoning on top.

**Cutaway material comes from the CLIENT (the operator, 2026-07-02: "dont use the detailing site as an example it sucks").** Never fill a cutaway slot with a stand-in the client has not approved — a site, stock clip, or template pulled because it existed. If no approved material exists for a beat, the beat falls back to level 2-4 grammar (angle burst + slams) and the slot stays wired for when material arrives. Priority order of real material: client screen recordings (OS, funnels, sites, dashboards) > client phone footage (vlogs, trips, working shots) > real screenshots (receipts, DMs, WhatsApp) > designed illustration clearly reading as illustration.

**Stock b-roll policy (refined 2026-07-02, the operator: "is there not a bunch of broll we could grab off the internet?").** Stock is allowed as CONCEPT TEXTURE and banned as PROOF. Concept texture = a sub-1.5s cinematic flash showing the literal thing a word means (bitcoin macro on "crypto", hourglass on "20 hours", mechanic over an engine on "car garage") — the reference VSL does exactly this with AI-generated clips. Proof = anything implying "this is MY student / MY site / MY payment"; that must be real client material, always. Rules for concept flashes: 0.9-1.5s, full-screen, unified grade (saturate 1.08 / contrast 1.1 / brightness ~0.88 + vignette + subtle brand tint), slight scale settle 1.12 -> 1.06, slams render ON TOP (reference strobe grammar), pick CINEMATIC clips (macro, shallow DOF, moody light) and reject anything that looks like corporate stock (handshakes, suits pointing at whiteboards). Curate via thumbnail contact sheet before downloading.

**House libraries + sources (no-attribution commercial licenses):**
- Video: Mixkit (`mixkit.co/free-stock-video/<slug>/` — page HTML contains direct `assets.mixkit.co/videos/<id>/<id>-720.mp4` links, curl with browser UA; 1080 variants 403). Pexels blocks curl (needs API key — ask the operator to make a free one for 4K). Library: `video-editor/assets/broll/` (copy into `engine/public/broll/` per project).
- SFX "dashboard": `video-editor/assets/sfx/` harvested from Mixkit SFX (`mixkit.co/free-sound-effects/<category>/`, preview mp3s are full-length: `assets.mixkit.co/active_storage/sfx/<id>/<id>-preview.mp3`). Categories stocked: whoosh, impact, notification, camera. Synthesized risers/sub-impacts (ffmpeg noise/sine recipes in pipeline.md) remain the go-to for tension builds.

## Trending sounds and visuals 

- Trending audio is a FEED-DISTRIBUTION tool, not an editing tool. It only pays off when attached in-app (IG/TikTok audio picker) so the algorithm links the post to the trend; burned into an exported file it gives zero distribution and risks copyright mute. So: reels export = dialogue + SFX + light bed; the trending sound gets layered at post time in the app.
- Where to find trends: TikTok Creative Center (creativecenter.tiktok.com — free, trending songs/hashtags/top ads by country and industry, updated daily) and Instagram's professional dashboard trending audio. Use top ads there as a swipe file for HOOK formats (first 1.5s visual pattern) — the visual trend matters more than the sound for conversion content.
- VSLs and sales pages: never trend-chase. No algorithm is watching, and a trend ages the video in weeks. Film-grammar scoring + diegetic sound only.
- Non-generic SFX = DIEGETIC sound: sounds that match what is literally on screen (mouse click when a screen appears, keyboard under typing shots, WhatsApp pop on a chat screenshot, cash-register thunk on a payment receipt). Literal sounds never read as generic because they belong to the picture. Keep the <=1 per 12-15s budget.

## Sound: sparingly 

SFX only on the moments that matter: money/price confirms (ding), the single biggest line (whip), section washes and cutaway reveals (whoosh). NO sound on ordinary slams, card enters, tick rows, or inserts — a sound on everything reads as slop. Rough budget: <= 1 SFX per 12-15s of runtime.

## Captions sizing (the operator note)

46px at 1080p (not 60), active-word scale 1.06. Big enough to read, small enough to never compete with the speaker or a cutaway.

## Emphasis text slams (the engagement engine)

- For every concrete claim (a number, a timeframe, a flat assertion), slam the word/number on screen AS IT IS SAID: scale in from ~1.5 to 1.0 in 4-6 frames with a small overshoot, 2-4px screen shake on landing, low thock/click SFX.
- Hold 0.8-2.5s (reading time), exit fast (3-4 frames, accelerate out).
- Anton caps, huge (90-200px), white or brand accent, thick stroke or heavy shadow. Place beside the speaker's head on the empty side, or bottom band. NEVER over the face.
- Cadence goal: some visual event every 3-6s; a text slam or insert at least every 10-15s.

## Proof inserts (b-roll for claims)

- Real screenshots (payments, DMs, dashboards) beat any designed graphic. Slam them in as tilted polaroids (white border, big shadow, 2-6 degree rotation, slight overshoot), 1.2-3s each, staggered when multiple.
- Hold detailed imagery >= 3s if the viewer must read it; 1-2s if it is just "proof exists".
- Never fabricate proof that claims to be a specific real thing it is not; stylized mockups must read as illustration.

## Simulated angles (single static cam)

- Framings must DIFFER meaningfully: wide 1.0 / mid ~1.16 / tight ~1.30-1.35. Small differences read as digital zoom (AI tell); big jumps read as camera cuts.
- Hard cut on sentence or emphasis boundaries. 15-25s cuts are fine in calm stretches; burst 3-4 quick cuts at high-energy moments.
- Add constant handheld micro-drift (1-2px sin/cos at ~0.3-0.7Hz) so held shots never look like a frozen digital crop.
- Speaker always sits OPPOSITE any side graphic. Face never covered (hard rule).

## Sound

- SFX on every slam/insert (low volume: 0.1-0.3). Whoosh only at section washes.
- Music: real track, ducked under VO (sidechaincompress). Generated tonal "melodies" sound fake; if no licensed track is available, use a near-silent textural room-tone wash or nothing, and ask for a track.

## Music scoring (the operator, 2026-07-02: "music should invoke emotion like movies do")

- Score to the chapter's emotional arc, not as wallpaper: pick the track for the FEELING of the section (confident drive for a money open, sparse/emotional under the big thesis line, momentum for proof sections).
- Film-style automation on the bed: DIP to near-silence 1-2s BEFORE the biggest line (the dropout is what makes the line land), gentle swell (+2-3dB) UNDER it, back to bed level after. `volume='if(between(t,A,B),0.08,if(between(t,B,C),1.3,1))':eval=frame` in ffmpeg.
- LEVEL DISCIPLINE (the operator: "too loud" at -25dB): normalize the track (loudnorm I=-24), then mix at ~-32dB base under speech with sidechain ducking (threshold 0.015, ratio 6, attack 8, release 450). The bed should be FELT in pauses and nearly invisible under speech. When unsure, quieter.
- Sources: incompetech.com (Kevin MacLeod) direct mp3s are curl-able, CC-BY 4.0 = free commercial use WITH one-line credit ("Music: Kevin MacLeod, incompetech.com") on the page/description. For fully credit-free, client supplies a licensed track (Artlist/Epidemic) and it drops into the same automation.

## Motion personality for VSLs

- Energetic, not Premium: enters 5-8 frames, exits 3-4 frames, ease-out-expo family, tiny overshoot (2-6%) on slams only.
- Three layers still apply (primary slam, secondary shake/shadow, ambient drift/vignette).

## Sources

- riverside.com/blog/hormozi-style-videos, ascynd.io/en/blog/hormozi-captions, submagic.co/blog/how-to-make-alex-hormozi-captions (caption specs)
- air.io retention-editing, edicionvideopro.com retention guides (cut cadence, burst sequences, pattern interrupts every ~15s)
