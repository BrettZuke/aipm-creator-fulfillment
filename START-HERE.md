# Start here

Everything needed to fulfil a creator or coach client, in the order you need it.

Work through `phases/01` to `phases/06` in order. Each phase is a runbook with the exact
commands and a checklist at the bottom. Do not jump ahead to the content machine: it writes
into the operating system, so the operating system has to exist first.

## The order, and why it is that order

| Phase | What you end up with |
|---|---|
| 1 | Their voice, written from their own transcripts, and an offer you both agree on |
| 2 | Who they are actually competing with, and what is working in that lane |
| 3 | Their operating system: board, revenue, pipeline, call reviews |
| 4 | Scripts arriving daily, on their board and in their inbox |
| 5 | The VSL and funnel, and the edit pipeline that produces it |
| 6 | The email automation behind it |

Phase 1 is the one people rush and the one that decides everything downstream. A voice
document built from someone's written material produces scripts that read like essays, and
nobody says an essay to a camera. Transcribe their reels and build it from the audio.

## Three things worth saying up front

**Everything runs on free keys.** Groq, Gemini, free Apify tokens. Two scripts can call a
paid Anthropic API and the README names them; neither is in the daily chain. Leave
`ANTHROPIC_API_KEY` out of your `.env` and nothing can fire it by accident.

**The client's infrastructure, not yours.** Their Vercel, their Supabase, their keys. Never
run a client on your instance, and put row-level security on every table you add. One client
being able to read another's data ends the business, not the project.

**Nothing here is hardcoded to a client.** Per-client settings live in exactly two places:
`.env` for credentials and ids, `knowledge/` for anything about the client themselves. When
you take on a second client, those are the only two things that change. That is deliberate:
a project ref left behind in a script writes one client's content onto another's board, and
nothing errors when it happens.

## One thing you may need to buy

The default caption style renders in Coolvetica. The font file is not included, because
redistributing it is a licensing question. Either license it, or point
`video-system/tools/captions.py` at a font you already have a licence for. Two lines at the
top of that file.

## If you get stuck

Work down the checklist at the bottom of the phase you are in. If something in the middle of
an earlier phase was skipped, everything after it behaves oddly rather than failing cleanly,
and that is almost always what has gone wrong.
