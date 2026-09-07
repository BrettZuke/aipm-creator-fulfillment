#!/usr/bin/env python3
"""
Scrape a single Instagram creator for client-research / dossier purposes.

Pulls:
  1. Profile details (bio, followers, external URL, business category)
  2. Recent posts (captions, type, engagement, video URLs for reels)

Writes raw JSON to .tmp/{username}/profile.json and posts.json.

Usage:
    python3 tools/instagram/scrape_creator_dossier.py --username dllanpatel
    python3 tools/instagram/scrape_creator_dossier.py --username dllanpatel --posts 50

Apify actor: apify/instagram-scraper
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    from apify_client import ApifyClient
    from apify_client.errors import ApifyApiError
except ImportError:
    print("Error: apify-client not installed. Run: pip install apify-client", file=sys.stderr)
    sys.exit(1)


REPO_ROOT = Path(__file__).resolve().parent.parent
TMP_ROOT = REPO_ROOT / ".tmp"
CLAUDE_CONFIG = Path.home() / ".claude.json"


def load_alt_tokens() -> list[str]:
    """Every token in the shared Apify pool (.env pool + ~/.claude.json)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from apify_pool import apify_tokens
    return apify_tokens()


def run_actor_with_fallback(actor_id: str, run_input: dict, tokens: list[str]) -> tuple[list[dict], str | None]:
    """Try each token in sequence until one succeeds (returns items + token used)."""
    last_err: Exception | None = None
    for i, tok in enumerate(tokens):
        client = ApifyClient(tok)
        try:
            run = client.actor(actor_id).call(run_input=run_input)
            if not run:
                continue
            dataset_id = run.get("defaultDatasetId")
            if not dataset_id:
                continue
            items = list(client.dataset(dataset_id).iterate_items())
            return items, tok
        except ApifyApiError as e:
            msg = str(e)
            print(f"  [token {i+1}/{len(tokens)}] failed: {msg[:120]}", file=sys.stderr)
            last_err = e
            if "limit" in msg.lower() or "quota" in msg.lower() or "exceeded" in msg.lower():
                continue
            raise
    if last_err:
        raise last_err
    return [], None


def fetch_profile(username: str, tokens: list[str]) -> tuple[dict | None, str | None]:
    url = f"https://www.instagram.com/{username}/"
    run_input = {
        "directUrls": [url],
        "resultsType": "details",
        "resultsLimit": 1,
        "searchType": "user",
        "searchLimit": 1,
    }
    items, tok = run_actor_with_fallback("apify/instagram-scraper", run_input, tokens)
    return (items[0] if items else None), tok


def fetch_posts(username: str, limit: int, tokens: list[str]) -> tuple[list[dict], str | None]:
    url = f"https://www.instagram.com/{username}/"
    run_input = {
        "directUrls": [url],
        "resultsType": "posts",
        "resultsLimit": limit,
        "searchType": "user",
        "searchLimit": 1,
        "addParentData": False,
    }
    return run_actor_with_fallback("apify/instagram-scraper", run_input, tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape a single IG creator for dossier research")
    parser.add_argument("--username", required=True, help="IG username without @")
    parser.add_argument("--posts", type=int, default=30, help="Number of recent posts to pull")
    args = parser.parse_args()

    primary = os.environ.get("APIFY_API_TOKEN")
    alts = load_alt_tokens()
    tokens = [t for t in ([primary] + alts) if t]
    seen = set()
    tokens = [t for t in tokens if not (t in seen or seen.add(t))]
    if not tokens:
        print("Error: no Apify tokens available (.env or ~/.claude.json)", file=sys.stderr)
        return 1
    print(f"Loaded {len(tokens)} Apify token(s) for fallback")

    out_dir = TMP_ROOT / args.username
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"[1/2] Fetching profile @{args.username}...")
    profile, used_tok = fetch_profile(args.username, tokens)
    if not profile:
        print(f"Error: no profile returned for @{args.username}", file=sys.stderr)
        return 2
    profile_path = out_dir / "profile.json"
    profile_path.write_text(json.dumps(profile, indent=2, default=str))
    print(f"  Saved {profile_path.relative_to(REPO_ROOT)}")
    print(f"  Followers: {profile.get('followersCount', 'n/a'):,}" if isinstance(profile.get('followersCount'), int) else f"  Followers: {profile.get('followersCount', 'n/a')}")
    print(f"  Full name: {profile.get('fullName', 'n/a')}")
    bio = (profile.get('biography') or '').strip().replace('\n', ' | ')
    print(f"  Bio: {bio[:200]}")
    print(f"  External URL: {profile.get('externalUrl', 'n/a')}")

    print(f"\n[2/2] Fetching {args.posts} recent posts @{args.username}...")
    # Reuse the token that worked for the profile fetch if possible
    posts_tokens = [used_tok] + [t for t in tokens if t != used_tok] if used_tok else tokens
    posts, _ = fetch_posts(args.username, args.posts, posts_tokens)
    posts_path = out_dir / "posts.json"
    posts_path.write_text(json.dumps(posts, indent=2, default=str))
    print(f"  Saved {posts_path.relative_to(REPO_ROOT)} ({len(posts)} posts)")

    types: dict[str, int] = {}
    for p in posts:
        types[p.get("type", "Unknown")] = types.get(p.get("type", "Unknown"), 0) + 1
    print(f"  Type breakdown: {types}")

    summary = {
        "username": args.username,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "profile_path": str(profile_path.relative_to(REPO_ROOT)),
        "posts_path": str(posts_path.relative_to(REPO_ROOT)),
        "follower_count": profile.get("followersCount"),
        "post_count_returned": len(posts),
        "post_types": types,
        "bio": profile.get("biography"),
        "external_url": profile.get("externalUrl"),
        "full_name": profile.get("fullName"),
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(f"\nDone. Output in .tmp/{args.username}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
