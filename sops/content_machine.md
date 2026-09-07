# Content Machine

The daily reel engine. Four stages, all on free keys, ending with scripts on the client's board.

```
  ROSTER          who we learn from, managed on the Creators tab
    |
  SCRAPE          their content, free Apify tokens
    |
  PARSE           what beat its own creator's median, and why
    |
  SCRIPT          Brain + today's signal, into content_cards
```

## Money rule

Everything here is FREE. Free Apify tokens (`apify-1` through `apify-10`, roughly $5/month each)
for scraping, free Gemini (`GEMINI_API_KEY`, model `gemini-2.5-flash`) for both agent passes. Never
`ANTHROPIC_API_KEY` or `OPENAI_API_KEY`; they are paid and off limits without a decision for
that specific run. See the Money and Paid Services rule in CLAUDE.md.

## The roster

Source of truth is the Supabase table `content_creators`, scoped to the client's workspace id
(`CONTENT_AGENCY_ID`) and managed at **/content?tab=creators** in their dashboard. Every creator
has a role and a status, and both change what the machine does:

| Role | What it means | Feeds |
|---|---|---|
| `strategist` | Teaches the craft of making content | The Brain |
| `emulate` | A direct copy target | Daily signal and scripts |
| `watch` | Tracked, lower weight | Collected, not scripted from |
| `ideas` | Top-of-funnel inspiration, format never copied | Nothing automatic |

`status = 'paused'` drops a creator from the daily scrape and from the scripts while keeping
everything already collected. Deleting is the destructive option.

`content-machine/roster.json` is the seed, not the truth. It exists so the roster can be rebuilt
from scratch, and `tools/<group>/seed_content_creators.py` pushes it up. Re-running the seed preserves
whatever role and status has since been set in the app; `--reset` forces the file's values back.

A worked example of the `ideas` role: an entertainer whose concepts are useful at the top of the
funnel but whose FORMAT must never be replicated, and whose YouTube is deliberately not scraped.
Tagging them `emulate` by mistake is how a serious account starts making novelty content.

## Running it

```bash
python3 tools/content-machine/content_machine_daily.py               # scrape, parse, script, 3 reels
python3 tools/content-machine/content_machine_daily.py --scripts 5
python3 tools/content-machine/content_machine_daily.py --skip-scrape # reuse today's scrape, re-script only
```

Roughly 1 minute with `--skip-scrape`; a full run is paced by the Instagram scrapes.

Individual stages, when something needs re-running on its own:

```bash
python3 tools/content-machine/content_signal_parser.py --no-llm      # outlier maths only, zero API calls
python3 tools/content-machine/content_scripter.py --count 3 --dry-run
```

## How an outlier is decided

Deterministic, no LLM. A post counts when it beats **its own creator's median** by
`--min-multiple` (default 2.0) and clears an absolute floor (5,000 views, or 300 engagement).
Judging every creator against their own baseline is what stops a 1.5M-view account from drowning
out a 15k-view one.

Instagram reports no view count for carousels, so a carousel-first account is measured on likes
plus comments instead. The metric name travels with every outlier, so nothing pretends engagement
is reach. Creators with fewer than 5 measurable posts are skipped and named in the output.

**Both platforms run independently.** Instagram uses captions as the hook; YouTube uses the video
title plus the opening of the transcript, which is the spoken hook. A creator with only a YouTube
channel and no Instagram still produces signal, and each platform gets its own median. Reading
YouTube inside the Instagram branch silently dropped a YouTube-only second channel once.

## Where the output lands

Scripts become cards in `content_cards`, stage `scripted`, visible at
**/content?tab=board**. `created_by` says which machine wrote it:
`agent:content_scripter` is the Python pipeline in this folder, `agent:content_machine` is the
cloud agent. Each card's notes record the pattern, why it works, and a link to the outlier it was
built from, so any script traces back to the post it is competing with.

A card is meant to be filmed from, not just read, so the body carries everything in the order it is
used: the title and thumbnail (YouTube only), the hook, the on-screen text, the script, the ask,
and a **SHOT LIST** naming the exact screens to capture. Every scripted card has one: the cloud
agent writes it, and the older Python cards were backfilled by
`scripts/backfill-shot-lists.ts` (Groq only, so the morning runs keep Gemini's allowance).

### The Record tab, where the filming happens

**/content?tab=record.** Nineteen finished scripts once sat on a board and none had been
filmed, because a board card is something to READ: the whole piece in one blob, at card size, labels
still in it. The Record tab is the same script laid out in the order it gets used, one at a time,
with a **Filmed it** button that moves the card to Filming.

Named Record, not Film, because **Film mode already exists** as the floating button that hides app
chrome for screen recording, and both appear on this page.

Parsing lives in the dashboard's `src/lib/content/film.ts`, pure and unit tested, because the labels are
written by the machine at one end and read by the view at the other. Three things only a browser
found:

- **The hook printed twice**, once as the hero and again as the script's first spoken line, because
  that is how scripts are written. Same at the other end with the ask. Both are stripped from the
  words, matched loosely so punctuation does not leave the duplicate behind.
- **A grid item defaults to `min-width: auto`**, so the horizontally scrolling picker refused to
  shrink and blew the panel wider than a phone, cutting the hook off mid-word at 390px. `min-w-0`
  on both grid children.
- **Nine of nineteen scripts were one unbroken paragraph**, because the fallback model ignores the
  line-break instruction. Each sentence gets its own line the way a teleprompter presents words,
  while beats the writer did separate stay separate.

House style is enforced such that `body === sanitize(body)` for every card the cloud agent files.
That invariant is what makes the audit trustworthy: run
`npx tsx scripts/audit-board-scripts.ts` from the dashboard repo to put every card on the board
through the same guards that gate new ones, and any difference it reports is a real problem rather
than formatting. 23 of 23 passed on 2026-08-01.

⚠️ The audit only applies the missing-ask check to cards at `scripted` or later. An idea is not a
script: the email intelligence agent files cards at the `ideas` stage that correctly have no call to
action, and flagging four of those buried the one finding that mattered. A noisy audit is how a real
problem gets missed.

Signal for the day is kept at `.tmp/_signal/<date>.json`. Dry-run scripts go to `.tmp/_scripts/`,
deliberately a different directory: they were once written next to the signal and got loaded back
in as signal on the following run.

## Gotchas

- **Shorts-only channels have no /videos tab.** yt-dlp raises rather than returning nothing, so
  `scrape_youtube_creator.py` falls back to /shorts and then the bare channel page. Those channels
  (for example @nickautomates) are the most useful ones to study for short-form, so treating the
  error as "no content" would skip exactly the wrong accounts.
- **`scrape_youtube_creator.py` takes `--channel`, not a positional argument.** Passing the handle
  positionally fails with an argparse error that is easy to miss inside a loop.
- **YouTube blocks free transcripts.** `youtube-transcript-api` and yt-dlp both return nothing on
  any real pull. Backfill with `tools/youtube/apify_yt_transcripts.py` (topaz actor, free tokens).
- **Folder naming.** `scrape_creator_deep.py` writes to `.tmp/<instagram handle>`, so the parser
  resolves `instagram or handle`. A roster handle that differs from the Instagram handle is fine;
  a parser that assumed `handle` would silently find nothing.
- **zsh does not word-split unquoted variables** the way bash does. Looping creator names from a
  single string ran all 16 as one username and returned 0 posts with no error. Use a literal list.
- **Apify tokens hit a monthly hard limit.** The scrapers rotate through all 10; a "usage hard
  limit exceeded" message means that token is spent, not that the run failed.
- **House style is enforced in code, not prompts.** Both agents run their output through
  `sanitize()`; the model emits em dashes and arrows no matter what the prompt says.

## Running it on a schedule

The stages are ordinary scripts, so any scheduler works: cron, a launchd agent, or a GitHub
Actions workflow if the client's data can live in a private repo. Run it once a day, early
enough that the scripts are waiting before the client starts work.

⚠️ **One script per run, never a batch of three.** Writing three at once needs roughly 13,000
tokens inside a minute, and the free tiers are per-minute limited well below that, so the third
call fails every time and on a capped day all three do. Space the runs a few minutes apart
instead. They need no coordination: everything a run needs it reads off the board, including how
many cards were filed today and which outliers have already been used.

### The subject is decided in code, not by the model

⚠️ **The first six scripts were the same video six times**: Content Machine Revealed, Content
Machine Exposed, Build AI Content Machine, Content Machine Setup Guide, My Free Content Machine,
My AI Scrapes 36 Creators. Each was built from a DIFFERENT outlier, so the skip-what-you-used rule
saw fresh input every morning and was satisfied. **What a viewer experiences as repetition is the
subject, and nothing was watching the subject.**

Two things were tried and only the second worked:

1. Showing the model the last 14 pieces and telling it not to repeat them. It made a sixth content
   machine video anyway. That section is first in the proof inventory, is literally labelled "this
   system", and matches the AI-automation signal it is shown alongside. Asking a model to avoid
   something loses to what is most salient in its own context.
2. **Deciding the subject in code before asking for an angle**, exactly as the platform is decided.
   The systems are read out of the proof inventory's `###` headings, the failure stories count as
   one more, and each run takes whichever has gone longest without being made.

⚠️ Naming the subject was still not enough on its own, because **the sections overlap**: one product
lists "attribution that follows a link from a post to a payment" as one of its bullets, and
Attribution is a subject in its own right, so two runs in a row produced the same tracking video.
Each run now gets **only that section's own lines** as material, plus the other subject names marked
off limits. Removing the neighbouring material beats asking the model to ignore it.

The choice is written to the card as a `Subject:` line and read back off the board next time, so a
deleted card frees its subject again and a failed run costs nothing. **Adding a `###` heading to
the proof inventory adds a subject to the rotation**, which is the cheapest way to widen what the
machine can talk about.

### Craft mode: what happens when the competitor posts run out

⚠️ **It never re-reads a post a script was already built from.** That fallback existed and it is
exactly how the machine would start repeating itself, so it is gone. When every collected outlier
has been used, the run switches to **craft mode** and writes from the knowledge base instead:

- The hook pattern comes from the **Hook Swipe File** in the Scripting Toolkit (12 named patterns),
  rotated least-recently-used exactly as subjects are, read back off the cards' `Pattern:` line.
- The prompt gets that one pattern's own reasoning and openers, and is told plainly not to copy an
  opener word for word: they are templates against placeholders, and the job is to fill them with
  the one specific thing from the proof inventory only he can say.
- **6 subjects times 12 patterns is 72 combinations**, so the knowledge base carries the machine for
  weeks with no new competitor data at all.

The card says which it was: `Built from the knowledge base, no new competitor post was left to
model` instead of `Inspired by <creator>`. The run stats say `Built from: The knowledge base` and
name the pattern.

Verified 2026-08-03 in the QA sandbox with ZERO competitor posts in it: three runs, three subjects,
three patterns, three different hooks.

### Rejecting a script is how the writer is taught

**Record tab, "Not this one".** Binning a script asks for a reason and the reason is the point: it
goes into a Brain document, `Script Feedback`, which the writer reads
before choosing an angle AND again before writing. The reason is required (a blank one would train
the writer on nothing), and the entry records the subject, the pattern and the actual hook so the
model knows what to avoid rather than just that something was wrong.

It is a normal knowledge doc, so it is visible and editable at **/knowledge** like any other. Only
the newest 10 entries reach the prompt: taste moves, and the whole file would crowd the craft out
of the smaller free provider.

Verified end to end 2026-08-03: a YouTube script with a nine-item shot list was binned for having
too many shots, and the next script on the same subject and pattern came back with six. The
feedback moves the writer; it does not command it, which is why the shot list is ALSO capped at 7
in code.

Verified over four consecutive runs, which produced the content machine, the product itself, attribution, and
the N8N DM setter flow. Four different videos.

Verified again 2026-08-02, unattended: the three morning crons produced the local business builder,
a failure story (the AI inventing fake view counts), and then the content machine as the rotation
came back around. All six subjects used, in 41s, 27s and 27s. That was also the first morning the
third run succeeded, having failed on both days it previously existed.

⚠️ **The free quotas are shared with this folder.** `tools/content-machine/content_machine_daily.py` and the
cloud agent use the SAME `GEMINI_API_KEY` and `GROQ_API_KEY`. On 2026-07-30 a local pipeline run
plus cloud testing drained both in one evening (Gemini 20 requests, Groq 100,000 tokens). Running
the Python pipeline on a day the cloud agent is running will starve one of them. Prefer the cloud
agent; use the CLI when the cloud one is being changed.

### What is still manual

**Scrape and parse.** The cloud agent runs the SCRIPT stage only. The post-level corpus the parser
reads (`posts_deep.json`, `youtube_videos.json`) lives in local `.tmp/` folders, not in Supabase,
and a full roster scrape cannot finish inside a serverless function's wall. So the signal is
refreshed by running the pipeline here, and the cloud writes from whatever signal is in
`content_outliers`. That is the right split for now, because the signal changes weekly at best and
the scripts are what is needed daily. Putting scrape in the cloud means a posts table plus an Apify
orchestration that survives being interrupted, and that is a separate build.


## The proof inventory (the specificity unlock)

`content-machine/proof_inventory.md` is the Scripter's third input, alongside the Brain (how content
is made) and the signal (what is working). It is the list of what the client can actually put on camera:
systems he can screen-record, things that broke and what they taught him, his real position.

Without it the Scripter writes "I build attribution systems", which any account could say. With it
it writes "the 3 screens I use to track content from first click to paid invoice". Specificity is
the entire difference between his content and generic AI content, and it cannot be invented, so it
has to be written down.

⚠️ Nothing in that file may be a result, a revenue figure, or a client outcome unless the client adds it
himself and it is true. The file says so at the top. Failure stories are the most valuable entries:
specific, true, and nobody else can tell them.

Keep it current. Every system shipped and every thing that breaks is a content asset, and the
Scripter can only reach for what is written down.

## The Scripter is two agents in sequence

Writing and deciding what to write are different skills. One call doing both produced hooks the client
rejected as generic, so the stages are split:

1. **Analyse.** Reads the Brain, the hook swipe file, and today's signal, then picks the angles
   worth making and says why each one is his to make. Output is a brief per script.
2. **Write.** One call per brief, so the model spends its whole attention on one piece. Each call
   writes six competing hooks, scores them against stated tests, picks a winner, and explains the
   choice. The rejected hooks are kept in the card notes.

Instagram and YouTube are prompted differently: a reel is 30 to 60 seconds of speech, a YouTube
video gets a title, thumbnail text, a fully written open, and a beat-by-beat body.

## Guards that run in code, not in the prompt

The model ignored the prompt and wrote "I got 80+ million views in the last 6 months", which the client
would have had to post as a lie. Prompts do not hold, so three rules are enforced in code and a
failing script is sent back with the offending lines quoted, up to three times:

- **Invented results.** Any first-person claim attaching a quantity to a result metric (views,
  followers, clients, revenue, "in 6 months"). Word quantities count: "hundreds of setups" is as
  unverifiable as "400 setups". Verifiable claims about the WORK pass: "reads 33 competitor
  accounts" is fine because it can be shown on screen.
- **Overpromises.** A CTA promising a personal reply ("personally", "I will DM you back"). Delivery
  is automated.
- **A missing call to action.** A script with no ask earns nothing. One shipped without one.
- **House style.** Em dashes, en dashes, emoji, and arrows are stripped from every field, and
  doubled words are collapsed. "You don't have an an ad problem" reached the board: a repeat is
  invisible when reading for meaning and obvious when reading aloud, which is how a script is used.

The same invented-result guard runs at the analysis stage, because an angle built on a fake number
has nothing left once the number is removed.

⚠️ A figure inside quotation marks is being REPORTED, not claimed, and is allowed. The guard was
dropping his best story (an AI inventing "I got 80 million views" inside one of his own scripts)
because it read the quoted mistake as the client making the claim. Telling that story requires repeating
the number.

## ⚠️ The parse run that wiped every analysis (2026-08-03, fixed)

`record_outliers` upserts on `(agency_id, url)` and used to write `= excluded.<col>` for EVERY
column, including the five the LLM fills in. So any run whose pattern pass produced nothing
rewrote every previously analysed row with nulls. **`--no-llm` did exactly that**, and one pass
blanked the analysis on all 232 outliers. The dashboard still showed 232 winners; none of them
carried a hook type, so the writer had no usable signal at all.

It was survivable only because craft mode had shipped an hour earlier. Before that, the next
morning's three runs would have produced nothing.

**The fix:** the five analysis columns are now `coalesce(excluded.<col>, content_outliers.<col>)`
and `analysed` is `or`ed, so an upsert can only ever ADD analysis, never blank it. Re-analysing
still works, because a non-null value from a new pass wins. Verified by replaying a `--no-llm`
style upsert against an analysed row and watching it survive.

**Recovering from it:** `tools/<group>/restore_outlier_analysis.py`. Saved signal files in
`.tmp/_signal/*.json` still hold the analysis for whatever was studied the day they were written,
so those come back by URL for free; anything left gets a fresh pattern pass on a free key, biggest
multiples first. Restored 60 analysed outliers on 2026-08-03 (25 free from disk, 35 named by
Gemini), against the 25 that existed before the wipe.

```bash
python3 tools/<group>/restore_outlier_analysis.py --dry-run
python3 tools/<group>/restore_outlier_analysis.py --top 60
```

## Free provider limits

Four separate limits, and they fail differently, so they need telling apart:

| Provider | Limit | What it means |
|---|---|---|
| Gemini | 20 requests per DAY per model | A day of testing exhausts it. Resets midnight Pacific. |
| Gemini | latency, not a quota | It is a reasoning model. Budget 25s a call, not 20; a 20s timeout wasted the whole run in production on 2026-07-30. |
| Groq | 12,000 tokens per MINUTE | Org-wide, shared with anything else on the same key. Clears in a minute, so it is worth waiting out. |
| Groq | 100,000 tokens per DAY | Org-wide. Drained on 2026-07-30 by one evening of testing plus a local pipeline run. |

The cloud agent classifies a 429 on the **whole** response body, never a truncation: Gemini does
not name `PerDay` until several hundred characters in, so classifying the first 200 characters read
a spent daily quota as a transient blip and sat waiting for a limit that resets tomorrow. A
per-minute limit is retried after exactly the delay the provider states (`retry-after`, or "try
again in 4.2s"); a daily wall moves straight to the next provider. When EVERY provider is out for
the day the run reports **skipped**, not error, because nothing is broken.

Gemini's free tier allows **20 requests per day per model**. A local run uses about 7 (one
analysis plus one per script plus the parser); the cloud agent uses 6 across its three runs. Groq
is the free fallback and takes over automatically on a quota wall.

Groq's per-minute token limit is far below Gemini's context window, so the prompts are sized to fit
the smaller one: the analysis gets 18k chars of brain, the writer gets the hook swipe file rather
than the whole 38k toolkit. Sending everything made the fallback fail with a 413 at exactly the
moment it was needed. Groq output is noticeably weaker than Gemini; it is a safety net, not a peer.

## Where the roster is used

`content_creators` is the single roster. Two things read it:

- The pipeline in this repo (parser and scripter, role `emulate`, status `active`).
- Any other agent in the dashboard that studies competitors. Keep them on this one table: two
  separate rosters is how the roster and the output stop matching, and nobody notices for days.


## Thumbnails

Pick one creator in the client's lane whose thumbnails clearly work, pull their twelve best, and
reverse engineer the layout into a knowledge doc. Load it as "Thumbnail Formula" and the Scripter
will write to it.

The load-bearing rule, whichever layout you land on: **the thumbnail words are not the title.**
The title carries information, the thumbnail carries a verdict. A title reading "You're not behind
(yet): how to learn AI in 18 minutes" pairs with a thumbnail that just says "This Works". If the
thumbnail only shortens the title, the slot is wasted.

The Scripter writes `thumbnail_text` (two to four words, a verdict) and `thumbnail_props` (what
flanks the face, restricted to the client's REAL screens rather than generic app logos) on every
YouTube script.

⚠️ Copy the structure, never the identity. The layout is a formula; the palette, the type and the
face are the client's own, and a thumbnail that looks like the creator it was modelled on is a
failure, not a success.

## The LLM JSON gotcha, worth reusing

Asking a model for a "script with a line break between beats" makes it put REAL newlines inside the
JSON string value. That is invalid JSON, so `JSON.parse` rejects a reply that opens with a brace,
closes with a brace, and is not truncated in any way. The failure looks nothing like its cause.

`repairControlChars()` in the dashboard's `src/lib/content` walks the text tracking whether it is
inside a string and escapes the control characters that are only illegal there. `extractJson()`
tries the raw text, the repaired text, a fence-stripped variant, and every brace position, so it
also survives a code fence, a prose preamble, a trailing remark, and a doubled opening brace.

Debugging lesson: print the response length, the head AND the tail. An 80-character head made a
complete response look truncated and sent two fixes down the wrong path.
