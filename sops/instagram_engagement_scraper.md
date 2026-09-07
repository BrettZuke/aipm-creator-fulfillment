# Instagram Engagement Lead Scraper

## Goal
Find Instagram sub-accounts (50k–2M followers) who are building audiences in the make-money-online / business opportunity niche by looking at who follows or engages with the biggest creators in that space. These people are already in the ecosystem and are likely selling courses, coaching, or running info-product businesses.

## Inputs
- **Mode**: `likers` (default, higher signal) or `followers`
- **Creator accounts**: The guru accounts to pull followers/engagers from (default: 8 built-in)
- **Follower range**: Min/max followers to qualify a lead (default: 50k–2M)
- **Scale parameters**: Posts per creator, likers per post, followers per creator

## Tools/Scripts
- Script: `tools/<group>/instagram_engagement_scraper.py`
- Dependencies: `APIFY_API_TOKEN` in `.env`, `apify-client` Python package
- Apify actor: `apify/instagram-scraper`

## Strategy

### Mode 1: likers (default — higher signal)
Pull recent posts from each big creator → get users who liked those posts → look up their full profiles → filter by follower count (50k–2M) and having a URL in bio.

**Why it's higher signal**: Active engagers are more likely to be running their own business in the same niche, not just passive fans.

### Mode 2: followers
Pull follower lists directly from the creator accounts → filter by follower count and bio URL.

**When to use**: When you want volume and likers mode has been exhausted. Less precise because fans from all walks of life follow gurus.

## Creator Accounts (built-in defaults)
| Handle | Niche |
|---|---|
| alexhormozi | Business / acquisition |
| cobratate | Mindset / money |
| grahamstephan | Personal finance / real estate |
| tailopez | Self-improvement / business |
| grantcardone | Sales / real estate |
| garyvee | Entrepreneurship / marketing |
| danlok | Sales / high-ticket |
| imangadzhi | SMMA / agency |

## Process

### 1. Test Run (always run first)
```bash
python3 tools/<group>/instagram_engagement_scraper.py --test
```
- Runs 1 creator, 2 posts, 20 likers per post
- Verify the output looks like real niche creators before doing a full run
- Check `.tmp/instagram_engagement_leads_*.json` for sample results

### 2. Full Run — Likers Mode (default)
```bash
python3 tools/<group>/instagram_engagement_scraper.py \
  --mode likers \
  --posts_per_creator 5 \
  --likers_per_post 100
```

### 3. Full Run — Followers Mode
```bash
python3 tools/<group>/instagram_engagement_scraper.py \
  --mode followers \
  --followers_per_creator 500
```

### 4. Custom Creator List
```bash
python3 tools/<group>/instagram_engagement_scraper.py \
  --creators alexhormozi cobratate imangadzhi \
  --mode likers
```

### 5. Adjust Follower Threshold
```bash
python3 tools/<group>/instagram_engagement_scraper.py \
  --min_followers 100000 \
  --max_followers 1000000
```

### 6. Push Results to Google Sheet (DELIVERABLE)
```bash
python3 tools/<group>/update_sheet.py .tmp/instagram_engagement_leads_*.json
```

## Output Columns
| Column | Description |
|---|---|
| username | Instagram handle |
| full_name | Display name |
| followers | Follower count |
| bio | First 250 chars of bio |
| website | Link in bio (offer signal — required to qualify) |
| is_verified | Whether account is verified |
| is_business | Whether it's a business account |
| business_category | IG business category if set |
| instagram_url | Direct link to profile |
| scraped_at | Date scraped |
| source_account | Which creator account this lead was found through |

## Qualification Logic
A lead qualifies if:
1. Followers between 50,000 and 2,000,000
2. Has an external URL in their bio (= they have an offer / something to sell)

## Cost Estimates (Apify)
- Likers mode, 8 creators, 5 posts each, 100 likers/post = ~4,000 raw profiles → profile lookup
  - Estimated: $2–5 per full run
- Followers mode, 8 creators, 500 followers each = ~4,000 raw → profile lookup
  - Estimated: $2–5 per full run
- Apify free tier: $5/month credit (test run uses < $0.50)

## Edge Cases
- **Private accounts**: Apify skips private profiles automatically — no follower count returned
- **Partial liker records**: Likers endpoint sometimes returns minimal data (username only). Script batch-looks up full profiles for those.
- **Partial follower records**: Same — script detects missing `followersCount` and does a batch profile lookup
- **Actor rate limits**: Script adds 1–2s pauses between posts and 2s between creators
- **No posts found**: Some accounts restrict post visibility. Script logs and skips them.
- **Deduplication**: Global dedup by username across all creators — a user found via multiple creators only appears once (attributed to the first creator they were found through)

## Learnings
*(Update this section as you run the scraper and discover patterns)*
- Which creator accounts yield the best quality leads
- Typical hit rate (% of likers that qualify)
- Whether likers vs followers mode produces meaningfully different lead quality
- Common business categories in qualified results
