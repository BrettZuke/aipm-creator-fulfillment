"""Scrape last 12 months of YouTube content for 4 competitor creators.

Uses yt-dlp (free) for metadata and youtube-transcript-api (free) for transcripts.
No Apify credits consumed in this phase.

Saves to .tmp/<creator_slug>/ with full transcripts so we can analyze what they
teach word-for-word.

Run:
    python3 tools/competitor-intel/scrape_competitors_4ch.py
"""
from __future__ import annotations

import json
import re
import sys
import time
import traceback
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yt_dlp
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    NoTranscriptFound,
    TranscriptsDisabled,
)

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
TMP = ROOT / ".tmp"
LOOKBACK_DAYS = 365  # 12 months


@dataclass(frozen=True)
class Creator:
    slug: str
    handle: str
    display_name: str


# The four channels to study, from phase 2. Slug names the output folder, handle is the
# YouTube handle including the @, display name is what appears in the report.
CREATORS: tuple[Creator, ...] = (
    # Creator("their_slug", "@TheirChannelHandle", "Their Name"),
)


def safe_slug(text: str) -> str:
    """Filename-safe slug."""
    s = re.sub(r"[^A-Za-z0-9_-]+", "_", text or "")
    return s.strip("_")[:120]


def parse_upload_date(date_str: str | int | None) -> datetime | None:
    if date_str is None:
        return None
    s = str(date_str)
    if len(s) == 8 and s.isdigit():
        try:
            return datetime.strptime(s, "%Y%m%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def fetch_channel_videos_flat(channel_url: str, log) -> list[dict]:
    """Fast, flat extract of all videos in the channel's videos tab.

    Returns minimal metadata (id, title, url). Doesn't fetch view counts or
    upload dates yet — we do that selectively to avoid 500+ network roundtrips.
    """
    log(f"  flat-extract {channel_url}")
    ydl_opts = {
        "extract_flat": "in_playlist",
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(channel_url, download=False)
    if not info:
        return []
    entries = info.get("entries") or []
    out: list[dict] = []
    for e in entries:
        if not e:
            continue
        out.append(
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "url": e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}",
                "duration": e.get("duration"),
                "view_count": e.get("view_count"),
                "_flat": True,
            }
        )
    return out


def fetch_video_detail(video_url: str, log) -> dict | None:
    ydl_opts = {
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
        "no_warnings": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=False)
    except Exception as exc:  # pragma: no cover - network
        log(f"    detail-fail {video_url} :: {exc}")
        return None
    if not info:
        return None
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "url": info.get("webpage_url") or video_url,
        "description": info.get("description"),
        "upload_date": info.get("upload_date"),
        "duration": info.get("duration"),
        "view_count": info.get("view_count"),
        "like_count": info.get("like_count"),
        "comment_count": info.get("comment_count"),
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "channel_url": info.get("channel_url"),
        "tags": info.get("tags"),
        "categories": info.get("categories"),
        "thumbnail": info.get("thumbnail"),
        "live_status": info.get("live_status"),
        "is_short": (info.get("duration") or 0) < 90,
    }


def fetch_transcript(video_id: str) -> str:
    if not video_id:
        return ""
    api = YouTubeTranscriptApi()
    try:
        result = api.fetch(video_id, languages=["en", "en-GB", "en-US"])
        return " ".join(s.text for s in result).strip()
    except (NoTranscriptFound, TranscriptsDisabled):
        return ""
    except Exception:
        return ""


def fetch_channel_info(channel_url: str, log) -> dict | None:
    log(f"  channel-info {channel_url}")
    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "skip_download": True,
        "ignoreerrors": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
    except Exception as exc:  # pragma: no cover - network
        log(f"    channel-info fail :: {exc}")
        return None
    if not info:
        return None
    return {
        "channel": info.get("channel"),
        "channel_id": info.get("channel_id"),
        "channel_url": info.get("channel_url") or info.get("webpage_url"),
        "uploader": info.get("uploader"),
        "uploader_id": info.get("uploader_id"),
        "description": info.get("description"),
        "channel_follower_count": info.get("channel_follower_count"),
        "tags": info.get("tags"),
    }


def scrape_creator(c: Creator) -> dict:
    out_dir = TMP / c.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "scrape_log.txt"

    def log(line: str) -> None:
        stamped = f"[{datetime.now().strftime('%H:%M:%S')}] {line}"
        print(stamped)
        with log_path.open("a") as f:
            f.write(stamped + "\n")

    log(f"=== START {c.display_name} ({c.handle}) ===")
    summary: dict = {
        "slug": c.slug,
        "handle": c.handle,
        "display_name": c.display_name,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        channel_url_videos = f"https://www.youtube.com/{c.handle}/videos"
        channel_url_root = f"https://www.youtube.com/{c.handle}"

        # 1. Channel-level info
        channel_info = fetch_channel_info(channel_url_root, log)
        if channel_info:
            (out_dir / "channel_info.json").write_text(
                json.dumps(channel_info, indent=2, ensure_ascii=False)
            )
            log(f"  saved channel_info.json (subs={channel_info.get('channel_follower_count')})")

        # 2. Flat-extract all videos
        flat_videos = fetch_channel_videos_flat(channel_url_videos, log)
        log(f"  flat: {len(flat_videos)} videos")
        if not flat_videos:
            summary["error"] = "no videos in flat extract"
            return summary

        (out_dir / "videos_flat.json").write_text(
            json.dumps(flat_videos, indent=2, ensure_ascii=False)
        )

        # 3. Fetch detailed metadata for each video (gives us upload_date)
        log("  detail-extracting per video (this is the slow bit)...")
        detailed: list[dict] = []
        for i, fv in enumerate(flat_videos):
            url = fv["url"]
            d = fetch_video_detail(url, log)
            if d:
                detailed.append(d)
            if (i + 1) % 25 == 0:
                log(f"    {i + 1}/{len(flat_videos)} done")
        log(f"  detail: {len(detailed)} videos")

        # 4. Filter to last 12 months
        cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
        recent: list[dict] = []
        for d in detailed:
            ud = parse_upload_date(d.get("upload_date"))
            if ud and ud >= cutoff:
                recent.append(d)
        log(f"  in-window (last {LOOKBACK_DAYS}d): {len(recent)} videos")

        (out_dir / "videos_meta.json").write_text(
            json.dumps(detailed, indent=2, ensure_ascii=False)
        )
        (out_dir / "videos_meta_12mo.json").write_text(
            json.dumps(recent, indent=2, ensure_ascii=False)
        )

        # 5. Fetch transcripts for the 12-month window
        transcripts_dir = out_dir / "transcripts"
        transcripts_dir.mkdir(exist_ok=True)
        videos_txt_dir = out_dir / "videos_txt"
        videos_txt_dir.mkdir(exist_ok=True)

        transcript_index: list[dict] = []
        ok = 0
        miss = 0
        log("  pulling transcripts...")
        for i, v in enumerate(recent):
            vid = v.get("id")
            if not vid:
                continue
            txt = fetch_transcript(vid)
            if txt:
                ok += 1
                (transcripts_dir / f"{vid}.txt").write_text(txt)
            else:
                miss += 1

            ud_str = (v.get("upload_date") or "00000000")[:8]
            tslug = safe_slug(v.get("title") or "untitled")
            combined = videos_txt_dir / f"{ud_str}__{vid}__{tslug}.txt"
            combined.write_text(
                "\n".join(
                    [
                        f"TITLE: {v.get('title')}",
                        f"URL: {v.get('url')}",
                        f"DATE: {ud_str}",
                        f"DURATION (s): {v.get('duration')}",
                        f"VIEWS: {v.get('view_count')}",
                        f"LIKES: {v.get('like_count')}",
                        f"COMMENTS: {v.get('comment_count')}",
                        "",
                        "=== DESCRIPTION ===",
                        v.get("description") or "(none)",
                        "",
                        "=== TRANSCRIPT ===",
                        txt or "(no transcript available)",
                    ]
                )
            )
            transcript_index.append(
                {
                    "id": vid,
                    "title": v.get("title"),
                    "url": v.get("url"),
                    "upload_date": ud_str,
                    "duration": v.get("duration"),
                    "view_count": v.get("view_count"),
                    "transcript_len": len(txt) if txt else 0,
                    "has_transcript": bool(txt),
                }
            )

            if (i + 1) % 20 == 0:
                log(f"    {i + 1}/{len(recent)} transcripts done (ok={ok} miss={miss})")
            # Light rate limiting to avoid YT throttling
            time.sleep(0.4)

        (out_dir / "transcripts_index.json").write_text(
            json.dumps(transcript_index, indent=2, ensure_ascii=False)
        )

        summary.update(
            {
                "channel_subs": (channel_info or {}).get("channel_follower_count"),
                "total_videos_flat": len(flat_videos),
                "total_videos_detail": len(detailed),
                "videos_in_window": len(recent),
                "transcripts_ok": ok,
                "transcripts_missing": miss,
            }
        )
        log(f"=== DONE {c.display_name} ===")
        return summary
    except Exception as exc:
        log(f"  FATAL :: {exc}")
        log(traceback.format_exc())
        summary["error"] = str(exc)
        return summary


def main() -> int:
    TMP.mkdir(exist_ok=True)
    summary_path = TMP / "competitors_scrape_summary.json"
    all_summaries: list[dict] = []
    for c in CREATORS:
        s = scrape_creator(c)
        all_summaries.append(s)
        summary_path.write_text(json.dumps(all_summaries, indent=2, ensure_ascii=False))

    print("\n\n=== ALL DONE ===")
    print(json.dumps(all_summaries, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
