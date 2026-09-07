# the operator captions - APPROVED

The approved default on Reel 001 / Reel 003 ("I like the captions").
**This is the default caption style for all of the operator's reels and YouTube videos
from now on.** Do not restyle without asking him.

Generator: `video-system/tools/captions.py`
First used on a vertical reel export at 1080x1920.

## The look

| | |
|---|---|
| Font | Coolvetica Rg (`assets/fonts/Coolvetica Rg.otf`) |
| Size | 78px at 1080x1920 (scale proportionally for other canvases) |
| Case | UPPERCASE |
| Colour | off-white `210,210,210`, spoken word `104,198,138` (green) |
| Outline | 5px black stroke at ~82% alpha |
| Backing | rounded box, radius 18, black at 59% alpha, 26px padding |
| Position | centred, text bottom at y=1560 (of 1920) |
| Line width | max 930px, one line only |
| Timing | word-synced; each word lit from its start until the next word starts |

## Rules that matter

- **Never cover his face.** His face runs roughly y150-800 and his hands reach
  y1200 when he gestures. y=1560 clears both. If a shot is framed differently,
  move the captions, do not let them cross him.
- **Break lines at clause ends, not on width alone.** Width-only splitting
  produced lines like "WAS DOING WAS LOOKING" that cut across the sentence. A
  word ending in `.,?!;:` closes the line, and so does a pause over 0.35s.
- **Off-white, not pure white.** the operator's footage is HLG HDR; 255 sits at peak
  brightness and glares on an HDR display. 210 reads as normal white.
- **Render as an overlay, never burn into decoded frames.** Drawing onto frames
  in Python round-trips the footage through the wrong colour matrix and darkens
  it. Output a transparent track and let ffmpeg composite. See
  [Colour](#colour-non-negotiable).

## Colour (non-negotiable)

the operator's phone shoots 10-bit HEVC, BT.2020 primaries, HLG transfer. Every encode
in the chain must carry:

```
-colorspace bt2020nc -color_trc arib-std-b67 -color_primaries bt2020 -color_range tv
```

He rejected an earlier version for looking graded when nothing had been graded:
the tags had been dropped and the footage pulled through OpenCV. Nothing in this
pipeline grades or corrects colour, and nothing should.

## Usage

```bash
python3 video-system/tools/captions.py \
    --video path/to/cut.mp4 --out path/to/final.mp4
```

Transcribes with faster-whisper (word timestamps), renders the overlay to a
qtrle .mov with alpha, composites, and preserves the source colour tags.
`--label "TEXT" --label-range 7.7:32.1` adds a top banner over a time range
(used for PATIENT DATA REDACTED).

## Notes for YouTube (16:9)

Not yet used on a 16:9 video. When first doing so: keep the font, case, colours
and clause-based breaking; recompute size and y-position for the canvas (78px
and y1560 are tuned for 1080x1920), and check against the actual framing rather
than assuming. Report back what landed so this file can be updated.
