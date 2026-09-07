#!/usr/bin/env python3
"""
Download a creator's IG reels, extract audio, transcribe with OpenAI Whisper.

Reads posts JSON, finds posts with videoUrl, downloads in parallel, extracts
audio with ffmpeg, sends each to whisper-1, and saves a transcript per post.

Usage:
    python3 tools/whisper_creator_reels.py --posts .tmp/theirhandle/posts_deep.json \\
        --out-dir .tmp/theirhandle/reel_transcripts \\
        --workers 6
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Read .env manually (avoid dotenv pkg quirks in scripts run from various cwd)
REPO_ROOT = Path(__file__).resolve().parent.parent


def load_openai_key() -> str | None:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().split("\n"):
            line = line.strip()
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENAI_API_KEY")


OPENAI_KEY = load_openai_key()
if not OPENAI_KEY:
    print("Error: OPENAI_API_KEY not found in .env or environment", file=sys.stderr)
    sys.exit(1)


def download_video(url: str, dst: Path) -> bool:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "*/*",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as r, open(dst, "wb") as f:
            while True:
                chunk = r.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        return dst.stat().st_size > 1024
    except Exception as e:
        print(f"  [download fail] {str(e)[:120]}", file=sys.stderr)
        return False


def extract_audio(mp4: Path, mp3: Path) -> bool:
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(mp4),
        "-vn", "-ac", "1", "-ar", "16000", "-b:a", "32k",
        str(mp3),
    ]
    try:
        subprocess.run(cmd, check=True, timeout=60)
        return mp3.exists() and mp3.stat().st_size > 256
    except Exception as e:
        print(f"  [ffmpeg fail] {str(e)[:120]}", file=sys.stderr)
        return False


def whisper_transcribe(audio: Path) -> dict | None:
    """POST to OpenAI Whisper-1 directly (no SDK dependency)."""
    boundary = "----WhisperBoundary7MA4YWxkTrZu0gW"
    body = bytearray()
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="model"\r\n\r\n'
    body += b"whisper-1\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="response_format"\r\n\r\n'
    body += b"verbose_json\r\n"
    body += f"--{boundary}\r\n".encode()
    body += b'Content-Disposition: form-data; name="language"\r\n\r\n'
    body += b"en\r\n"
    body += f"--{boundary}\r\n".encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{audio.name}"\r\n'.encode()
    body += b"Content-Type: audio/mpeg\r\n\r\n"
    body += audio.read_bytes()
    body += f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        "https://api.openai.com/v1/audio/transcriptions",
        data=bytes(body),
        headers={
            "Authorization": f"Bearer {OPENAI_KEY}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(r.read())
    except Exception as e:
        print(f"  [whisper fail] {str(e)[:140]}", file=sys.stderr)
        return None


def process_one(post: dict, out_dir: Path) -> dict:
    sc = post.get("shortCode") or "unknown"
    out_path = out_dir / f"{sc}.json"
    if out_path.exists():
        return {"shortCode": sc, "skipped": True}

    url = post.get("videoUrl")
    if not url:
        return {"shortCode": sc, "error": "no videoUrl"}

    with tempfile.TemporaryDirectory() as td:
        mp4 = Path(td) / f"{sc}.mp4"
        mp3 = Path(td) / f"{sc}.mp3"

        if not download_video(url, mp4):
            return {"shortCode": sc, "error": "download failed"}

        if not extract_audio(mp4, mp3):
            return {"shortCode": sc, "error": "audio extract failed"}

        size_mb = mp3.stat().st_size / 1024 / 1024
        if size_mb > 24:
            return {"shortCode": sc, "error": f"audio too large ({size_mb:.1f}MB)"}

        result = whisper_transcribe(mp3)
        if not result:
            return {"shortCode": sc, "error": "whisper failed"}

    record = {
        "shortCode": sc,
        "url": post.get("url"),
        "timestamp": post.get("timestamp"),
        "caption": post.get("caption"),
        "type": post.get("type"),
        "likes": post.get("likesCount"),
        "comments": post.get("commentsCount"),
        "views": post.get("videoPlayCount"),
        "duration_seconds": post.get("videoDuration") or result.get("duration"),
        "text": result.get("text"),
        "language": result.get("language"),
        "segments": result.get("segments"),
    }
    out_path.write_text(json.dumps(record, indent=2, default=str))
    return {"shortCode": sc, "text_chars": len(result.get("text") or "")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--posts", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--limit", type=int, default=0, help="0=all")
    args = parser.parse_args()

    posts = json.loads(Path(args.posts).read_text())
    targets = [p for p in posts if p.get("videoUrl")]
    if args.limit:
        targets = targets[: args.limit]
    print(f"Found {len(targets)} reels with video URLs")

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    done: list[dict] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(process_one, p, out_dir): p.get("shortCode") for p in targets}
        for i, f in enumerate(as_completed(futs), 1):
            res = f.result()
            done.append(res)
            tag = (
                f"SKIP {res['shortCode']}" if res.get("skipped")
                else f"OK   {res['shortCode']} ({res.get('text_chars',0):>5} chars)"
                if "text_chars" in res
                else f"FAIL {res['shortCode']} ({res.get('error','?')})"
            )
            print(f"  [{i:>2}/{len(targets)}] {tag}")

    n_ok = sum(1 for r in done if "text_chars" in r)
    n_fail = sum(1 for r in done if r.get("error"))
    n_skip = sum(1 for r in done if r.get("skipped"))
    total_chars = sum(r.get("text_chars", 0) for r in done)

    print(f"\n=== Done ===")
    print(f"  Successful: {n_ok}")
    print(f"  Skipped (already had): {n_skip}")
    print(f"  Failed: {n_fail}")
    print(f"  Total transcript chars: {total_chars:,}")

    # Stitch all transcripts into one combined file
    combined = []
    for jf in sorted(out_dir.glob("*.json")):
        try:
            combined.append(json.loads(jf.read_text()))
        except Exception:
            continue
    Path(args.out_dir).parent.joinpath("reels_transcripts_all.json").write_text(
        json.dumps(combined, indent=2, default=str)
    )
    print(f"  Stitched {len(combined)} transcripts into reels_transcripts_all.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
