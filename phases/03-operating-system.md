# Phase 3. Their operating system

**Deliverable:** one dashboard the client logs into that shows the content board, the
money, the buyers and the sales calls.

**Done when:** the client stops asking you for updates because the answer is on a screen
they can open.

Do this before phase 4. The content machine reads its roster from, and writes its cards
to, this system. Without it phase 4 has nowhere to put anything.

---

## 1. Stand up the dashboard

The dashboard lives in [AIPM-Complete-Setup](https://github.com/BrettZuke/AIPM-Complete-Setup)
under `tools/dashboard`. Deploy it on the client's own Vercel and Supabase.

It ships with multi-tenant workspaces isolated by row-level security, clients and CRM,
revenue and MRR tracking, sales pipeline, commissions and payments, tasks and goals,
webinar registrations and attendance, a UTM link builder with `/go/...` channel links and
lead attribution, an in-app AI assistant that can run on free Groq, and the content board
that phase 4 writes into.

Apply every migration in `supabase/migrations/`, including the five `content_*` ones. Those
five are the content machine's tables and phase 4 fails without them.

Two rules that are not optional:

- **Their Supabase, their Vercel, their keys.** Never run a client on your instance. One
  client's data must never be reachable from another's workspace.
- **Row-level security on every new table.** If you add a table and skip RLS, that table
  is readable across workspaces.

If the full dashboard is more than the client needs, the lighter option is
[aipm-dashboard-template](https://github.com/BrettZuke/aipm-dashboard-template), a
sheet-driven 7-page dashboard.

## 2. The content board

The board is where scripts land, get recorded, and get published. Columns that work:

`Scripted` → `Recording` → `Edited` → `Scheduled` → `Published`

Phase 4's scripter writes into `Scripted`. Everything after that is the client moving
cards.

Note the project ref you deploy with, and the workspace id the dashboard creates on first
run. Phase 4 needs both in `.env` as `SUPABASE_PROJECT_REF` and `CONTENT_AGENCY_ID`.

## 3. Buyer onboarding

When someone buys, three things fire, in this order:

1. They are tagged as a customer in the email platform, so they stop receiving the sales
   sequence that same day.
2. The onboarding form goes out, as a single link.
3. Access is delivered.

Do not send an onboarding form before payment. Prospects get a call booking link; buyers
get forms.

The mechanics for the tagging step are in
[aipm-marketing-sops](https://github.com/BrettZuke/aipm-marketing-sops) and the sequence
copy in [ai-partner-method-email-toolkit](https://github.com/BrettZuke/ai-partner-method-email-toolkit).

## 4. Sales calls: transcripts, reviews, and the post-call form

**Pull the transcripts.** Fathom share links are readable with no login when the owner has
link sharing on.

```bash
python3 tools/sales-calls/fathom_pull_transcript.py <share-url> [<share-url> ...]
python3 tools/sales-calls/fathom_pull_transcript.py --inbox   # every link pasted in sales-calls/inbox.md
```

Each call lands in `sales-calls/transcripts/<date>_<prospect>_<id>.md` with a row in
`sales-calls/index.md`. Already-pulled calls are skipped unless you pass `--force`.

**Review them.** `sops/sales_call_review.md` is the doctrine: what gets scored, and what
counts as evidence rather than opinion.

```bash
python3 tools/sales-calls/closer_review_run.py
```

Run reviews on a cheap model. This is volume work and there is no judgment upside to
spending more per call.

**The closer post-call form.** After every call the closer fills one form: outcome, price
quoted, objection raised, next step, and whether they bought. This is what makes buyer
tagging reliable, because a payment webhook alone cannot tell you a deposit from a full
purchase.

**The cross-call brief.** Weekly, read every call at once and ask what the marketing should
change:

```bash
python3 tools/sales-calls/sales_call_intelligence.py
```

One call is an anecdote. Twenty calls tell you which objection to answer in the VSL.

## 5. Revenue and revenue per video

Revenue, MRR and pipeline come with the dashboard. Revenue per video does not; you have to
wire it.

Give every piece of content a UTM through the built-in link builder, send traffic through
`/go/<code>`, and the attribution table connects a published video to the money that came
after it. Without the UTM step, revenue per video is a guess.

---

## Checklist

- [ ] Dashboard deployed on the client's own Vercel and Supabase
- [ ] RLS confirmed on every table, including any you added
- [ ] Content board columns created
- [ ] Supabase project ref noted for phase 4
- [ ] Buyer onboarding fires: tag, form, access
- [ ] Fathom transcripts pulling into `sales-calls/`
- [ ] Closer post-call form live and being filled after every call
- [ ] UTMs on every piece of content so revenue per video is real
