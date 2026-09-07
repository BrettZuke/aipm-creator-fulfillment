#!/usr/bin/env python3
"""Create a new formatted Google Doc from one or more markdown files.

Combines all input files (in order, separated by horizontal rules) into a single
Google Doc with formatting preserved (headings, bold, bullets, tables-as-monospace).
Shared with "anyone with the link can edit."

Reuses the markdown→Docs API logic from format_md_into_gdoc_tab.py so we don't
duplicate the conversion logic.

The service account has no Drive storage quota, so the new doc must be created
inside a folder that the service account can write to (one you own and have
shared with the SA, or one shared "anyone with link can edit"). Set the parent
folder via the GDOC_PARENT_FOLDER_ID env var (in .env).

Usage:
  python3 tools/youtube/create_formatted_gdoc.py "Doc Title" file1.md [file2.md ...]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

load_dotenv()

# Reuse the markdown-to-docs logic from the existing formatter.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from format_md_into_gdoc_tab import build_requests, convert_md  # noqa: E402

SA_KEY_PATH = Path(__file__).resolve().parent.parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


def get_creds() -> Credentials:
    with open(SA_KEY_PATH) as f:
        sa_info = json.load(f)
    return Credentials.from_service_account_info(sa_info, scopes=SCOPES)


def combine_markdown_files(paths: list[Path]) -> str:
    """Concatenate markdown files in order, separated by a horizontal rule."""
    parts: list[str] = []
    for i, p in enumerate(paths):
        if i > 0:
            parts.append("\n\n---\n\n")
        parts.append(p.read_text())
    return "".join(parts).strip() + "\n"


def create_empty_doc(drive, title: str, parent_folder_id: str | None) -> str:
    meta: dict = {"name": title, "mimeType": "application/vnd.google-apps.document"}
    if parent_folder_id:
        meta["parents"] = [parent_folder_id]
    file = drive.files().create(
        body=meta, fields="id", supportsAllDrives=True
    ).execute()
    return file["id"]


def get_first_tab(docs, doc_id: str) -> tuple[str, int]:
    """Return (tab_id, current_end_index) for the doc's default tab."""
    doc = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    tabs = doc.get("tabs", [])
    if not tabs:
        raise RuntimeError(f"doc {doc_id} has no tabs")
    first = tabs[0]
    tab_id = first["tabProperties"]["tabId"]
    body = first.get("documentTab", {}).get("body", {})
    end_index = body.get("content", [{}])[-1].get("endIndex", 1)
    return tab_id, end_index


def make_shareable(drive, doc_id: str) -> None:
    drive.permissions().create(
        fileId=doc_id,
        body={"type": "anyone", "role": "writer"},
    ).execute()


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 1

    title = sys.argv[1]
    md_paths = [Path(p) for p in sys.argv[2:]]
    for p in md_paths:
        if not p.exists():
            print(f"file not found: {p}")
            return 1

    combined_md = combine_markdown_files(md_paths)
    text, ops = convert_md(combined_md)
    print(f"converted: {len(text)} chars, {len(ops)} ops from {len(md_paths)} file(s)")

    creds = get_creds()
    drive = build("drive", "v3", credentials=creds)
    docs = build("docs", "v1", credentials=creds)

    parent_folder_id = os.environ.get("GDOC_PARENT_FOLDER_ID")
    doc_id = create_empty_doc(drive, title, parent_folder_id)
    print(f"created doc: {doc_id} (parent folder: {parent_folder_id or 'none'})")

    tab_id, initial_end = get_first_tab(docs, doc_id)
    print(f"first tab: {tab_id} (end_index={initial_end})")

    requests = build_requests(tab_id, text, ops, initial_end)
    print(f"sending {len(requests)} format requests")
    docs.documents().batchUpdate(
        documentId=doc_id, body={"requests": requests}
    ).execute()

    make_shareable(drive, doc_id)
    print(
        f"\nDone. Open your Google Doc here:\n"
        f"https://docs.google.com/document/d/{doc_id}/edit"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
