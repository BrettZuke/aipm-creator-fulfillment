#!/usr/bin/env python3
"""
Pull a YouTube channel's recent videos + transcripts using yt-dlp + youtube-transcript-api.
Free (no API quota). Outputs to .tmp/<username>/youtube_*.json.

Usage:
    python3 tools/scrape_youtube_creator.py --channel @theirhandle \\
        --max-videos 50 --transcripts 15
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)


REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_ROOT = REPO_ROOT / ".tmp"


def fetch_channel_videos(channel_url: str, max_videos: int) -> list[dict]:
    """Pull video metadata for a channel (no download). Uses extract_flat for speed.

    A Shorts-only channel has no /videos tab at all and yt-dlp raises rather than returning an
    empty list, so /shorts is tried next. Those channels are the most relevant ones to study for
    short-form, so treating the failure as "no content" would skip exactly the wrong accounts.
    """
    opts = {
        "quiet": True,
        "extract_flat": True,
        "playlist_items": f"1-{max_videos}",
    }
    last: Exception | None = None
    for tab in ("/videos", "/shorts", ""):
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"{channel_url}{tab}", download=False)
            entries = [e for e in (info.get("entries") or []) if e]
            # The bare channel URL returns tab playlists rather than videos on some channels;
            # flatten one level so those still yield entries.
            if entries and entries[0].get("_type") == "playlist":
                entries = [e for p in entries for e in (p.get("entries") or []) if e]
            if entries:
                if tab != "/videos":
                    print(f"  (no {'videos' if tab else 'videos or shorts'} tab, "
                          f"used {tab or 'the channel page'})")
                return entries[:max_videos]
        except Exception as e:  # noqa: BLE001
            last = e
    if last:
        print(f"  could not list videos: {str(last)[:120]}", file=sys.stderr)
    return []


def hydrate_video(video_id: str) -> dict:
    """Full metadata for a single video (views, likes, description, duration)."""
    opts = {"quiet": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
        return {
            "id": info.get("id"),
            "title": info.get("title"),
            "description": info.get("description"),
            "view_count": info.get("view_count"),
            "like_count": info.get("like_count"),
            "comment_count": info.get("comment_count"),
            "duration_seconds": info.get("duration"),
            "upload_date": info.get("upload_date"),
            "tags": info.get("tags") or [],
            "categories": info.get("categories") or [],
            "channel": info.get("channel"),
            "channel_url": info.get("channel_url"),
            "uploader": info.get("uploader"),
            "thumbnail": info.get("thumbnail"),
            "webpage_url": info.get("webpage_url"),
        }
    except Exception as e:
        return {"id": video_id, "error": str(e)[:200]}


def fetch_transcript(video_id: str) -> str | None:
    try:
        items = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB"])
        return " ".join(it["text"] for it in items)
    except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
        return None
    except Exception as e:
        print(f"  [transcript {video_id}] {str(e)[:120]}", file=sys.stderr)
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--channel", required=True, help="YouTube channel handle, e.g. @theirhandle")
    parser.add_argument("--max-videos", type=int, default=50)
    parser.add_argument("--transcripts", type=int, default=15, help="Top N by views to transcribe")
    parser.add_argument("--username", default=None, help="Output folder name (defaults to channel)")
    args = parser.parse_args()

    raw = args.channel.strip()
    if raw.startswith("http") or "/channel/" in raw or raw.startswith("UC"):
        channel_url = raw if raw.startswith("http") else f"https://www.youtube.com/channel/{raw}"
        handle = args.username or raw.rstrip("/").split("/")[-1]
    else:
        handle = raw.lstrip("@")
        channel_url = f"https://www.youtube.com/@{handle}"
    folder = args.username or handle
    out_dir = TMP_ROOT / folder
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/3] Fetching channel video list (up to {args.max_videos}) from {channel_url} ...")
    flat = fetch_channel_videos(channel_url, args.max_videos)
    print(f"  Found {len(flat)} videos")

    print(f"\n[2/3] Hydrating each video with full metadata...")
    hydrated: list[dict] = []
    blocked = 0
    for i, e in enumerate(flat, 1):
        vid = e.get("id")
        if not vid:
            continue
        h = hydrate_video(vid)
        # YouTube rate limits per-video hydration ("Sign in to confirm you're not a bot") long
        # before it limits the channel listing, and the listing already carries id, title, view
        # count and thumbnail. Falling back to it keeps a blocked run useful instead of writing
        # a file full of error records.
        if h.get("view_count") is None and e.get("view_count") is not None:
            h = {
                "id": vid,
                "title": e.get("title"),
                "view_count": e.get("view_count"),
                "thumbnail": (e.get("thumbnails") or [{}])[-1].get("url"),
                "webpage_url": e.get("url") or f"https://www.youtube.com/watch?v={vid}",
                "partial": "from channel listing, hydration was rate limited",
            }
            blocked += 1
        hydrated.append(h)
        if i % 5 == 0 or i == len(flat):
            print(f"  {i}/{len(flat)} hydrated")
    if blocked:
        print(f"  {blocked} of {len(hydrated)} fell back to listing data (YouTube rate limited)")
    # YouTube IP-blocks hydration intermittently ("Sign in to confirm you're not a bot"), and a
    # blocked run produces a full list of {id, error} records. Writing that over a good file
    # destroys real data and looks like success, so a run that hydrated nothing keeps what is
    # already on disk. Re-running a channel is meant to be safe.
    usable = [v for v in hydrated if v.get("view_count") is not None]
    videos_path = out_dir / "youtube_videos.json"
    if not usable and videos_path.exists():
        existing = json.loads(videos_path.read_text())
        if any(v.get("view_count") is not None for v in existing):
            print(f"  hydration was blocked ({len(hydrated)} errors), keeping the "
                  f"{len(existing)} videos already saved")
            hydrated = existing
        else:
            videos_path.write_text(json.dumps(hydrated, indent=2, default=str))
    else:
        videos_path.write_text(json.dumps(hydrated, indent=2, default=str))
        print(f"  Saved youtube_videos.json ({len(hydrated)} videos, {len(usable)} with metadata)")
    if not usable:
        print("  WARNING: no video metadata this run, YouTube is rate limiting. "
              "Transcripts will be skipped; re-run later.", file=sys.stderr)

    valid = [v for v in hydrated if v.get("view_count") is not None]
    valid.sort(key=lambda v: v.get("view_count") or 0, reverse=True)
    top = valid[: args.transcripts]

    tpath = out_dir / "youtube_transcripts.json"
    if not top and tpath.exists():
        # Nothing to select from, so leave whatever the Apify backfill has already filled in.
        print("\n[3/3] No metadata to rank, keeping the existing transcripts file")
        print(f"\nDone. Output in {out_dir}/")
        return 0

    print(f"\n[3/3] Pulling transcripts on top {len(top)} by views...")
    transcripts: list[dict] = []
    for i, v in enumerate(top, 1):
        text = fetch_transcript(v["id"])
        transcripts.append(
            {
                "id": v["id"],
                "title": v["title"],
                "view_count": v["view_count"],
                "upload_date": v.get("upload_date"),
                "duration_seconds": v.get("duration_seconds"),
                "transcript": text,
                "transcript_length": len(text) if text else 0,
            }
        )
        status = f"{len(text)} chars" if text else "no transcript"
        print(f"  {i:>2}. {v['title'][:60]:<60} | {v['view_count']:>9,} views | {status}")
    (out_dir / "youtube_transcripts.json").write_text(json.dumps(transcripts, indent=2, default=str))
    print(f"\n  Saved youtube_transcripts.json")
    print(f"\nDone. Output in .tmp/{folder}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
