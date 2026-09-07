#!/usr/bin/env python3
"""Turn competitor marketing emails into content ideas on the client's board.

Scope: ONLY content ideas. This does not draft anyone's emails and does not copy anyone's
writing. It reads what other operators are choosing to talk about this week and extracts the
ANGLE, which is the reusable part. An email arguing "back to school matters even if you do not
sell school supplies" is not an ecommerce tip, it is the shape "the season everyone ignores is
actually your best window", and that shape runs in any lane.

It pulls TWO things, because they are different and both useful:
  STORY: a concrete thing that happened, WITH the numbers. "Opus 5 matches Fable 5 on CursorBench
         at half the cost per task." The client reports it and adds their take. Facts are copied
         verbatim from the email and never invented.
  ANGLE: the reusable shape with the topic stripped out, for when the subject does not transfer.

WHO gets read is a list in knowledge/email_sources.json. Sender-based, not a dedicated
signup address: the newsletters worth reading are already arriving in the inbox, so re-subscribing
to everything would be make-work.

Reading is IMAP with an app password rather than OAuth: no token to expire, no consent screen to
re-approve, and it survives unattended for months. GMAIL_APP_PASSWORD lives in .env. The password
is ONLY needed for the unattended 7am run; anything interactive can read the same mail without it.

Everything runs FREE (CLAUDE.md money rule): OmniRoute fans the analysis across Gemini, Groq,
Mistral and OpenRouter free tiers. No paid key is ever called.

Usage:
    python3 tools/competitor-intel/competitor_email_intel.py                    # last 3 days from your sources
    python3 tools/competitor-intel/competitor_email_intel.py --days 7
    python3 tools/competitor-intel/competitor_email_intel.py --dry-run          # print ideas, file nothing
    python3 tools/competitor-intel/competitor_email_intel.py --from-json f.json # analyse emails from a file
"""
from __future__ import annotations

import argparse
import email
import email.utils
import html as html_mod
import imaplib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
# Per client, from .env. See phase 4. Resolved lazily inside main() rather than at import,
# because env_value is defined below this point and calling it here is a NameError.
PROJECT_REF = ""
AGENCY_ID = ""
SOURCES_FILE = ROOT / "knowledge" / "email_sources.json"
OMNIROUTE_BASE = "http://localhost:20128/v1"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")

# Marketing email is mostly chrome: nav bars, unsubscribe blocks, tracking pixels, sponsor slots.
# Stripping it before the model sees it is what keeps this inside a free context window.
_BOILERPLATE = re.compile(
    r"(?i)(unsubscribe|update your preferences|view (this )?in browser|privacy policy|"
    r"you (are )?receiv(ing|ed) this|manage (your )?subscription|sent to you by|"
    r"copyright|all rights reserved|no longer wish to receive)")


def env_value(key: str) -> str | None:
    try:
        for line in (ROOT / ".env").read_text().splitlines():
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    except OSError:
        return None
    return None


def active_sources() -> list[str]:
    """Who gets read. Edit knowledge/email_sources.json and nothing else.

    Sender-based rather than a dedicated address: the newsletters worth reading were already
    arriving in his inbox, so asking him to re-subscribe to everything with a plus address was
    make-work that would have delayed this by days for no gain."""
    try:
        data = json.loads(SOURCES_FILE.read_text())
    except OSError:
        raise SystemExit(
            f"{SOURCES_FILE} not found. Copy knowledge/email_sources_TEMPLATE.json "
            "to that name and list the senders worth reading.")
    return [s["from"] for s in data.get("sources", [])
            if s.get("active") and s.get("from")]


def run_sql(sql: str):
    tok = env_value("SUPABASE_ACCESS_TOKEN")
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


# House style is enforced HERE, not in the prompt. The prompt already says "no em dashes" and the
# model shipped "an afternoon-here is why" anyway on the first real run, which is exactly why every
# other guard in this pipeline lives in code.
_EMOJI = re.compile("[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF]", re.UNICODE)
_SMART = {"‘": "'", "’": "'", "“": '"', "”": '"', "…": "...",
          " ": " "}


def sanitize(text: str) -> str:
    """Strip what the house style bans, so an idea can go straight onto a card."""
    if not isinstance(text, str):
        return text
    text = _EMOJI.sub("", text)
    text = re.sub(r"\s*[—–]\s*", ", ", text)   # em and en dash
    for bad, good in _SMART.items():
        text = text.replace(bad, good)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def clean_text(raw: str) -> str:
    """HTML email to something a model can read cheaply."""
    raw = re.sub(r"(?is)<(script|style|head).*?</\1>", " ", raw)
    raw = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", raw)
    raw = re.sub(r"<[^>]+>", " ", raw)
    raw = html_mod.unescape(raw)
    raw = re.sub(r"https?://\S+", "", raw)          # tracking links carry no meaning
    raw = re.sub(r"[ \t ]+", " ", raw)
    lines = [ln.strip() for ln in raw.split("\n")]
    keep = [ln for ln in lines if ln and not _BOILERPLATE.search(ln) and len(ln) > 2]
    out = "\n".join(keep)
    return re.sub(r"\n{3,}", "\n\n", out).strip()


def body_of(msg: email.message.Message) -> str:
    """Prefer text/plain; fall back to stripping the HTML part."""
    plain, rich = "", ""
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue
            try:
                payload = part.get_payload(decode=True) or b""
                text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                continue
            if part.get_content_type() == "text/plain" and not plain:
                plain = text
            elif part.get_content_type() == "text/html" and not rich:
                rich = text
    else:
        payload = msg.get_payload(decode=True) or b""
        text = payload.decode(msg.get_content_charset() or "utf-8", errors="replace")
        if msg.get_content_type() == "text/html":
            rich = text
        else:
            plain = text
    return clean_text(plain or rich)


def fetch_emails(days: int) -> list[dict]:
    """Read the intel label over IMAP. Fails with an actionable message, not a stack trace."""
    pw = env_value("GMAIL_APP_PASSWORD")
    addr = env_value("GMAIL_ADDRESS")
    if not pw:
        raise SystemExit(
            "GMAIL_APP_PASSWORD is not in .env.\n"
            "  1. Turn on 2-step verification at myaccount.google.com/security\n"
            "  2. Create an app password at myaccount.google.com/apppasswords\n"
            "  3. Add it to .env as GMAIL_APP_PASSWORD=<the 16 characters>"
        )
    senders = active_sources()
    if not senders:
        raise SystemExit(f"no active sources in {SOURCES_FILE}")
    out: list[dict] = []
    with imaplib.IMAP4_SSL("imap.gmail.com") as M:
        M.login(addr, pw)
        # All Mail plus Gmail's OWN search syntax via X-GM-RAW. Searching by SENDER is what removes
        # the setup burden entirely: no filter, no label, no new address to sign up with. The operator
        # edits a list of people and that is the whole configuration.
        M.select('"[Gmail]/All Mail"', readonly=True)
        query = "(" + " OR ".join(f"from:{s}" for s in senders) + f") newer_than:{days}d"
        status, data = M.search(None, "X-GM-RAW", f'"{query}"')
        ids = data[0].split() if status == "OK" else []
        if not ids:
            print(f"  nothing from your {len(senders)} sources in the last {days} days")
        for mid in ids:
            status, blob = M.fetch(mid, "(RFC822)")
            if status != "OK" or not blob or not isinstance(blob[0], tuple):
                continue
            msg = email.message_from_bytes(blob[0][1])
            subject = str(email.header.make_header(email.header.decode_header(msg.get("Subject", ""))))
            out.append({
                "subject": subject,
                "sender": msg.get("From", ""),
                "date": msg.get("Date", ""),
                "body": body_of(msg),
            })
    return out


def _who() -> str:
    """The client, in one paragraph: who they are, what they do, who for, and what they are NOT."""
    f = ROOT / "knowledge" / "WHO.md"
    if not f.exists():
        raise SystemExit(
            f"{f} is missing. Write one paragraph about the client there: what they do, who for, "
            "what they never talk about, and what their proof is. Every idea is aimed at it.")
    return f.read_text().strip()


PROMPT = """You are a content strategist reading a competitor's marketing email for a client.

Pull out TWO different kinds of thing. Both are valuable and they are not the same.

KIND 1, "story": a concrete thing that is actually happening, WITH the facts attached.
A model launched, a price changed, a platform shipped a feature, a benchmark landed, a company did
something. The client can report this themselves and add their own take. Carry the real numbers
and names across: they are the whole value, and the reel cannot be made without them.
  Example: the email says Opus 5 landed within half a percent of Fable 5 on CursorBench at half the
  cost per task, and is the new default on Max.
  -> story: "Opus 5 matches Fable 5 on CursorBench at half the cost per task, now default on Max"
  -> facts: ["within 0.5% of Fable 5 on CursorBench", "half the cost per task", "default on Max"]
  The client makes a reel explaining what that means for anyone paying for AI coding.
  NEVER invent a number. If the email does not state it, leave it out.

KIND 2, "angle": the reusable SHAPE of the argument, with the topic stripped out.
The client does not sell what these people sell, so the topic rarely transfers but the shape does.
  Example: the email argues back to school matters even if you do not sell school supplies.
  -> worthless: "write about back to school"
  -> angle: "the season everyone in your niche writes off is the one with no competition"
  -> for them: the work nobody wants is where the money is, because nobody is pitching it

THE CLIENT: __WHO__

Return JSON only, no prose, no code fences:
[
  {
    "kind": "story" or "angle",
    "angle": "for a story: what happened, one sentence. for an angle: the reusable shape as a claim",
    "facts": ["the specific numbers and names from the email, verbatim"],
    "for_them": "the specific thing THEY would say or explain, one sentence",
    "hook": "a first line they could open a reel with, under 15 words, in their voice",
    "why": "why this is worth their time, one sentence",
    "strength": 1 to 5, where 5 means drop everything and make this
  }
]

"facts" must be empty for an angle and populated for a story. Every fact must appear in the email.
Return at most 4 in total. Only ones genuinely worth making: an empty list is a valid and useful
answer, and most marketing emails contain nothing. Do not pad.
No emoji. No em dashes or en dashes.

THE EMAIL
Subject: __SUBJECT__
From: __SENDER__

__BODY__
"""


def omniroute_up() -> bool:
    try:
        req = urllib.request.Request(f"{OMNIROUTE_BASE}/models", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def repair_control_chars(text: str) -> str:
    """Escape real newlines inside JSON strings. Same failure the scripter hit: a model asked for
    prose inside JSON emits literal newlines and json.loads rejects the lot."""
    out, in_string, escaped = [], False, False
    for ch in text:
        if escaped:
            out.append(ch); escaped = False; continue
        if ch == "\\":
            out.append(ch); escaped = True; continue
        if ch == '"':
            in_string = not in_string; out.append(ch); continue
        if in_string and ch in "\n\r\t":
            out.append({"\n": "\\n", "\r": "\\r", "\t": "\\t"}[ch]); continue
        out.append(ch)
    return "".join(out)


def extract_angles(mail: dict) -> list[dict]:
    from openai import OpenAI
    if not omniroute_up():
        raise SystemExit("OmniRoute is not running. Start it with: cd ~ && omniroute serve")
    client = OpenAI(api_key="local", base_url=OMNIROUTE_BASE)
    # Explicit replacement, not .format(): the prompt contains a literal JSON example and every
    # brace in it would be read as a placeholder.
    prompt = (PROMPT
              # Who this is for. One paragraph in knowledge/WHO.md, written in phase 1. Without it
              # every idea comes back generic, because the model has nothing to aim at.
              .replace("__WHO__", _who())
              .replace("__SUBJECT__", mail["subject"][:200])
              .replace("__SENDER__", mail["sender"][:120])
              # free-tier context budget; the angle is always near the top of a marketing email
              .replace("__BODY__", mail["body"][:6000]))
    for attempt in range(1, 4):
        try:
            resp = client.chat.completions.create(
                model="auto",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
            )
            raw = (resp.choices[0].message.content or "").strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
            parsed = json.loads(repair_control_chars(raw))
            if isinstance(parsed, list):
                out = []
                for p in parsed:
                    if not isinstance(p, dict) or not p.get("angle"):
                        continue
                    for k in ("angle", "for_them", "hook", "why", "kind"):
                        if k in p:
                            p[k] = sanitize(p[k])
                    # Facts are the entire point of a story card: without the numbers nobody can
                    # make the reel, and he will not go digging for them in an email from last week.
                    p["facts"] = [sanitize(f) for f in (p.get("facts") or []) if isinstance(f, str)]
                    out.append(p)
                return out
        except Exception as e:  # noqa: BLE001
            if attempt == 3:
                print(f"    could not read: {str(e)[:100]}", file=sys.stderr)
    return []


def q(value: str | None) -> str:
    if value is None or value == "":
        return "null"
    return "'" + str(value).replace("'", "''") + "'"


def file_ideas(ideas: list[dict]) -> int:
    """File as IDEAS, never as scripts. These are unproven angles from someone else's audience;
    they earn their way onto the board by being picked, not by arriving pre-written."""
    if not ideas:
        return 0
    base = run_sql(
        "select coalesce(min(position), 0) as p from public.content_cards "
        f"where agency_id = '{AGENCY_ID}' and stage = 'ideas'"
    )[0]["p"]
    values = []
    for i, idea in enumerate(ideas):
        facts = idea.get("facts") or []
        is_story = (idea.get("kind") or "").lower() == "story"
        notes = "\n".join(filter(None, [
            f"{'What happened' if is_story else 'Angle'}: {idea.get('angle')}",
            ("\nThe facts, from the email:\n" + "\n".join(f"  - {f}" for f in facts))
            if facts else None,
            f"\nWhy it is worth making: {idea.get('why')}" if idea.get("why") else None,
            f"\nSeen in: {idea.get('source_subject')}" if idea.get("source_subject") else None,
            f"From: {idea.get('source_sender')}" if idea.get("source_sender") else None,
        ]))
        values.append("(" + ",".join([
            q(AGENCY_ID), "'ideas'", str(base - (i + 1)),
            q((idea.get("for_them") or idea.get("angle"))[:200]),
            q(idea.get("hook")), q(notes),
            q(f"competitor email {datetime.now().strftime('%Y-%m-%d')}"),
            "'agent:email_intel'",
        ]) + ")")
    run_sql(
        "insert into public.content_cards "
        "(agency_id, stage, position, title, hook, notes, source, created_by) "
        f"values {', '.join(values)}"
    )
    return len(values)


def main() -> int:
    global PROJECT_REF, AGENCY_ID
    PROJECT_REF = env_value("SUPABASE_PROJECT_REF") or ""
    AGENCY_ID = env_value("CONTENT_AGENCY_ID") or ""
    if not PROJECT_REF or not AGENCY_ID:
        raise SystemExit(
            "SUPABASE_PROJECT_REF and CONTENT_AGENCY_ID must be set in .env (see phase 4)")
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=3)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-json", default=None,
                    help="analyse emails from a JSON file instead of IMAP")
    ap.add_argument("--min-strength", type=int, default=3,
                    help="only file ideas at or above this strength")
    args = ap.parse_args()

    if args.from_json:
        mails = json.loads(Path(args.from_json).read_text())
    else:
        mails = fetch_emails(args.days)

    if not mails:
        print(f"no emails in the {LABEL} label in the last {args.days} days")
        return 0
    print(f"reading {len(mails)} competitor email(s)")

    ideas: list[dict] = []
    for m in mails:
        print(f"  {m['subject'][:70]}")
        for idea in extract_angles(m):
            idea["source_subject"] = m["subject"][:200]
            idea["source_sender"] = m["sender"][:120]
            ideas.append(idea)
            star = "*" * int(idea.get("strength") or 0)
            print(f"    {star:5s} {str(idea.get('for_them'))[:88]}")

    strong = [i for i in ideas if int(i.get("strength") or 0) >= args.min_strength]
    print(f"\n{len(ideas)} angles found, {len(strong)} at strength {args.min_strength} or above")

    if args.dry_run:
        print("dry run, nothing filed")
        return 0
    n = file_ideas(strong)
    print(f"filed {n} ideas on the board at /content?tab=board under Ideas")
    return 0


if __name__ == "__main__":
    sys.exit(main())
