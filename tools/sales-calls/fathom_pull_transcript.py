#!/usr/bin/env python3
"""Pull Fathom call transcripts from public share links into sales-calls/transcripts/.

A Fathom share page (fathom.video/share/<token>) is readable with no login when the owner
has link sharing on. The page is an Inertia app; its data-page JSON carries the call id, the
start time and a `copyTranscriptUrl` (calls/<id>/copy_transcript?token=<share token>) that
returns {"html": ..., "plain_text": ...} with speaker labels and timestamps. No API key.

  python3 tools/sales-calls/fathom_pull_transcript.py <share url> [<share url> ...]
  python3 tools/sales-calls/fathom_pull_transcript.py --inbox        # every link pasted in sales-calls/inbox.md
  python3 tools/sales-calls/fathom_pull_transcript.py --force <url>  # re-pull a call that already exists

Each call becomes sales-calls/transcripts/<date>_<prospect>_<call id>.md and gets a row in
sales-calls/index.md. Already-pulled call ids are skipped unless --force is given.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
CALLS_DIR = ROOT / "sales-calls"
TRANSCRIPTS_DIR = CALLS_DIR / "transcripts"
INBOX = CALLS_DIR / "inbox.md"
INDEX = CALLS_DIR / "index.md"
RAW_DIR = ROOT / ".tmp" / "fathom"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
HOST_NAME = os.environ.get("FATHOM_HOST_NAME", "")    # your name as it appears in transcripts
HOST_EMAIL = os.environ.get("FATHOM_HOST_EMAIL", "")  # Fathom appends it after your name
SHARE_RE = re.compile(r"https?://fathom\.video/share/([A-Za-z0-9_-]+)")
# Fathom serves the share page to any browser-looking client; a bare urllib UA gets a 403.
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"}
INDEX_HEADER = (
    "# Sales calls\n\n"
    "One row per call. Outcome and review get filled in after the call is reviewed.\n\n"
    "| Date (PT) | Prospect | Length | Outcome | Transcript | Review | Fathom |\n"
    "|---|---|---|---|---|---|---|\n"
)


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        raise SystemExit(f"{url} -> HTTP {exc.code}. If this is 403/404 the share link is "
                         f"private or expired; open it in a browser to check.") from exc


def share_page_props(share_url: str) -> dict:
    page = fetch(share_url).decode("utf-8", "replace")
    match = re.search(r'data-page="([^"]+)"', page)
    if not match:
        raise SystemExit(f"{share_url}: no Inertia data-page found; Fathom may have changed the page.")
    props = json.loads(html.unescape(match.group(1)))["props"]
    if not props.get("copyTranscriptUrl"):
        raise SystemExit(f"{share_url}: page loaded but has no transcript URL "
                         f"(access={props.get('access')}). The call may still be processing.")
    return props


def speakers_in(plain_text: str) -> list[str]:
    seen: list[str] = []
    for name in re.findall(r"^\d{1,2}:\d{2}(?::\d{2})? - (.+)$", plain_text, flags=re.M):
        name = re.sub(r"\s*\([^)]*@[^)]*\)", "", name).strip()
        if name not in seen:
            seen.append(name)
    return seen


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "unknown"


def transcript_body(plain_text: str) -> str:
    # Drop Fathom's own header (title line + "VIEW RECORDING" line) and start at the first cue.
    parts = plain_text.split("\n---\n", 1)
    body = parts[1] if len(parts) == 2 else plain_text
    # Fathom appends the host's email after their name on every line they speak.
    if HOST_EMAIL:
        body = re.sub(r"\s*\(" + re.escape(HOST_EMAIL) + r"\)", "", body)
    return body.strip() + "\n"


def index_rows() -> str:
    return INDEX.read_text() if INDEX.exists() else INDEX_HEADER


def add_index_row(existing: str, row: str, call_id: int) -> str:
    if f"_{call_id}.md" in existing:
        return existing
    return existing.rstrip("\n") + "\n" + row + "\n"


def pull(share_url: str, force: bool) -> Path | None:
    token = SHARE_RE.search(share_url).group(1)
    props = share_page_props(share_url)
    call = props["call"]
    call_id = int(call["id"])
    existing = sorted(TRANSCRIPTS_DIR.glob(f"*_{call_id}.md"))
    if existing and not force:
        print(f"skip  {call_id} already pulled -> {existing[0].relative_to(ROOT)}")
        return None

    payload = json.loads(fetch(props["copyTranscriptUrl"]).decode("utf-8"))
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{call_id}.json").write_text(json.dumps({"props": props, "transcript": payload}, indent=1))

    started = datetime.fromisoformat(call["started_at"].replace("Z", "+00:00")).astimezone(LOCAL_TZ)
    minutes = int(round(float(props["duration"]) / 60))
    speakers = speakers_in(payload["plain_text"])
    prospects = [s for s in speakers if HOST_NAME not in s] or ["unknown"]
    prospect = prospects[0]
    date_str = started.strftime("%Y-%m-%d")
    out = TRANSCRIPTS_DIR / f"{date_str}_{slugify(prospect)}_{call_id}.md"

    header = (
        f"# Sales call: {prospect}, {started.strftime('%a %d %b %Y, %I:%M %p PT')}\n\n"
        f"- Length: {minutes} min\n"
        f"- Fathom: {share_url}\n"
        f"- Speakers: {', '.join(f'{s} ({'closer' if HOST_NAME in s else 'prospect'})' for s in speakers)}\n"
        f"- Outcome: (fill in)\n\n---\n\n"
    )
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    out.write_text(header + transcript_body(payload["plain_text"]))

    row = (f"| {started.strftime('%Y-%m-%d %I:%M %p')} | {prospect} | {minutes} min | ? "
           f"| [transcript](transcripts/{out.name}) |  | [link]({share_url}) |")
    INDEX.write_text(add_index_row(index_rows(), row, call_id))
    print(f"saved {call_id} {prospect} ({minutes} min) -> {out.relative_to(ROOT)}")
    return out


def urls_from_inbox() -> list[str]:
    if not INBOX.exists():
        return []
    return list(dict.fromkeys(m.group(0) for m in SHARE_RE.finditer(INBOX.read_text())))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("urls", nargs="*", help="Fathom share links")
    ap.add_argument("--inbox", action="store_true", help=f"also pull every link in {INBOX.relative_to(ROOT)}")
    ap.add_argument("--force", action="store_true", help="re-pull calls that already have a transcript file")
    args = ap.parse_args()

    urls = [u for u in args.urls if SHARE_RE.search(u)]
    bad = [u for u in args.urls if not SHARE_RE.search(u)]
    if bad:
        raise SystemExit(f"not Fathom share links: {bad}")
    if args.inbox:
        urls += urls_from_inbox()
    urls = list(dict.fromkeys(urls))
    if not urls:
        raise SystemExit("no share links given (pass URLs, or --inbox with links in sales-calls/inbox.md)")

    for url in urls:
        pull(url, args.force)


if __name__ == "__main__":
    main()
