#!/usr/bin/env python3
"""
Creator content engine — competitor intelligence -> client-voice scripts.

Reliable replacement for the May pipeline whose transcripts failed (free
youtube-transcript-api got blocked) and whose IG scrape needed a fragile
instaloader session. This routes the FETCH layer through the Apify actors
already proven in this repo, keeps the existing Claude script generator
(content_plan_generator.generate_content_plan, in the client's exact brand voice),
and delivers a formatted Google Doc.

Pipeline:
  YouTube : yt-dlp lists each channel's recent videos (free, with view counts)
            -> rank top-N in the lookback window by views
            -> topaz_sharingan/Youtube-Transcript-Scraper-1 (Apify) for transcripts
  Instagram: apify/instagram-scraper -> recent posts
            -> keep reels in window, rank top-N by plays/views/likes
            -> Groq Whisper (free) transcribes the spoken audio
  Enrich  : one Claude call per platform tags format / hook / topic / structure
  Generate: content_plan_generator -> 2 YT scripts + 14 reel scripts in the client's voice
  Deliver : render markdown -> create_formatted_gdoc.py -> shared Google Doc

Apify tokens: primary APIFY_API_TOKEN (.env) + every apify-* token in
~/.claude.json, tried in order (quota fallback). Never printed.

Usage:
  python3 tools/youtube/creator_content_engine.py --smoke          # 1 channel + 1 account, no generate/deliver
  python3 tools/youtube/creator_content_engine.py                  # full run -> Google Doc
  python3 tools/youtube/creator_content_engine.py --per 8 --months 6
  flags: --yt-only --ig-only --no-enrich --no-deliver --per N --months M
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
TMP = ROOT / ".tmp" / "creator_content_engine"
sys.path.insert(0, str(Path(__file__).resolve().parent))

from competitors import CLIENT_COMPETITORS  # noqa: E402

# Everything below says "the client" rather than a name, and takes the real one from
# competitors.py. A name baked into a prompt is how one client's voice ends up in
# another client's scripts.
CLIENT = CLIENT_COMPETITORS.get("name") or "the client"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
ENRICH_MODEL = os.getenv("CONTENT_ENRICH_MODEL", "claude-opus-4-8")
YT_TRANSCRIPT_ACTOR = "topaz_sharingan/Youtube-Transcript-Scraper-1"
IG_ACTOR = "apify/instagram-scraper"  # legacy (caption-level only); reel actor below is preferred
IG_REEL_ACTOR = "apify/instagram-reel-scraper"  # built-in transcript + video URL + play counts
# The shared Google Doc the scripts get appended to. Per client, so it lives in .env:
# SCRIPTS_DOC_ID=<the doc id from its URL>. Unset means the run writes locally only.
SCRIPTS_DOC_ID = os.getenv("SCRIPTS_DOC_ID", "")


def log(msg: str) -> None:
    print(msg, flush=True)


# ── Apify (multi-token fallback, never printed) ──────────────────────────────

def load_apify_tokens() -> list[str]:
    """Every token in the shared Apify pool (.env pool + ~/.claude.json)."""
    from apify_pool import apify_tokens
    return apify_tokens()


def run_apify(actor: str, run_input: dict, tokens: list[str], timeout_secs: int = 600) -> list[dict]:
    """Run an Apify actor, trying each token until one returns items."""
    from apify_client import ApifyClient
    for i, tok in enumerate(tokens):
        try:
            log(f"  [apify] {actor} (token {i + 1}/{len(tokens)})...")
            client = ApifyClient(tok)
            run = client.actor(actor).call(run_input=run_input, timeout_secs=timeout_secs)
            if not run:
                continue
            ds = run.get("defaultDatasetId")
            if not ds:
                continue
            items = list(client.dataset(ds).iterate_items())
            if items:
                log(f"  [apify] got {len(items)} items")
                return items
            log("  [apify] 0 items, trying next token")
        except Exception as e:
            log(f"  [apify] token {i + 1} failed: {str(e)[:160]}")
    return []


# ── YouTube ──────────────────────────────────────────────────────────────────

YT_ID_RE = re.compile(r"(?:v=|/shorts/|/watch\?v=|youtu\.be/|/embed/)?([A-Za-z0-9_-]{11})")


def yt_video_id(url: str) -> str:
    if not url:
        return ""
    m = re.search(r"[?&]v=([A-Za-z0-9_-]{11})", url) or re.search(r"/([A-Za-z0-9_-]{11})(?:\?|$|/)", url)
    return m.group(1) if m else ""


def yt_list_channel(handle: str, scan: int) -> list[dict]:
    """Flat-list a channel's recent videos with view counts via yt-dlp (free)."""
    import yt_dlp
    url = f"https://www.youtube.com/@{handle}/videos"
    opts = {"quiet": True, "no_warnings": True, "extract_flat": "in_playlist",
            "skip_download": True, "ignoreerrors": True, "playlistend": scan}
    out: list[dict] = []
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        for e in (info or {}).get("entries", []) or []:
            if not e or not e.get("id"):
                continue
            out.append({
                "platform": "youtube",
                "channel": e.get("channel") or handle,
                "channel_handle": handle,
                "video_id": e.get("id"),
                "title": e.get("title") or "",
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                "views": e.get("view_count") or 0,
                "duration_secs": e.get("duration") or 0,
            })
    except Exception as e:
        log(f"  [yt] list error @{handle}: {str(e)[:160]}")
    return out


def yt_fill_dates(videos: list[dict]) -> None:
    """Flat extract omits upload_date; fetch it per top video so we can window-filter."""
    import yt_dlp
    opts = {"quiet": True, "no_warnings": True, "skip_download": True, "ignoreerrors": True}
    with yt_dlp.YoutubeDL(opts) as ydl:
        for v in videos:
            try:
                info = ydl.extract_info(f"https://www.youtube.com/watch?v={v['video_id']}", download=False)
                if info:
                    v["upload_date"] = (info.get("upload_date") or "")[:8]
                    v["views"] = info.get("view_count") or v["views"]
                    v["duration_secs"] = info.get("duration") or v["duration_secs"]
                    v["description"] = (info.get("description") or "")[:600]
            except Exception:
                v.setdefault("upload_date", "")


def fmt_dur(secs: int) -> str:
    secs = int(secs or 0)
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def extract_transcript(item: dict) -> str:
    for key in ("transcript", "text", "captionsText", "content"):
        v = item.get(key)
        if isinstance(v, str) and v.strip():
            return v.strip()
    caps = item.get("captions") or item.get("data") or item.get("subtitles")
    if isinstance(caps, list):
        parts = []
        for c in caps:
            if isinstance(c, dict):
                parts.append(c.get("text") or c.get("caption") or c.get("snippet") or "")
            elif isinstance(c, str):
                parts.append(c)
        joined = " ".join(p for p in parts if p).strip()
        if joined:
            return joined
    return ""


def yt_fetch_transcripts(videos: list[dict], tokens: list[str]) -> None:
    """Bulk-fetch transcripts for the given videos via the topaz Apify actor."""
    urls = [f"https://www.youtube.com/watch?v={v['video_id']}" for v in videos]
    if not urls:
        return
    items = run_apify(
        YT_TRANSCRIPT_ACTOR,
        {"startUrls": [{"url": u} for u in urls], "timestamps": False},
        tokens, timeout_secs=1800,
    )
    by_id: dict[str, str] = {}
    for it in items:
        vid = yt_video_id(it.get("url") or it.get("videoUrl") or it.get("video_url") or "") or it.get("videoId", "")
        txt = extract_transcript(it)
        if vid and txt:
            by_id[vid] = txt
    for v in videos:
        v["transcript"] = by_id.get(v["video_id"], "")


def fetch_youtube(handles: list[str], per: int, months: int, tokens: list[str]) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=months * 30)).strftime("%Y%m%d")
    picked: list[dict] = []
    for h in handles:
        log(f"[yt] @{h}")
        listed = yt_list_channel(h, scan=max(per * 4, 25))
        listed.sort(key=lambda v: v["views"], reverse=True)
        top = listed[:max(per * 2, per)]   # over-pick, then date-filter
        yt_fill_dates(top)
        inwin = [v for v in top if not v.get("upload_date") or v["upload_date"] >= cutoff]
        inwin.sort(key=lambda v: v["views"], reverse=True)
        chosen = inwin[:per]
        for v in chosen:
            v["duration_str"] = fmt_dur(v["duration_secs"])
        log(f"  picked {len(chosen)} (of {len(listed)} listed) by views in last {months}mo")
        picked.extend(chosen)
    if picked:
        log(f"[yt] fetching transcripts for {len(picked)} videos via Apify...")
        yt_fetch_transcripts(picked, tokens)
        ok = sum(1 for v in picked if v.get("transcript"))
        log(f"[yt] transcripts: {ok}/{len(picked)} ok (captions)")
        yt_groq_fallback(picked)
        ok2 = sum(1 for v in picked if v.get("transcript"))
        log(f"[yt] transcripts: {ok2}/{len(picked)} ok (after Groq fallback)")
    return picked


# ── Instagram ──────────────────────────────────────────────────────────────

def ig_visual_format(video_url: str) -> str:
    """Best-effort GPT-4o read of a reel's VISUAL format from one frame (talking head /
    text-overlay / B-roll / faceless voiceover / heavily-edited). '' if unavailable."""
    if not video_url:
        return ""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return ""
    try:
        from openai import OpenAI
    except Exception:
        return ""
    import base64
    mp4 = frame = ""
    try:
        r = httpx.get(video_url, timeout=60, follow_redirects=True)
        if r.status_code != 200 or not r.content:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(r.content)
            mp4 = tf.name
        frame = mp4 + ".jpg"
        subprocess.run(["ffmpeg", "-y", "-ss", "2", "-i", mp4, "-frames:v", "1", "-q:v", "3", frame],
                       capture_output=True, timeout=30)
        if not os.path.exists(frame):
            return ""
        with open(frame, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        client = OpenAI(api_key=key)
        resp = client.chat.completions.create(
            model="gpt-4o", max_tokens=90,
            messages=[{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                {"type": "text", "text": ("One sentence: the visual format of this Instagram reel "
                 "(talking head | talking head + B-roll | text-overlay | faceless voiceover | "
                 "vlog/handheld | heavily edited fast-cuts | lightly edited). Then 3-5 words on what's "
                 "distinctive: caption/subtitle style, background, on-screen text.")},
            ]}],
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        log(f"    [ig] visual-format error: {str(e)[:100]}")
        return ""
    finally:
        for p in (mp4, frame):
            try:
                if p:
                    os.unlink(p)
            except Exception:
                pass


def _groq_post(audio_path: str) -> str:
    """POST an audio file to Groq Whisper; return transcript text ('' on failure)."""
    if not GROQ_API_KEY:
        return ""
    for attempt in range(1, 4):
        try:
            with open(audio_path, "rb") as f:
                files = {"file": (os.path.basename(audio_path), f, "audio/mpeg")}
                data = {"model": GROQ_MODEL, "response_format": "text", "language": "en"}
                headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
                with httpx.Client(timeout=300) as c:
                    resp = c.post(GROQ_URL, headers=headers, data=data, files=files)
            if resp.status_code == 429:
                time.sleep(5 * attempt)
                continue
            if resp.status_code == 200:
                return (resp.text or "").strip()
            log(f"    groq HTTP {resp.status_code}: {resp.text[:120]}")
            return ""
        except Exception as e:
            log(f"    groq error: {str(e)[:120]}")
            time.sleep(2 * attempt)
    return ""


def _to_mono_mp3(src: str) -> str:
    """ffmpeg -> small mono 16k mp3 next to src; returns src unchanged if ffmpeg is missing."""
    out_mp3 = src + ".mp3"
    try:
        res = subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", "16000", "-q:a", "5", out_mp3],
            capture_output=True, timeout=180,
        )
        if res.returncode == 0 and os.path.exists(out_mp3):
            return out_mp3
    except Exception:
        pass
    return src


def groq_transcribe(video_url: str) -> str:
    """Download a reel and transcribe spoken audio with Groq Whisper (free)."""
    if not video_url or not GROQ_API_KEY:
        return ""
    try:
        r = httpx.get(video_url, timeout=90, follow_redirects=True)
        if r.status_code != 200 or not r.content:
            return ""
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            tf.write(r.content)
            mp4 = tf.name
    except Exception as e:
        log(f"    [ig] download fail: {str(e)[:120]}")
        return ""
    audio = _to_mono_mp3(mp4)
    text = _groq_post(audio)
    for p in {mp4, audio}:
        try:
            os.unlink(p)
        except Exception:
            pass
    return text


def yt_groq_fallback(videos: list[dict], max_videos: int = 12, max_minutes: int = 30) -> None:
    """For picked videos with no caption transcript, download audio + Groq transcribe.

    YouTube long-form usually has captions (the topaz actor gets those), but the
    occasional top performer (e.g. a re-uploaded talk) has none. This recovers them.
    """
    import yt_dlp
    targets = [v for v in videos
               if not v.get("transcript")
               and 0 < (v.get("duration_secs") or 0) <= max_minutes * 60][:max_videos]
    if not targets:
        return
    log(f"[yt] Groq fallback for {len(targets)} caption-less videos...")
    for v in targets:
        with tempfile.TemporaryDirectory() as td:
            opts = {"quiet": True, "no_warnings": True, "format": "bestaudio/best",
                    "outtmpl": os.path.join(td, "%(id)s.%(ext)s"),
                    "postprocessors": [{"key": "FFmpegExtractAudio",
                                        "preferredcodec": "mp3", "preferredquality": "5"}]}
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([f"https://www.youtube.com/watch?v={v['video_id']}"])
                mp3 = os.path.join(td, f"{v['video_id']}.mp3")
                if os.path.exists(mp3):
                    v["transcript"] = _groq_post(mp3)
                    log(f"  @{v['channel_handle']} {v['title'][:45]} -> {len(v['transcript'])}c")
            except Exception as e:
                log(f"  fallback fail {v['video_id']}: {str(e)[:120]}")


def fetch_instagram(usernames: list[str], per: int, months: int, tokens: list[str]) -> list[dict]:
    """Top reels per account via apify/instagram-reel-scraper: built-in spoken transcript +
    video URL + play counts. One actor run covers all accounts; then GPT-4o reads visual format."""
    items = run_apify(
        IG_REEL_ACTOR,
        {"username": usernames, "resultsLimit": max(per, 5),
         "onlyPostsNewerThan": f"{months} months", "skipPinnedPosts": True,
         "includeTranscript": True},
        tokens, timeout_secs=1800,
    )
    by_acct: dict[str, list[dict]] = {}
    for it in items:
        acct = (it.get("ownerUsername") or it.get("username") or "").lower().strip()
        ts = it.get("timestamp") or ""
        plays = it.get("videoPlayCount") or it.get("videoViewCount") or it.get("playCount") or 0
        likes = it.get("likesCount") or 0
        comments = it.get("commentsCount") or 0
        dur = int(it.get("videoDuration") or 0)
        sc = it.get("shortCode") or it.get("shortcode") or ""
        reel = {
            "platform": "instagram",
            "account": acct or "?",
            "caption": (it.get("caption") or "")[:2000],
            "transcript": (it.get("transcript") or "").strip(),
            "likes": likes,
            "comments": comments,
            "plays": plays,
            "engagement": plays or (likes + comments * 5),
            "type": "Reel",
            "duration_secs": dur,
            "duration_str": f"{dur}s",
            "video_url": it.get("videoUrl") or "",
            "shortcode": sc,
            "url": it.get("url") or (f"https://www.instagram.com/reel/{sc}/" if sc else ""),
            "post_date": ts[:10],
            "timestamp": ts,
            "visual_format": "",
        }
        by_acct.setdefault(reel["account"], []).append(reel)
    if not by_acct:
        log("[ig] reel scraper returned nothing")
        return []
    picked: list[dict] = []
    for acct, reels in by_acct.items():
        reels.sort(key=lambda r: r["engagement"], reverse=True)
        chosen = reels[:per]
        log(f"[ig] @{acct}: kept {len(chosen)}/{len(reels)} reels, "
            f"{sum(1 for r in chosen if r['transcript'])} w/ transcript")
        picked.extend(chosen)
    withvid = [r for r in picked if r["video_url"]]
    if withvid:
        log(f"[ig] reading visual format on {len(withvid)} reels (GPT-4o)...")
        for r in withvid:
            r["visual_format"] = ig_visual_format(r["video_url"])
    return picked


# ── Enrichment (one Claude call per platform: format / hook / topic) ─────────

def _anthropic():
    import anthropic
    return anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _parse_json_array(raw: str) -> list:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()
    return json.loads(raw)


def enrich_youtube(videos: list[dict]) -> None:
    if not videos:
        return
    blocks = []
    for i, v in enumerate(videos, 1):
        blocks.append(f"VIDEO {i}: \"{v['title']}\" [{v['channel']}, {v.get('duration_str','?')}, {v['views']:,} views]\n"
                      f"Transcript: {(v.get('transcript') or '(none)')[:900]}")
    prompt = (f"Analyze these {len(videos)} YouTube videos for a content strategist.\n\n"
              + "\n---\n".join(blocks)
              + f"\n\nFor EACH video return format_type, topic_category, editing_style, hook_style, "
              "visual_style (1 sentence), core_topic (5-8 words).\n"
              f"Return ONLY a JSON array of {len(videos)} objects with those keys.")
    try:
        resp = _anthropic().messages.create(model=ENRICH_MODEL, max_tokens=6000,
                                             messages=[{"role": "user", "content": prompt}])
        for i, a in enumerate(_parse_json_array(resp.content[0].text)):
            if i < len(videos):
                videos[i].update(a)
    except Exception as e:
        log(f"[yt] enrich error: {str(e)[:160]}")


def enrich_instagram(posts: list[dict]) -> None:
    if not posts:
        return
    blocks = []
    for i, p in enumerate(posts, 1):
        content = p.get("transcript") or p.get("caption", "")
        blocks.append(f"REEL {i}: @{p['account']} [{p['duration_str']}, {p['engagement']:,} eng]\n"
                      f"Content: {content[:800]}")
    prompt = (f"Analyze these {len(posts)} Instagram reels from business / personal-brand creators.\n"
              + "\n---\n".join(blocks)
              + f"\n\nFor EACH reel return hook_style, format, topic_category, script_structure "
              "(1-sentence flow e.g. 'bold hook -> 3 mistakes -> CTA'), core_topic (5-8 words), "
              "recreate_brief (2-sentence filming brief).\n"
              f"Return ONLY a JSON array of {len(posts)} objects with those keys.")
    try:
        resp = _anthropic().messages.create(model=ENRICH_MODEL, max_tokens=6000,
                                             messages=[{"role": "user", "content": prompt}])
        for i, a in enumerate(_parse_json_array(resp.content[0].text)):
            if i < len(posts):
                posts[i].update(a)
    except Exception as e:
        log(f"[ig] enrich error: {str(e)[:160]}")


# ── Markdown render + Google Doc delivery ────────────────────────────────────

def render_markdown(plan: dict, yt: list[dict], ig: list[dict]) -> str:
    today = plan.get("date", datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    L: list[str] = [f"# {CLIENT} — Weekly Content Scripts ({today})", ""]
    L.append("> Generated from competitor intelligence in the client's brand voice. "
             "Record straight off these. YouTube scripts first, then 14 reels (2/day).\n")

    L.append("## YouTube scripts\n")
    for i, idea in enumerate(plan.get("youtube_ideas", []), 1):
        L.append(f"### YT {i}. {idea.get('title','')}")
        L.append(f"**Angle:** {idea.get('angle','')}")
        L.append(f"**Format:** {idea.get('format_recommendation','')}")
        L.append(f"**Hook (first 20s):** {idea.get('hook','')}")
        L.append("\n**Full script:**\n")
        L.append(idea.get("full_script", ""))
        L.append("\n---\n")

    L.append("## Instagram reels (2 per day, 7 days)\n")
    for idea in plan.get("reel_ideas", []):
        L.append(f"### {idea.get('day','')} — {idea.get('title','')}")
        L.append(f"**Hook:** {idea.get('hook','')}  ·  **Format:** {idea.get('format','')}  ·  **Style:** {idea.get('hook_style','')}")
        L.append(f"**Filming brief:** {idea.get('filming_brief','')}")
        L.append("\n**Script:**\n")
        L.append(idea.get("full_script", ""))
        L.append("\n---\n")

    # Competitor intel appendix — what the scripts were built from.
    L.append("## Appendix — competitor intel this week\n")
    L.append("### Top YouTube videos analyzed\n")
    for v in sorted(yt, key=lambda x: x.get("views", 0), reverse=True):
        L.append(f"- **{v.get('views',0):,} views** · {v.get('channel','')} · \"{v.get('title','')}\" "
                 f"({v.get('hook_style','?')} hook · {v.get('format_type','?')}) — {v.get('url','')}")
    L.append("\n### Top Instagram reels analyzed\n")
    for p in sorted(ig, key=lambda x: x.get("engagement", 0), reverse=True):
        L.append(f"- **{p.get('engagement',0):,} eng** · @{p.get('account','')} · {p.get('core_topic', (p.get('caption','') or '')[:40])} "
                 f"({p.get('hook_style','?')} hook) — {p.get('url','')}")
    return "\n".join(L) + "\n"


def deliver_doc(md_path: Path, title: str) -> str:
    """Create a formatted, shared Google Doc from the markdown via create_formatted_gdoc.py."""
    res = subprocess.run(
        [sys.executable, str(Path(__file__).resolve().parent / "create_formatted_gdoc.py"), title, str(md_path)],
        capture_output=True, text=True,
    )
    out = (res.stdout or "") + (res.stderr or "")
    m = re.search(r"https://docs\.google\.com/document/d/[\w-]+/edit", out)
    if m:
        return m.group(0)
    log(out[-800:])
    return ""


def deliver_to_doc(md_path: Path, doc_id: str) -> str:
    """Append the rendered markdown into an EXISTING Google Doc's first tab. The service
    account can edit a Doc shared with it as editor, even though it cannot create one
    (no My-Drive quota). Reuses the proven markdown->Docs conversion."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    from create_formatted_gdoc import get_creds, get_first_tab
    from format_md_into_gdoc_tab import build_requests, convert_md
    from googleapiclient.discovery import build
    creds = get_creds()
    docs = build("docs", "v1", credentials=creds)
    text, ops = convert_md(md_path.read_text(encoding="utf-8"))
    tab_id, end_index = get_first_tab(docs, doc_id)
    # Replace prior content so each run leaves ONE clean copy (idempotent for weekly re-runs).
    if end_index and end_index > 2:
        try:
            docs.documents().batchUpdate(documentId=doc_id, body={"requests": [
                {"deleteContentRange": {"range": {"tabId": tab_id, "startIndex": 1, "endIndex": end_index - 1}}}
            ]}).execute()
            tab_id, end_index = get_first_tab(docs, doc_id)
        except Exception as e:
            log(f"[doc] wipe skipped ({str(e)[:120]}); appending instead")
    requests = build_requests(tab_id, text, ops, end_index)
    docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    return f"https://docs.google.com/document/d/{doc_id}/edit"


# ── Market-research brief + content ideas (the default deliverable) ──────────
# The flow: research competitors' top content -> show what is working -> propose
# ideas with strong titles -> he picks -> THEN we script. (We do NOT auto-script.)

def _load_brand_voice() -> str:
    p = ROOT / CLIENT_COMPETITORS.get("brand_voice_path", "knowledge/BRAND_VOICE.md")
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _parse_json_obj(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip().rstrip("```").strip()
    return json.loads(raw)


def _yt_research_ctx(videos: list[dict]) -> str:
    out = []
    for v in videos:
        out.append(
            f"[YT] {v.get('channel','?')} | {v.get('views',0):,} views | {v.get('duration_str','?')}\n"
            f"  Title: {v.get('title','')}\n"
            f"  Opens: {(v.get('transcript') or '')[:220]}\n"
            f"  Tags: {v.get('hook_style','?')} hook / {v.get('format_type','?')} / topic: {v.get('core_topic','?')}")
    return "\n".join(out) or "(none)"


def _ig_research_ctx(posts: list[dict]) -> str:
    out = []
    for p in posts:
        out.append(
            f"[IG] @{p.get('account','?')} | {p.get('engagement',0):,} plays | {p.get('duration_str','?')}\n"
            f"  Caption: {(p.get('caption') or '')[:150]}\n"
            f"  Spoken: {(p.get('transcript') or '')[:220]}\n"
            f"  Visual format: {p.get('visual_format','?')}\n"
            f"  Tags: {p.get('hook_style','?')} hook / topic: {p.get('core_topic','?')}")
    return "\n".join(out) or "(none)"


def generate_research_brief(yt: list[dict], ig: list[dict], idea_count: int = 15) -> dict:
    """One Opus pass: (1) market-research insights on what's working, (2) content IDEAS
    with strong client-voice titles. NO full scripts: a human picks ideas first, then they get scripted."""
    bv = _load_brand_voice()
    niche = CLIENT_COMPETITORS.get("niche", "")
    system = (
        f"You are a sharp short-form content strategist and market researcher for {CLIENT}.\n\n"
        "THE BRAND VOICE (titles and ideas MUST sound like them, and this document outranks every "
        "instruction below it):\n" + bv + "\n\n"
        f"Their niche and offer: {niche}\n\n"
        "You are analysing the TOP-PERFORMING recent content of their competitors and of viral "
        "reference creators. Do TWO things, in order:\n"
        "1) RESEARCH: what is actually WORKING. Recurring topics, hook styles, formats, and the "
        "specific top performers, with concrete numbers and creator names. This gets read by a human.\n"
        "2) IDEAS: propose content ideas, each a STRONG title plus a clear angle, grounded in a "
        "specific thing that worked for a competitor and tied to this client's own world and offer. "
        "DO NOT write full scripts.\n\n"
        "TITLE RULES: specific, curiosity-driving or a concrete bold claim, in their voice. "
        "BANNED: 'I grew to X followers', 'The secret to...', 'How I...', vague guru-bait, hype "
        "words. A weak generic title is a failed run."
    )
    user = (
        "TOP YOUTUBE PERFORMERS (direct competitors, mine topics and angles):\n"
        f"{_yt_research_ctx(yt)}\n\n"
        "TOP INSTAGRAM REELS (viral references — mine hooks + formats):\n"
        f"{_ig_research_ctx(ig)}\n\n"
        "Return ONLY JSON, no markdown:\n"
        "{\n"
        '  "research": {\n'
        '    "top_performers": [{"platform":"YouTube|Instagram","creator":"...","title_or_topic":"...","metric":"e.g. 220k views","why_it_worked":"1 sentence"}],\n'
        '    "winning_topics": ["concrete theme + why"],\n'
        '    "hook_patterns": ["hook style + a real example"],\n'
        '    "format_patterns": ["format/structure winning"],\n'
        '    "openings": ["gap or angle this client is uniquely placed to win"]\n'
        "  },\n"
        f'  "ideas": [{{"n":1,"title":"...","type":"YouTube|Reel","angle":"one line","based_on":"competitor signal it is built on","offer_tie":"how it leads toward their offer"}}]  // exactly {idea_count}, mixed, best title first\n'
        "}"
    )
    resp = _anthropic().messages.create(
        model=os.getenv("CONTENT_GEN_MODEL", "claude-opus-4-8"),
        max_tokens=12000, system=system,
        messages=[{"role": "user", "content": user}],
    )
    brief = _parse_json_obj(resp.content[0].text)
    brief["date"] = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    nideas = len(brief.get("ideas", []))
    log(f"[research] {len(brief.get('research',{}).get('top_performers',[]))} top performers analysed, {nideas} ideas")
    return brief


def render_research_md(brief: dict) -> str:
    r = brief.get("research", {})
    ideas = brief.get("ideas", [])
    today = brief.get("date", "")
    L: list[str] = [f"# {CLIENT} — Competitor Research + Content Ideas ({today})", ""]
    L.append("> Market research on competitors' top-performing content, then content ideas to choose from. "
             "Tell me which idea numbers to script and I'll write them in your voice.\n")
    L.append("## What's working right now\n")
    L.append("### Top performers analysed\n")
    for tp in r.get("top_performers", []):
        L.append(f"- **{tp.get('metric','')}** · {tp.get('platform','')} · {tp.get('creator','')} — "
                 f"\"{tp.get('title_or_topic','')}\" — {tp.get('why_it_worked','')}")
    for heading, key in [("Winning topics", "winning_topics"), ("Hook patterns", "hook_patterns"),
                         ("Format patterns", "format_patterns"), ("Openings", "openings")]:
        rows = r.get(key, [])
        if rows:
            L.append(f"\n### {heading}\n")
            for x in rows:
                L.append(f"- {x}")
    L.append("\n## Content ideas — pick the ones you want scripted\n")
    for idea in ideas:
        L.append(f"**{idea.get('n','')}. {idea.get('title','')}**  _({idea.get('type','')})_")
        L.append(f"- Angle: {idea.get('angle','')}")
        L.append(f"- Based on: {idea.get('based_on','')}")
        L.append(f"- Leads to: {idea.get('offer_tie','')}\n")
    return "\n".join(L) + "\n"


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=8, help="top-N videos/reels per account")
    ap.add_argument("--months", type=int, default=6, help="lookback window")
    ap.add_argument("--smoke", action="store_true", help="1 channel + 1 account, no generate/deliver")
    ap.add_argument("--yt-only", action="store_true")
    ap.add_argument("--ig-only", action="store_true")
    ap.add_argument("--no-enrich", action="store_true")
    ap.add_argument("--no-deliver", action="store_true")
    ap.add_argument("--reuse-yt", action="store_true", help="reuse cached youtube.json instead of re-scraping YouTube")
    ap.add_argument("--reuse-ig", action="store_true", help="reuse cached instagram.json instead of re-scraping Instagram")
    ap.add_argument("--scripts", action="store_true", help="Stage 2: write full scripts (default is Stage 1: research + ideas)")
    args = ap.parse_args()

    TMP.mkdir(parents=True, exist_ok=True)
    tokens = load_apify_tokens()
    if not tokens:
        log("ERROR: no Apify tokens found (APIFY_API_TOKEN / ~/.claude.json)")
        return 1
    log(f"Loaded {len(tokens)} Apify token(s)")

    yt_handles = list(CLIENT_COMPETITORS["youtube"])
    ig_users = list(CLIENT_COMPETITORS["instagram"])
    per = args.per
    if args.smoke:
        yt_handles, ig_users, per = yt_handles[:1], ig_users[:1], 3
        log(f"SMOKE: yt=@{yt_handles[0]} ig=@{ig_users[0]} per={per}")

    yt: list[dict] = []
    ig: list[dict] = []
    if not args.ig_only:
        cache = TMP / "youtube.json"
        if args.reuse_yt and cache.exists():
            yt = json.loads(cache.read_text())
            log(f"[yt] reusing {len(yt)} cached videos ({sum(1 for v in yt if v.get('transcript'))} w/ transcript)")
        else:
            yt = fetch_youtube(yt_handles, per, args.months, tokens)
            cache.write_text(json.dumps(yt, indent=2, ensure_ascii=False))
    if not args.yt_only:
        ig_cache = TMP / "instagram.json"
        if args.reuse_ig and ig_cache.exists():
            ig = json.loads(ig_cache.read_text())
            log(f"[ig] reusing {len(ig)} cached reels ({sum(1 for p in ig if p.get('transcript'))} w/ transcript)")
        else:
            ig = fetch_instagram(ig_users, per, args.months, tokens)
            ig_cache.write_text(json.dumps(ig, indent=2, ensure_ascii=False))

    log(f"\n=== Fetched: {len(yt)} YT videos ({sum(1 for v in yt if v.get('transcript'))} w/ transcript), "
        f"{len(ig)} IG reels ({sum(1 for p in ig if p.get('transcript'))} w/ transcript) ===")

    if args.smoke:
        log("SMOKE done, inspect .tmp/creator_content_engine/*.json")
        for v in yt:
            log(f"  YT {v['views']:,}v {v.get('title','')[:55]} | transcript {len(v.get('transcript',''))}c")
        for p in ig:
            log(f"  IG {p['engagement']:,}e @{p['account']} {p['duration_str']} | transcript {len(p.get('transcript',''))}c")
        return 0

    # Feed the generator the strongest performers only (keeps the prompt focused
    # on what actually worked, not every scraped item).
    yt_top = sorted(yt, key=lambda v: v.get("views", 0), reverse=True)[:18]
    ig_top = sorted(ig, key=lambda p: p.get("engagement", 0), reverse=True)[:18]

    # Enrich only the top performers (small batch -> no JSON truncation). Mutates the
    # same dicts held in yt/ig, so the saved json carries the tags too.
    if not args.no_enrich:
        log("[enrich] tagging format/hook/topic on top performers...")
        enrich_youtube(yt_top)
        enrich_instagram(ig_top)
        (TMP / "youtube.json").write_text(json.dumps(yt, indent=2, ensure_ascii=False))
        (TMP / "instagram.json").write_text(json.dumps(ig, indent=2, ensure_ascii=False))

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    plan = None
    if args.scripts:
        # Stage 2: write full scripts (run once the ideas have been picked).
        from content_plan_generator import generate_content_plan
        plan = generate_content_plan(
            yt_top, ig_top,
            brand_voice_path=CLIENT_COMPETITORS.get("brand_voice_path", "knowledge/BRAND_VOICE.md"),
            youtube_count=CLIENT_COMPETITORS.get("youtube_videos_per_week", 2),
            reels_count=CLIENT_COMPETITORS.get("reels_per_week", 14),
            niche=CLIENT_COMPETITORS.get("niche", ""),
        )
        (TMP / "plan.json").write_text(json.dumps(plan, indent=2, ensure_ascii=False))
        md = render_markdown(plan, yt_top, ig_top)
        md_path = TMP / f"scripts_{stamp}.md"
    else:
        # Stage 1 (DEFAULT): competitor market research + content ideas to pick from.
        brief = generate_research_brief(yt_top, ig_top)
        (TMP / "research_brief.json").write_text(json.dumps(brief, indent=2, ensure_ascii=False))
        md = render_research_md(brief)
        md_path = TMP / f"research_{stamp}.md"
    md_path.write_text(md, encoding="utf-8")
    log(f"[render] markdown -> {md_path}")

    if args.no_deliver:
        log(f"Skipping delivery (--no-deliver). Markdown ready at {md_path}")
        return 0

    # Primary: append into the shared scripts Doc (the service account needs editor access). Then fall
    # back to a fresh Doc (GDOC_PARENT_FOLDER_ID), the content Sheet, and local markdown.
    if SCRIPTS_DOC_ID:
        try:
            url = deliver_to_doc(md_path, SCRIPTS_DOC_ID)
            log(f"\nDONE. Written to Google Doc:\n{url}")
            return 0
        except Exception as e:
            log(f"Doc write failed ({SCRIPTS_DOC_ID}): {str(e)[:200]}")
    if os.getenv("GDOC_PARENT_FOLDER_ID"):
        url = deliver_doc(md_path, f"{CLIENT} — Content Scripts {stamp}")
        if url:
            log(f"\nDONE. Google Doc:\n{url}")
            return 0
    sheet_id = os.getenv("GOOGLE_SHEETS_ID")
    if sheet_id and plan:
        try:
            from content_plan_generator import upload_to_sheets
            upload_to_sheets(plan, sheet_id)
            log(f"\nDONE (fallback -> Sheet):\nhttps://docs.google.com/spreadsheets/d/{sheet_id}/edit")
        except Exception as e:
            log(f"Sheet delivery failed: {str(e)[:160]}")
    log(f"\nMarkdown (always available): {md_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
