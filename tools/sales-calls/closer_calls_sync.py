#!/usr/bin/env python3
"""Pull every new closer post-call form submission and its Fathom transcript.

The closer post-call form asks for the call
recording link. Its responses live in the forms platform's Google Sheet, tab
`r_<form id>`, with the raw answers as JSON in column C. This script reads that tab,
pulls the transcript for any response carrying a Fathom share link, and writes it to
sales-calls/transcripts/ using the same file shape as fathom_pull_transcript.py.

It then prints (or writes with --json) the list of calls that still need a review, so
the nightly Claude run knows exactly what to work on:

    python3 tools/sales-calls/closer_calls_sync.py                     # sync + list pending
    python3 tools/sales-calls/closer_calls_sync.py --json pending.json # for the nightly runner
    python3 tools/sales-calls/closer_calls_sync.py --all               # ignore existing reviews

A response with no recording link is reported as `needs_link` rather than silently
skipped: the closer has to go back and add it, and that is worth seeing.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closer_sheet import (  # noqa: E402
    FORM_TAB, MANUAL_HEADER, MANUAL_TAB, REVIEWS_TAB, ensure_reviews_tab, read_values,
    sheets_session,
)
from fathom_pull_transcript import SHARE_RE, pull  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
TRANSCRIPTS = ROOT / "sales-calls" / "transcripts"


def normalize(row: list[str]) -> dict | None:
    if len(row) < 3 or not row[1]:
        return None
    try:
        answers = json.loads(row[2] or "{}")
    except json.JSONDecodeError:
        answers = {}
    lead = str(answers.get("lead_name", "")).strip()
    link = str(answers.get("call_link", "")).strip()
    share = SHARE_RE.search(link)
    return {
        "response_id": row[1],
        "submitted": row[0],
        "lead": lead,
        "closer": str(answers.get("closer", "")).strip(),
        "outcome": str(answers.get("outcome", "")).strip(),
        "cash": str(answers.get("cash", "")).strip(),
        "deal_value": str(answers.get("deal_value", "")).strip(),
        "objections": str(answers.get("objections", "")).strip(),
        "struggle": str(answers.get("struggle", "")).strip(),
        "improve_close": str(answers.get("improve_close", "")).strip(),
        "gap": str(answers.get("gap", "")).strip(),
        "share_url": share.group(0) if share else "",
        "raw_link": link,
        "is_test": bool(re.search(r"test", lead, re.I)),
    }


def normalize_manual(row: list[str]) -> dict:
    """A hand-added call, on the _calls_manual tab, in the same shape as a form response.

    Its id is prefixed so it can never collide with a form response id, and so the
    reviews tab keys the two sources apart.
    """
    d = dict(zip(MANUAL_HEADER, row + [""] * len(MANUAL_HEADER)))
    return {
        "response_id": "manual:" + d["call_id"],
        "submitted": d["started_at"],
        "lead": d["lead"],
        "closer": d["closer"],
        "outcome": d["outcome"],
        "cash": d["cash"],
        "deal_value": d["deal_value"],
        "objections": d["objections"],
        "struggle": "",
        "improve_close": "",
        "gap": d["notes"],
        "share_url": d["share_url"],
        "raw_link": d["share_url"],
        "is_test": False,
    }


def transcript_for(share_url: str, force: bool) -> Path | None:
    """Pull the transcript, or return the existing file if it is already on disk."""
    out = pull(share_url, force=False)
    if out is not None:
        return out
    token = SHARE_RE.search(share_url).group(1)
    for path in TRANSCRIPTS.glob("*.md"):
        if token in path.read_text(errors="replace")[:600]:
            return path
    return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", type=Path, help="write the pending list to this file")
    ap.add_argument("--all", action="store_true", help="include calls that already have a review")
    ap.add_argument("--limit", type=int, default=0, help="cap how many pending calls are returned")
    args = ap.parse_args()

    sess = sheets_session()
    ensure_reviews_tab(sess)
    rows = read_values(sess, f"{FORM_TAB}!A2:C100000")
    manual_rows = read_values(sess, f"{MANUAL_TAB}!A2:M100000")
    reviewed = {r[0] for r in read_values(sess, f"{REVIEWS_TAB}!A2:A100000") if r}

    # A call logged on the form wins over a hand-added row for the same recording.
    form_links = set()
    for row in rows:
        c = normalize(row)
        if c and c["share_url"]:
            form_links.add(SHARE_RE.search(c["share_url"]).group(1))

    calls = [normalize(r) for r in rows]
    for r in manual_rows:
        if not r or not r[0]:
            continue
        c = normalize_manual(r)
        token = SHARE_RE.search(c["share_url"]) if c["share_url"] else None
        if token and token.group(1) in form_links:
            continue
        calls.append(c)

    pending, needs_link, skipped = [], [], 0
    for call in calls:
        if not call or call["is_test"]:
            skipped += 1
            continue
        if call["response_id"] in reviewed and not args.all:
            continue
        if not call["share_url"]:
            needs_link.append(call)
            continue
        path = transcript_for(call["share_url"], args.all)
        if path is None:
            print(f"WARN  no transcript for {call['lead']} ({call['share_url']})", file=sys.stderr)
            continue
        call["transcript"] = str(path.relative_to(ROOT))
        pending.append(call)

    if args.limit:
        pending = pending[: args.limit]

    payload = {"pending": pending, "needs_link": needs_link}
    if args.json:
        args.json.write_text(json.dumps(payload, indent=1))

    print(f"{len(rows)} form responses + {len(manual_rows)} manual, {skipped} test/blank skipped, {len(reviewed)} already reviewed")
    for c in pending:
        print(f"PENDING  {c['submitted']}  {c['closer']:8s}  {c['lead'][:24]:24s}  {c['outcome'][:22]:22s}  {c['transcript']}")
    for c in needs_link:
        print(f"NEEDS LINK  {c['submitted']}  {c['closer']:8s}  {c['lead'][:24]:24s}  {c['outcome']}")


if __name__ == "__main__":
    main()
