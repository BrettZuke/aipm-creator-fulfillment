#!/usr/bin/env python3
"""Backfill YouTube transcripts via Apify when the free path is blocked.

youtube-transcript-api and yt-dlp both get IP-blocked by YouTube on bigger pulls
(symptom: every video returns "no transcript", or yt-dlp saves records shaped
{"id": ..., "error": "This video is not available"}). This routes the SAME video
ids through the topaz Apify actor, which uses its own proxy pool.

Reads  .tmp/<slug>/youtube_transcripts.json  (needs an "id" per record)
Writes the same file back with "transcript" and "transcript_length" filled.

Reuses the token-rotation and actor plumbing from creator_content_engine.

Cost: roughly $0.0025 per actor start plus $0.01 per transcript returned.

Usage:
    python3 tools/youtube/apify_yt_transcripts.py toponepercentt longevitypenguin
    python3 tools/youtube/apify_yt_transcripts.py --all
    python3 tools/youtube/apify_yt_transcripts.py --all --chunk 25
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
sys.path.insert(0, str(Path(__file__).resolve().parent))

from creator_content_engine import load_apify_tokens, yt_fetch_transcripts  # noqa: E402

TMP = ROOT / ".tmp"


def creator_dirs() -> list[str]:
    return sorted(
        p.name for p in TMP.iterdir()
        if p.is_dir() and (p / "youtube_transcripts.json").exists()
    )


def backfill(slug: str, tokens: list[str], chunk: int) -> tuple[int, int]:
    path = TMP / slug / "youtube_transcripts.json"
    if not path.exists():
        print(f"[{slug}] no youtube_transcripts.json, skipping")
        return (0, 0)

    records = json.loads(path.read_text())
    missing = [r for r in records if r.get("id") and not (r.get("transcript") or "").strip()]
    if not missing:
        print(f"[{slug}] already complete ({len(records)} records)")
        return (len(records), len(records))

    print(f"[{slug}] {len(missing)} of {len(records)} missing, fetching via Apify...")
    filled: dict[str, str] = {}
    for i in range(0, len(missing), chunk):
        batch = missing[i : i + chunk]
        videos = [{"video_id": r["id"]} for r in batch]
        try:
            yt_fetch_transcripts(videos, tokens)
        except Exception as exc:  # a dead batch must not kill the rest
            print(f"  batch {i // chunk + 1}: FAILED ({type(exc).__name__}: {exc})")
            continue
        got = 0
        for v in videos:
            txt = (v.get("transcript") or "").strip()
            if txt:
                filled[v["video_id"]] = txt
                got += 1
        print(f"  batch {i // chunk + 1}: {got}/{len(batch)} transcripts")

    for r in records:
        txt = filled.get(r.get("id", ""))
        if txt:
            r["transcript"] = txt
            r["transcript_length"] = len(txt)

    path.write_text(json.dumps(records, indent=2))
    have = sum(1 for r in records if (r.get("transcript") or "").strip())
    print(f"[{slug}] now {have}/{len(records)} with text")
    return (have, len(records))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="*", help="creator folder names under .tmp/")
    ap.add_argument("--all", action="store_true", help="every .tmp dir with a transcripts file")
    ap.add_argument("--chunk", type=int, default=25, help="videos per actor run")
    args = ap.parse_args()

    slugs = creator_dirs() if args.all else args.slugs
    if not slugs:
        print(__doc__)
        return 1

    tokens = load_apify_tokens()
    if not tokens:
        print("No Apify tokens found.")
        return 2
    print(f"Loaded {len(tokens)} Apify tokens.\n")

    total_have = total_all = 0
    for slug in slugs:
        have, all_n = backfill(slug, tokens, args.chunk)
        total_have += have
        total_all += all_n
        print()

    print(f"TOTAL: {total_have}/{total_all} videos have transcript text")
    return 0


if __name__ == "__main__":
    sys.exit(main())
