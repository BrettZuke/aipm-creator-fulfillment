# The video system

A seven-stage editing pipeline driven by Claude Code. Raw footage in, finished video out.
This is the system behind the client's reels, shorts and VSL.

`CLAUDE.md` is the operating instruction. Open this folder in Claude Code and talk to it
the way you would talk to an editor. It runs the pipeline and only asks when a creative
call genuinely needs a decision.

## The seven stages

1. **Intake**: raw clip in, project folder created
2. **Rough cut**: WhisperX word-level transcription, then cut silences, filler words, false
   starts and bad takes
3. **Graphics**: one graphic per content beat, built as separate compositions so a change
   re-renders one segment rather than the whole video
4. **Refine**: the notes pass, graphic by graphic. This is the step that separates a good
   edit from AI slop
5. **Captions**: short-form only
6. **Render**: chapter-based, so a note re-renders one chapter
7. **Export**

Never start graphics before the rough cut is locked. Changing cuts after graphics means
redoing every sync point.

## What is in here

```
CLAUDE.md            the pipeline, in full. Read this first
workflows/
  pipeline.md        the mechanics of each stage
  editing-style.md   the default look and why
  retention-editor.md  keeping people watching
presets/
  captions-approved.md   the default caption style
  captions-cinematic.md        the opt-in alternative, for hero pieces
  short-form-explainer.md      reels and shorts
  tiktok-raw.md                lower production, higher volume
  long-form.md                 YouTube and VSL
tools/
  captions.py        renders the default caption style onto a cut
  caption_ab.py      renders both styles on the same cut so you can compare
  beat_grid.py       computes the cut rhythm from word timestamps
  gesture_cues.py    finds the moments worth punching into
  sound_board.py     sound design under the voiceover
  bg_replace_v2.py   background replacement
```

## Before you run anything

**Install the dependencies.** WhisperX for transcription with word-level timestamps, and
FFmpeg 8 for cutting, concatenation and export.

```bash
uv tool install whisperx
brew install ffmpeg
```

**Get the fonts.** `tools/captions.py` renders in Coolvetica and expects
`../assets/fonts/Coolvetica Rg.otf` and `Coolvetica Rg Cond.otf`. The font is not included
here because redistributing it is a licensing question, not a technical one. Buy or license
it from Typodermic, create `assets/fonts/` next to this folder and drop the two files in.
Or change `CAP_FONT` and `LAB_FONT` at the top of `captions.py` to a font you already have
a licence for, which is the honest answer for most people.

## The rules that matter most

**One motion personality per project.** The default is Premium: about 400ms,
`cubic-bezier(0.16, 1, 0.3, 1)`, no overshoot. Overshoot pops are reserved for money and
hero moments. Mixing personalities is the single fastest way to make an edit look amateur.

**Three motion layers, always.** Primary is the card or the number. Secondary is icon
draw-ins and shadows. Ambient is panel sheen and a breathing vignette. If an edit looks
flat, it is missing layers.

**The six-second rule.** No stretch of frame goes more than about six seconds without a
visual change: a cut, a punch-in snap, a card beat, or a type moment.

**Hide every cut.** Punch-ins are 1.0 to 1.07 snaps over four frames at cut points, with a
slow drift between and a three-frame brightness kiss on each snap. Set the transform origin
near the face and never punch into the face itself.

**Quiet is professional, loud is slop.** Card enters around 0.15, ticks around 0.09, money
dings around 0.22, whooshes on section washes around 0.3.

**Never touch the colour.** If the source is HDR, carry the colour tags through and never
draw onto decoded frames. Getting this wrong washes the whole video out and it is not
recoverable without a re-export.

## Captions

Two styles. **The approved style is the default. Do not switch without deciding to.**

**Approved** (`presets/captions-approved.md`): Coolvetica 78px, uppercase, off-white
with the spoken word in green, black rounded box, fixed band at y=1560. One command:

```bash
python3 tools/captions.py --video cut.mp4 --out final.mp4
```

Reuse the WhisperX transcript rather than transcribing twice:
`captions.py --words <timings.json>` takes pre-computed word timings and skips its own pass.

**Cinematic** (`presets/captions-cinematic.md`): picks the words that carry the claim,
scales those up, and places them around the speaker with real subject depth. Runs on
HyperFrames, costs closer to an hour per clip, and is for a hero piece rather than volume.
Read that preset's overrides before running it; they beat the skill's own defaults on
colour, face clearance and typography.

To compare them on the same cut: `python3 tools/caption_ab.py`.

## A note on names

`CLAUDE.md` and some presets say "ask the operator" and reference a `dan-vsl` project. Read those
as "ask whoever owns the creative call", which on your projects is you and your client.
The caption preset is named `captions-approved` because that is the style that was
signed off, not because it only applies to one person. It is a good default; keep it unless
your client's brand says otherwise.

## Where this fits

The simpler alternative is
[aipm-reel-editor](https://github.com/BrettZuke/aipm-reel-editor): one command, strips
silences and filler words, no graphics. Use that for volume talking-head content.

Use this system when the video needs graphics: the VSL, a launch video, a hero piece.
