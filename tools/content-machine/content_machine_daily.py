#!/usr/bin/env python3
"""Run the whole content machine once: scrape, parse, script.

  1. SCRAPE   every ACTIVE creator on the roster (Instagram, free Apify tokens)
  2. PARSE    outliers and the patterns behind them (tools/content-machine/content_signal_parser.py)
  3. SCRIPT   today's reels from the Brain plus that signal (tools/content-machine/content_scripter.py)

The roster lives in Supabase, so pausing a creator in the dashboard under Content > Creators genuinely
takes them out of tomorrow's run. Nothing here reads a local list.

Everything runs on FREE keys (CLAUDE.md money rule): free Apify tokens for scraping, free Gemini
for the two agent passes. No paid API is ever called.

A stage that fails does not silently produce a thin result: scraping failures are counted and
reported, and a failed parse or script stops the run with a non-zero exit so a scheduler notices.

Usage:
    python3 tools/content-machine/content_machine_daily.py
    python3 tools/content-machine/content_machine_daily.py --scripts 5
    python3 tools/content-machine/content_machine_daily.py --skip-scrape   # reuse today's scrape
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root, two levels above tools/<group>/


def _cfg(key: str) -> str:
    """One required setting, from the environment or the repo's .env. Fails loudly: a blank
    project ref or workspace id would silently read an empty board rather than error."""
    v = os.environ.get(key)
    if not v:
        for name in (".env", ".env.local"):
            f = ROOT / name
            if not f.exists():
                continue
            for line in f.read_text().split("\n"):
                line = line.strip()
                if line.startswith(f"{key}=") and not line.startswith("#"):
                    v = line.split("=", 1)[1].strip().strip("\"'")
                    break
            if v:
                break
    if not v:
        raise SystemExit(f"{key} must be set, in the environment or in {ROOT}/.env")
    return v


# The stages live next to each other under tools/, so each call names its own group. They used
# to share one folder; a single EXEC path silently pointed every stage at a directory that does
# not exist in this layout, and the whole chain failed at the first step.
TOOLS = ROOT / "tools"
CONTENT = TOOLS / "content-machine"
INSTAGRAM = TOOLS / "instagram"
PY = sys.executable
# Per client, from the repo's .env, never hardcoded. One operator runs several clients and a
# ref left over from the last one writes this client's scripts into that client's board.
#   SUPABASE_PROJECT_REF=  the client's Supabase project ref
#   CONTENT_AGENCY_ID=     the client's workspace id on it
PROJECT_REF = _cfg("SUPABASE_PROJECT_REF")
AGENCY_ID = _cfg("CONTENT_AGENCY_ID")


def env_value(key: str) -> str:
    with open(ROOT / ".env") as f:
        for line in f:
            if line.startswith(f"{key}="):
                return line.split("=", 1)[1].strip()
    raise SystemExit(f"{key} not found in .env")


def run_sql(sql: str):
    req = urllib.request.Request(
        f"https://api.supabase.com/v1/projects/{PROJECT_REF}/database/query",
        data=json.dumps({"query": sql}).encode(),
        headers={
            "Authorization": f"Bearer {env_value('SUPABASE_ACCESS_TOKEN')}",
            "Content-Type": "application/json",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
            ),
        },
        method="POST",
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def active_creators() -> list[dict]:
    """Everyone the operator currently wants collected, whatever job they do."""
    return run_sql(
        "select handle, name, instagram, role from public.content_creators "
        f"where agency_id = '{AGENCY_ID}' and status = 'active' and instagram is not null "
        "order by role, name"
    )


def stage(title: str) -> None:
    print(f"\n{'=' * 62}\n{title}\n{'=' * 62}")


def scrape(creators: list[dict]) -> tuple[int, list[str]]:
    ok, failed = 0, []
    for i, c in enumerate(creators, 1):
        print(f"[{i}/{len(creators)}] {c['name']} ({c['instagram']})")
        # scrape_creator_deep writes to .tmp/<username>, so the Instagram handle is what names
        # the folder. The parser resolves the same way, which keeps the two in step even where a
        # roster handle and an Instagram handle differ.
        proc = subprocess.run(
            [PY, str(INSTAGRAM / "scrape_creator_deep.py"), "--username", c["instagram"],
             "--skip-tiktok", "--ig-posts", "50"],
            cwd=ROOT, capture_output=True, text=True,
        )
        if proc.returncode == 0:
            ok += 1
        else:
            failed.append(c["name"])
            print(f"  failed: {(proc.stderr or proc.stdout).strip().splitlines()[-1:]}")
    return ok, failed


def record_scrape(creators: list[dict]) -> None:
    """Stamp last_scraped_at so the Creators tab shows when each creator was last collected."""
    handles = ",".join("'" + c["handle"].replace("'", "''") + "'" for c in creators)
    run_sql(
        "update public.content_creators set last_scraped_at = now(), updated_at = now() "
        f"where agency_id = '{AGENCY_ID}' and handle in ({handles})"
    )


def step(name: str, argv: list[str]) -> None:
    proc = subprocess.run([PY, *argv], cwd=ROOT)
    if proc.returncode != 0:
        raise SystemExit(f"{name} failed with exit code {proc.returncode}")


def main():
    ap = argparse.ArgumentParser()
    # Reels and YouTube are prompted differently and shot differently, so they are counted
    # separately. A sensible daily target is 6: four reels and two long form.
    ap.add_argument("--reels", type=int, default=4, help="Instagram reel scripts")
    ap.add_argument("--youtube", type=int, default=2, help="YouTube scripts")
    ap.add_argument("--skip-scrape", action="store_true", help="reuse whatever is already scraped")
    ap.add_argument("--min-multiple", type=float, default=2.0)
    ap.add_argument("--no-email", action="store_true", help="skip the morning email")
    args = ap.parse_args()

    started = datetime.now(timezone.utc)
    print(f"content machine, {started.strftime('%Y-%m-%d %H:%M')} UTC")

    creators = active_creators()
    if not creators:
        raise SystemExit("no active creators on the roster, nothing to do")

    if args.skip_scrape:
        stage(f"1. SCRAPE  skipped, reusing what is on disk ({len(creators)} active creators)")
    else:
        stage(f"1. SCRAPE  {len(creators)} active creators on free Apify tokens")
        ok, failed = scrape(creators)
        print(f"\nscraped {ok} of {len(creators)}")
        if failed:
            print(f"failed: {', '.join(failed)}")
        if ok == 0:
            raise SystemExit("every scrape failed, stopping before the agents run")
        record_scrape([c for c in creators if c["name"] not in failed])

    stage("2. PARSE  outliers and the patterns behind them, free Gemini")
    step("parser", [str(CONTENT / "content_signal_parser.py"), "--min-multiple", str(args.min_multiple)])

    total = args.reels + args.youtube
    stage(f"3. SCRIPT  {args.reels} reels + {args.youtube} YouTube from the Brain plus today's "
          f"signal, free Gemini")
    # --count was passed here until 2026-07-30 and the scripter has never accepted it, so stage 3
    # died on every unattended run. Flags are mirrored from content_scripter.py's parser.
    step("scripter", [str(CONTENT / "content_scripter.py"),
                      "--reels", str(args.reels), "--youtube", str(args.youtube)])

    # The email is the point of the 7am run: a board he has to remember to open is a board he does
    # not read. A send failure must not fail the run, the scripts are already safely on the board.
    if not args.no_email:
        stage("4. EMAIL  the morning's scripts, hooks first")
        try:
            step("email", [str(CONTENT / "content_machine_email.py")])
        except SystemExit as e:
            print(f"  scripts are on the board but the email did not send: {e}")

    mins = (datetime.now(timezone.utc) - started).total_seconds() / 60
    print(f"\ndone in {mins:.1f} min, {total} scripts. Board: "
          f"{_cfg('CONTENT_APP_URL').rstrip('/')}/content?tab=board under Scripted.")


if __name__ == "__main__":
    main()
