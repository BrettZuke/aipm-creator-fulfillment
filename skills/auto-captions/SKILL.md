---
name: auto-captions
description: Add automatic word-level captions (subtitles) to a talking-head or VSL video. Transcribes the exact rendered clip with WhisperX, converts to the Remotion Caption format, and renders a bottom-middle karaoke caption band that highlights each word as it is spoken and NEVER covers the speaker's face. Use when the user asks for captions, subtitles, auto-captions, burned-in text of what is said, or "add captions to my video".
metadata:
  tags: captions, subtitles, whisperx, remotion, karaoke, talking-head
---

# Auto-Captions

Word-level, karaoke-highlight captions for a finished video cut. Two rules that make captions look professional instead of amateur:

1. **Caption the EXACT rendered clip, not the raw footage.** If the video was cut, transcribe the cut (its own timeline), or every caption drifts out of sync. One WhisperX pass per chapter/clip.
2. **Bottom-middle safe zone ONLY.** Captions live along the bottom third and never cross the speaker's face. If a full-width bottom moment (kinetic interlude, lower-third animation) is on screen, suppress captions for that span so they don't collide.

## Pipeline

### 1. Transcribe the rendered clip (word timings in the clip's own time)

```bash
ffmpeg -y -v error -i CLIP.mp4 -vn -ac 1 -ar 16000 /tmp/cap16k.wav
whisperx /tmp/cap16k.wav --model small --device cpu --compute_type int8 \
  --output_dir OUTDIR --output_format json --language en
```

On Apple Silicon `--device cpu --compute_type int8` is required. `--model small` is the floor (never `tiny` — it drops words). Correct obvious ASR errors (names, numbers, product terms) after, and make the caption text agree with any on-screen number that was arbitrated differently (e.g. a money figure fixed by a larger model).

### 2. Convert WhisperX JSON to the Remotion `Caption[]` format

```python
import json
d = json.load(open("OUTDIR/cap16k.json"))
words = [w for s in d["segments"] for w in s.get("words", []) if "start" in w and "end" in w]
caps = []
for w in words:
    t = w["word"].strip()
    if not t: continue
    caps.append({
        "text": (" " if caps else "") + t,     # leading space per token; whiteSpace:"pre"
        "startMs": int(w["start"] * 1000),
        "endMs": int(w["end"] * 1000),
        "timestampMs": int((w["start"] + w["end"]) / 2 * 1000),
        "confidence": w.get("score"),
    })
json.dump(caps, open("src/captions-CLIP.json", "w"), indent=0)
```

The `Caption` type is `{ text, startMs, endMs, timestampMs, confidence }`. Text is whitespace-sensitive — put the space BEFORE each word and render with `whiteSpace: "pre"`.

### 3. Page + render in Remotion (bottom-middle karaoke)

Install once: `npx remotion add @remotion/captions`. Group tokens into short pages with `createTikTokStyleCaptions({ captions, combineTokensWithinMilliseconds: 1100 })` (raise for more words per page, lower for word-by-word). Render each page in a `<Sequence>`; inside a page highlight the active token (`fromMs <= now < toMs`) in the brand accent, the rest in white, on a subtle glass pill. Anchor `bottom: 74`, `left: 50%`, `translate: -50% 0`, `maxWidth ~1160`. Working reference implementation: `video-editor/engine/src/Captions.tsx`.

**Mute ranges**: keep a list of `[startSec, endSec]` where a full-width bottom graphic owns the band (interlude, roles strip) and return `null` for pages starting inside them.

### 4. Style defaults

- Font: match the video's brand font (weight 800 for legibility over footage).
- Active word: brand accent color, slight `scale: 1.04`. Inactive: white.
- Background: low-opacity glass pill (`rgba(8,7,14,0.62)` + blur) so text reads on any background.
- Text shadow `0 3px 14px rgba(0,0,0,0.6)` for a hard-edge fallback.

## Not this skill

- Plain SRT export with no styling → just write the `.srt` from the WhisperX JSON.
- HyperFrames engine instead of Remotion → use `/embedded-captions`.
