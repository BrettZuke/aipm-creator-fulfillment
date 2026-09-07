# Sales call review (SOP)

Every sales call gets read by a model overnight and comes back with a summary, feedback for the
closer, and scores. The point is not a transcript archive: it is that a closer sees, the next
morning, the one thing that cost them the last deal.

## Where everything lives

- Closers fill a post-call form after EVERY call, including no-shows. The "call recording link"
  field is what makes a review possible: no link, no review.
- Submissions land in the forms platform's Google Sheet, on the tab named `r_<form id>` for that
  form, raw answers as JSON in column C. Set that tab name as `CLOSER_FORM_TAB` in `.env`.
- `tools/sales-calls/closer_calls_sync.py` reads that tab, pulls each transcript into
  `sales-calls/transcripts/`, and reports what still needs a review or a link.
- `tools/sales-calls/closer_review_run.py` is the nightly job: sync, then one headless model pass
  per call, then append to the `_call_reviews` tab.
- `tools/sales-calls/sales_call_intelligence.py` reads ACROSS calls and writes one brief about
  the marketing and the offer, rather than about any individual closer.
- Calls that never got a form go in by hand on the `_calls_manual` tab, in the same shape as a
  form response. The review run picks those up like any other call, and a manual row is ignored
  if the same recording later arrives through the form, so adding one is never destructive.

## What a review contains

Three things, and nothing else:

1. **summary**, 3 to 5 sentences: how the call was framed, what the prospect actually wanted,
   where the price landed, how it ended, and the real block if there was one. Quote the prospect
   where a quote says it best.
2. **feedback**, 120 to 220 words to the closer as "you": highest-leverage fix first, a timestamp
   for every point, and one thing to do differently next call. Praise only where earned, one
   sentence.
3. **scores**, 0 to 10 on discovery, pitch, price, close, follow-up. 5 is competent, 8 or above is
   excellent. Use the whole range or the trend means nothing.

## What to look for

These came out of reading real calls and they repeat across every offer we have run this on.

- **Self-objecting on price.** "It's X, I'm assuming that's too much" hands the prospect the
  discount before they asked. Price is a flat statement followed by silence.
- **Letting the prospect name the number.** "What feels comfortable?" invites the lowest number
  in the room. Plans come from a fixed menu the closer does not improvise on.
- **Closes that leave the call.** "I'll message you later" is not a close. That is what deposits
  exist for, and every unresolved call needs a booked slot with a time on it.
- **Volunteering trust killers.** "Nobody showed up to the last call", "we just started",
  "there's only a few people inside". Skeptics buy proof, not candour about being small.
- **Missing proof.** The pattern that stalls the most deals: a burnt buyer asks for results and
  wants to speak to a current client. Have three client results with numbers, and one client who
  will take a ten-minute call.
- **Discovery that stops before the gap hurts.** The close should replay the prospect's own words
  about what they want and what staying the same costs them.
- **Product tours.** Fifteen minutes of screen share is a tour, not a pitch. One screen, one
  story, one proof, five minutes.
- **Arguing past the no.** Once a prospect wants it free or genuinely has no money, exit warm in
  two minutes. Nobody ever won the argument and the deal.
- **Tangents after the yes.** Confirm the date, give the first steps, get off the call.

## What the scoreboard should track

Three headline numbers (cash collected against signed value, close rate, calls taken with show
rate), then the funnel booked to showed to pitched to closed, then cash per call taken, average
deal, pitch-to-close, collected upfront, paid-in-full split, recurring booked, open pipeline
value, and review coverage. Per closer: the same set plus their average scores by area, which is
where a coaching trend actually shows up.

Decide once, and write it down, what counts as a win. Ours: paid in full, financed, and paid
below full price all count. Deposits and booked follow-ups sit in pipeline until the balance is
agreed, never counted as wins. No-shows and cancellations count against show rate, never against
close rate. Any definition works as long as it never moves.

⚠️ **Every step needs its own denominator.** A funnel drawn as raw volume collapses into
invisible dots when the top is thousands and the bottom is single figures. Draw each bar as the
share of the step before it.

⚠️ **Registration counts from any webinar platform include bots and duplicates.** A raw show
rate computed against them is a floor, not the truth. Say so next to the number, every time, or
someone will optimise against a metric that is mostly noise.

## Correcting an outcome after the call

Closers log an outcome in the moment and it changes later: a deposit becomes a full payment, a
follow-up becomes a no. Corrections belong in one place with a timestamp and who made them, and
they must never edit the original form response. A review that silently changes cannot be
trusted, and a closer who sees their own history rewritten stops filing forms honestly.

## Running it

```bash
python3 tools/sales-calls/fathom_pull_transcript.py <share-url>   # one call
python3 tools/sales-calls/fathom_pull_transcript.py --inbox       # everything in inbox.md
python3 tools/sales-calls/closer_review_run.py --dry-run          # what would be reviewed
python3 tools/sales-calls/closer_review_run.py                    # the nightly job
python3 tools/sales-calls/sales_call_intelligence.py              # the cross-call brief
```

Put the review run on a nightly schedule. It costs plan usage rather than money: it goes through
the local `claude` CLI and strips paid API keys out of the child environment so it cannot bill
one by accident.

Before the first run, write `knowledge/OFFER.md` (what is being sold, on what terms),
`knowledge/AUDIENCE.md` (who actually buys) and `knowledge/SETTLED_DECISIONS.md` (what is already
decided and not up for re-argument). Templates for all three sit beside them. Without the offer
the reviewer cannot tell a good close from a bad one, and without the settled decisions the
cross-call brief reports your own deliberate choices back to you as defects.

## Gotchas

- The service account credentials live in this repo's `.env` as `GOOGLE_SERVICE_ACCOUNT_JSON` and
  `SHEET_ID`. If a run 403s, the service account has lost edit access to the spreadsheet:
  re-share it with the `client_email` inside that JSON.
- ⚠️ **On macOS, a scheduled job cannot write under `~/Desktop` without Full Disk Access**, and
  the redirect fails before the interpreter starts, so the job dies leaving nothing in the log
  you are watching. Put scheduled logs under `~/Library/Logs/`.
- ⚠️ **A throwaway launch agent proves nothing.** macOS grants file access per agent label, so a
  brand new test agent is refused writes that the real one is allowed. Test with the real label
  or not at all.
