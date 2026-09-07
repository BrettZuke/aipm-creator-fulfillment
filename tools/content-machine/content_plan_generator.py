"""
Weekly content plan generator.

Takes competitor YouTube + Instagram data (with full transcripts) and uses
Claude to generate a weekly content plan in the client's exact brand voice:
- 2 YouTube video scripts
- 14 Instagram Reel scripts (2 per day)

Also uploads everything to a Google Sheet for weekly tracking.
"""

import os
import sys
import json
from pathlib import Path
from datetime import date
from dotenv import load_dotenv

load_dotenv()

try:
    import anthropic
except ImportError:
    print("Error: anthropic not installed.", file=sys.stderr)
    sys.exit(1)

BASE_DIR = Path(__file__).parent.parent


def load_brand_voice(path: str) -> str:
    full_path = BASE_DIR / path
    return full_path.read_text(encoding="utf-8") if full_path.exists() else ""


def format_youtube_context(videos: list[dict]) -> str:
    if not videos:
        return "No YouTube data available."
    lines = []
    for i, v in enumerate(videos, 1):
        transcript = v.get("transcript", "")
        transcript_block = (
            f"   Full transcript:\n   {transcript[:2000]}"
            if transcript
            else "   (no transcript available)"
        )
        thumbnail_block = (
            f"   Thumbnail: {v['thumbnail_analysis']}"
            if v.get("thumbnail_analysis") else ""
        )
        comment_block = (
            f"   Audience reaction: {v['comment_themes']}"
            if v.get("comment_themes") else ""
        )
        lines.append(
            f"{i}. [{v['channel']}] \"{v['title']}\"\n"
            f"   Views: {v['views']:,} | Format: {v.get('format_type','?')} | "
            f"Hook: {v.get('hook_style','?')} | Topic: {v.get('core_topic','?')}\n"
            f"   Visual style: {v.get('visual_style','?')}\n"
            + (thumbnail_block + "\n" if thumbnail_block else "")
            + (comment_block + "\n" if comment_block else "")
            + transcript_block
        )
    return "\n\n".join(lines)


def format_instagram_context(posts: list[dict]) -> str:
    if not posts:
        return "No Instagram data available."
    lines = []
    for i, p in enumerate(posts, 1):
        spoken = p.get("transcript", "")
        caption = p.get("caption", "")
        content_block = ""
        if spoken:
            content_block = f"   Spoken transcript: {spoken[:800]}\n   Caption: {caption[:300]}"
        else:
            content_block = f"   Caption: {caption[:800]}"
        comment_block = (
            f"   Audience reaction: {p['comment_themes']}"
            if p.get("comment_themes") else ""
        )
        visual_block = (
            f"   Visual format (GPT-4V): {p['visual_format']}"
            if p.get("visual_format") else ""
        )
        lines.append(
            f"{i}. [@{p['account']}] {p['type']} — {p['likes']:,} likes\n"
            f"   Format: {p.get('format','?')} | Hook: {p.get('hook_style','?')}\n"
            f"   Topic: {p.get('core_topic','?')}\n"
            + (visual_block + "\n" if visual_block else "")
            + f"   Structure: {p.get('script_structure','')}\n"
            f"   Recreate brief: {p.get('recreate_brief','')}\n"
            + (comment_block + "\n" if comment_block else "")
            + content_block
        )
    return "\n\n".join(lines)


def generate_content_plan(
    youtube_data: list[dict],
    instagram_data: list[dict],
    brand_voice_path: str = "knowledge/BRAND_VOICE.md",
    youtube_count: int = 2,
    reels_count: int = 14,
    niche: str = "",
    client: str = "the client",
) -> dict:
    """
    Generate weekly content plan using Claude.
    Returns structured dict with youtube_ideas, reel_ideas, and source data.
    """
    brand_voice = load_brand_voice(brand_voice_path)
    yt_context = format_youtube_context(youtube_data)
    ig_context = format_instagram_context(instagram_data)

    ai_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    system_prompt = f"""You are writing scripts AS {client}. Not for them. AS them.

THEIR BRAND VOICE. Study this before writing anything, and treat it as outranking every
instruction below it. It was built from their own transcripts, so where a rule here and an
example there disagree, the example wins:
{brand_voice}

THEIR NICHE AND OFFER:
{niche}

HARD RULES, break any of these and the script is wrong:
- Write the way they SPEAK, not the way anyone writes. Reels are spoken. A script built from
  written material reads as an essay and nobody says an essay to a camera.
- Short sentences that land. No flowing prose.
- Specific concrete details over vague statements. The specifics are the whole difference
  between their content and generic content, and they cannot be invented, so use the ones in
  the voice document and the proof inventory.
- Never invent a number, a result or a client story. If it is not in the material you were
  given, it does not go in the script.
- No motivational-speaker energy. No hype. If it sounds like a generic business guru, it is
  wrong. Start over.
- Match their vocabulary exactly, including the words they never use."""

    user_prompt = f"""Here's this week's content intelligence split into two categories:

━━━ NICHE COMPETITORS (direct competition, same offer, same audience) ━━━
These are creators competing directly. Study what topics and angles are
working for them, so this client can make the better version.

{yt_context}

━━━ BROADER VIRAL REFERENCE (top online creators, any niche, far ahead on numbers) ━━━
These are not competitors. Analyse for format innovation, hook styles, and
what content formats are going viral across the wider creator space right now.
Apply those formats to this client's niche, never their subject matter.

{ig_context}

Generate the weekly content plan:

**{youtube_count} YOUTUBE VIDEO SCRIPTS**
For each video:
- title: their version of the title, compelling, in their voice
- hook: first 20 seconds spoken on camera (what they say to open)
- angle: One sentence on what makes their take different or better
- format_recommendation: how to film it (talking head, B-roll needed, and so on)
- full_script: complete video script in their voice. 600-900 words.
  Structure: hook (20s), problem and context, their method or take, specific examples and proof, CTA
  Write it as if they are speaking directly to camera. Line breaks. Conversational.

**{reels_count} INSTAGRAM REEL SCRIPTS**
{reels_count} reels = 2 per day for 7 days. Label each with Day 1, Day 2, etc.
For each reel:
- day: Day 1 through Day 7 (2 reels per day)
- title: Internal concept name
- hook: First line spoken on camera — creates a gap in under 3 seconds
- format: talking head | talking head + B-roll | text overlay | carousel
- hook_style: bold claim | question | story open | stat | challenge
- filming_brief: 2-3 sentences on exactly how to film it
- full_script: complete reel script in their voice. 120-200 words max.
  Punchy. Line breaks. Ends with soft CTA or question. NOT a pitch.

Return ONLY valid JSON. No markdown. No extra text. Exact structure:
{{
  "youtube_ideas": [
    {{
      "title": "...",
      "hook": "...",
      "angle": "...",
      "format_recommendation": "...",
      "full_script": "..."
    }}
  ],
  "reel_ideas": [
    {{
      "day": "Day 1",
      "title": "...",
      "hook": "...",
      "format": "...",
      "hook_style": "...",
      "filming_brief": "...",
      "full_script": "..."
    }}
  ]
}}"""

    print("[Content Plan] Calling Claude to generate scripts...")
    response = ai_client.messages.create(
        model=os.getenv("CONTENT_GEN_MODEL", "claude-opus-4-8"),
        max_tokens=12000,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()

    plan = json.loads(raw)
    plan["top_yt_videos"] = youtube_data
    plan["top_ig_posts"] = instagram_data
    plan["date"] = date.today().isoformat()

    yt_count = len(plan.get("youtube_ideas", []))
    reel_count = len(plan.get("reel_ideas", []))
    print(f"[Content Plan] Generated {yt_count} YouTube scripts + {reel_count} Reel scripts.")

    return plan


# ── Google Sheets helpers ─────────────────────────────────────────────────────

def _get_or_create_sheet(sh, name: str, rows: int = 1000, cols: int = 20):
    """Get existing worksheet or create it."""
    try:
        import gspread
        return sh.worksheet(name)
    except Exception:
        return sh.add_worksheet(name, rows=rows, cols=cols)


def _append_rows_batch(ws, rows: list[list]) -> None:
    """Append rows one at a time (gspread batch append)."""
    for row in rows:
        ws.append_row(row, value_input_option="USER_ENTERED")


# ── Google Sheets upload ──────────────────────────────────────────────────────

def upload_to_sheets(plan: dict, sheet_id: str) -> None:
    """
    Upload the weekly content plan to Google Sheets.
    Four tabs:
      - YT Competitor Intel    (one row per competitor video)
      - IG Competitor Intel    (one row per competitor post)
      - Content Scripts        (the generated scripts for the week)
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("[Sheets] gspread not installed — skipping.", file=sys.stderr)
        return

    creds_path = BASE_DIR / "service_account.json"
    if not creds_path.exists():
        print("[Sheets] service_account.json not found — skipping.", file=sys.stderr)
        return

    try:
        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
    except Exception as e:
        print(f"[Sheets] Auth error: {e}", file=sys.stderr)
        return

    week = plan.get("date", date.today().isoformat())

    # ── Tab 1: YT Competitor Intel ────────────────────────────────────────────
    try:
        yt_tab = _get_or_create_sheet(sh, "YT Competitor Intel", rows=1000, cols=18)

        # Write headers only if sheet is empty
        if not yt_tab.get_all_values():
            yt_tab.append_row([
                "Week", "Channel", "Title", "URL", "Views", "Duration",
                "Upload Date", "Format", "Topic Category", "Editing Style",
                "Hook Style", "Visual Style", "Core Topic",
                "Transcript (first 500 chars)",
            ], value_input_option="USER_ENTERED")

        rows = []
        for v in plan.get("top_yt_videos", []):
            rows.append([
                week,
                v.get("channel", ""),
                v.get("title", ""),
                v.get("url", ""),
                v.get("views", 0),
                v.get("duration_str", ""),
                v.get("upload_date", ""),
                v.get("format_type", ""),
                v.get("topic_category", ""),
                v.get("editing_style", ""),
                v.get("hook_style", ""),
                v.get("visual_style", ""),
                v.get("core_topic", ""),
                (v.get("transcript", "") or "")[:500],
            ])

        _append_rows_batch(yt_tab, rows)
        print(f"[Sheets] YT Competitor Intel — {len(rows)} videos added.")

    except Exception as e:
        print(f"[Sheets] Error writing YT Competitor Intel: {e}", file=sys.stderr)

    # ── Tab 2: IG Competitor Intel ────────────────────────────────────────────
    try:
        ig_tab = _get_or_create_sheet(sh, "IG Competitor Intel", rows=1000, cols=18)

        if not ig_tab.get_all_values():
            ig_tab.append_row([
                "Week", "Account", "Post Type", "Duration / Slides",
                "Likes", "Comments", "Engagement", "Post Date", "URL",
                "Format", "Topic Category", "Hook Style",
                "Script Structure", "Core Topic", "Recreate Brief",
                "Caption (first 500 chars)", "Transcript (first 500 chars)",
            ], value_input_option="USER_ENTERED")

        rows = []
        for p in plan.get("top_ig_posts", []):
            # Duration or slide count depending on type
            if p.get("type") == "Carousel" and p.get("slide_count"):
                detail = f"{p['slide_count']} slides"
            elif p.get("type") == "Reel":
                detail = p.get("duration_str", "")
            else:
                detail = ""

            rows.append([
                week,
                f"@{p.get('account', '')}",
                p.get("type", ""),
                detail,
                p.get("likes", 0),
                p.get("comments", 0),
                p.get("engagement", 0),
                p.get("post_date", ""),
                p.get("url", ""),
                p.get("format", ""),
                p.get("topic_category", ""),
                p.get("hook_style", ""),
                p.get("script_structure", ""),
                p.get("core_topic", ""),
                p.get("recreate_brief", ""),
                (p.get("caption", "") or "")[:500],
                (p.get("transcript", "") or "")[:500],
            ])

        _append_rows_batch(ig_tab, rows)
        print(f"[Sheets] IG Competitor Intel — {len(rows)} posts added.")

    except Exception as e:
        print(f"[Sheets] Error writing IG Competitor Intel: {e}", file=sys.stderr)

    # ── Tab 3: Content Scripts ────────────────────────────────────────────────
    try:
        scripts_tab = _get_or_create_sheet(sh, "Content Scripts", rows=1000, cols=12)

        if not scripts_tab.get_all_values():
            scripts_tab.append_row([
                "Week", "Platform", "Day / Order", "Title", "Hook",
                "Format", "Hook Style", "Angle / Brief", "Full Script",
            ], value_input_option="USER_ENTERED")

        rows = []
        for i, idea in enumerate(plan.get("youtube_ideas", []), 1):
            rows.append([
                week, "YouTube", f"Video {i}",
                idea.get("title", ""),
                idea.get("hook", ""),
                idea.get("format_recommendation", ""),
                "",
                idea.get("angle", ""),
                idea.get("full_script", ""),
            ])

        for idea in plan.get("reel_ideas", []):
            rows.append([
                week, "Instagram Reel", idea.get("day", ""),
                idea.get("title", ""),
                idea.get("hook", ""),
                idea.get("format", ""),
                idea.get("hook_style", ""),
                idea.get("filming_brief", ""),
                idea.get("full_script", ""),
            ])

        _append_rows_batch(scripts_tab, rows)
        print(f"[Sheets] Content Scripts — {len(rows)} scripts added.")

    except Exception as e:
        print(f"[Sheets] Error writing Content Scripts: {e}", file=sys.stderr)


def upload_monthly_report_to_sheets(report: dict, sheet_id: str) -> None:
    """
    Upload monthly trends report to 'Monthly Trends' tab.
    Called from monthly_report_generator.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        print("[Sheets] gspread not installed — skipping.", file=sys.stderr)
        return

    creds_path = BASE_DIR / "service_account.json"
    if not creds_path.exists():
        print("[Sheets] service_account.json not found — skipping.", file=sys.stderr)
        return

    try:
        creds = Credentials.from_service_account_file(
            str(creds_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
    except Exception as e:
        print(f"[Sheets] Auth error: {e}", file=sys.stderr)
        return

    try:
        tab = _get_or_create_sheet(sh, "Monthly Trends", rows=500, cols=12)

        if not tab.get_all_values():
            tab.append_row([
                "Month", "Top YT Format", "Top IG Format", "Top Hook Style",
                "Top Topic Categories", "Content Gaps", "Recommended Focus",
                "Full Analysis",
                "Top YT Videos (title | views | channel)",
                "Top IG Posts (account | type | engagement)",
            ], value_input_option="USER_ENTERED")

        month = report.get("month", "")
        insights = report.get("insights", {})

        # Top videos summary (pipe-separated for sheet)
        top_yt = " | ".join(
            f"{v.get('title','')[:40]} ({v.get('views',0):,}v, {v.get('channel','')})"
            for v in report.get("top_yt_videos", [])[:5]
        )
        top_ig = " | ".join(
            f"@{p.get('account','')} {p.get('type','')} ({p.get('engagement',0):,})"
            for p in report.get("top_ig_posts", [])[:5]
        )

        tab.append_row([
            month,
            insights.get("top_yt_format", ""),
            insights.get("top_ig_format", ""),
            insights.get("top_hook_style", ""),
            insights.get("top_topic_categories", ""),
            insights.get("content_gaps", ""),
            insights.get("recommended_focus", ""),
            insights.get("full_analysis", ""),
            top_yt,
            top_ig,
        ], value_input_option="USER_ENTERED")

        print(f"[Sheets] Monthly Trends — {month} added.")

    except Exception as e:
        print(f"[Sheets] Error writing Monthly Trends: {e}", file=sys.stderr)


if __name__ == "__main__":
    # Test with mock data
    mock_yt = [{
        "platform": "youtube",
        "channel": "ExampleCreatorHQ",
        "channel_handle": "ExampleCreatorHQ",
        "title": "The one thing that changed how I do outreach",
        "url": "https://youtube.com/watch?v=test",
        "views": 180_000,
        "likes": 6_200,
        "comments": 340,
        "upload_date": "2026-03-20",
        "format_type": "talking head",
        "hook_style": "bold claim",
        "core_topic": "getting coaching clients through Instagram",
        "visual_style": "solo presenter, clean background, direct to camera",
        "transcript": (
            "I got 10 paying clients in 30 days using only Instagram. "
            "No cold DMs. No ads. No big following. Here's exactly what I did..."
        ),
    }]
    mock_ig = [{
        "platform": "instagram",
        "account": "example_creator",
        "caption": "Your personal brand is either working for you or against you. Here's why...",
        "likes": 28_000,
        "comments": 450,
        "engagement": 30_250,
        "type": "Reel",
        "url": "https://instagram.com/p/test",
        "post_date": "2026-03-21",
        "transcript": "Your personal brand is either making you money or costing you money. Most coaches don't realise this...",
        "hook_style": "bold claim",
        "format": "talking head",
        "core_topic": "personal brand ROI for coaches",
        "script_structure": "bold hook → problem → 3-step solution → CTA to follow",
        "recreate_brief": "Film talking head, direct to camera. Open with the bold claim, pause for effect.",
    }]

    result = generate_content_plan(mock_yt, mock_ig)
    print(json.dumps({
        "youtube_count": len(result.get("youtube_ideas", [])),
        "reel_count": len(result.get("reel_ideas", [])),
        "first_yt_title": result.get("youtube_ideas", [{}])[0].get("title", ""),
        "first_reel_hook": result.get("reel_ideas", [{}])[0].get("hook", ""),
    }, indent=2))
