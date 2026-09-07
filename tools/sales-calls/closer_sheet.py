#!/usr/bin/env python3
"""Shared Google Sheets access for the closer post-call form and its call reviews.

The forms platform keeps every form's responses in one spreadsheet: a tab `r_<form id>` per
form, with the raw answers as JSON in column C. This module reads that sheet and owns the
`_call_reviews` tab the nightly review run writes to, which the closer scoreboard then reads.

Config, all per client, from the repo's .env:

    GOOGLE_SERVICE_ACCOUNT_JSON   the service account with access to the spreadsheet
    SHEET_ID                      the spreadsheet holding the form responses
    CLOSER_FORM_TAB               the response tab for the post-call form, `r_<form id>`

The service account needs edit access on that spreadsheet. Share it with the address in the
JSON's client_email, the same way you would share with a person.

Used as a CLI it prints one row per review already written:

    python3 tools/sales-calls/closer_sheet.py
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
from pathlib import Path

from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

ROOT = Path(__file__).resolve().parent.parent.parent
FORMS_ENV = ROOT / ".env"
FORM_TAB = os.environ.get("CLOSER_FORM_TAB", "")   # the post-call form's response tab, r_<form id>
REVIEWS_TAB = "_call_reviews"
MANUAL_TAB = "_calls_manual"    # calls added by hand, for anything that never got a form
MANUAL_HEADER = [
    "call_id", "started_at", "lead", "closer", "outcome", "cash", "deal_value",
    "tier", "recurring_amt", "presented", "objections", "notes", "share_url",
]
REVIEW_HEADER = [
    "response_id", "reviewed_at", "call_date", "closer", "lead",
    "summary", "feedback", "scores_json", "transcript", "share_url",
]
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
API = "https://sheets.googleapis.com/v4/spreadsheets"

_state: dict = {}


def _load_env() -> tuple[dict, str]:
    """Parse GOOGLE_SERVICE_ACCOUNT_JSON and SHEET_ID out of the repo's .env.

    The service-account value is a double-quoted JSON blob with escaped newlines, so a
    naive line-based dotenv parse truncates it at the first newline. Slice from the
    opening quote to the next VAR= line instead.
    """
    if not FORMS_ENV.exists():
        raise SystemExit(
            f"{FORMS_ENV} missing. It needs GOOGLE_SERVICE_ACCOUNT_JSON (double-quoted, one "
            "line) and SHEET_ID. If the forms live in a Vercel project, pull them with: "
            "vercel env pull .env --yes --environment=production --cwd <that project>"
        )
    text = FORMS_ENV.read_text()
    key = 'GOOGLE_SERVICE_ACCOUNT_JSON="'
    start = text.index(key) + len(key)
    nxt = re.search(r"\n[A-Z0-9_]+=", text[start:])
    block = (text[start: start + nxt.start()] if nxt else text[start:]).rstrip().rstrip('"')
    sa = json.loads(block.replace("\\n", "\n"), strict=False)
    m = re.search(r'^SHEET_ID="?([A-Za-z0-9_-]+)"?', text, re.M)
    if not m:
        raise SystemExit("SHEET_ID not found in " + str(FORMS_ENV))
    return sa, m.group(1)


def sheets_session() -> AuthorizedSession:
    if "session" not in _state:
        sa, sheet_id = _load_env()
        creds = service_account.Credentials.from_service_account_info(sa, scopes=SCOPES)
        _state["session"] = AuthorizedSession(creds)
        _state["sheet_id"] = sheet_id
    return _state["session"]


def sheet_id() -> str:
    sheets_session()
    return _state["sheet_id"]


def read_values(sess: AuthorizedSession, rng: str) -> list[list[str]]:
    url = f"{API}/{sheet_id()}/values/{urllib.parse.quote(rng, safe='')}"
    resp = sess.get(url, timeout=60)
    if resp.status_code == 400:
        return []  # tab does not exist yet
    resp.raise_for_status()
    return resp.json().get("values", [])


def append_values(sess: AuthorizedSession, rng: str, rows: list[list[str]]) -> None:
    url = (f"{API}/{sheet_id()}/values/{urllib.parse.quote(rng, safe='')}:append"
           "?valueInputOption=RAW&insertDataOption=INSERT_ROWS")
    resp = sess.post(url, json={"values": rows}, timeout=60)
    resp.raise_for_status()


def ensure_tab(sess: AuthorizedSession, tab: str, header: list[str]) -> None:
    """Create a tab with its header row if it is not there yet."""
    meta = sess.get(f"{API}/{sheet_id()}?fields=sheets.properties.title", timeout=60)
    meta.raise_for_status()
    titles = [s["properties"]["title"] for s in meta.json().get("sheets", [])]
    if tab not in titles:
        add = sess.post(f"{API}/{sheet_id()}:batchUpdate", timeout=60,
                        json={"requests": [{"addSheet": {"properties": {"title": tab}}}]})
        add.raise_for_status()
    col = chr(ord("A") + len(header) - 1)
    head = read_values(sess, f"{tab}!A1:{col}1")
    if not head or not head[0]:
        url = (f"{API}/{sheet_id()}/values/{urllib.parse.quote(tab + '!A1', safe='')}"
               "?valueInputOption=RAW")
        sess.put(url, json={"values": [header]}, timeout=60).raise_for_status()


def ensure_reviews_tab(sess: AuthorizedSession) -> None:
    ensure_tab(sess, REVIEWS_TAB, REVIEW_HEADER)


def write_review(sess: AuthorizedSession, row: dict) -> None:
    """Append one review row. `scores` is a dict of area -> 0-10."""
    append_values(sess, f"{REVIEWS_TAB}!A1", [[
        row.get("response_id", ""), row.get("reviewed_at", ""), row.get("call_date", ""),
        row.get("closer", ""), row.get("lead", ""), row.get("summary", ""),
        row.get("feedback", ""), json.dumps(row.get("scores") or {}),
        row.get("transcript", ""), row.get("share_url", ""),
    ]])


if __name__ == "__main__":
    s = sheets_session()
    ensure_reviews_tab(s)
    rows = read_values(s, f"{REVIEWS_TAB}!A2:J100000")
    print(f"{len(rows)} reviews in {REVIEWS_TAB}")
    for r in rows:
        print(" ", (r + [""] * 10)[1][:16], (r + [""] * 10)[3][:8], (r + [""] * 10)[4][:24])
