---
name: analyze-creator
description: >
  Creator Intelligence — analyzes any creator's recent content using Apify to scrape
  their last 20 posts and extract what's working: engagement patterns, hook styles,
  top formats, posting frequency. Use for competitor research or client prospecting.
---

# /analyze-creator — Creator Intelligence

Scrapes and analyzes any creator's recent content to extract what's working and why.

## Workflow

1. Ask: creator's username/handle, platform (Instagram/YouTube/TikTok), what you want to learn (hooks / formats / engagement patterns / content themes / all)
2. Check Apify is installed — if not, prompt to install
3. Run the appropriate Apify actor to scrape their last 20 posts
4. Analyze the data
5. Deliver a structured breakdown

## Analysis Framework

**Engagement analysis**: which posts have the highest likes/views/comments/saves and why
**Hook patterns**: what opening lines or visual patterns appear on their best content
**Content formats**: talking head vs B-roll vs text overlay vs POV, what ratio
**Topic clusters**: recurring themes that consistently perform
**Posting cadence**: frequency, best days/times based on engagement
**Comment mining**: what questions/reactions appear most in comments

## Apify Rules

- Pay-per-use actors only (PAY_PER_EVENT or PRICE_PER_DATASET_ITEM pricing)
- Prefer official Apify actors (isOfficialApify: true)
- Warn with cost estimate before running
- Run test on 5 posts first if uncertain about actor quality

## Output

- Top 5 posts with analysis of why they worked
- 3 hook formulas this creator uses repeatedly
- Content format breakdown (%)
- 3 content angles you could apply to your own channel
- One thing they're not doing that's an obvious gap
