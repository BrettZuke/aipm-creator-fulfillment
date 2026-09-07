# the operator captions - CINEMATIC (alternative, opt-in)

Added 2026-09-02. **This does not replace
[captions-approved.md](captions-approved.md), which is still the
default for every reel and YouTube video.** This is a second style to reach for
when a clip is worth the extra work, and it is the style to run against the
approved one whenever the operator wants to compare.

Source: the `cinematic-caption` skill at `~/.claude/skills/cinematic-caption/`
(from `github.com/audrey-560/hyperframes-cinematic-caption`, MIT). Read
`references/style-system.md` in that skill before designing, and
`references/dynamic-layout-recipes.md` too when a passage has three or more
designed moments.

## The difference in one line

Approved puts every word in the same place and lights the spoken one.
Cinematic decides which words carry the claim, makes those big, and places them
around the speaker.

| | Approved | Cinematic |
|---|---|---|
| Engine | `tools/captions.py` (Python, PIL, ffmpeg) | HyperFrames (HTML compositions) |
| Placement | fixed band, text bottom y=1560 | subject-relative, changes per beat |
| Emphasis | spoken word lit green | hero words scaled up, rest is support |
| Typography | one face, one size | support sans plus a heavy display face |
| Depth | flat overlay | hero words can sit behind hair and shoulders via a real matte |
| Cost per clip | one command, minutes | a plan file, a matte, review passes, closer to an hour |
| Best for | talking-head reels, volume, anything shipping today | one hero clip, a launch video, a piece worth the time |

## Route

HyperFrames is already working on this machine (checked 2026-09-02: Node 22.22.3,
ffmpeg 8.1.1, whisper present; only Kokoro TTS, MusicGen and Docker are missing
and none of those are used for captions).

```bash
npx hyperframes init <slug>          # or work in an existing composition
```

Then invoke the skill and let it run its own workflow:

```text
Apply the cinematic-caption skill to renders/roughcut.mp4
```

It writes `cinematic-caption-plan.json` before it touches anything, so read that
plan and correct the hero-word choices before any render. That plan file is the
cheap place to disagree with it.

## Overrides (these beat the skill's defaults)

The skill was written for generic footage. the operator's footage is not generic, so
where they conflict, this list wins.

- **Off-white, never 255.** The skill says "prefer white for normal support
  captions". the operator's phone shoots 10-bit HEVC, BT.2020, HLG. Pure white sits at
  peak brightness and glares on an HDR display. Use `210,210,210` for support
  copy, same as the approved style.
- **Colour tags survive or the render is rejected.** Every encode carries
  `-colorspace bt2020nc -color_trc arib-std-b67 -color_primaries bt2020
  -color_range tv`. Nothing in this pipeline grades. He rejected an earlier
  build for looking graded when nothing had been graded. See
  `captions-approved.md` and the never-touch-colour rule.
- **Never cover his face.** His face runs roughly y150-800 and his hands reach
  y1200 when he gestures. The skill's "10-22% overlap around hair or outer head
  contours" is allowed on hair and shoulders only. Face, mouth and gesturing
  hands stay clear, always. This rule outranks any layout the skill proposes.
- **No emoji, no em dashes, no en dashes** in any on-screen text, per the
  project rules in `../CLAUDE.md`.
- **Coolvetica is the house face.** `assets/fonts/Coolvetica Rg.otf` for support
  copy and `Coolvetica Rg Cond.otf` where the skill calls for condensed. If a
  clip genuinely needs a heavier display face for hero words, bundle it locally
  and say which one in the project notes, do not synthesise weight from a light
  file (the skill bans that too, and it is right).
- **Cuts stay hidden.** The alternating punch in and out that hides every cut is
  a separate rule and still applies; captions do not change it, and a punch must
  never push into his face.

## Where the two genuinely disagree

Worth knowing before judging the comparison, because these are choices, not bugs.

- The approved style is a **bottom band**. The cinematic skill explicitly bans
  bottom-centre karaoke. If the operator prefers the band after seeing both, that is a
  real answer and this preset stays a special-occasion tool.
- The approved style lights **every** word. The cinematic skill treats a big
  word on every cue as a failure and wants one hero per sentence.
- The cinematic skill refuses to claim text is behind a person without a real
  matte. If the matte is bad, it will place the word in negative space instead
  of faking depth. That is correct behaviour, not a fallback to complain about.

## Comparing the two

```bash
python3 tools/caption_ab.py --cut renders/roughcut.mp4 \
    --b renders/cinematic.mp4 --out renders/compare
```

Renders the approved version from the same cut (unless `--a` is given), stacks
both side by side with a label burned over each, and drops paired stills.
The side-by-side is a **review copy only, never a deliverable.**

Judge on: does a hero word ever sit on his face or hands, is the spelling of
every hero word still unambiguous, does the eye know where to look next, and
does the footage still look ungraded.

## Status

Not yet run on a real the operator clip. First time it is used, record which one he
picked and why in this file, so the choice is not re-litigated every edit.
