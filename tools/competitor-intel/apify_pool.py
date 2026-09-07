"""Single source of truth for the Apify token pool.

Run a pool of free-tier Apify accounts ($5 credit each per month) and
scrapers fall through them when one hits its monthly limit. The tokens used to
live in ~/.claude.json as apify-* MCP servers; on 2026-08-12 all but apify-1
and apify-2 were moved into .env to stop ten MCP servers loading per session.
Loaders that only read ~/.claude.json therefore see 2 of 11 tokens, which is
why this module exists: every caller gets the whole pool from one place.

Order: APIFY_API_TOKEN, APIFY_TOKEN, APIFY_TOKEN_2..APIFY_TOKEN_30,
APIFY_TOKENS (comma-separated, used by the cloud cron), then any apify-*
MCP server still in ~/.claude.json. Deduped, order preserved. Never printed.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

MAX_NUMBERED = 30
CLAUDE_CONFIG = Path.home() / ".claude.json"
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _env_file_values() -> dict[str, str]:
    """Parse the project .env directly.

    Deliberately dependency-free: python-dotenv is missing from some of the
    interpreters these scripts get run under, and a pool that silently shrinks
    to whatever is already exported is worse than no pool at all.
    """
    if not _ENV_FILE.exists():
        return {}
    values: dict[str, str] = {}
    for line in _ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, _, val = line.partition("=")
        key = key.strip()
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        else:
            # Unquoted values may carry a trailing inline comment, as several
            # of the pool entries do. Strip it the way python-dotenv would.
            hash_at = val.find(" #")
            if hash_at != -1:
                val = val[:hash_at].strip()
        if key:
            values[key] = val
    return values


def _lookup(name: str, file_values: dict[str, str]) -> str:
    """Real environment wins over the .env file, matching load_dotenv defaults."""
    return os.environ.get(name) or file_values.get(name, "")


def _claude_config_tokens() -> list[str]:
    if not CLAUDE_CONFIG.exists():
        return []
    try:
        data = json.loads(CLAUDE_CONFIG.read_text())
    except Exception:
        return []
    found: list[str] = []

    def walk(obj):
        if isinstance(obj, dict):
            env = obj.get("env") if isinstance(obj.get("env"), dict) else None
            if env:
                tok = env.get("APIFY_TOKEN") or env.get("APIFY_API_TOKEN") or env.get("APIFY_API_KEY")
                if isinstance(tok, str):
                    found.append(tok)
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for v in obj:
                walk(v)

    walk(data)
    return found


def apify_tokens(include_claude_config: bool = True) -> list[str]:
    """Every Apify token available, best-first, deduped."""
    file_values = _env_file_values()
    names = ["APIFY_API_TOKEN", "APIFY_TOKEN"] + [f"APIFY_TOKEN_{i}" for i in range(2, MAX_NUMBERED + 1)]
    raw = [_lookup(n, file_values) for n in names]
    raw += _lookup("APIFY_TOKENS", file_values).split(",")
    if include_claude_config:
        raw += _claude_config_tokens()
    seen: set[str] = set()
    out: list[str] = []
    for t in raw:
        t = (t or "").strip()
        if t and t not in seen:
            seen.add(t)
            out.append(t)
    return out


# Back-compat alias for callers that already say load_apify_tokens().
load_apify_tokens = apify_tokens


if __name__ == "__main__":
    toks = apify_tokens()
    print(f"{len(toks)} Apify tokens in the pool")
    for i, t in enumerate(toks, 1):
        print(f"  {i:>2}. {t[:14]}...{t[-4:]}")
