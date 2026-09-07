#!/usr/bin/env python3
"""Load a markdown file into the operating system's knowledge_docs for one workspace.

The scripter refuses to run without two of these docs, so this is the step that unblocks it:
"Content Strategist Brain" and "Scripting Toolkit" both live here, not in the repo, because the
writer reads them out of the database on every run and the client can edit them at /knowledge
without touching a file.

Idempotent: keyed on (agency_id, title). Re-running updates the existing row rather than
creating a duplicate.

Workspace ids are per-client and must never be crossed. Look one up with:
    curl "$NEXT_PUBLIC_SUPABASE_URL/rest/v1/agencies?select=id,name" \\
         -H "apikey: $SUPABASE_SERVICE_ROLE_KEY"

Usage, from the repo root:
    python3 tools/content-machine/load_knowledge_doc.py \\
        --agency <the client workspace id> \\
        --title "Content Strategist Brain" \\
        --source-type content_strategy \\
        --file knowledge/CONTENT_STRATEGIST_BRAIN.md

    python3 tools/content-machine/load_knowledge_doc.py \\
        --agency <the client workspace id> \\
        --title "Scripting Toolkit" \\
        --file knowledge/SCRIPTING_TOOLKIT.md

The craft in both docs is client-agnostic, so one file serves every client and `--rewrite` swaps
any wording on the way up. A rewrite whose OLD side matches nothing is a hard error, because a
silent no-op is how one client's name quietly ships into another client's brain.

Credentials come from the repo's own .env: NEXT_PUBLIC_SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY, both from the CLIENT's Supabase project, never yours.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def load_env() -> tuple[str, str]:
    env: dict[str, str] = dict(os.environ)
    for name in (".env", ".env.local"):
        p = REPO_ROOT / name
        if not p.exists():
            continue
        for line in p.read_text().split("\n"):
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env.setdefault(k.strip(), v.strip().strip("\"'"))
    url = env.get("NEXT_PUBLIC_SUPABASE_URL")
    key = env.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        raise RuntimeError(
            "NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set, either in the "
            f"environment or in {REPO_ROOT}/.env . Both come from the client's Supabase project.")
    return url, key


def call(url: str, key: str, method: str, path: str, body: dict | None = None) -> list[dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{url}/rest/v1/{path}", data=data, method=method)
    req.add_header("apikey", key)
    req.add_header("Authorization", f"Bearer {key}")
    req.add_header("Content-Type", "application/json")
    req.add_header("Prefer", "return=representation")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode().strip()
            return json.loads(raw) if raw else []
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"{method} {path} failed {e.code}: {e.read().decode()[:400]}") from e


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agency", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--source-type", default="content_strategy")
    ap.add_argument("--source-url", default=None)
    ap.add_argument(
        "--rewrite", action="append", default=[], metavar="OLD=NEW",
        help="Literal substitution applied before upload, repeatable. Lets one canonical "
             "file serve several workspaces without a duplicate that drifts.")
    ap.add_argument(
        "--truncate-at", default=None, metavar="MARKER",
        help="Drop MARKER and everything after it. For sections that are one client's "
             "judgement rather than shared craft.")
    ap.add_argument(
        "--append-file", action="append", default=[], metavar="PATH",
        help="Append another file after the (possibly truncated) body, repeatable. "
             "This is where a client's own rulings and house rules go.")
    args = ap.parse_args()

    path = Path(args.file)
    if not path.is_absolute():
        path = REPO_ROOT / path
    content = path.read_text(encoding="utf-8")

    rewrites: list[tuple[str, str]] = []
    for pair in args.rewrite:
        if "=" not in pair:
            raise SystemExit(f"--rewrite expects OLD=NEW, got {pair!r}")
        old, new = pair.split("=", 1)
        if not old:
            raise SystemExit("--rewrite OLD side cannot be empty")
        if old not in content:
            raise SystemExit(f"--rewrite {old!r} matches nothing in {path.name}")
        rewrites.append((old, new))
    for old, new in rewrites:
        content = content.replace(old, new)

    if args.truncate_at:
        cut = content.find(args.truncate_at)
        if cut == -1:
            raise SystemExit(f"--truncate-at {args.truncate_at!r} matches nothing in {path.name}")
        content = content[:cut].rstrip() + "\n"

    for extra in args.append_file:
        p = Path(extra)
        if not p.is_absolute():
            p = REPO_ROOT / p
        if not p.exists():
            raise SystemExit(f"--append-file {p} does not exist")
        content = content.rstrip() + "\n\n" + p.read_text(encoding="utf-8").strip() + "\n"

    url, key = load_env()
    q = urllib.parse.quote(args.title, safe="")
    existing = call(url, key, "GET",
                    f"knowledge_docs?agency_id=eq.{args.agency}&title=eq.{q}&select=id")

    payload = {
        "agency_id": args.agency,
        "title": args.title,
        "source_type": args.source_type,
        "source_url": args.source_url,
        "content_text": content,
        "metadata": {
            "loaded_by": "load_knowledge_doc.py",
            "source_file": str(path),
            "rewrites": [f"{o}={n}" for o, n in rewrites],
            "truncated_at": args.truncate_at,
            "appended": args.append_file,
        },
    }

    if existing:
        doc_id = existing[0]["id"]
        call(url, key, "PATCH", f"knowledge_docs?id=eq.{doc_id}", payload)
        print(f"UPDATED {doc_id} | {args.title} | {len(content):,} chars")
    else:
        rows = call(url, key, "POST", "knowledge_docs", payload)
        doc_id = rows[0]["id"] if rows else "?"
        print(f"INSERTED {doc_id} | {args.title} | {len(content):,} chars")
    return 0


if __name__ == "__main__":
    sys.exit(main())
