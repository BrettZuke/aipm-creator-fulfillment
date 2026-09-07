# Phase 5. VSL, landing page, funnel, and the edit

**Deliverable:** a scripted and edited VSL, a landing page it sits on, and a funnel that
carries someone from click to booked call.

**Done when:** you can send one link to a cold visitor and a qualified call appears in the
calendar, and you can point at the numbers at each step.

Needs the offer from phase 1 and the competitor funnels from phase 2.

---

## 1. Script the VSL

`sops/vsl_sop.md` is the process. The core rule: **a VSL carries ethos and pathos. Logos is
for the sales call.** A VSL that argues its case with logic converts worse than one that
establishes who this person is and why the viewer should feel understood. Save the proof
and the mechanism detail for the call, where there is someone to answer objections.

Write it against the offer document from phase 1. If the offer is vague, stop and fix the
offer; you cannot write your way past it.

Two more sources worth reading before you draft:

- `sops/copywriting_frameworks.md`, the eight-module framework set
- [ai-partner-method-direct-response-toolkit](https://github.com/BrettZuke/ai-partner-method-direct-response-toolkit)
  for triggers, swipe headlines and voice constraints

And one hard-won caution from a real deck: do not teach so much before the pitch that the
viewer has already got what they came for. If most of the value lands before the offer,
the offer becomes optional.

Run the finished script through `skills/avoid-ai-writing` and `skills/stop-slop`. Then read
it out loud in the client's voice. If it does not survive being spoken, it will not survive
being filmed.

## 2. Build the page

Read the winning references first. Do not freestyle a design; cloning the closest proven
reference beats inventing one, and freestyled design has been rejected repeatedly.

Load `skills/high-end-visual-design` plus `skills/premium-funnel-page`. Start from
[ai-partner-method-personal-page-build](https://github.com/BrettZuke/ai-partner-method-personal-page-build),
or from the premium template pack if you have been given access to it.

Non-negotiables:

- Inter and Roboto are banned. Pick a real typographic identity.
- Check it at 1440px and at 390px. Mobile is most of the traffic.
- Console clean, no errors.
- Click every link and CTA yourself and confirm where each one lands.

## 3. Wire the funnel

The standard shape:

```
Traffic  ->  Opt-in page  ->  VSL page  ->  Booking page  ->  Confirmation page
              (email captured)   (watch)      (qualified)      (what happens next)
```

At each step:

- **Opt-in:** email into the client's platform, tagged by source so you know which content
  produced it.
- **VSL page:** the CTA appears at the pitch, not at the start, and not only at the end.
- **Booking:** qualifying questions on the form. An unqualified booked call costs more than
  no call.
- **Confirmation:** tell them exactly what happens next and when. This is where show-up
  rate is won or lost.
- **UTMs on everything**, so phase 3's attribution can tie a booked call back to the video
  that caused it.

Reminders before the call matter more than any of the copy. Text reminders measurably
increase show-up rate. Voice reminders do not, and most of them hit voicemail, so they are
not worth the cost or the annoyance.

If you send SMS, send only to countries where the audience can actually afford the offer,
and check delivery: some destinations accept the message and never deliver it, and you pay
either way.

## 4. Edit the VSL

A VSL earns the full pipeline. Use [`video-system/`](../video-system/): seven stages from
transcription through graphics to render, with the rough cut locked before any graphic is
built. Read `video-system/README.md` first, then open that folder in Claude Code.

For the quick first pass on its own,
[aipm-reel-editor](https://github.com/BrettZuke/aipm-reel-editor) strips silences, filler
words and duplicate takes in one command:

```bash
python3 edit.py vsl_raw.mp4
```

Either way, the manual pass is what makes it look professional:

- **Hide every cut.** Alternate a slight punch in and out across each join. Never punch
  into the face.
- **Cover the flubs.** Cut the audio and put an overlay over the join.
- **Captions.** Burn them in. Most of the audience watches muted first. The default style
  is `video-system/presets/captions-approved.md`, rendered by
  `video-system/tools/captions.py`. The cinematic alternative is for hero pieces and costs
  about an hour a clip.
- **One motion personality.** About 400ms, `cubic-bezier(0.16, 1, 0.3, 1)`, no overshoot.
  Save overshoot for money moments. Mixing personalities is what makes an edit look amateur.
- **The six-second rule.** No stretch of frame goes past about six seconds without a visual
  change.
- **Never touch the colour.** If the source is HDR, carry the colour tags through and never
  draw onto decoded frames. Getting this wrong makes the whole video look washed out and it
  is not recoverable without a re-export.

Before you upload anywhere, if the file came out of CapCut, re-encode it with faststart so
the moov atom is at the front. Without it a browser downloads the whole file before it
plays, and a VSL that takes twenty seconds to start has already lost.

```bash
ffmpeg -i vsl_edited.mp4 -c copy -movflags +faststart vsl_final.mp4
```

## 5. Host it

Video over about 100MB should not sit on Vercel; the bandwidth cost is real and the limits
bite. Put it on object storage such as Cloudflare R2 and serve it from there.

---

## Checklist

- [ ] Offer document is specific enough to write against
- [ ] VSL scripted with ethos and pathos, logos held for the call
- [ ] Script run through the anti-slop skills and read aloud
- [ ] Page built from a proven reference, not freestyled
- [ ] Checked at 1440px and 390px, console clean, every CTA clicked
- [ ] Funnel wired end to end with UTMs at every step
- [ ] Qualifying questions on the booking form
- [ ] Text reminders set up before the call
- [ ] VSL edited, cuts hidden, captions burned in, colour untouched
- [ ] Re-encoded with faststart and hosted off Vercel
- [ ] You have walked the whole funnel yourself as a cold visitor, on a phone
