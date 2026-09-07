#!/usr/bin/env python3
"""Email the morning's scripts so the client can read them and pick what to record.

The board is the source of truth, but a board you have to remember to open is a board you do not
read. This puts the same cards in front of him at breakfast, hooks first so he can scan and decide
before reading a single full script.

Sends through Resend (free tier). Every credential and id comes from the repo's .env, all of them
belonging to the CLIENT, never to you. Never uses a paid LLM key: this script calls no model at
all, it only formats what the scripter already wrote.

Usage:
    python3 tools/content-machine/content_machine_email.py
    python3 tools/content-machine/content_machine_email.py --to someone@example.com
    python3 tools/content-machine/content_machine_email.py --dry-run     # print, send nothing
    python3 tools/content-machine/content_machine_email.py --since 2026-07-29
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import html
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def _env() -> dict[str, str]:
    """Config from the environment, falling back to the repo's own .env.

    Everything here is per-client: the Supabase project the scripts write to, the workspace on it,
    the address the scripts get emailed to, and the URL of that client's operating system. None of
    it is hardcoded, because one operator runs several clients and a wrong id here would email one
    client another client's scripts.
    """
    env: dict[str, str] = dict(os.environ)
    for name in (".env", ".env.local"):
        f = ROOT / name
        if not f.exists():
            continue
        for line in f.read_text().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip("\"'"))
    return env


_E = _env()
PROJECT_REF = _E.get("SUPABASE_PROJECT_REF", "")
AGENCY_ID = _E.get("CONTENT_AGENCY_ID", "")
DEFAULT_TO = _E.get("CONTENT_EMAIL_TO", "")

# How far back one send looks. A daily rhythm wants a little over a day so a run that slips is
# still covered; a client who films in batches wants the whole week in one email instead.
WORKSPACES = {
    "daily": {"agency": AGENCY_ID, "to": DEFAULT_TO, "hours": 26},
    "weekly": {"agency": AGENCY_ID, "to": DEFAULT_TO, "hours": 24 * 7},
}

# The client's own operating system, where the board and the feedback endpoint live. The feedback
# buttons in this email post back to it, so pointing this at anyone else's instance sends this
# client's verdicts into that instance instead.
APP_URL = _E.get("CONTENT_APP_URL", "").rstrip("/")
BOARD_URL = f"{APP_URL}/content?tab=board"

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# House style is enforced in code, not in a prompt, because the scripter's output flows straight
# into this email and a stray dash or emoji would ship to a real inbox.
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF]", re.UNICODE)


# Curly quotes render as mojibake the moment any client along the chain guesses a
# non-UTF-8 charset, which is not worth risking in an inbox. Everything is folded to ASCII.
_SMART = {"‘": "'", "’": "'", "“": '"', "”": '"', "…": "...", " ": " "}


def clean(text: str) -> str:
    text = _EMOJI.sub("", text or "")
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    for bad, good in _SMART.items():
        text = text.replace(bad, good)
    return text.strip()


def env_from(path: Path, key: str) -> str | None:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def run_sql(sql: str):
    tok = env_from(ROOT / ".env", "SUPABASE_ACCESS_TOKEN")
    if not tok:
        raise SystemExit("SUPABASE_ACCESS_TOKEN not found in .env")
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read())


def todays_cards(since_iso: str, agency_id: str = AGENCY_ID) -> list[dict]:
    return run_sql(
        "select id, title, format, platform, hook, script, notes, source, created_at "
        "from public.content_cards "
        f"where agency_id = '{agency_id}' and stage = 'scripted' "
        f"and created_at >= '{since_iso}' "
        "order by created_at asc"
    )


# Must stay byte-identical to signFeedback() in the operating system's
# src/lib/content/feedback-token.ts, or every
# button in this email 403s. The key is derived from SECRETS_ENCRYPTION_KEY with a label rather
# than used directly, so a signing oracle here is not one for the encrypted Stripe credentials.
FEEDBACK_LABEL = b"content-feedback-v1"


def feedback_link(card_id: str, verdict: str) -> str:
    secret = _E.get("SECRETS_ENCRYPTION_KEY")
    if not secret:
        return ""
    key = hmac.new(secret.encode(), FEEDBACK_LABEL, hashlib.sha256).digest()
    token = hmac.new(key, f"{card_id}:{verdict}".encode(), hashlib.sha256).hexdigest()[:32]
    return f"{APP_URL}/api/content/feedback?card={card_id}&v={verdict}&t={token}"


def feedback_buttons(card_id: str) -> str:
    """Three one-click verdicts. Without these the scripts go to the void: a client judges all six in
    his head every morning and the machine learns nothing, so it pitches the rejected angles again
    tomorrow."""
    if not card_id or not feedback_link(card_id, "accepted"):
        return ""
    btn = ("display:inline-block;text-decoration:none;font-weight:600;font-size:14px;"
           "padding:10px 16px;border-radius:8px;margin:0 8px 8px 0;")
    return f"""
  <div style="margin-top:14px;padding-top:14px;border-top:1px solid #E4DDCD;">
    <a href="{feedback_link(card_id, 'accepted')}"
       style="{btn}background:#1E7A46;color:#FCFAF3;">I'll record this</a>
    <a href="{feedback_link(card_id, 'revise')}"
       style="{btn}background:#FCFAF3;color:#8A6D2F;border:1px solid #E4DDCD;">Needs a rewrite</a>
    <a href="{feedback_link(card_id, 'rejected')}"
       style="{btn}background:#FCFAF3;color:#8A4B3C;border:1px solid #E4DDCD;">Not for me</a>
    <div style="margin-top:2px;font-size:12px;color:#8A8578;">
      Every button opens a box where you can say why, in your own words. That sentence goes
      straight into the writer's brain and it reads the newest ones before writing the next batch.
    </div>
  </div>"""


def surface(card: dict) -> str:
    """What he actually films. platform 'yt' means a long form YouTube video, everything else
    is a reel; the two are shot completely differently so the label leads every entry."""
    return "YouTube" if (card.get("platform") or "").lower() in ("yt", "youtube") else "Reel"


def first_line(text: str, limit: int = 200) -> str:
    line = clean((text or "").strip().split("\n")[0])
    return line[:limit] + ("..." if len(line) > limit else "")


def split_header(script: str) -> tuple[dict[str, str], str]:
    """YouTube scripts open with a TITLE / THUMBNAIL / HOOK block, reels just repeat the hook.

    Returns the header fields plus the body with that block removed. Title and hook are already
    shown above, so leaving them in makes every script read as a stutter. THUMBNAIL is pulled out
    rather than dropped: it is the 2 to 4 words that go on the thumbnail, and it is the one field
    the reader cannot get anywhere else in this email."""
    header: dict[str, str] = {}
    lines = (script or "").split("\n")
    while lines:
        stripped = lines[0].strip()
        if not stripped:
            lines.pop(0)
            continue
        matched = False
        for key in ("TITLE:", "THUMBNAIL:", "HOOK:"):
            if stripped.upper().startswith(key):
                header[key.rstrip(":").lower()] = clean(stripped[len(key):].strip())
                lines.pop(0)
                matched = True
                break
        if not matched:
            break
    return header, clean("\n".join(lines))


def staleness(agency_id: str) -> list[str]:
    """Warnings that the machine is starting to repeat itself, in plain English.

    If the content starts feeling generic, spot it and fix it by
    pulling in more competitor material and finding new angles. The failure is gradual, so nobody
    notices from one batch. These are the three measurable signals that precede it, checked every
    send so the warning arrives BEFORE the writing goes flat rather than after.
    """
    out = []

    # 1. The competitor pool draining. When nothing fresh is left the writer falls back to the
    #    knowledge base, which is finite and starts sounding like itself.
    fresh = run_sql(
        "select count(*) n from public.content_outliers o "
        f"where o.agency_id = '{agency_id}' and o.url is not null "
        "and not exists (select 1 from public.content_cards c "
        f"  where c.agency_id = '{agency_id}' and c.notes like '%' || o.url || '%')"
    )[0]["n"]
    if fresh < 40:
        out.append(f"Only {fresh} competitor posts left that no script has used. "
                   "Time to scrape the roster again or add creators.")

    # 2. How much of the recent output came from the knowledge base rather than a real post.
    recent = run_sql(
        "select notes from public.content_cards "
        f"where agency_id = '{agency_id}' and created_by = 'agent:content_machine' "
        "order by created_at desc limit 12"
    )
    craft = sum(1 for r in recent if "knowledge base" in (r.get("notes") or ""))
    if recent and craft * 100 // len(recent) >= 50:
        out.append(f"{craft} of the last {len(recent)} scripts were written from the knowledge "
                   "base with no competitor post to model. That is the well running dry.")

    # 3. A subject coming round again too soon. With 40-odd subjects a repeat inside two weeks
    #    means the rotation is being forced, usually because one lane has too few subjects.
    import re as _re
    subs = [(_re.search(r"^Subject: (.+)$", r.get("notes") or "", _re.M) or [None, None])[1]
            for r in recent]
    subs = [s for s in subs if s]
    dupes = {s for s in subs if subs.count(s) > 1}
    if dupes:
        out.append("Repeated inside the last dozen scripts: " + ", ".join(sorted(dupes)[:3])
                   + ". That lane needs more subjects in the proof inventory.")
    return out


def build_html(cards: list[dict], run_note: str, warnings: list[str] | None = None) -> str:
    day = datetime.now().strftime("%A %d %B")
    reels = sum(1 for c in cards if surface(c) == "Reel")
    yts = len(cards) - reels

    # Hooks first. He decides what to record by scanning hooks, not by reading six full scripts,
    # so the scan list comes before any detail.
    scan = "".join(
        f'<li style="margin:0 0 10px 0;"><span style="color:#1E7A46;font-weight:600;">'
        f'{surface(c)}</span> &nbsp;{html.escape(first_line(c.get("hook") or c.get("title") or ""))}</li>'
        for c in cards
    )

    warn_html = ""
    if warnings:
        items = "".join(f'<li style="margin:0 0 6px 0;">{html.escape(w)}</li>' for w in warnings)
        warn_html = (
            '<div style="background:#FBF3E2;border:1px solid #E4C98A;border-radius:10px;'
            'padding:14px 16px;margin:0 0 18px 0;">'
            '<div style="font-size:12px;text-transform:uppercase;letter-spacing:0.07em;'
            'color:#8A6D2F;font-weight:700;">The machine is starting to repeat itself</div>'
            f'<ul style="margin:8px 0 0 18px;padding:0;color:#1E211C;font-size:14px;">{items}</ul>'
            '</div>'
        )

    blocks = []
    for i, c in enumerate(cards, 1):
        note = clean(c.get("notes") or "")
        why = ""
        for line in note.split("\n"):
            if line.lower().startswith(("pattern:", "hook chosen because:", "inspired by")):
                why += f'<div style="color:#4C5247;font-size:13px;margin:2px 0;">{html.escape(line)}</div>'

        # A rewrite is flagged at the TOP of the card with what was asked for. Reading a second
        # pass cold, with no memory of the note, makes it impossible to judge whether the note
        # was actually answered, which is the only question that matters for a rewrite.
        redo = ""
        asked = next((l.split(":", 1)[1].strip() for l in note.split("\n")
                      if l.startswith("REWRITE. You sent this back saying:")), None)
        was = next((l.split(":", 1)[1].strip() for l in note.split("\n")
                    if l.startswith("The version you rejected opened:")), None)
        if asked is not None:
            redo = (
                '<div style="background:#FBF3E2;border:1px solid #E4C98A;border-radius:8px;'
                'padding:10px 12px;margin:0 0 12px 0;">'
                '<div style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;'
                'color:#8A6D2F;font-weight:700;">Rewritten from your feedback</div>'
                f'<div style="font-size:13px;color:#1E211C;margin-top:4px;">You said: '
                f'&ldquo;{html.escape(asked)}&rdquo;</div>'
                + (f'<div style="font-size:12px;color:#8A8578;margin-top:4px;">Old hook: '
                   f'{html.escape(was)}</div>' if was else "")
                + '</div>'
            )
        header, body = split_header(c.get("script") or "")
        script_html = html.escape(body).replace("\n", "<br>")
        thumb = ""
        if header.get("thumbnail"):
            thumb = (
                '<div style="display:inline-block;background:#1E211C;color:#FCFAF3;padding:6px 12px;'
                'border-radius:6px;font-weight:700;font-size:14px;letter-spacing:0.02em;'
                'margin:0 0 12px 0;">Thumbnail: '
                f'{html.escape(header["thumbnail"])}</div>'
            )
        blocks.append(f"""
<div style="border:1px solid #E4DDCD;border-radius:12px;padding:18px;margin:0 0 16px 0;background:#FCFAF3;">
  <div style="font-size:12px;letter-spacing:0.08em;text-transform:uppercase;color:#1E7A46;font-weight:700;">
    {i}. {surface(c)}
  </div>
  <div style="font-size:19px;font-weight:700;color:#1E211C;margin:6px 0 10px 0;line-height:1.3;">
    {html.escape(clean(c.get("title") or ""))}
  </div>
  {redo}
  <div style="background:#F6F1E7;border-left:3px solid #1E7A46;padding:10px 12px;margin:0 0 12px 0;">
    <div style="font-size:11px;text-transform:uppercase;letter-spacing:0.06em;color:#4C5247;">Hook</div>
    <div style="font-size:15px;color:#1E211C;font-weight:600;">{html.escape(clean(c.get("hook") or ""))}</div>
  </div>
  {thumb}
  <div style="font-size:14px;color:#1E211C;line-height:1.6;">{script_html}</div>
  <div style="margin-top:12px;padding-top:10px;border-top:1px solid #E4DDCD;">{why}</div>
  {feedback_buttons(str(c.get("id") or ""))}
</div>""")

    return f"""<div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
background:#F6F1E7;padding:24px;max-width:680px;margin:0 auto;">
  <div style="font-size:12px;letter-spacing:0.1em;text-transform:uppercase;color:#4C5247;">{day}</div>
  <div style="font-size:26px;font-weight:700;color:#1E211C;margin:4px 0 2px 0;">
    {len(cards)} script{'' if len(cards) == 1 else 's'} ready
  </div>
  <div style="font-size:14px;color:#4C5247;margin-bottom:20px;">
    {reels} reel{'' if reels == 1 else 's'}, {yts} YouTube. {html.escape(run_note)}
  </div>

  <div style="background:#FCFAF3;border:1px solid #E4DDCD;border-radius:12px;padding:18px;margin-bottom:22px;">
    <div style="font-size:12px;text-transform:uppercase;letter-spacing:0.06em;color:#4C5247;margin-bottom:10px;">
      Pick what to record
    </div>
    <ol style="margin:0;padding-left:20px;font-size:15px;color:#1E211C;line-height:1.45;">{scan}</ol>
  </div>

  {warn_html}

  {''.join(blocks)}

  <div style="text-align:center;margin-top:24px;">
    <a href="{BOARD_URL}" style="display:inline-block;background:#1E7A46;color:#FCFAF3;
       text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:600;font-size:15px;">
      Open the board
    </a>
  </div>
  <div style="text-align:center;font-size:12px;color:#7C8595;margin-top:14px;">
    Written by the content machine from {run_note.lower() or 'your tracked creators'}.
  </div>
</div>"""


def send(to: str, subject: str, body_html: str) -> None:
    key = _E.get("RESEND_API_KEY")
    if not key:
        raise SystemExit(f"RESEND_API_KEY not set, in the environment or in {ROOT}/.env")
    sender = _E.get("RESEND_FROM") or "Content Machine <onboarding@resend.dev>"
    # Resend sits behind Cloudflare, which returns 403 "error code: 1010" to a default urllib
    # user-agent. A browser UA is required here exactly as it is for the Supabase management API.
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps({"from": sender, "to": [to], "subject": subject, "html": body_html}).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "User-Agent": UA, "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f"  sent to {to}: {json.loads(r.read()).get('id', 'ok')}")
    except urllib.error.HTTPError as e:
        raise SystemExit(f"Resend refused the send: HTTP {e.code} {e.read().decode()[:300]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workspace", default="daily", choices=sorted(WORKSPACES),
                    help="whose board to report on, and at what rhythm")
    ap.add_argument("--to", default=None,
                    help="override the recipient. Defaults to the workspace's own address, and a "
                         "workspace with no address set refuses to send rather than guessing.")
    ap.add_argument("--since", default=None, help="ISO date; defaults to the last 18 hours")
    ap.add_argument("--since-hours", type=int, default=None,
                    help="look back this many hours instead (26 covers a daily run that slips)")
    ap.add_argument("--every-n-days", type=int, default=0,
                    help="send at most once every N days. The job can then run daily and decide "
                         "for itself, which survives a missed morning instead of skipping a whole "
                         "cycle the way a fixed weekday would.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    # Hours, not "today", so a run that finishes just after midnight still reports its own work.
    # The scheduled job uses 26 to overlap the previous day: a script written at 06:59 must not
    # fall down the crack between two runs and never be mentioned to anyone.
    ws = WORKSPACES[args.workspace]

    # Cadence gate. State is a file per workspace rather than a weekday, so "every second day"
    # stays every second day even if the Mac was asleep on the day it was due.
    stamp = ROOT / ".tmp" / f"last_send_{args.workspace}.txt"
    if args.every_n_days and not args.dry_run and stamp.exists():
        try:
            last = datetime.fromisoformat(stamp.read_text().strip())
        except ValueError:
            last = None
        if last:
            due_in = args.every_n_days - (datetime.now(timezone.utc) - last).days
            if due_in > 0:
                print(f"last sent {(datetime.now(timezone.utc) - last).days}d ago, "
                      f"next due in {due_in}d, sending nothing")
                return 0
    recipient = args.to or ws["to"]
    # A weekly send is a week of work in one message, so getting the address wrong is not a small
    # mistake. No default, no guess: an unset address stops the run.
    if not recipient and not args.dry_run:
        raise SystemExit(
            f"no recipient set for the {args.workspace} workspace. Pass --to, or add the address "
            f"to WORKSPACES once it is confirmed.")

    hours = args.since_hours or ws["hours"]
    since = args.since or (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    cards = todays_cards(since, ws["agency"])

    if not cards:
        print("no new scripts, sending nothing")
        return 0

    run_note = clean(cards[0].get("source") or "")
    # A week's worth reads as a batch to film, a day's worth reads as today's job.
    weekly = hours > 48
    subject = (
        f"{len(cards)} scripts ready to film this week"
        if weekly else
        f"{len(cards)} scripts ready, {datetime.now().strftime('%d %b')}"
    )
    body = build_html(cards, run_note, staleness(ws['agency']))

    if args.dry_run:
        print(f"  workspace: {args.workspace} ({ws['agency']})")
        print(f"  to:        {recipient or 'NOT SET, would refuse to send'}")
        print(f"  window:    last {hours}h")
        print(f"  subject:   {subject}")
        print(f"  cards:     {len(cards)}")
        for c in cards:
            print(f"    [{surface(c)}] {first_line(c.get('hook') or c.get('title') or '')}")
        return 0

    send(recipient, subject, body)
    if args.every_n_days:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(datetime.now(timezone.utc).isoformat())
    return 0


if __name__ == "__main__":
    sys.exit(main())
