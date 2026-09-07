---
name: scraper
description: >
  Lead Finder — finds and qualifies leads across Instagram, YouTube, and TikTok using Apify.
  Asks for niche, platform, and criteria, then scrapes, qualifies, and exports to CSV.
  Use when you need to build a prospect list for any niche.
---

# /scraper — Lead Finder

Find and qualify social media leads at scale using Apify actors.

## Workflow

1. Ask: which niche, which platform (Instagram/YouTube/TikTok), follower range, engagement threshold, any other qualifiers
2. Select the right Apify actor (pay-per-use only, prefer official Apify actors, 4.5+ rating)
3. Run a 10-account test batch first — confirm data quality before scaling
4. Qualify results against criteria
5. Find contact emails where possible
6. Export to CSV in `.tmp/leads_[niche]_[date].csv`

## Apify Rules (always follow)

- **Pay-per-use only** — no flat monthly subscription actors (PAY_PER_EVENT or PRICE_PER_DATASET_ITEM pricing only)
- **Prefer official Apify actors** — check `isOfficialApify: true` on the developer
- **Vet non-official actors** — rating 4.5+, meaningful review count, high success rate, large user base
- Always run a small test batch before any large run
- Warn user with estimated cost before running anything

## Output Format

CSV with: username, platform, followers, engagement_rate, niche, email (if found), profile_url, scraped_date

## Notes

- If Apify is not installed, prompt user to install it via Claude Code → Settings → MCP Servers
- For Instagram: use official Instagram Scraper actor
- For YouTube: use official YouTube Scraper actor  
- For TikTok: use official TikTok Scraper actor
