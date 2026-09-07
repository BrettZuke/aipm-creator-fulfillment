# Pipeline mechanics

Concrete commands and formats per stage. Claude reads this when executing; adjust flags when a tool errors and record the fix here (self-anneal).

## Transcription (stage 2)

```bash
whisperx "<raw.mp4>" --device cpu --compute_type int8 \
  --output_dir "projects/<slug>/transcript" --output_format json --language en
```

- Apple Silicon has no CUDA: `--device cpu --compute_type int8` is required or whisperx exits with a float16 error.
- Output JSON has `segments[]` each with `words[]` carrying `word`, `start`, `end` (seconds, word-level). This is the single source of truth for every cut and caption.
- Long files: expect roughly 0.3 to 0.5x realtime on CPU. Run in background.

## Cut list format (stage 2)

`cuts/cuts.json`:

```json
{
  "source": "source/raw.mp4",
  "keep": [
    {"start": 3.42, "end": 11.87, "text": "This video was edited by Claude...", "note": "take 2 of intro, kept last take"}
  ]
}
```

Build the mechanical first pass with the helper script, then apply judgment by editing the JSON:

```bash
python3 scripts/build_cutlist.py projects/<slug>/transcript/raw.json source/raw.mp4 projects/<slug>/cuts/cuts.json
```

Rules for building the keep-list from the transcript:
- Drop gaps between words longer than 0.6s (trim silence), but leave 0.15s of padding before the first word and after the last word of each kept segment so cuts do not clip audio.
- Detect retakes: consecutive segments with high text overlap; keep the last take.
- Drop filler-only segments ("um", "uh", "so, yeah") unless they carry intent.
- When the user says a cut is too tight ("give it more space in front"), widen that segment's start by 0.1 to 0.3s.

## Rendering the cut (stage 2)

Render with the helper script (it generates the filter_complex; never hand-type it):

```bash
python3 scripts/render_cuts.py projects/<slug>/cuts/cuts.json projects/<slug>/renders/roughcut.mp4
```

After rendering, verify cut cleanliness: re-transcribe the rough cut (`whisperx renders/roughcut.mp4 --model small ... --output_format txt`) and check the text equals the keep-list text with no fragments of dropped takes and no clipped first/last words. Cheap, catches boundary errors immediately.

For reference, the generated command shape for up to ~60 segments is a single filter_complex:

```bash
ffmpeg -i source/raw.mp4 -filter_complex \
"[0:v]trim=start=3.42:end=11.87,setpts=PTS-STARTPTS[v0];[0:a]atrim=start=3.42:end=11.87,asetpts=PTS-STARTPTS[a0];...\
[v0][a0][v1][a1]...concat=n=<N>:v=1:a=1[outv][outa]" \
-map "[outv]" -map "[outa]" -c:v libx264 -crf 18 -preset fast -c:a aac renders/roughcut.mp4
```

For more segments, cut each to a file and use the concat demuxer. Always re-encode (stream copy at arbitrary timestamps lands on non-keyframes and desyncs).

## Graphics (stages 3 and 4)

- Route through `/talking-head-recut` (overlay cards on existing footage). It plans cards from the transcript, authors HTML per card, renders via hyperframes.
- One composition per graphic segment in `graphics/<nn>-<name>/`. A note on one graphic re-renders only that composition.
- Composite a transparent overlay onto the base video at its timestamp:

```bash
ffmpeg -i renders/roughcut.mp4 -i graphics/03-stat-callout/out.mov \
  -filter_complex "[0:v][1:v]overlay=0:0:enable='between(t,42.1,47.8)'[v]" \
  -map "[v]" -map 0:a -c:v libx264 -crf 18 -c:a copy renders/pass2.mp4
```

Chain multiple overlays in one filter_complex rather than re-encoding per graphic.

## Captions (stage 5)

- Reuse `transcript/*.json`. Word timing drives per-word animate-in.
- Style default: Coolvetica, white text, solid black box behind words, middle band. Coolvetica is a free font (dafont.com/coolvetica.font); download to `assets/fonts/` on first use if missing.
- Prefer `/embedded-captions` with the preset's identity; verbatim rail default.

## Music (stage 6)

```bash
ffmpeg -i renders/pass2.mp4 -stream_loop -1 -i "assets/music/<track>" -filter_complex \
"[1:a]volume=-18dB,afade=t=out:st=<dur-3>:d=3[bg];[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[a]" \
-map 0:v -map "[a]" -c:v copy -c:a aac renders/pass3.mp4
```

Iterate the volume dB with the user; -18 start, many land near -23.

## Export (stage 7)

```bash
cp renders/final.mp4 ~/Downloads/<slug>.mp4
```

Keep everything in the project folder. Never clean up intermediates without being asked.

## Remotion engine (primary since 2026-07-02)

Stages 3-6 now run in the Remotion project at `engine/`. Per chapter: pre-cut the chapter from the locked rough cut with dense keyframes, drop it in `engine/public/`, author a `<Chapter>` composition importing the shared kit (`src/theme.ts`, `src/ui.tsx`), render with `npx remotion render <comp> out/x.mp4`. QA cheaply first: `npx remotion still <comp> --frame=N --scale=0.4` and eyeball the PNG.

- **Simulated angles (single static cam):** `angleAt()` + `ANGLE_CUTS[]` in the chapter file. Angles crop the frame (scale 1.0-1.28 + horizontal translate, origin ~50% 34%) and HARD-CUT on beats. Cap push at ~1.28x on 1080 source. HARD RULE: whenever a side card is on screen, the angle must put the speaker on the OPPOSITE side; full-screen type/list moments go in the BOTTOM band. Never cover the face — verify with stills at every card + interlude moment.
- **Auto-captions:** transcribe the RENDERED chapter (its own timeline), convert WhisperX JSON to `Caption[]`, render bottom-middle karaoke via `@remotion/captions` (`src/Captions.tsx`). Gate captions off during full-width bottom moments. See the `auto-captions` skill.
- **Ducked music:** generate/supply a bed, then duck under the VO after render:
  `ffmpeg -i out/ch.mp4 -i bed.wav -filter_complex "[0:a]asplit=2[vo][key];[1:a][key]sidechaincompress=threshold=0.02:ratio=8:attack=5:release=350[dm];[vo][dm]amix=inputs=2:normalize=0[a]" -map 0:v -map "[a]" -c:v copy -c:a aac out/ch_music.mp4`
- **Gotchas:** fonts via `@remotion/google-fonts` (NOT @remotion/fonts loadFont — webpack error in render); WebGL effects need `Config.setChromiumOpenGlRenderer("angle")`; ffmpeg `tremolo` frequency must be >= 0.1; the rendered mp4 finalizes (moov atom) only at the very end — wait for the task-complete signal before muxing.

## Known issues log

- 2026-07-02 dan-vsl: word-level trims must CLAMP edge padding to half the gap to the neighboring word, or the pad swallows a fragment of the next word (caught a dangling "And" before a splice). Fixed in dan-vsl cuts/apply_edit.py add(); apply the same clamp in any future word-anchored cutting.
- 2026-07-02 dan-vsl: on real VSL footage the retake pattern is: flub -> profanity ("fuck off") -> several false starts -> one long clean take. Resolve each chain by keeping the LAST long take; profanity segments are reliable flub markers to search for.
- 2026-07-02 smoke test: `--model tiny` is NOT usable — on a 30s test clip it dropped two of five speech blocks and produced wrong timestamps. Use `--model small` (the default) or larger, always. Verify transcript coverage against `ffmpeg -af silencedetect=noise=-35dB:d=0.8` speech blocks when a transcript looks short.
- 2026-07-02 dan-vsl: Whisper can SILENTLY MERGE a flubbed take + restart into one clean transcript sentence, dropping the flub words (including profanity) from the text entirely — the editorial read never sees them and they leak into the render. Four leaked this way. Detection: (a) the re-transcription diff is MANDATORY, it caught all four as insertions; (b) scan the raw transcript for intra-segment word-timestamp gaps > 1.5s in kept regions — a merged retake leaves a gap (the 5.9s "fuck off" flub showed as a 5.5s gap inside one "clean" sentence). Note: most such gaps are just pauses already handled by the silence trim; confirm against the verify transcript before excising.
- 2026-07-02 dan-vsl: when patching cuts by text anchors, NEVER anchor with an absolute occurrence number — VSL phrases repeat ("make more money" matched 11 minutes early and the patch would have excised 658s; caught in the printout before rendering). Anchor the fix to the flub position first (e.g. find "fuck off"), then take the NEAREST preceding hit (find_before pattern in dan-vsl cuts/fix_leaked_flubs.py). Always eyeball the printed excise durations before rendering.
- 2026-07-02 dan-vsl: after splitting segments, drop orphan slivers < 0.35s (a split left a 0.2s 5-frame flash of the speaker mid-breath).
- 2026-07-02 dan-vsl v5 z-order bug: giving the speaker video layer a static `zIndex: 3` (added so the PiP would ride above a cutaway page) silently painted the FULL-FRAME video over every overlay for the entire non-cutaway runtime — v5 rendered as a bare talking head for 2 minutes. Fix: `zIndex: pip > 0.02 ? 3 : 0` (elevated only while actually PiP). RULE: after ANY stacking/layer change, QA stills must sample at least one slam beat, one caption beat, and one card beat OUTSIDE the section you were working on — v5's pre-render QA only checked the cutaway beats, which were the only frames that worked.
- 2026-07-02 dan-vsl: full-page screenshots of scroll-reveal sites (GSAP/IntersectionObserver) capture SOLID BLACK below the fold — sections are unrevealed at capture time. The detailing capture was 80% black (rows y1800-8400 of 9097 uniform value 5) and the cutaway scrolled into void. Fix: step-scroll the live page first (600px steps, ~180ms waits) to fire every reveal, THEN screenshot fullPage — in ONE Playwright call (page state does not survive across separate MCP calls; a later screenshot call ran against about:blank). ALWAYS verify a capture with a PIL row-brightness scan before building a cutaway on it. Playwright MCP "Browser is already in use" -> `pkill -f mcp-chrome-98bf167`.
