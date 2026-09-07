"""Format a markdown file into a specific Google Docs tab.

Converts:
  # / ## / ### / ####    → HEADING_1..4 styles (## and deeper also get a light-green highlight)
  **bold**               → bold text run
  `code`                 → monospace text run
  - / * bullet           → bulleted paragraph
  --- divider line       → blank paragraph
  | a | b |  table rows  → monospace text (fixed-width table look)

Usage:
  python3 tools/youtube/format_md_into_gdoc_tab.py <doc_id> <tab_id> <markdown_path> [--no-highlight]

  --no-highlight  skip the light-green heading highlight (use for legal/prose docs,
                  where the content-tracking colour legend does not apply)
"""
from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

SA_KEY_PATH = Path(__file__).resolve().parent.parent / "service_account.json"
SCOPES = [
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/documents",
]


@dataclass(frozen=True)
class Op:
    kind: str  # "heading", "bold", "code", "bullet"
    start: int
    end: int
    level: int = 0


def process_inline(text: str, base_pos: int) -> tuple[str, list[Op]]:
    ops: list[Op] = []
    out_chars: list[str] = []
    i = 0
    cur = base_pos
    while i < len(text):
        if text[i : i + 2] == "**":
            end = text.find("**", i + 2)
            if end > 0:
                inner = text[i + 2 : end]
                ops.append(Op("bold", cur, cur + len(inner)))
                out_chars.append(inner)
                cur += len(inner)
                i = end + 2
                continue
        if text[i] == "`":
            end = text.find("`", i + 1)
            if end > 0:
                inner = text[i + 1 : end]
                ops.append(Op("code", cur, cur + len(inner)))
                out_chars.append(inner)
                cur += len(inner)
                i = end + 1
                continue
        out_chars.append(text[i])
        cur += 1
        i += 1
    return "".join(out_chars), ops


def convert_md(md: str) -> tuple[str, list[Op]]:
    out_lines: list[str] = []
    ops: list[Op] = []
    pos = 0  # cursor in output (excluding leading char-1 that Docs reserves)

    in_code_block = False
    for raw in md.split("\n"):
        line = raw

        # fenced code blocks
        if line.startswith("```"):
            in_code_block = not in_code_block
            out_lines.append("")
            pos += 1
            continue
        if in_code_block:
            out_lines.append(line)
            if line:
                ops.append(Op("code", pos, pos + len(line)))
            pos += len(line) + 1
            continue

        # headings
        m = re.match(r"^(#{1,4})\s+(.+)$", line)
        if m:
            level = len(m.group(1))
            text = m.group(2).strip()
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
            text = re.sub(r"`([^`]+)`", r"\1", text)
            out_lines.append(text)
            ops.append(Op("heading", pos, pos + len(text), level=level))
            pos += len(text) + 1
            continue

        # horizontal rule
        if line.strip() == "---":
            out_lines.append("")
            pos += 1
            continue

        # markdown tables — render as monospace, keep as-is
        if "|" in line and line.strip().startswith("|"):
            out_lines.append(line)
            ops.append(Op("code", pos, pos + len(line)))
            pos += len(line) + 1
            continue

        # bullets
        bm = re.match(r"^(\s*)[-*]\s+(.+)$", line)
        if bm:
            indent = bm.group(1)
            text = bm.group(2)
            line_start = pos
            rendered, inline_ops = process_inline(text, pos + len(indent))
            line_text = indent + rendered
            out_lines.append(line_text)
            ops.append(Op("bullet", line_start, line_start + len(line_text)))
            ops.extend(inline_ops)
            pos += len(line_text) + 1
            continue

        # regular paragraph
        rendered, inline_ops = process_inline(line, pos)
        out_lines.append(rendered)
        ops.extend(inline_ops)
        pos += len(rendered) + 1

    return "\n".join(out_lines), ops


def build_requests(tab_id: str, text: str, ops: list[Op], initial_end: int, highlight_headings: bool = True) -> list[dict]:
    reqs: list[dict] = []
    # 1. wipe existing content (skip mandatory 1-char preamble at startIndex=1)
    if initial_end > 2:
        reqs.append(
            {
                "deleteContentRange": {
                    "range": {
                        "startIndex": 1,
                        "endIndex": initial_end - 1,
                        "tabId": tab_id,
                    }
                }
            }
        )
    # 2. insert text
    reqs.append(
        {
            "insertText": {
                "location": {"tabId": tab_id, "index": 1},
                "text": text,
            }
        }
    )
    # 3. apply formatting ops (offset by +1 because we inserted at index=1)
    base = 1
    for op in ops:
        s = op.start + base
        e = op.end + base
        if e <= s:
            continue
        if op.kind == "heading":
            named = {1: "HEADING_1", 2: "HEADING_2", 3: "HEADING_3", 4: "HEADING_4"}.get(op.level, "HEADING_3")
            reqs.append(
                {
                    "updateParagraphStyle": {
                        "range": {"startIndex": s, "endIndex": e, "tabId": tab_id},
                        "paragraphStyle": {"namedStyleType": named},
                        "fields": "namedStyleType",
                    }
                }
            )
            # Light-green highlight on section + piece titles (level >= 2) so the reader can
            # scan the tab at a glance and recolour each title to track status (legend
            # at the top of the tab: green = ready, yellow = recorded, blue = posted, red = scrap).
            if op.level >= 2 and highlight_headings:
                reqs.append(
                    {
                        "updateTextStyle": {
                            "range": {"startIndex": s, "endIndex": e, "tabId": tab_id},
                            "textStyle": {
                                "backgroundColor": {
                                    "color": {"rgbColor": {"red": 0.851, "green": 0.918, "blue": 0.827}}
                                }
                            },
                            "fields": "backgroundColor",
                        }
                    }
                )
        elif op.kind == "bullet":
            reqs.append(
                {
                    "createParagraphBullets": {
                        "range": {"startIndex": s, "endIndex": e, "tabId": tab_id},
                        "bulletPreset": "BULLET_DISC_CIRCLE_SQUARE",
                    }
                }
            )
        elif op.kind == "bold":
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": s, "endIndex": e, "tabId": tab_id},
                        "textStyle": {"bold": True},
                        "fields": "bold",
                    }
                }
            )
        elif op.kind == "code":
            reqs.append(
                {
                    "updateTextStyle": {
                        "range": {"startIndex": s, "endIndex": e, "tabId": tab_id},
                        "textStyle": {
                            "weightedFontFamily": {"fontFamily": "Roboto Mono"},
                            "backgroundColor": {
                                "color": {"rgbColor": {"red": 0.96, "green": 0.96, "blue": 0.96}}
                            },
                        },
                        "fields": "weightedFontFamily,backgroundColor",
                    }
                }
            )
    return reqs


def get_tab_end(doc: dict, tab_id: str) -> int:
    def walk(tabs):
        for t in tabs or []:
            if t.get("tabProperties", {}).get("tabId") == tab_id:
                return t
            r = walk(t.get("childTabs", []))
            if r:
                return r
        return None

    tab = walk(doc.get("tabs", []))
    if not tab:
        raise RuntimeError(f"tab {tab_id} not found")
    body = tab.get("documentTab", {}).get("body", {})
    return body.get("content", [{}])[-1].get("endIndex", 1)


def main() -> int:
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    if len(args) < 3:
        print(__doc__)
        return 1
    doc_id, tab_id, md_path = args[0], args[1], args[2]
    highlight_headings = "--no-highlight" not in flags

    with open(SA_KEY_PATH) as f:
        sa_info = json.load(f)
    creds = Credentials.from_service_account_info(sa_info, scopes=SCOPES)
    docs = build("docs", "v1", credentials=creds)

    md = Path(md_path).read_text()
    text, ops = convert_md(md)
    print(f"converted: {len(text)} chars, {len(ops)} ops")

    doc = docs.documents().get(documentId=doc_id, includeTabsContent=True).execute()
    initial_end = get_tab_end(doc, tab_id)
    print(f"tab current end_index: {initial_end}")

    requests = build_requests(tab_id, text, ops, initial_end, highlight_headings)
    print(f"sending {len(requests)} requests")
    result = docs.documents().batchUpdate(documentId=doc_id, body={"requests": requests}).execute()
    print(f"replies: {len(result.get('replies', []))}")
    print(f"doc URL: https://docs.google.com/document/d/{doc_id}/edit?tab={tab_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
