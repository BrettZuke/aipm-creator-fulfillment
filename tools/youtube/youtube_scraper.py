"""
YouTube competitor content scraper.

Uses yt-dlp to scrape recent videos from channels (free, no API limits),
youtube-transcript-api for full transcripts, and Claude to analyze format,
topic category, and editing style.
"""

import os
import sys
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

try:
    import yt_dlp
except ImportError:
    print("Error: yt-dlp not installed. Run: pip install yt-dlp", file=sys.stderr)
    sys.exit(1)

try:
    from youtube_transcript_api import YouTubeTranscriptApi, NoTranscriptFound, TranscriptsDisabled
except ImportError:
    print("Error: youtube-transcript-api not installed.", file=sys.stderr)
    sys.exit(1)

# Imported lazily inside the analysis function, which is the only PAID step and the only
# thing that needs it. Exiting at import time made the scraper unusable on the free-only
# setup this repo prescribes, including the scraping it does fine without a model.

VIDEOS_PER_CHANNEL = 15
DAYS_LOOKBACK = 30


def parse_upload_date(date_str: str) -> datetime | None:
    """Parse yt-dlp upload_date (YYYYMMDD) or ISO format."""
    if not date_str:
        return None
    s = str(date_str)
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.strptime(s, "%Y%m%d")
        except ValueError:
            return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(s[:19], fmt)
        except ValueError:
            continue
    return None


def format_duration(seconds: int) -> str:
    """Convert seconds to MM:SS or HH:MM:SS string."""
    if not seconds:
        return "unknown"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def fetch_transcript(video_id: str) -> str:
    """Fetch full transcript. Returns text or empty string."""
    if not video_id:
        return ""
    api = YouTubeTranscriptApi()
    try:
        result = api.fetch(video_id, languages=["en", "en-GB", "en-US"])
        return " ".join(s.text for s in result).strip()
    except (NoTranscriptFound, TranscriptsDisabled):
        pass
    except Exception:
        pass
    try:
        transcript_list = api.list(video_id)
        for t in transcript_list:
            result = t.fetch()
            return " ".join(s.text for s in result).strip()
    except Exception:
        return ""
    return ""


def get_video_duration(video_id: str) -> int:
    """Fetch duration in seconds for a single video."""
    if not video_id:
        return 0
    ydl_opts = {"quiet": True, "no_warnings": True}
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
            return info.get("duration") or 0
    except Exception:
        return 0


def fetch_video_comments(video_id: str, max_comments: int = 30) -> list[dict]:
    """Fetch top comments for a video using yt-dlp. Returns list of {author, text, likes}."""
    if not video_id:
        return []
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "getcomments": True,
        "extractor_args": {"youtube": {"max_comments": [str(max_comments)]}},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={video_id}", download=False
            )
            raw = info.get("comments") or []
            return [
                {
                    "author": c.get("author", ""),
                    "text": (c.get("text") or "").strip(),
                    "likes": c.get("like_count") or 0,
                }
                for c in raw[:max_comments]
                if (c.get("text") or "").strip()
            ]
    except Exception:
        return []


def analyze_thumbnail_batch(videos: list[dict]) -> list[dict]:
    """
    Use OpenAI GPT-4o vision to analyze YouTube thumbnails.
    Adds thumbnail_analysis field to each video dict.
    """
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        for v in videos:
            v.setdefault("thumbnail_analysis", "")
        return videos

    try:
        from openai import OpenAI
    except ImportError:
        for v in videos:
            v.setdefault("thumbnail_analysis", "")
        return videos

    client = OpenAI(api_key=openai_key)

    for v in videos:
        video_id = v.get("video_id", "")
        title = v.get("title", "")
        if not video_id:
            v["thumbnail_analysis"] = ""
            continue

        thumbnail_url = f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg"
        try:
            resp = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=150,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": thumbnail_url}},
                        {
                            "type": "text",
                            "text": (
                                f'YouTube thumbnail for: "{title}". '
                                "Sentence 1: identify the likely video format — "
                                "talking head | talking head + B-roll | split screen | "
                                "vlog/handheld | whiteboard/miro board | heavily edited | "
                                "lightly edited | raw/no edit | documentary style. "
                                "Sentence 2: describe what's visually prominent "
                                "(expression, text overlays, background, graphics) "
                                "and what makes this thumbnail click-worthy."
                            ),
                        },
                    ],
                }],
            )
            v["thumbnail_analysis"] = resp.choices[0].message.content.strip()
        except Exception:
            v["thumbnail_analysis"] = ""

    return videos


def analyze_format_batch(videos: list[dict]) -> list[dict]:
    """
    Use Claude to analyze each video's format, topic category, editing style,
    hook style, visual style, and core topic.
    """
    if not videos:
        return videos

    try:
        import anthropic
    except ImportError:
        print("  skipping analysis: anthropic is not installed (it is the paid path). "
              "Videos are returned unanalysed.", file=sys.stderr)
        return videos
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("  skipping analysis: ANTHROPIC_API_KEY is not set, which is the default. "
              "Videos are returned unanalysed.", file=sys.stderr)
        return videos
    ai_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    video_summaries = []
    for i, v in enumerate(videos, 1):
        transcript_excerpt = (v.get("transcript") or "")[:800]
        video_summaries.append(
            f"VIDEO {i}: \"{v['title']}\"\n"
            f"Channel: {v['channel']} | Duration: {v.get('duration_str', 'unknown')}\n"
            f"Transcript excerpt: {transcript_excerpt or '(no transcript)'}\n"
        )

    # Include top comments in summaries if available
    video_summaries_with_comments = []
    for i, v in enumerate(videos, 1):
        transcript_excerpt = (v.get("transcript") or "")[:800]
        comments = v.get("comments_data") or []
        comment_block = ""
        if comments:
            top = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)[:5]
            comment_block = "\nTop comments:\n" + "\n".join(
                f"  [{c.get('likes',0)} likes] {c.get('text','')[:120]}" for c in top
            )
        video_summaries_with_comments.append(
            f"VIDEO {i}: \"{v['title']}\"\n"
            f"Channel: {v['channel']} | Duration: {v.get('duration_str', 'unknown')}\n"
            f"Transcript excerpt: {transcript_excerpt or '(no transcript)'}"
            + comment_block + "\n"
        )

    prompt = (
        f"Analyze these {len(videos)} YouTube videos for a content strategist.\n\n"
        + "\n---\n".join(video_summaries_with_comments)
        + "\n\nFor EACH video, identify ALL of the following:\n"
        "1. format_type: talking head | talking head + B-roll | vlog | interview | "
        "screen recording | listicle | story-time | other\n"
        "2. topic_category: teaching/educational | lifestyle | personal story | "
        "motivational | challenge/transformation | commentary | behind-the-scenes\n"
        "3. editing_style: heavily edited (fast cuts, graphics, music) | "
        "lightly edited (clean cuts, minimal graphics) | raw/vlog (minimal editing)\n"
        "4. hook_style: stat/number | bold claim | story open | question | "
        "challenge/call-out | curiosity gap | before/after\n"
        "5. visual_style: one sentence on how it's likely filmed/presented\n"
        "6. core_topic: the main subject in 5-8 words\n"
        "7. comment_themes: 1-2 sentences on what the audience is saying/asking in comments "
        "(only if comment data is present, otherwise empty string)\n\n"
        f"Return ONLY a JSON array with {len(videos)} objects:\n"
        '[{"format_type":"...","topic_category":"...","editing_style":"...",'
        '"hook_style":"...","visual_style":"...","core_topic":"...","comment_themes":"..."}]'
    )

    try:
        response = ai_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        analyses = json.loads(raw)
        for i, video in enumerate(videos):
            if i < len(analyses):
                video.update(analyses[i])
    except Exception as e:
        print(f"  [YT] Format analysis error: {e}", file=sys.stderr)
        for video in videos:
            video.setdefault("format_type", "unknown")
            video.setdefault("topic_category", "unknown")
            video.setdefault("editing_style", "unknown")
            video.setdefault("hook_style", "unknown")
            video.setdefault("visual_style", "")
            video.setdefault("core_topic", "")
            video.setdefault("comment_themes", "")

    return videos


def scrape_channel(handle: str) -> list[dict]:
    """Scrape recent videos from a single YouTube channel using yt-dlp."""
    url = f"https://www.youtube.com/@{handle}/videos"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "playlistend": VIDEOS_PER_CHANNEL,
    }
    cutoff = datetime.utcnow() - timedelta(days=DAYS_LOOKBACK)
    videos = []

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return []
            entries = info.get("entries", []) or []

            for entry in entries:
                if not entry:
                    continue
                title = entry.get("title", "")
                if not title:
                    continue

                video_id = entry.get("id", "")
                upload_date = parse_upload_date(entry.get("upload_date", ""))

                if upload_date and upload_date < cutoff:
                    continue

                duration_secs = entry.get("duration") or 0

                videos.append({
                    "platform": "youtube",
                    "channel": entry.get("channel") or handle,
                    "channel_handle": handle,
                    "title": title,
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "views": entry.get("view_count") or 0,
                    "likes": 0,
                    "comments": 0,
                    "upload_date": upload_date.strftime("%Y-%m-%d") if upload_date else "unknown",
                    "duration_secs": duration_secs,
                    "duration_str": format_duration(duration_secs),
                    "description": (entry.get("description") or "")[:500],
                    "transcript": "",
                })

        return videos

    except Exception as e:
        print(f"  [YT] yt-dlp error for @{handle}: {e}", file=sys.stderr)
        return []


def scrape_youtube_competitors(channel_handles: list[str]) -> list[dict]:
    """
    Scrape top recent videos from channel handles.
    Filters already-seen content via cache, fetches transcripts, analyzes format.
    Returns top 10 unseen videos sorted by view count.
    """
    from scrape_cache import filter_unseen

    all_videos = []

    print(f"\n[YouTube] Scraping {len(channel_handles)} channels...")
    for handle in channel_handles:
        print(f"  Scraping @{handle}...")
        videos = scrape_channel(handle)
        print(f"  Got {len(videos)} videos")
        all_videos.extend(videos)

    if not all_videos:
        print("[YouTube] No videos found.", file=sys.stderr)
        return []

    # Filter out previously used content
    all_videos, skipped = filter_unseen(all_videos, "video_id")
    if skipped:
        print(f"  Skipped {skipped} already-used videos (cache)")

    # Sort by views, keep top 10
    all_videos.sort(key=lambda v: v["views"], reverse=True)
    top_videos = all_videos[:10]

    # Fetch comments for top videos
    print(f"\n[YouTube] Fetching comments for top {len(top_videos)} videos...")
    for v in top_videos:
        if v["video_id"]:
            comments = fetch_video_comments(v["video_id"], max_comments=30)
            v["comments_data"] = comments
            print(f"  {v['title'][:50]} — {len(comments)} comments fetched")
        else:
            v["comments_data"] = []

    # Fetch transcripts
    print(f"\n[YouTube] Fetching transcripts for top {len(top_videos)} videos...")
    for v in top_videos:
        if v["video_id"]:
            transcript = fetch_transcript(v["video_id"])
            v["transcript"] = transcript
            status = f"{len(transcript)} chars" if transcript else "unavailable"
            print(f"  {v['title'][:50]} — transcript: {status}")
        else:
            print(f"  {v['title'][:50]} — no video ID")

    # Fetch durations for videos where yt-dlp flat mode didn't return it
    missing_duration = [v for v in top_videos if not v["duration_secs"] and v["video_id"]]
    if missing_duration:
        print(f"\n[YouTube] Fetching duration for {len(missing_duration)} videos...")
        for v in missing_duration:
            secs = get_video_duration(v["video_id"])
            v["duration_secs"] = secs
            v["duration_str"] = format_duration(secs)

    # Analyze format, topic, editing style (Claude)
    print("\n[YouTube] Analyzing video formats with Claude...")
    top_videos = analyze_format_batch(top_videos)

    # Analyze thumbnails with OpenAI GPT-4V
    print("\n[YouTube] Analyzing thumbnails with GPT-4V...")
    top_videos = analyze_thumbnail_batch(top_videos)

    print(f"\n[YouTube] Top {len(top_videos)} videos:")
    for v in top_videos:
        print(f"  {v['views']:,}v {v['duration_str']} — {v['channel']} — {v['title'][:45]}")
        print(f"    {v.get('topic_category','?')} | {v.get('format_type','?')} | "
              f"hook: {v.get('hook_style','?')} | editing: {v.get('editing_style','?')}")

    return top_videos


if __name__ == "__main__":
    from competitors import CLIENT_COMPETITORS
    results = scrape_youtube_competitors(CLIENT_COMPETITORS["youtube"])
    print(f"\nTotal returned: {len(results)}")
