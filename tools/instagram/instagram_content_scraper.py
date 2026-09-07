"""
Instagram competitor content scraper.

Uses instaloader to scrape recent posts from public accounts.
For Reels: downloads video and transcribes with OpenAI Whisper.
For Carousels: captures slide count and caption.
Analyzes format/structure with Claude.
"""

import os
import sys
import json
import time
import tempfile
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

try:
    import instaloader
except ImportError:
    print("Error: instaloader not installed. Run: pip install instaloader", file=sys.stderr)
    sys.exit(1)

# Imported lazily inside analyze_post_formats(), which is the only thing that needs it and is
# the only PAID step here. Exiting at import time made the whole scraper unusable on the
# free-only setup this repo prescribes, including the scraping it does perfectly well without
# a model.

try:
    import httpx
except ImportError:
    print("Error: httpx not installed.", file=sys.stderr)
    sys.exit(1)

POSTS_PER_ACCOUNT = 15
DAYS_LOOKBACK = 30
WHISPER_MAX_BYTES = 24 * 1024 * 1024  # 24MB

SESSION_FILE = os.path.join(os.path.dirname(__file__), ".instagram_session")


# ── Auth ──────────────────────────────────────────────────────────────────────

def _make_loader() -> "instaloader.Instaloader":
    return instaloader.Instaloader(
        quiet=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,  # We fetch comments manually via post.get_comments()
        save_metadata=False,
        compress_json=False,
    )


def fetch_post_comments(post: "instaloader.Post", max_comments: int = 20) -> list[dict]:
    """Fetch top comments from a post. Returns list of {author, text, likes}."""
    comments = []
    try:
        for comment in post.get_comments():
            if len(comments) >= max_comments:
                break
            text = (comment.text or "").strip()
            if not text:
                continue
            comments.append({
                "author": getattr(comment.owner, "username", "") if comment.owner else "",
                "text": text,
                "likes": getattr(comment, "likes_count", 0) or 0,
            })
    except Exception:
        pass
    return comments


def get_loader() -> "instaloader.Instaloader":
    """
    Return an authenticated Instaloader instance.
    Uses saved session file if available (set up via instagram_login / instagram_2fa_login).
    """
    username = os.getenv("INSTAGRAM_USERNAME", "")
    loader = _make_loader()

    if not username:
        print("[IG] WARNING: INSTAGRAM_USERNAME not set in .env.", file=sys.stderr)
        return loader

    # Use saved session (no 2FA needed once this file exists)
    if os.path.exists(SESSION_FILE):
        try:
            loader.load_session_from_file(username, SESSION_FILE)
            print(f"[IG] Loaded Instagram session for @{username}")
            return loader
        except Exception:
            print("[IG] Saved session expired — need to re-authenticate.", file=sys.stderr)

    print(
        "[IG] No valid session found. Go to the dashboard → Instagram Setup to authenticate.",
        file=sys.stderr,
    )
    return loader


def instagram_login(username: str, password: str) -> tuple[bool, str, "instaloader.Instaloader | None"]:
    """
    Attempt Instagram login. Returns (success, message, loader).
    If 2FA is required, returns (False, '2fa_required', loader_in_pending_state).
    """
    loader = _make_loader()
    loader.context.quiet = False  # show errors

    try:
        loader.login(username, password)
        loader.save_session_to_file(SESSION_FILE)
        return True, "Logged in successfully.", loader
    except instaloader.exceptions.TwoFactorAuthRequiredException:
        return False, "2fa_required", loader
    except instaloader.exceptions.BadCredentialsException:
        return False, "Incorrect username or password.", None
    except Exception as e:
        return False, str(e), None


def instagram_2fa_login(loader: "instaloader.Instaloader", code: str) -> tuple[bool, str]:
    """
    Complete 2FA login with the code from the authenticator app / SMS.
    Returns (success, message).
    """
    try:
        loader.two_factor_login(code.strip())
        loader.save_session_to_file(SESSION_FILE)
        return True, "2FA login successful. Session saved."
    except instaloader.exceptions.BadCredentialsException:
        return False, "Invalid 2FA code. Try again."
    except Exception as e:
        return False, str(e)


# ── Reel analysis (Whisper + GPT-4V) ─────────────────────────────────────────

def _extract_frame_base64(video_path: str, offset_secs: float = 3.0) -> str:
    """
    Extract a single frame from a video file using ffmpeg.
    Returns base64-encoded JPEG string, or '' if ffmpeg is unavailable.
    """
    import subprocess
    import base64
    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
        frame_path = f.name
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y", "-ss", str(offset_secs), "-i", video_path,
                "-frames:v", "1", "-q:v", "3", frame_path,
            ],
            capture_output=True, timeout=15,
        )
        if result.returncode != 0:
            return ""
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return ""
    finally:
        try:
            os.unlink(frame_path)
        except Exception:
            pass


def _analyze_reel_visuals(video_path: str, client: "OpenAI") -> str:
    """
    Use GPT-4o to analyze editing style and format of a Reel from extracted frames.
    Returns a 1-2 sentence description.
    """
    frame_b64 = _extract_frame_base64(video_path, offset_secs=3.0)
    mid_b64 = _extract_frame_base64(video_path, offset_secs=8.0)

    images = []
    for b64 in [frame_b64, mid_b64]:
        if b64:
            images.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

    if not images:
        return ""

    images.append({
        "type": "text",
        "text": (
            "These are frames from an Instagram Reel. Identify the visual format and editing style in ONE sentence. "
            "Choose the primary style from: talking head | talking head + B-roll | split screen | "
            "vlog/handheld | whiteboard/miro board | text-on-screen only | faceless voiceover | "
            "heavily edited (fast cuts, transitions, text animations) | lightly edited (clean cuts) | raw/no edit. "
            "Then in a second sentence describe what makes the visual presentation distinctive "
            "(e.g. background, camera angle, text overlays, graphics)."
        ),
    })

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=100,
            messages=[{"role": "user", "content": images}],
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


def transcribe_and_analyze_reel(video_url: str) -> tuple[str, str]:
    """
    Download a Reel, transcribe with Whisper, and analyze visuals with GPT-4V.
    Returns (transcript, visual_format_analysis).
    Both strings are '' on failure.
    """
    if not video_url:
        return "", ""

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        return "", ""

    try:
        from openai import OpenAI
    except ImportError:
        return "", ""

    try:
        response = httpx.get(video_url, timeout=60, follow_redirects=True)
        if response.status_code != 200:
            return "", ""

        video_bytes = response.content
        if len(video_bytes) > WHISPER_MAX_BYTES:
            print(f"  [IG] Video too large ({len(video_bytes) / 1e6:.1f}MB), skipping.", file=sys.stderr)
            return "", ""

        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name

        client = OpenAI(api_key=openai_key)

        # Whisper transcription
        transcript = ""
        try:
            with open(tmp_path, "rb") as f:
                transcript = client.audio.transcriptions.create(
                    model="whisper-1", file=f
                ).text.strip()
        except Exception as e:
            print(f"  [IG] Whisper error: {e}", file=sys.stderr)

        # GPT-4V visual format analysis
        visual_format = _analyze_reel_visuals(tmp_path, client)

        os.unlink(tmp_path)
        return transcript, visual_format

    except Exception as e:
        print(f"  [IG] Reel analysis error: {e}", file=sys.stderr)
        return "", ""


# Keep old name as alias for any callers that use it directly
def transcribe_reel(video_url: str) -> str:
    transcript, _ = transcribe_and_analyze_reel(video_url)
    return transcript


# ── Scraping ──────────────────────────────────────────────────────────────────

def scrape_account_posts(username: str, loader: "instaloader.Instaloader") -> list[dict]:
    """Scrape recent posts from a single Instagram account."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=DAYS_LOOKBACK)
    posts = []

    try:
        profile = instaloader.Profile.from_username(loader.context, username)

        for post in profile.get_posts():
            if len(posts) >= POSTS_PER_ACCOUNT:
                break

            post_date = post.date_utc.replace(tzinfo=timezone.utc)
            if post_date < cutoff:
                break

            caption = (post.caption or "").strip()
            likes = post.likes or 0
            comments = post.comments or 0

            # Post type
            if post.is_video:
                post_type = "Reel"
            elif post.typename == "GraphSidecar":
                post_type = "Carousel"
            else:
                post_type = "Image"

            # Duration for Reels (seconds)
            duration_secs = 0
            if post.is_video:
                try:
                    duration_secs = int(post.video_duration or 0)
                except Exception:
                    duration_secs = 0

            # Slide count for Carousels
            slide_count = 0
            if post.typename == "GraphSidecar":
                try:
                    slide_count = post.mediacount or 0
                except Exception:
                    slide_count = 0

            # Video URL for Reels
            video_url = ""
            if post.is_video:
                try:
                    video_url = post.video_url or ""
                except Exception:
                    video_url = ""

            shortcode = post.shortcode or ""
            url = f"https://www.instagram.com/p/{shortcode}/" if shortcode else ""

            posts.append({
                "platform": "instagram",
                "account": username,
                "caption": caption[:2000],
                "likes": likes,
                "comments": comments,
                "engagement": likes + (comments * 5),
                "type": post_type,
                "duration_secs": duration_secs,
                "duration_str": f"{duration_secs}s" if duration_secs else "unknown",
                "slide_count": slide_count,
                "video_url": video_url,
                "shortcode": shortcode,
                "url": url,
                "post_date": post_date.strftime("%Y-%m-%d"),
                "transcript": "",
            })

        return posts

    except instaloader.exceptions.ProfileNotExistsException:
        print(f"  [IG] Profile @{username} not found or private.", file=sys.stderr)
        return []
    except Exception as e:
        print(f"  [IG] instaloader error for @{username}: {e}", file=sys.stderr)
        return []


# ── Format analysis ───────────────────────────────────────────────────────────

def analyze_post_formats(posts: list[dict]) -> list[dict]:
    """Use Claude to analyze format, hook style, script structure per post."""
    if not posts:
        return posts

    try:
        import anthropic
    except ImportError:
        print("  skipping format analysis: anthropic is not installed (it is the paid path). "
              "Posts are returned unanalysed.", file=sys.stderr)
        return posts
    if not os.getenv("ANTHROPIC_API_KEY"):
        print("  skipping format analysis: ANTHROPIC_API_KEY is not set, which is the default. "
              "Posts are returned unanalysed.", file=sys.stderr)
        return posts
    ai_client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

    posts_text = ""
    for i, post in enumerate(posts, 1):
        content = post.get("transcript") or post.get("caption", "")
        type_detail = post["type"]
        if post["type"] == "Reel" and post["duration_secs"]:
            type_detail += f" ({post['duration_str']})"
        if post["type"] == "Carousel" and post["slide_count"]:
            type_detail += f" ({post['slide_count']} slides)"
        comments = post.get("comments_data") or []
        comment_block = ""
        if comments:
            top = sorted(comments, key=lambda c: c.get("likes", 0), reverse=True)[:5]
            comment_block = "\nTop comments:\n" + "\n".join(
                f"  [{c.get('likes',0)} likes] {c.get('text','')[:120]}" for c in top
            )
        visual_block = ""
        if post.get("visual_format"):
            visual_block = f"\nGPT-4V visual analysis: {post['visual_format']}"
        posts_text += (
            f"\nPOST {i} — @{post['account']} | {type_detail} | {post['likes']:,} likes\n"
            f"Content: {content[:800]}"
            + visual_block
            + comment_block + "\n---"
        )

    prompt = (
        f"Analyze these {len(posts)} Instagram posts from personal brand / "
        "business coaching creators.\n"
        f"{posts_text}\n\n"
        f"For EACH of the {len(posts)} posts, identify:\n"
        "1. hook_style: bold claim | question | story open | stat | "
        "challenge/call-out | curiosity gap\n"
        "2. format: talking head | talking head + B-roll | text overlay | "
        "carousel slides | static image | faceless voiceover\n"
        "3. topic_category: teaching/educational | personal story | lifestyle | "
        "motivational | social proof | challenge/transformation\n"
        "4. script_structure: 1-sentence breakdown of flow (e.g. 'bold hook → 3 mistakes → CTA')\n"
        "5. core_topic: main subject in 5-8 words\n"
        "6. recreate_brief: 2-sentence filming brief for Dan — be specific about "
        "how to film it and what the opening line should do\n"
        "7. comment_themes: 1-2 sentences on what the audience is asking/saying "
        "in comments (only if comment data present, otherwise empty string)\n\n"
        f"Return ONLY a JSON array with exactly {len(posts)} objects:\n"
        '[{"hook_style":"...","format":"...","topic_category":"...","script_structure":"...",'
        '"core_topic":"...","recreate_brief":"...","comment_themes":"..."}]'
    )

    try:
        response = ai_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=3000,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        analyses = json.loads(raw)
        for i, post in enumerate(posts):
            if i < len(analyses):
                post.update(analyses[i])
    except Exception as e:
        print(f"  [IG] Format analysis error: {e}", file=sys.stderr)
        for post in posts:
            post.setdefault("hook_style", "unknown")
            post.setdefault("format", "unknown")
            post.setdefault("topic_category", "unknown")
            post.setdefault("script_structure", "")
            post.setdefault("core_topic", "")
            post.setdefault("recreate_brief", "")
            post.setdefault("comment_themes", "")

    return posts


# ── Main entry point ──────────────────────────────────────────────────────────

def scrape_instagram_competitors(usernames: list[str]) -> list[dict]:
    """
    Scrape top recent posts from Instagram accounts.
    Filters cache, transcribes Reels, analyzes format.
    Returns top 20 unseen posts sorted by engagement.
    """
    from scrape_cache import filter_unseen

    loader = get_loader()
    all_posts = []

    print(f"\n[Instagram] Scraping {len(usernames)} accounts...")
    for i, username in enumerate(usernames):
        print(f"  Scraping @{username}...")
        posts = scrape_account_posts(username, loader)
        print(f"  Got {len(posts)} posts")
        all_posts.extend(posts)
        if i < len(usernames) - 1:
            time.sleep(3)

    if not all_posts:
        print("[Instagram] No posts found.", file=sys.stderr)
        return []

    # Filter already-used content
    all_posts, skipped = filter_unseen(all_posts, "shortcode")
    if skipped:
        print(f"  Skipped {skipped} already-used posts (cache)")

    # Sort by engagement, keep top 20
    all_posts.sort(key=lambda p: p["engagement"], reverse=True)
    top_posts = all_posts[:20]

    # Fetch comments for top posts
    print(f"\n[Instagram] Fetching comments for top {len(top_posts)} posts...")
    # Need original Post objects — re-scrape to get comment access.
    # We cache them during the main scrape run using a lookup dict.
    post_objects: dict[str, "instaloader.Post"] = {}
    for username in usernames:
        try:
            profile = instaloader.Profile.from_username(loader.context, username)
            for post in profile.get_posts():
                if post.shortcode in {p["shortcode"] for p in top_posts}:
                    post_objects[post.shortcode] = post
                if len(post_objects) >= len(top_posts):
                    break
        except Exception:
            pass

    for p in top_posts:
        post_obj = post_objects.get(p["shortcode"])
        if post_obj:
            comments = fetch_post_comments(post_obj, max_comments=20)
            p["comments_data"] = comments
            print(f"  @{p['account']} — {len(comments)} comments")
        else:
            p["comments_data"] = []

    # Transcribe + visual analysis of Reels (Whisper + GPT-4V)
    reels = [p for p in top_posts if p["type"] == "Reel" and p["video_url"]]
    print(f"\n[Instagram] Transcribing + analyzing {len(reels)} Reels (Whisper + GPT-4V)...")
    for post in reels:
        print(f"  @{post['account']} reel ({post['duration_str']})...")
        transcript, visual_format = transcribe_and_analyze_reel(post["video_url"])
        post["transcript"] = transcript
        post["visual_format"] = visual_format
        status = f"{len(transcript)} chars" if transcript else "using caption"
        fmt_status = visual_format[:60] if visual_format else "no visual analysis"
        print(f"  Done — transcript: {status} | format: {fmt_status}")

    # Analyze format
    print("\n[Instagram] Analyzing post formats...")
    top_posts = analyze_post_formats(top_posts)

    print("\n[Instagram] Top posts:")
    for p in top_posts:
        detail = f"{p['duration_str']}" if p["type"] == "Reel" else \
                 f"{p['slide_count']} slides" if p["type"] == "Carousel" else "image"
        print(
            f"  {p['engagement']:,} eng — @{p['account']} — "
            f"{p['type']} ({detail}) — {p.get('core_topic', p['caption'][:35])}"
        )

    return top_posts


if __name__ == "__main__":
    from competitors import CLIENT_COMPETITORS
    results = scrape_instagram_competitors(CLIENT_COMPETITORS["instagram"])
    print(f"\nTotal returned: {len(results)}")
