# Phase 6. The personalised Make.com email scenario

**Deliverable:** an automation that sends a genuinely personalised email per lead, not a
mail merge with a first name in it.

**Done when:** you could show a prospect the email that went to them and they would believe
a person wrote it.

---

## What "personalised" has to mean

A first name token is not personalisation and every recipient knows it. What makes these
work is a specific, verifiable detail about that person: something they posted, something
their site says, a number from their own business.

That means the scenario needs a research step before the send step. The scrapers from
phases 1 and 2 are that step. Feed each lead through
`tools/instagram/scrape_creator_dossier.py` or the site extractor, and let the email
reference what came back.

## The shape

```
Trigger            new row in the sheet, form submission, or a webhook from the CRM
   ->  Enrich      pull the lead's profile, site, or recent posts
   ->  Generate    write the email from the enrichment, on a free model
   ->  Guard       skip anything missing its personalisation field, log why
   ->  Send        through the client's email platform
   ->  Log         write the result back so the CRM knows what was sent
```

The guard step is not optional. Without it, one lead with a missing field sends an email
containing a blank where the personal detail should be, and that is worse than sending
nothing.

## Building it

This sits inside the wider outreach flow: the first message, the follow-up, and where the
video goes. Send outreach from a real account at a human pace and reply personally when
someone answers. Automating the sending itself gets accounts restricted, and a restricted
account costs more than the time it saved.

Copy for the emails themselves comes from
[ai-partner-method-email-toolkit](https://github.com/BrettZuke/ai-partner-method-email-toolkit)
and [ai-partner-method-direct-response-toolkit](https://github.com/BrettZuke/ai-partner-method-direct-response-toolkit).

Rules that come from things that have actually gone wrong:

- **Cap every loop.** An uncapped iterator with a sleep inside it will hit the platform's
  execution limit mid-run, and on a mail provider it will produce a rate-limit storm you
  then have to clear by hand.
- **Fail closed on webhooks.** Validate a shared secret on every request. Never act on an
  unauthenticated POST.
- **Deduplicate by identity, not by count.** Group by email address. "The number looks
  right" is not a check.
- **Never send to a buyer from a prospect sequence.** Tag buyers the day they buy and
  suppress them. A customer receiving the pitch they already accepted is the fastest way to
  a refund request.
- **New scenario webhooks start disabled.** Enable the trigger explicitly, then send one
  real test through it and read the output.

## Never do this

Do not ask a prospect to fill in a form. Outreach sends a proposal or a video and asks for
a call. Forms are for people who have already paid.

---

## Checklist

- [ ] Enrichment step runs before generation and its output is actually used in the copy
- [ ] Guard skips and logs any lead missing its personalisation field
- [ ] Every loop capped
- [ ] Webhook validates a shared secret and fails closed
- [ ] Buyers suppressed from prospect sequences
- [ ] One real test send read end to end before turning it on
- [ ] The CTA is a call booking, never a form
