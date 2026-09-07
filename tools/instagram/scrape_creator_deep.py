#!/usr/bin/env python3
"""
Deep multi-source creator scrape — IG (paginated), TikTok, YouTube — rotating tokens.

Pulls Instagram posts in date-windowed chunks to bypass the per-token MAX_PAID_DATASET_ITEMS
cap. Each token contributes ~25-30 posts; with 10 tokens we get up to ~250 historical posts.

Usage:
    python3 tools/scrape_creator_deep.py --username theirhandle \\
        --ig-posts 200 --tt-posts 80
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from apify_client import ApifyClient
    from apify_client.errors import ApifyApiError
except ImportError:
    print("Error: apify-client not installed", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_ROOT = REPO_ROOT / ".tmp"
CLAUDE_CONFIG = Path.home() / ".claude.json"


def load_alt_tokens() -> list[str]:
    """Every token in the shared Apify pool (.env pool + ~/.claude.json)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from apify_pool import apify_tokens
    return apify_tokens()


def get_all_tokens() -> list[str]:
    primary = os.environ.get("APIFY_API_TOKEN")
    alts = load_alt_tokens()
    raw = [t for t in ([primary] + alts) if t]
    seen: set[str] = set()
    return [t for t in raw if not (t in seen or seen.add(t))]


def run_actor_with_token(
    actor_id: str, run_input: dict, token: str, label: str = ""
) -> tuple[list[dict], bool]:
    """Returns (items, hit_limit_flag). hit_limit means quota issue; caller should retry next token."""
    client = ApifyClient(token)
    try:
        run = client.actor(actor_id).call(run_input=run_input)
        if not run:
            return [], False
        dataset_id = run.get("defaultDatasetId")
        if not dataset_id:
            return [], False
        items = list(client.dataset(dataset_id).iterate_items())
        return items, False
    except ApifyApiError as e:
        msg = str(e).lower()
        is_quota = any(k in msg for k in ("limit", "quota", "exceeded", "insufficient"))
        print(f"  [{label}] {str(e)[:140]}", file=sys.stderr)
        return [], is_quota


def fetch_ig_posts_deep(username: str, target: int, tokens: list[str]) -> list[dict]:
    """Pull IG posts in date-windowed chunks. Newest first; each call gets up to its token cap."""
    url = f"https://www.instagram.com/{username}/"
    all_items: list[dict] = []
    seen_shortcodes: set[str] = set()
    oldest_date: str | None = None
    token_idx = 0

    while len(all_items) < target and token_idx < len(tokens):
        run_input: dict = {
            "directUrls": [url],
            "resultsType": "posts",
            "resultsLimit": 50,
            "searchType": "user",
            "searchLimit": 1,
            "addParentData": False,
        }
        if oldest_date:
            run_input["onlyPostsNewerThan"] = "1900-01-01"  # accept all
            run_input["onlyPostsOlderThan"] = oldest_date

        tok = tokens[token_idx]
        items, hit_limit = run_actor_with_token(
            "apify/instagram-scraper", run_input, tok, f"ig posts tok#{token_idx+1}"
        )

        if not items:
            if hit_limit:
                print(f"  Token {token_idx+1} hit quota, rotating", file=sys.stderr)
                token_idx += 1
                continue
            else:
                print(f"  Token {token_idx+1} returned 0 items, stopping", file=sys.stderr)
                break

        new_count = 0
        for it in items:
            sc = it.get("shortCode")
            if not sc or sc in seen_shortcodes:
                continue
            seen_shortcodes.add(sc)
            all_items.append(it)
            new_count += 1

        if new_count == 0:
            print(f"  No new posts in batch (all duplicates). Stopping.", file=sys.stderr)
            break

        ts_list = [it.get("timestamp") for it in items if it.get("timestamp")]
        if ts_list:
            new_oldest = min(ts_list)
            if new_oldest == oldest_date:
                print(f"  Same oldest_date as last batch; stopping", file=sys.stderr)
                break
            oldest_date = new_oldest

        print(
            f"  Batch #{token_idx+1}: +{new_count} new (total {len(all_items)}, oldest now {oldest_date[:10] if oldest_date else 'n/a'})"
        )
        token_idx += 1

    return all_items[:target]


def fetch_ig_profile(username: str, tokens: list[str]) -> dict | None:
    url = f"https://www.instagram.com/{username}/"
    run_input = {
        "directUrls": [url],
        "resultsType": "details",
        "resultsLimit": 1,
        "searchType": "user",
        "searchLimit": 1,
    }
    for i, tok in enumerate(tokens):
        items, hit_limit = run_actor_with_token(
            "apify/instagram-scraper", run_input, tok, f"profile tok#{i+1}"
        )
        if items:
            return items[0]
        if not hit_limit:
            break
    return None


def fetch_tiktok(username: str, target: int, tokens: list[str]) -> list[dict]:
    run_input = {
        "profiles": [username],
        "resultsPerPage": min(target, 100),
        "shouldDownloadVideos": False,
        "shouldDownloadCovers": False,
        "shouldDownloadSubtitles": False,
    }
    for i, tok in enumerate(tokens):
        items, hit_limit = run_actor_with_token(
            "clockworks/tiktok-scraper", run_input, tok, f"tiktok tok#{i+1}"
        )
        if items:
            return items[:target]
        if not hit_limit:
            print(f"  TikTok actor returned 0 items on tok#{i+1}, trying next", file=sys.stderr)
            continue
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description="Deep multi-source creator scrape")
    parser.add_argument("--username", required=True)
    parser.add_argument("--ig-posts", type=int, default=150)
    parser.add_argument("--tt-posts", type=int, default=60)
    parser.add_argument("--skip-tiktok", action="store_true")
    parser.add_argument("--skip-ig", action="store_true")
    args = parser.parse_args()

    tokens = get_all_tokens()
    if not tokens:
        print("Error: no Apify tokens", file=sys.stderr)
        return 1
    print(f"Loaded {len(tokens)} Apify tokens for rotation")

    out_dir = TMP_ROOT / args.username
    out_dir.mkdir(parents=True, exist_ok=True)

    summary: dict = {"username": args.username, "scraped_at": datetime.now(timezone.utc).isoformat()}

    if not args.skip_ig:
        print(f"\n[IG] Profile for @{args.username}")
        profile = fetch_ig_profile(args.username, tokens)
        if profile:
            (out_dir / "profile.json").write_text(json.dumps(profile, indent=2, default=str))
            print(f"  Saved profile.json (followers: {profile.get('followersCount', 'n/a')})")
            summary["followers"] = profile.get("followersCount")
            summary["bio"] = profile.get("biography")

        print(f"\n[IG] Deep pull up to {args.ig_posts} posts...")
        posts = fetch_ig_posts_deep(args.username, args.ig_posts, tokens)
        (out_dir / "posts_deep.json").write_text(json.dumps(posts, indent=2, default=str))
        print(f"  Saved posts_deep.json ({len(posts)} posts)")
        summary["ig_posts"] = len(posts)
        if posts:
            dates = sorted(p.get("timestamp") for p in posts if p.get("timestamp"))
            print(f"  Date range: {dates[0][:10]} -> {dates[-1][:10]}")
            summary["ig_date_range"] = [dates[0][:10], dates[-1][:10]]

    if not args.skip_tiktok:
        print(f"\n[TikTok] Pulling up to {args.tt_posts} videos for @{args.username}...")
        tt = fetch_tiktok(args.username, args.tt_posts, tokens)
        (out_dir / "tiktok.json").write_text(json.dumps(tt, indent=2, default=str))
        print(f"  Saved tiktok.json ({len(tt)} videos)")
        summary["tiktok_posts"] = len(tt)

    (out_dir / "deep_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nDone. Output in .tmp/{args.username}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
