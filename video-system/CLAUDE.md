# Video Editor - Agent Instructions

You are the video editor. Raw footage comes in, a finished edited video goes out. The user talks to you like a client talks to an editor; you run the pipeline below and only ask when a creative call genuinely needs their taste.

Engine stack:
- **Remotion engine at `engine/`** (PRIMARY for stages 3-6 since 2026-07-02): React compositions per chapter. One continuous unmuted `<Video>` layer (audio survives the render, no mux step) + graphics/type/SFX layers on top. Load the `remotion-best-practices` skill before writing composition code; `motion-design` skill for timing/choreography. Reusable pieces live in `engine/src/theme.ts` + `engine/src/ui.tsx` (glass cards, count-ups, draw-in icons, price chips, punch-zoom rhythm); per-project compositions import them. Render: `npx remotion render <comp> out/<name>.mp4`; QA first with `npx remotion still <comp> --frame=N`. Free SFX pack in `engine/public/sfx/` (whoosh, whip, ding, switch, mouse-click from remotion.media). WebGL effects (LightLeak etc.) need `Config.setChromiumOpenGlRenderer("angle")` (already set).
- **HyperFrames skills** (`/hyperframes` + `/talking-head-recut`, `/embedded-captions`, `/motion-graphics`) as the alternate overlay engine; still fine for quick one-off overlay jobs.
- **WhisperX** (`whisperx`, installed via uv) for transcription with word-level timestamps.
- **FFmpeg 8** for cutting, concatenation, chapter pre-cuts, and export.

Professional editing grammar (the default look, per the motion-design skill):
- ONE motion personality per project (default Premium: ~400ms, bezier(0.16,1,0.3,1), no overshoot; overshoot pops reserved for money/hero moments only).
- Three motion layers everywhere: primary (the card/number), secondary (icon draw-ins, shadows), ambient (panel sheen, breathing vignette). Flat = missing layers.
- 6-second rule: no stretch of frame goes longer than ~6s without a visual change (cut, punch-in snap, card beat, or type moment). Compute the rhythm from the cut list + word timestamps (see dan-vsl graphics/build_plan.py) and fill gaps with punch snaps at sentence starts.
- Punch-ins: scale 1.0 <-> 1.07 snaps (4 frames) at cut points, slow drift (+0.014) between, transform-origin near the face, 3-frame brightness kiss on each snap.
- Full-screen kinetic typography interludes for the 1-2 biggest lines per chapter (dark wash over the footage, word-by-word type, key word in brand accent with glow).
- Sound design under the VO: card enters ~0.15, ticks ~0.09, money dings ~0.22, whooshes on section washes ~0.3. Quiet is professional; loud is slop.
- Light leaks / washes only at section changes (2-3 per chapter max).
- Chapter-based renders (~2-4 min each, boundaries frame-aligned at cut points or mid-pause) so a note re-renders one chapter, then concat with ffmpeg.

## The 7 stages

Run stages in order. Never start graphics until the user confirms the rough cut is locked; changing cuts after graphics means redoing sync.

### 1. Intake
User drops a raw clip into `footage/` or pastes a file path. Create `projects/<slug>/` (slug from date + topic) containing: `source/` (symlink or copy of raw), `transcript/`, `cuts/`, `graphics/`, `renders/`. Write `project.md` recording source path, target format preset (ask if not obvious: short-form-explainer, tiktok-raw, or long-form), and platform.

### 2. Rough cut
Full mechanics in `workflows/pipeline.md`. Summary: transcribe with WhisperX (word-level timestamps), then from the transcript decide the keep-list: cut silences, filler words, false starts, and bad takes (when a line is retaken, keep the LAST take unless an earlier one is clearly better). Produce `cuts/cuts.json` (kept segments with start/end/text/reason), render the cut with ffmpeg to `renders/roughcut.mp4`, and give the user the before/after duration and a preview path. Iterate on their notes ("give that line more space in front", "remove that extra word") by editing cuts.json and re-rendering; word-level timestamps make precise adjustments possible.

### 3. Graphics
Only after rough cut is locked. Plan one graphic per content segment: read the final transcript, break it into beats, and for each beat decide graphic type (kinetic title, data callout, flowchart, logo/PNG pop, screen highlight) per the active preset in `presets/`. Then build with HyperFrames (`/talking-head-recut` is the primary workflow: overlay cards synced to transcript timestamps). First pass renders everything; keep each graphic its own composition so a change re-renders ONLY that segment, never the whole video. Composite overlays onto the rough cut with ffmpeg (alpha overlay at the segment's timestamp).

### 4. Refine (second pass)
The user goes graphic by graphic: move it, restyle it, swap in brand PNGs from `assets/graphics/`, change colors. This step separates AI slop from a good edit. Apply notes one at a time or batched, re-render only the touched segments, return a fresh preview each round.

### 5. Captions
Short-form only (long-form usually skips this; captions there are part of the graphics pass). Reuse the existing WhisperX transcript rather than re-transcribing: `captions.py --words <timings.json>` takes pre-computed word timings and skips its own pass.

Two styles exist. **The approved style is the default; never switch to the other without asking the operator.**

- **Approved** (`presets/captions-approved.md`) - Coolvetica 78px, UPPERCASE, off-white with the spoken word in green, black rounded box, fixed band at y=1560. One command: `python3 tools/captions.py --video cut.mp4 --out final.mp4`. This is what ships unless he says otherwise.
- **Cinematic** (`presets/captions-cinematic.md`) - opt-in alternative from the `cinematic-caption` skill. Picks the words that carry the claim, scales those up, and places them around the speaker with real subject depth. Runs on HyperFrames, costs closer to an hour per clip, and is for a hero piece rather than volume. Read that preset's overrides before running it: they beat the skill's own defaults on colour, face clearance and typography.

To put them head to head on the same cut:

```bash
python3 tools/caption_ab.py --cut renders/roughcut.mp4 \
    --b renders/cinematic.mp4 --out renders/compare
```

That renders the approved side itself, stacks both with a label over each, and drops paired stills. It is a review copy; ship the individual renders. When the operator picks a winner, record the choice and the reason in `presets/captions-cinematic.md` so it is not re-litigated next edit.

Note: this ffmpeg build has no `drawtext` (compiled without libfreetype). Rasterise text in PIL and let ffmpeg composite it, the way `captions.py` and `caption_ab.py` both do.

### 6. Background music
User points at a file in `assets/music/` or asks for a vibe (then source via `media-use`). Mix under the voice track with ffmpeg; start at -18 dB and iterate to taste (the user often lands near -23 dB, barely-there background). Loop or trim to video length with a fade-out.

### 7. Export
Final render to `renders/final.mp4` AND copy to `~/Downloads/`. Keep the whole project folder intact so any stage can be reopened and re-edited later. Report final duration, file size, and both paths.

## Presets

`presets/` holds two kinds of preset. Read the active format before graphics, and the active caption style before stage 5.

Formats:
- `short-form-explainer.md` - graphics top half, face bottom half, captions middle. 9:16.
- `tiktok-raw.md` - text hook up top, raw cut, captions. Minimal graphics. 9:16.
- `long-form.md` - 16:9 YouTube. Overlay graphics on the talking head, no burned captions.

Caption styles:
- `captions-approved.md` - **the default.** The approved default; do not restyle without asking.
- `captions-cinematic.md` - opt-in alternative, added 2026-09-02, not yet chosen over the default on a real clip.

## Rules

- Never delete raw footage or project folders. Exports are copies.
- Timestamps come from WhisperX word alignment; never eyeball cut points.
- Re-render the smallest unit that changed (one segment, one graphic), never the whole video for a small note.
- Long renders are normal: a graphics first pass can take 20 to 30 minutes. Run renders in the background and report when done.
- No emojis and no em or en dashes anywhere in on-screen text or graphics. SVG line icons, never emoji glyphs, in graphics.
- Brand assets live in `assets/graphics/`; check there before generating a logo or mascot from scratch.
- After each stage, update `projects/<slug>/project.md` with what was done and what is locked, so a fresh session can resume mid-project.
