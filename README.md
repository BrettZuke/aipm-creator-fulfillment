# Creator Client Fulfilment Stack

Everything needed to deliver a creator or coach client end to end: onboarding, brand
voice, competitor intelligence, an operating system, a daily content scripter, a VSL
and funnel, and a personalised email machine.

This is the **creator track**. It is not the local-business track. If the client is a
plumber, roofer or trades business, use
[AIPM-Complete-Setup](https://github.com/BrettZuke/AIPM-Complete-Setup) instead.

Two kinds of thing live here:

- **Pointers** to repos that are already built and public. Clone those, do not rebuild them.
- **Tools and SOPs** that were not packaged anywhere else. Those are in `tools/`, `sops/` and `skills/`.

---

## If you only want the daily scripter

Most of this repo is the wider fulfilment stack. The piece students ask for first is the
**content machine**: it studies the creators your client competes with, writes their scripts,
emails them over every morning, and gets better every time your client presses a button on one.

```
  their competitors  ->  what beat its own creator's average  ->  scripts in their inbox
                                                                          |
                          the writer reads every verdict  <-  they press Yes / Rewrite / No
```

Five steps, all on free keys:

1. **Deploy their dashboard.** `tools/dashboard` in
   [AIPM-Complete-Setup](https://github.com/BrettZuke/AIPM-Complete-Setup), on the client's own
   Vercel and Supabase. Apply every migration, including the five named `content_*`: those are
   the board, the roster, the signal, the run log and the feedback.
2. **Fill in `.env`.** Copy `.env.example`. The scripter will not start without it and tells you
   exactly which value is missing.
3. **Write the client files** in `knowledge/`: `WHO.md`, `BRAND_VOICE.md`, `PROOF_INVENTORY.md`.
   Copy the `*_TEMPLATE.md` files beside them. This is the step that decides whether the scripts
   sound like your client or like nobody, so do it before the first run, never after.
4. **Load the two craft documents**, which are already written and the same for every client:
   ```bash
   python3 tools/content-machine/load_knowledge_doc.py --agency <workspace id> \
     --title "Content Strategist Brain" --file knowledge/CONTENT_STRATEGIST_BRAIN.md
   python3 tools/content-machine/load_knowledge_doc.py --agency <workspace id> \
     --title "Scripting Toolkit" --file knowledge/SCRIPTING_TOOLKIT.md
   ```
5. **Run it.**
   ```bash
   python3 tools/content-machine/content_machine_daily.py   # scrape, find winners, write, email
   ```
   Put that on a daily schedule and you are done. Scripts land on the client's board under
   Scripted, and in their inbox with three buttons on each one.

**The feedback is the point.** Yes, Rewrite and No each write a verdict and a typed reason into
`content_feedback`, and the writer reads them before it picks the next angle. Accepted counts as
much as rejected: only ever telling a writer what to avoid teaches it to be cautious rather than
good.

Full detail in [phases/04-content-machine-and-scripter.md](phases/04-content-machine-and-scripter.md).

---

## Start here: the six phases

| Phase | What you deliver | Runbook |
|---|---|---|
| 1 | Onboarding forms, socials scraped, brand voice written | [phases/01-onboard-and-brand-voice.md](phases/01-onboard-and-brand-voice.md) |
| 2 | Competitors and industry leaders scraped: content, funnels, emails | [phases/02-competitor-and-market-intel.md](phases/02-competitor-and-market-intel.md) |
| 3 | Their operating system: board, revenue, buyers, call reviews | [phases/03-operating-system.md](phases/03-operating-system.md) |
| 4 | Daily scripter emailing scripts, plus the weekly email ritual | [phases/04-content-machine-and-scripter.md](phases/04-content-machine-and-scripter.md) |
| 5 | VSL script, landing page, funnel, VSL edit | [phases/05-vsl-funnel-and-edit.md](phases/05-vsl-funnel-and-edit.md) |
| 6 | Personalised Make.com email scenario | [phases/06-make-email-scenario.md](phases/06-make-email-scenario.md) |

Do them in order. Phase 4 needs the brand voice from phase 1 and the signal from phase 2.
Phase 5 needs the offer from phase 1.

---

## The repos to clone (all public)

Clone these once into a working folder. Nothing here duplicates them.

| Repo | What it is | Used in phase |
|---|---|---|
| [ai-partner-method-onboarding](https://github.com/BrettZuke/ai-partner-method-onboarding) | Creator client onboarding system, forms and intake | 1 |
| [settoku-forms](https://github.com/BrettZuke/settoku-forms) | Self-hosted Typeform replacement. Build and host the forms yourself | 1 |
| [aipm-student-form-templates](https://github.com/BrettZuke/aipm-student-form-templates) | Ready-made form templates | 1 |
| [aipm-client-research](https://github.com/BrettZuke/aipm-client-research) | Market research dossier toolkit | 1, 2 |
| [youtube-creator-scraper](https://github.com/BrettZuke/youtube-creator-scraper) | Scrape qualified YouTube creators in a niche | 2 |
| [AIPM-Complete-Setup](https://github.com/BrettZuke/AIPM-Complete-Setup) `tools/dashboard` | Self-hostable dashboard: CRM, revenue, pipeline, tasks, attribution, AI chat, content board | 3 |
| [aipm-dashboard-template](https://github.com/BrettZuke/aipm-dashboard-template) | Sheet-driven 7-page sales operating dashboard, lighter alternative to the above | 3 |
| [aipm-marketing-sops](https://github.com/BrettZuke/aipm-marketing-sops) | Marketing and sales SOPs, copywriting frameworks, VSL SOP, webinar SOPs | 2, 4, 5 |
| [ai-partner-method-email-toolkit](https://github.com/BrettZuke/ai-partner-method-email-toolkit) | Email copywriting system: frameworks, subject lines, templates | 4, 6 |
| [ai-partner-method-direct-response-toolkit](https://github.com/BrettZuke/ai-partner-method-direct-response-toolkit) | Direct response copy system: triggers, swipe headlines, voice constraints | 5, 6 |
| [aipm-skill-pack](https://github.com/BrettZuke/aipm-skill-pack) | 15 Claude Code skills: client-brand, sales-call-analyzer, viral-reel-generator, premium-funnel-page and more | all |
| [ai-partner-method-claude-starter](https://github.com/BrettZuke/ai-partner-method-claude-starter) | 53 Claude Code skills, the wider set | all |
| [ai-partner-method-personal-page-build](https://github.com/BrettZuke/ai-partner-method-personal-page-build) | Claude Code kit for building a personal brand page | 5 |
| [aipm-reel-editor](https://github.com/BrettZuke/aipm-reel-editor) | One-command edit: strips silences, filler words and duplicate takes. Use for volume talking-head content | 4, 5 |
| aipm-templates | 20 premium website templates. **Currently private**, ask for access or a copy | 5 |

---

## What is in this repo

```
tools/instagram/          Instagram scraping: profile, posts, reels, transcripts
tools/youtube/            YouTube scraping: videos and transcripts, free and Apify fallback
tools/content-machine/    The daily scripter: scrape, parse signal, write scripts, email them
tools/competitor-intel/   Competitor content and marketing-email intelligence
tools/sales-calls/        Pull call transcripts, review them, build a cross-call marketing brief
video-system/             The seven-stage editing pipeline: rough cut, graphics, captions, render
sops/                     The SOPs that are not in aipm-marketing-sops
skills/                   45 Claude Code skills not in aipm-skill-pack. See skills/INDEX.md
knowledge/                The two documents the scripter reads, plus the templates you fill in
phases/                   The six runbooks
```

---

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # then fill it in
cp -R skills/* ~/.claude/skills/
rm -f ~/.claude/skills/INDEX.md
```

Phase 5 also needs FFmpeg and WhisperX for the video system. They are not needed for
anything in phases 1 to 4, so install them when you get there:
`brew install ffmpeg && uv tool install whisperx`. Details in
[video-system/README.md](video-system/README.md).

[`skills/INDEX.md`](skills/INDEX.md) maps every skill to the phase it belongs to and when
to reach for it. Read it once; 45 unexplained skills is the same as none.

`skills/INDEX.md` is reference material rather than a skill, which is what the `rm` above is
for.

---

## Money rule

Default to **free** keys: Groq, Gemini, and free Apify tokens. Then know exactly which
scripts break that default, because several do.

**These call a paid Anthropic API directly.** They will spend real money the moment
`ANTHROPIC_API_KEY` is set. Leave it unset unless you are deliberately running one of them.

| Script | Line |
|---|---|
| `tools/content-machine/content_plan_generator.py` | 115 |
| `tools/instagram/instagram_content_scraper.py` | 369 |
| `tools/youtube/youtube_scraper.py` | 202 |
| `tools/youtube/creator_content_engine.py` | 440 |

**These run on free keys only** and call no paid API at any point:
`content_machine_daily.py`, `content_signal_parser.py`, `content_scripter.py` (free Gemini,
Groq fallback) and `content_machine_email.py` (calls no model at all).

**These run through the local `claude` CLI on a Claude subscription**, so a run costs plan
usage rather than money: `tools/sales-calls/closer_review_run.py` and
`tools/sales-calls/sales_call_intelligence.py`. Both deliberately strip
`ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and `OPENAI_API_KEY` out of the child
environment so the CLI cannot bill a paid key by accident. Do not remove that stripping.

The safe default: leave `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` out of `.env` entirely.
Everything you need for daily operation runs without them.

## What you must set before anything works

Nothing in this repo is hardcoded to one client. Everything per-client lives in two places:
`.env` for credentials and ids, and `knowledge/` for anything about the client themselves.
That is deliberate. An operator running two clients will otherwise leave one client's project
ref in a script and write the second client's content onto the first client's board, and
nothing errors when that happens.

### `.env`

Copy `.env.example` and fill it in. The content machine will not start without these:

| Variable | What it is |
|---|---|
| `SUPABASE_PROJECT_REF` | the client's Supabase project ref, from phase 3 |
| `CONTENT_AGENCY_ID` | their workspace id on that project |
| `SUPABASE_ACCESS_TOKEN` | a Supabase management token |
| `CONTENT_APP_URL` | their dashboard, e.g. `https://os.theirdomain.com` |
| `CONTENT_EMAIL_TO` | who receives the scripts |
| `SECRETS_ENCRYPTION_KEY` | must match the dashboard exactly, or the email buttons 403 |
| `RESEND_API_KEY` | free tier is fine |
| `GEMINI_API_KEY`, `GROQ_API_KEY` | the two writing passes |
| `APIFY_TOKENS` | comma separated pool of free tokens |

### `knowledge/`

The client, in four short documents. These decide whose voice comes out, and a missing one
either stops the run or quietly makes everything generic.

| File | What goes in it | Written in |
|---|---|---|
| `WHO.md` | one paragraph: who they are, what they do, who for, what they are NOT | phase 1 |
| `BRAND_VOICE.md` | how they actually talk, built from their own transcripts | phase 1 |
| `PROOF_INVENTORY.md` | what they can put on camera. Start from the template beside it | phase 1 |
| `OFFER.md` | price, tiers, payment plans, what is being sold on a call | phase 3 |

`CONTENT_STRATEGIST_BRAIN.md` and `SCRIPTING_TOOLKIT.md` are already written and are craft
rather than client work, so the same two serve every client. Load all of them into the
dashboard with `tools/content-machine/load_knowledge_doc.py`, see phase 4.

⚠️ Write these before the first run, never after. A script written against the wrong voice is
not worth editing, and a client seeing one is worse than a client seeing nothing.

### Competitor lists

`competitors.py` ships with `CLIENT_COMPETITORS` empty and commented, plus a real list of
public info-space benchmarks (Hormozi and similar) to measure against. Fill the client's own
competitors in from phase 2. It is copied into three tool folders so the sibling imports
resolve; edit one and copy it over the others, or they will disagree and nothing will tell you.

### Google Sheets

`tools/sales-calls/closer_sheet.py` reads a `SHEET_ID` from the environment. Create the
client's own sheet and set it. The sales-call scripts also expect a `sales-calls/`
directory with `inbox.md`, `transcripts/`, `index.md` and `briefs/`. Create it in your
working folder:

```bash
mkdir -p sales-calls/{transcripts,briefs} && touch sales-calls/inbox.md sales-calls/index.md
```
