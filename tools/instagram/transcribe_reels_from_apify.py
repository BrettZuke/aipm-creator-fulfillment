#!/usr/bin/env python3
"""Transcribe a creator's Instagram reels from an Apify reel-scraper dataset.

Why this exists: Dan's voice was built from his WRITTEN material (emails, the ebook, the brand
voice doc) and the scripts that came out read like essays. "You do not lack capital" is a sentence
nobody says out loud. Reels are spoken, and how he actually talks on camera only exists in the
audio, so it has to be pulled out of the audio.

Cost: the Apify scrape is the only paid part and it is fractions of a cent per reel. Transcription
runs on Groq's FREE whisper-large-v3-turbo, the same free route the YouTube pipeline already uses,
so a few hundred reels cost nothing to transcribe. Never route this at a paid transcription API.

Usage:
    python3 tools/instagram/transcribe_reels_from_apify.py --dataset <id> --out .tmp/dan_reels_voice
    python3 tools/instagram/transcribe_reels_from_apify.py --dataset <id> --out DIR --limit 120
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = "whisper-large-v3-turbo"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def env_value(key: str) -> str:
    for line in (ROOT / ".env").read_text().split("\n"):
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise SystemExit(f"{key} not found in .env")


def fetch_dataset(dataset_id: str) -> list[dict]:
    token = env_value("APIFY_API_TOKEN")
    url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={token}&clean=true"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read())


def audio_from(video_url: str) -> bytes | None:
    """Reel video to 16k mono audio, entirely in temp files.

    ffmpeg reads the URL directly rather than downloading first: these are short clips and one
    pass is both faster and leaves nothing on disk to clean up.
    """
    with tempfile.NamedTemporaryFile(suffix=".m4a", delete=True) as out:
        cmd = ["ffmpeg", "-y", "-loglevel", "error", "-user_agent", UA,
               "-i", video_url, "-vn", "-ac", "1", "-ar", "16000", "-b:a", "48k", out.name]
        if subprocess.run(cmd, capture_output=True, timeout=180).returncode != 0:
            return None
        data = Path(out.name).read_bytes()
    return data or None


def groq_transcribe(audio: bytes, key: str) -> str | None:
    import httpx
    for attempt in range(3):
        try:
            files = {"file": ("reel.m4a", audio, "audio/m4a")}
            data = {"model": GROQ_MODEL, "response_format": "text", "language": "en"}
            with httpx.Client(timeout=180) as c:
                r = c.post(GROQ_URL, headers={"Authorization": f"Bearer {key}"},
                           data=data, files=files)
            if r.status_code == 200:
                return r.text.strip()
            # 429 here is a per-minute window on a free tier, so it is worth one wait.
            if r.status_code == 429 and attempt < 2:
                import time
                time.sleep(20)
                continue
            return None
        except Exception:
            if attempt == 2:
                return None
    return None


def one(item: dict, key: str) -> dict | None:
    url = item.get("videoUrl")
    if not url:
        return None
    audio = audio_from(url)
    if not audio:
        return None
    text = groq_transcribe(audio, key)
    if not text:
        return None
    return {
        "shortCode": item.get("shortCode"),
        "url": item.get("url"),
        "views": item.get("videoPlayCount") or item.get("videoViewCount") or 0,
        "likes": item.get("likesCount") or 0,
        "comments": item.get("commentsCount") or 0,
        "duration": item.get("videoDuration"),
        "timestamp": item.get("timestamp"),
        "caption": (item.get("caption") or "").strip(),
        "transcript": text,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0, help="0 means every reel in the dataset")
    ap.add_argument("--workers", type=int, default=4,
                    help="kept low on purpose: Groq's free tier is per-minute limited and "
                         "hammering it turns a free run into a failed one")
    args = ap.parse_args()

    key = env_value("GROQ_API_KEY")
    items = [i for i in fetch_dataset(args.dataset) if i.get("videoUrl")]
    # Best performers first, so a truncated run still captures the voice that actually works.
    items.sort(key=lambda i: -(i.get("videoPlayCount") or i.get("videoViewCount") or 0))
    if args.limit:
        items = items[: args.limit]
    print(f"{len(items)} reels with video to transcribe")

    out_dir = Path(args.out)
    if not out_dir.is_absolute():
        out_dir = ROOT / out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    done: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(one, i, key): i for i in items}
        for n, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res:
                done.append(res)
            if n % 10 == 0 or n == len(items):
                print(f"  {n}/{len(items)} attempted, {len(done)} transcribed", flush=True)

    done.sort(key=lambda r: -r["views"])
    (out_dir / "reels_transcribed.json").write_text(json.dumps(done, indent=1))
    print(f"wrote {len(done)} transcripts to {out_dir/'reels_transcribed.json'}")
    if done:
        med = sorted(r["views"] for r in done)[len(done) // 2]
        print(f"median views {med:,}, top {done[0]['views']:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
