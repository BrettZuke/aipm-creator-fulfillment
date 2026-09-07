# Phase 2. Competitors and industry leaders

**Deliverable:** a dossier per competitor covering their content, their funnel and their
emails, and a one-page signal of what is measurably working in this lane right now.

**Done when:** you can say which hooks, formats and offers are working in the niche, with
numbers, and you have their competitors' full funnels captured.

---

## 1. Build the competitor list

Two sources, and the second matters more than people expect.

**Direct competitors:** who the client names, plus who their audience follows.

**Industry leaders:** the people winning in the lane the client wants to be in, even at a
much bigger scale. Their content is the ceiling and it tells you where the lane is going.

To find creators systematically rather than by guessing, use
[youtube-creator-scraper](https://github.com/BrettZuke/youtube-creator-scraper). YouTube
search is the reliable discovery method here. Instagram hashtag discovery does not work,
so do not build on it.

## 2. Scrape their content

```bash
python3 tools/instagram/scrape_creator_deep.py --username competitor --ig-posts 200
python3 tools/youtube/scrape_youtube_creator.py --channel @competitor --max-videos 50 --transcripts 15
python3 tools/competitor-intel/scrape_competitors_4ch.py     # 12 months of YouTube across four creators
```

For a fast read on one account without the full pipeline, use the `analyze-creator` skill
in `skills/`. For pulling out the viral outliers and their hooks specifically, use
`skills/spy`.

## 3. Capture their funnel

Do this by hand. It is an hour and it is the highest-value hour in the phase.

For each competitor, opt in to their funnel with a fresh email address and record:

- The opt-in page: headline, promise, the mechanism they name
- What arrives immediately, and how fast
- The VSL or webinar: what they teach before they pitch, and where the pitch lands
- The booking page and the qualifying questions
- Price, payment options, and the guarantee

Screenshot every page. `skills/scraper` handles the pages that fight back.

## 4. Capture their emails

Those fresh opt-ins now receive their email sequences. Let them run for two weeks, then:

```bash
python3 tools/competitor-intel/competitor_email_intel.py --days 14
```

This pulls two things from each email and keeps them separate: the **story** (a concrete
thing that happened, with the numbers, copied verbatim, never invented) and the **angle**
(the reusable shape with the topic stripped out).

Scope, deliberately: this extracts angles for content ideas. It does not copy anyone's
writing and it does not draft the client's emails. Copying a competitor's emails is how
you produce a client who sounds like a worse version of someone else.

## 5. Turn it into signal

```bash
python3 tools/content-machine/content_signal_parser.py
```

That reads everything scraped and answers one question: what is working in this lane right
now. It is the input to phase 4's scripter, so it needs to be running before you get there.

---

## Checklist

- [ ] Competitor list built, direct competitors and industry leaders both
- [ ] All competitor content scraped, transcripts included
- [ ] Every competitor funnel walked and screenshotted end to end
- [ ] Fresh emails opted in and collecting sequences
- [ ] Signal parser running and producing output
- [ ] Findings written up as a dossier per competitor, using [aipm-client-research](https://github.com/BrettZuke/aipm-client-research)
