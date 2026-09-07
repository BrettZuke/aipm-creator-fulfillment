# Phase 4. The daily scripter, and the weekly email ritual

**Deliverable:** scripts in the client's inbox every morning and on the board, so they can
record daily without deciding what to record.

**Done when:** the client wakes up, opens one email, picks a script, and films it. No
briefing call, no blank page.

Needs phase 1 (voice), phase 2 (signal) and phase 3 (a board to write to).

---

## How it works

Four stages, run as one command:

1. **Scrape** every active creator on the roster
2. **Parse** the outliers and the patterns behind them into today's signal
3. **Script** today's content from the brand voice plus that signal
4. **Email** the scripts, hooks first, so they can scan and decide before reading in full

The scripter is deliberately two passes, not one. **Analyse** reads the brand voice, the
scripting toolkit and today's signal, and picks the strongest angles for this specific
client with a reason for each. **Write** then takes one brief at a time, drafts several
competing hooks, picks the strongest against stated criteria, and writes the script under
it. Asking a single call to do both produced generic hooks, which is why it is split.

## Set it up

**1. Create the five tables.** The scripter reads and writes tables that do not exist in a
fresh instance. They ship as migrations in the operating system repo from phase 3
(`supabase/migrations/`, the five files named `content_*`): `content_cards` is the board,
`content_creators` is the roster, `content_outliers` is the signal, `content_machine_runs`
is the run log, and `content_feedback` records every verdict. Apply the migrations before
anything else in this phase. All five have row-level security on and are scoped to one
workspace, so a second client on the same instance can never read this one's board.

**2. Point it at the client's instance.** Nothing is hardcoded: every script reads the same
`.env` at the repo root, so switching client is switching one file rather than editing six.
That is deliberate, because a project ref left over from the last client writes this client's
scripts onto that client's board and nothing errors.

```
SUPABASE_PROJECT_REF=   the client's project ref
CONTENT_AGENCY_ID=      the client's workspace id
CONTENT_EMAIL_TO=       who gets the scripts
CONTENT_APP_URL=        the client's operating system, e.g. https://os.theirdomain.com
SECRETS_ENCRYPTION_KEY= the same value as the operating system, or the buttons will 403
RESEND_API_KEY=         free tier is fine
```

`SECRETS_ENCRYPTION_KEY` has to match the value in the operating system's own environment
exactly. The email signs each feedback button with it and the app verifies the signature,
so a mismatch makes every button in the email fail.

**3. Load the two knowledge documents.** The scripter refuses to run without them and says
so: `missing from knowledge_docs: Content Strategist Brain, Scripting Toolkit`. They are
not in the database of a fresh instance, so load them from `knowledge/`:

```bash
python3 tools/content-machine/load_knowledge_doc.py \
  --agency <workspace id> --title "Content Strategist Brain" \
  --file knowledge/CONTENT_STRATEGIST_BRAIN.md

python3 tools/content-machine/load_knowledge_doc.py \
  --agency <workspace id> --title "Scripting Toolkit" \
  --file knowledge/SCRIPTING_TOOLKIT.md
```

Both are craft, not client-specific, so the same two files serve every client you run. They
land at `/knowledge` in the app, editable there, and the writer re-reads them on every run.

Two more docs are optional and both make the scripts markedly better:

- **Proof Inventory**, from `knowledge/PROOF_INVENTORY_TEMPLATE.md`. What this client can
  actually show on camera. Without it the writer falls back to claims any account could
  make. Each `##` heading in it is one subject in the rotation, so adding a heading is the
  cheapest way to widen what the machine can talk about.
- **Script Feedback**, created automatically the first time a script is rejected. Do not
  write it by hand.

**4. Add the roster.** The active creators live in Supabase, not in a local list. Pausing a
creator in the dashboard genuinely takes them out of tomorrow's run.

**5. Write the client files.** Nothing carries a persona in its code, so three short files
under `knowledge/` decide whose voice comes out. All three are read at run time, and a
missing one either stops the run or quietly makes the output generic:

- `WHO.md`: one paragraph. Their name and handle, what they actually do, who for, what they
  are NOT, and what their proof is. The scripter and the email intel both read it.
- `BRAND_VOICE.md`: from phase 1, built from their own transcripts. This is the one that
  decides whether a script sounds like them.
- `PROOF_INVENTORY.md`: from `knowledge/PROOF_INVENTORY_TEMPLATE.md`.

⚠️ Do this before the first run, not after. A script written against the wrong voice is not
worth editing, and the client seeing one is worse than them seeing nothing.

**6. Free keys only.** `GEMINI_API_KEY` for the two agent passes, `GROQ_API_KEY` as
fallback, free Apify tokens for scraping. The daily chain
(`content_machine_daily.py` -> `content_signal_parser.py` -> `content_scripter.py` ->
`content_machine_email.py`) calls no paid API at any point.

`content_plan_generator.py` is different: it calls a paid Anthropic API directly at line
115. It is not part of the daily run. Leave `ANTHROPIC_API_KEY` unset and the daily chain
works fine.

## Run it

```bash
# Dry run first, always
python3 tools/content-machine/content_machine_daily.py --reels --dry-run

# For real
python3 tools/content-machine/content_machine_daily.py --reels

# YouTube scripts
python3 tools/content-machine/content_machine_daily.py --youtube

# Signal already fresh? Skip the scrape
python3 tools/content-machine/content_machine_daily.py --reels --skip-scrape

# Email only, to a different address
python3 tools/content-machine/content_machine_email.py --to client@example.com
```

Useful flags: `--min-multiple` sets how far above a creator's own average a post must be
before it counts as an outlier. `--no-email` writes the board without sending.

A stage that fails does not silently produce a thin result; scraping failures are counted
and surfaced. If the output looks thin, read the run output before rerunning.

## Schedule it

Run it daily, early, so scripts are there before the client starts work.

On a Mac, if you schedule with `launchd`, two things will bite you. A script that lives
under `~/Desktop` cannot be executed by a launch agent, and a symlink does not fix it: put
a real copy under `~/Library/Scripts` and re-copy it after every edit. And permissions are
granted per agent label, so testing with a throwaway label proves nothing about the real
one.

Cloud cron is the less painful path. A scheduled serverless function hitting an endpoint
avoids all of the above.

## The three formats

The scripter covers reels and YouTube. Stories are written by hand, and they are the
cheapest trust you will ever build.

- **IG Stories:** daily, unscripted, phone-shot. What they are doing, what they just
  learned, one question to the audience. `sops/personal_brand_sop.md`.
- **Reels:** the scripter's `--reels` output. Hook in the first two seconds or nothing else
  matters. `skills/viral-reel-generator` and `skills/viral-hook-creator` if you are writing
  by hand.
- **YouTube:** `--youtube` output, plus `sops/youtube_content_sop.md`. Longer, belief-shifting,
  and the thing that produces qualified calls rather than views.

Run every script through `skills/avoid-ai-writing` before it reaches the client.

## Editing

[aipm-reel-editor](https://github.com/BrettZuke/aipm-reel-editor) removes silences, filler
words and accidental repeats from a talking-head clip, and stitches multiple clips
together. Point Claude Code at the folder and say "edit my clip".

```bash
python3 edit.py my_clip.mp4     # -> my_clip_edited.mp4 + a report of every cut
```

Two things it will not do for you. Hide the cuts: alternate a slight punch in and out
across every join so the edit does not read as a jump cut, and never punch into the face.
And cover the flubs: cut the audio and put an overlay over the join.

For anything that needs graphics rather than just a tighter cut, use
[`video-system/`](../video-system/) instead. It is the full seven-stage pipeline:
transcribe, rough cut, graphics, refine, captions, render. Read its `README.md` first.
Captions for volume content: `python3 video-system/tools/captions.py --video cut.mp4 --out final.mp4`.

## The weekly email ritual

Once the daily content runs itself, the weekly ritual is what keeps the list warm.

Every week, on a fixed day, write the next seven days of emails in one sitting. Not one
email at a time as the day arrives; the whole week, in one pass, so the arc holds together.

Build it as a Claude Code skill so it runs the same way every week. The shape that works:

- **A fixed day**, tied to whatever the client's weekly anchor is (their live call, their
  webinar, their drop). The emails are written in the gap between one anchor and the next.
- **The whole week in one pass**, so the arc holds together. Written one at a time as each day
  arrives, they repeat themselves and go nowhere.
- **Voice and audience come from `knowledge/`**, never from the skill itself. The skill is the
  ritual; the client is the input. Write it that way and the same skill serves the next client
  by pointing it at a different profile, instead of being forked and drifting.

On Telegram specifically: it is worth it when the audience is already there and active. It
is not worth building an audience on a second platform from zero while the email list is
still small. Default to email only, and add Telegram when the client asks for it.

Frameworks and templates for the emails themselves:
[ai-partner-method-email-toolkit](https://github.com/BrettZuke/ai-partner-method-email-toolkit).

---

## Checklist

- [ ] The five `content_*` migrations applied to the client's Supabase
- [ ] Both knowledge documents loaded, and visible at /knowledge
- [ ] `.env` filled in, with `SECRETS_ENCRYPTION_KEY` matching the app exactly
- [ ] All three `PROJECT_REF` lines pointed at the client's Supabase
- [ ] Board URL and recipient email changed
- [ ] Roster populated in the dashboard
- [ ] Free keys only; `ANTHROPIC_API_KEY` left unset
- [ ] Dry run produces sensible scripts in the client's voice
- [ ] Scheduled daily and confirmed running for three consecutive days
- [ ] Client has recorded from a generated script and was happy with it
- [ ] Weekly email ritual set up with a fixed day
