"""
Scrape cache — tracks which competitor videos/posts have already been used
to generate Dan's content so we never feed the same source material twice.

Cache file: .tmp/scraped_cache.json
Expiry: 90 days (content can resurface after that)
"""

import json
from pathlib import Path
from datetime import datetime, timedelta

BASE_DIR = Path(__file__).parent.parent
CACHE_FILE = BASE_DIR / ".tmp" / "scraped_cache.json"
EXPIRE_DAYS = 90


def load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text())
    except Exception:
        return {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, indent=2))


def mark_used(item_ids: list[str], metadata: dict = None) -> None:
    """Mark a list of IDs as used for generation."""
    cache = load_cache()
    now = datetime.utcnow().isoformat()
    for item_id in item_ids:
        if item_id:
            cache[item_id] = {"date": now, **(metadata or {})}
    save_cache(cache)


def filter_unseen(items: list[dict], id_field: str) -> tuple[list[dict], int]:
    """
    Remove items already in the cache (seen within EXPIRE_DAYS).
    Returns (unseen_items, skipped_count).
    """
    cache = load_cache()
    now = datetime.utcnow()
    unseen = []
    skipped = 0

    for item in items:
        item_id = str(item.get(id_field, "")).strip()
        if not item_id:
            unseen.append(item)
            continue

        if item_id in cache:
            try:
                cached_dt = datetime.fromisoformat(cache[item_id]["date"])
                if now - cached_dt <= timedelta(days=EXPIRE_DAYS):
                    skipped += 1
                    continue
            except Exception:
                pass  # Bad cache entry — include the item

        unseen.append(item)

    return unseen, skipped


def get_cache_stats() -> dict:
    """Return summary stats about the cache."""
    cache = load_cache()
    now = datetime.utcnow()
    active = sum(
        1 for v in cache.values()
        if now - datetime.fromisoformat(v["date"]) <= timedelta(days=EXPIRE_DAYS)
    )
    return {"total_cached": len(cache), "active": active, "expired": len(cache) - active}
