#!/usr/bin/env python3
"""Read every sales call at once and say what the marketing should change.

    python3 tools/sales-calls/sales_call_intelligence.py                # since the last run
    python3 tools/sales-calls/sales_call_intelligence.py --all          # every transcript ever
    python3 tools/sales-calls/sales_call_intelligence.py --since 2026-08-23
    python3 tools/sales-calls/sales_call_intelligence.py --dry-run      # print, write nothing
    python3 tools/sales-calls/sales_call_intelligence.py --model opus   # deeper pass

WHY THIS IS NOT closer_review_run.py. That job reviews ONE call for ONE closer and answers
"how did you do". Useful to the closer, useless to the marketing, because the thing worth
knowing is never in a single call: it is the sentence nine leads in a row used, the belief
they all walked in with, and the minute of the webinar that put it there. Nothing was
reading across them. This does.

WHAT IT IS FOR: what the calls teach should feed the whole marketing and sales process, the
emails, the video scripts, the webinar slides. So the output is not a summary. Every finding
has to name the thing to change and where it goes, or it does not earn its place.

HOW IT RUNS. Through the local `claude` CLI on your own subscription, exactly like the
nightly review, so a run costs plan usage and not money. ⛔It strips ANTHROPIC_API_KEY and
OPENAI_API_KEY out of the child environment so the CLI cannot bill a paid key by accident.

Output goes to `sales-calls/briefs/<date>-intelligence.md` and, unless --dry-run, the
`_call_intel` tab of the forms sheet so the HQ can read it later.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closer_sheet import append_values, ensure_tab, read_values, sheets_session  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
TRANSCRIPTS = ROOT / "sales-calls" / "transcripts"
BRIEFS = ROOT / "sales-calls" / "briefs"
# ⚠️WITHOUT THIS THE BRIEF INVENTS PROBLEMS. On the first run of this tool for one client it
# reported four deliberate decisions as defects (multiple live prices, no price on the
# webinar, an automation claim, a scarcity line) and every one had to be corrected by hand.
# A finding that re-opens a settled decision buries the real ones. Write the decisions the
# client has already made, and does not want re-argued, into this file.
SETTLED = ROOT / "knowledge" / "SETTLED_DECISIONS.md"
STATE = ROOT / ".tmp" / "sales_intel_state.json"
INTEL_TAB = "_call_intel"
INTEL_COLS = ["generated_at", "calls_read", "window", "model", "brief_path", "headline"]

# Kept deliberately tight. A prompt that asks for "insights" gets adjectives; a prompt that
# names the artefact each finding has to change gets something actionable the same day.
PROMPT = """You are reading {n} real sales call transcripts for this offer:

{offer}

And this is who buys it:

{audience}

The transcripts are these files. Read every one in full before writing anything:
{files}

⚠️FIRST, read {settled} in full. It lists the decisions already made and not up for re-opening,
and it names what IS worth reporting. A brief that proposes undoing a settled decision wastes
time and buries the findings that matter. If you believe something in that
file has stopped being true, say so explicitly and show the evidence; do not quietly argue
against it.

Your job is NOT to review the closers. It is to find what the whole set says that no single
call could, and turn it into changes to the marketing and the sales process.

Rules:
- Every claim must be grounded in at least two different calls. Say which, by lead name.
- Quote the lead's own words. Their phrasing is the asset; your paraphrase is not.
- If the evidence is thin, say so rather than rounding it up. "Two of {n}" is a real finding
  when it is stated as two of {n}.
- No hedging and no filler. No emojis. No em dashes or en dashes anywhere.

Return a markdown brief with exactly these sections:

## The one thing
The single highest-value change, and what it is worth. One paragraph.

## What they believed walking in
What the webinar actually installed, right and wrong. Where a lead arrived with a wrong idea,
name the slide or claim that probably caused it.

## The objections, in rank order
For each: how many calls it appeared in, the exact words leads use, when in the call it lands,
and what would have to change UPSTREAM so it never gets raised on a call again.

## The words they use
The phrases that keep recurring, verbatim, grouped by what they are describing (their
situation, their fear, their goal, the money). This section is raw material for copy, so give
quantity over commentary.

## Where deals die
The specific moment and reason. Separate "could not afford it" from "was not sold".

## Change this week
A numbered list. Each item names the artefact (a webinar slide, an email, a video script, the
call opener, the prep form, the pricing page), what to change, and the line of evidence from
the calls that justifies it. Be specific enough that somebody could do it without asking you
a question.

## What we still cannot see
What the transcripts do not answer, and what would have to be captured to answer it.
"""


def claude_bin() -> str:
    """launchd runs with a minimal PATH, so a bare `claude` will not resolve at 21:30."""
    override = os.environ.get("CLAUDE_BIN")
    if override:
        return override
    found = shutil.which("claude")
    if found:
        return found
    for cand in (Path.home() / ".hermes/node/bin/claude",
                 Path("/opt/homebrew/bin/claude"),
                 Path.home() / ".local/bin/claude"):
        if cand.exists():
            return str(cand)
    raise SystemExit("claude CLI not found. Set CLAUDE_BIN to its full path.")


def transcripts(since: str | None) -> list[Path]:
    if not TRANSCRIPTS.exists():
        return []
    out = []
    for f in sorted(TRANSCRIPTS.glob("*.md")):
        # Files are named <date>_<prospect-slug>_<recording-id>.md
        m = re.match(r"(\d{4}-\d{2}-\d{2})", f.name)
        if since and (not m or m.group(1) < since):
            continue
        out.append(f)
    return out


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--since", help="only calls on or after this date (YYYY-MM-DD)")
    ap.add_argument("--all", action="store_true", help="every transcript, ignoring the watermark")
    ap.add_argument("--model", default="sonnet", help="sonnet (default) or opus for a deeper pass")
    ap.add_argument("--timeout", type=int, default=1800, help="seconds")
    ap.add_argument("--dry-run", action="store_true", help="print, write nothing to the sheet")
    args = ap.parse_args()

    state = load_state()
    since = None if args.all else (args.since or state.get("last_since"))
    files = transcripts(since)
    # ⚠️A cross-call brief needs a set to compare. One transcript produces a call review
    # dressed up as strategy, which is worse than nothing because it reads as a pattern.
    if len(files) < 3:
        print(f"only {len(files)} transcript(s) in scope; need at least 3 for a pattern. "
              f"Use --all to read everything.")
        return

    listing = "\n".join(f"  - {f}" for f in files)
    offer = ROOT / "knowledge" / "OFFER.md"
    audience = ROOT / "knowledge" / "AUDIENCE.md"
    for f in (offer, audience):
        if not f.exists():
            raise SystemExit(
                f"{f} is missing. The brief is only as good as what it knows about the offer and "
                "who buys it. OFFER.md: price, tiers, how it is sold. AUDIENCE.md: who the buyers "
                "actually are, in plain language, from the calls themselves.")
    prompt = PROMPT.format(
        n=len(files), files=listing, settled=SETTLED,
        offer=offer.read_text().strip(), audience=audience.read_text().strip())
    print(f"reading {len(files)} transcripts with {args.model}"
          f"{f' since {since}' if since else ''}...")

    cmd = [claude_bin(), "-p", prompt, "--model", args.model,
           "--allowed-tools", "Read,Glob,Grep",
           "--add-dir", str(ROOT / "sales-calls"), "--add-dir", str(ROOT / "directives")]
    # ⛔The CLI must run on your subscription. A paid key in the environment would be
    # billed, so it is stripped from the child.
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY")}
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout,
                          cwd=str(ROOT), env=env)
    if proc.returncode != 0:
        sys.exit(f"claude failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    brief = proc.stdout.strip().replace("—", ", ").replace("–", "-")
    if len(brief) < 400:
        sys.exit(f"brief came back too short to trust:\n{brief[:300]}")

    BRIEFS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc)
    path = BRIEFS / f"{stamp:%Y-%m-%d}-intelligence.md"
    header = (f"# Sales call intelligence, {stamp:%d %b %Y}\n\n"
              f"{len(files)} calls read"
              f"{f', from {since} on' if since else ', all time'}. "
              f"Model {args.model}.\n\n---\n\n")
    path.write_text(header + brief + "\n")
    print(f"\nwritten: {path}")

    headline = ""
    m = re.search(r"##\s*The one thing\s*\n+(.+?)(?:\n\s*\n|\n##)", brief, re.S)
    if m:
        headline = " ".join(m.group(1).split())[:900]

    if args.dry_run:
        print("\n--dry-run: nothing written to the sheet.\n")
        print(brief[:1800])
        return

    sess = sheets_session()
    ensure_tab(sess, INTEL_TAB, INTEL_COLS)
    append_values(sess, f"{INTEL_TAB}!A:F",
                  [[stamp.isoformat(timespec="seconds"), str(len(files)),
                    since or "all time", args.model, str(path.relative_to(ROOT)), headline]])
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"last_run": stamp.isoformat(timespec="seconds"),
                                 "last_since": since, "calls_read": len(files)}, indent=1))
    print(f"logged to {INTEL_TAB}.")
    if headline:
        print(f"\nTHE ONE THING: {headline[:400]}")


if __name__ == "__main__":
    main()
