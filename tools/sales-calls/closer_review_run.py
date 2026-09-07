#!/usr/bin/env python3
"""Review every unreviewed closer call and write the results back for the Closer HQ.

This is the nightly job. It runs `closer_calls_sync.py` to pull any new post-call form
submission and its Fathom transcript, then for each pending call runs one headless
Claude pass over the transcript and appends the result to the `_call_reviews` tab of
the forms sheet, which the Closer HQ scoreboard reads.

    python3 tools/sales-calls/closer_review_run.py                 # the nightly run
    python3 tools/sales-calls/closer_review_run.py --dry-run       # show what it would review
    python3 tools/sales-calls/closer_review_run.py --limit 1       # one call, for a test
    python3 tools/sales-calls/closer_review_run.py --model opus    # deeper (and pricier) pass

Model note: this runs through the local `claude` CLI, which uses your Claude
subscription. It never touches ANTHROPIC_API_KEY or any paid API key, so a run costs
plan usage, not money. One call is roughly one 60-minute transcript in and about a
page out; the default model is Sonnet to keep a 6-call night cheap.

Each review is written once. A call already in `_call_reviews` is skipped, so the job
is safe to run twice in a day, and safe to re-run after a failure.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from closer_sheet import ensure_reviews_tab, sheets_session, write_review  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/
SYNC = ROOT / "tools" / "sales-calls" / "closer_calls_sync.py"
DOCTRINE = ROOT / "sops" / "sales_call_review.md"
# The client's commercial terms in plain sentences: price, tiers, payment plans,
# deposits, any revenue share. The reviewer cannot judge a close it does not understand,
# and terms baked into this file would be the last client's.
OFFER_FILE = ROOT / "knowledge" / "OFFER.md"
# A transcript runs 50-70k characters. Claude reads the file itself, so the prompt
# stays small and the model gets the whole call rather than a truncated slice.
PROMPT = """Read the sales call transcript at {transcript} in full, then review it.

Context you already have from the closer's own post-call form (do not repeat it back, use it):
- Closer: {closer}
- Prospect: {lead}
- Outcome they logged: {outcome}
- Cash collected: {cash}
- Contract value: {deal_value}
- Objections they logged: {objections}
- What they said they struggled with: {struggle}
- What they said would have improved it: {improve_close}

The offer being sold on this call:
{offer}

The review doctrine is at {doctrine} if it exists. Follow it.

Return ONE JSON object and nothing else, no markdown fence, with exactly these keys:
  "summary": 3-5 sentences on what actually happened on this call, in order: how they
      framed it, what the prospect wanted, where the price landed, how it ended. Name the
      real block if there was one. Quote the prospect where a quote says it best.
  "feedback": the coaching, 120 to 220 words, addressed to the closer as "you". Lead with the
      single highest-leverage fix, cite a timestamp from the transcript for each point, and
      end with the one thing to do differently on the next call. Say what went well only if
      it genuinely did, in one sentence.
  "scores": an object with integer 0 to 10 keys "discovery", "pitch", "price", "close",
      "followup". 5 is competent, 8+ is excellent, be honest and use the whole range.

No emojis. No em dashes or en dashes anywhere in your output.
"""


def run_sync(limit: int, include_all: bool) -> dict:
    out = Path(tempfile.gettempdir()) / "closer_pending.json"
    cmd = [sys.executable, str(SYNC), "--json", str(out)]
    if include_all:
        cmd.append("--all")
    if limit:
        cmd += ["--limit", str(limit)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(proc.stdout)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        raise SystemExit("sync failed")
    return json.loads(out.read_text())


def parse_review(text: str) -> dict | None:
    """Pull the JSON object out of the model's reply, fenced or bare."""
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    blob = fence.group(1) if fence else None
    if blob is None:
        start = text.find("{")
        if start < 0:
            return None
        try:
            blob, _ = json.JSONDecoder().raw_decode(text[start:])
            return blob if isinstance(blob, dict) else None
        except json.JSONDecodeError:
            return None
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def claude_bin() -> str:
    """Absolute path to the claude CLI.

    launchd runs this job with a minimal PATH that does not include the node bin
    directories, so a bare "claude" resolves under an interactive shell and fails
    at 21:30. Resolve it here, and let CLAUDE_BIN override.
    """
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


def review_one(call: dict, model: str, timeout: int) -> dict | None:
    if not OFFER_FILE.exists():
        raise SystemExit(
            f"{OFFER_FILE} is missing. Write the offer being sold in plain sentences: price, "
            "tiers, payment plans, deposits, and any revenue share. Reviews are meaningless "
            "without it, because the model cannot tell a good close from a bad one.")
    prompt = PROMPT.format(
        offer=OFFER_FILE.read_text().strip(),
        transcript=ROOT / call["transcript"],
        doctrine=DOCTRINE,
        closer=call.get("closer") or "unknown",
        lead=call.get("lead") or "unknown",
        outcome=call.get("outcome") or "unknown",
        cash=call.get("cash") or "none logged",
        deal_value=call.get("deal_value") or "none logged",
        objections=call.get("objections") or "none logged",
        struggle=call.get("struggle") or "none logged",
        improve_close=call.get("improve_close") or "none logged",
    )
    cmd = [claude_bin(), "-p", prompt, "--model", model,
           "--allowed-tools", "Read", "--add-dir", str(ROOT / "sales-calls")]
    # The CLI must run on your subscription. If a paid key is present in the
    # environment the CLI would bill it, so it is removed from the child env.
    env = {k: v for k, v in os.environ.items()
           if k not in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "OPENAI_API_KEY")}
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout,
                          cwd=str(ROOT), env=env)
    if proc.returncode != 0:
        print(f"  claude failed ({proc.returncode}): {proc.stderr.strip()[:300]}", file=sys.stderr)
        return None
    review = parse_review(proc.stdout)
    if review is None:
        print(f"  could not parse a review out of: {proc.stdout.strip()[:300]}", file=sys.stderr)
    return review


def clean(text: str) -> str:
    """Strip the dash characters the house style bans, in case the model slips."""
    return str(text or "").replace("—", ", ").replace("–", "-").strip()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=0, help="review at most N calls this run")
    # Sonnet only. Reviews are volume work; the expensive models are reserved for
    # judgment you ask for directly.
    ap.add_argument("--model", default="sonnet", choices=["sonnet", "haiku"],
                    help="claude model (sonnet by default; opus and fable are off limits here)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds per call review")
    ap.add_argument("--all", action="store_true", help="re-review calls that already have a review")
    ap.add_argument("--dry-run", action="store_true", help="sync and list, review nothing")
    args = ap.parse_args()

    payload = run_sync(args.limit, args.all)
    pending, needs_link = payload["pending"], payload["needs_link"]
    if needs_link:
        print(f"\n{len(needs_link)} call(s) have no recording link and cannot be reviewed:")
        for c in needs_link:
            print(f"  {c['submitted']}  {c['closer']}  {c['lead']}  ({c['outcome']})")
    if not pending:
        print("\nNothing to review.")
        return
    if args.dry_run:
        print(f"\n--dry-run: {len(pending)} call(s) would be reviewed with {args.model}.")
        return

    sess = sheets_session()
    ensure_reviews_tab(sess)
    done = 0
    for call in pending:
        print(f"\nreviewing {call['lead']} ({call['closer']}, {call['outcome']}) with {args.model}...")
        try:
            review = review_one(call, args.model, args.timeout)
        except subprocess.TimeoutExpired:
            print("  timed out", file=sys.stderr)
            continue
        if not review or not review.get("summary"):
            continue
        scores = {k: v for k, v in (review.get("scores") or {}).items() if isinstance(v, int)}
        write_review(sess, {
            "response_id": call["response_id"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "call_date": call["submitted"],
            "closer": call["closer"],
            "lead": call["lead"],
            "summary": clean(review.get("summary")),
            "feedback": clean(review.get("feedback")),
            "scores": scores,
            "transcript": call["transcript"],
            "share_url": call["share_url"],
        })
        done += 1
        print(f"  written. scores: {scores}")

    print(f"\n{done}/{len(pending)} reviewed. They are live on the Closer HQ scoreboard.")


if __name__ == "__main__":
    main()
