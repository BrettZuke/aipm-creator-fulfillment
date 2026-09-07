#!/usr/bin/env python3
"""The Scripter: analyse the creators and the brain, then write scripts.

Stage 4 of the content machine (scrape -> parse -> SCRIPT). This is one agent doing two jobs in
sequence, which is the whole point: writing and deciding what to write are different skills, and
asking for both in a single call produced generic hooks.

  ANALYSE   reads the Brain (how content is made), the Scripting Toolkit (hook types and
            skeletons), and today's signal (what is measurably working), then picks the strongest
            angles for THIS operator and says why. Output is a brief per script, not prose.
  WRITE     one call per brief, so the model spends its whole attention on one script. Each call
            writes several competing hooks, picks the strongest against stated criteria, then
            writes the script under that hook.

Covers both surfaces: Instagram reels (30 to 60 seconds spoken) and YouTube (title, thumbnail
text, and a beat-by-beat script). A YouTube video and a reel fail for different reasons, so they
are prompted differently rather than sharing one template.

Scripts land as cards on the content board (stage 'scripted'), each recording the outlier
that inspired it, so any script traces back to the post it is competing with.

FREE keys only (CLAUDE.md money rule): GEMINI_API_KEY. Never the paid Anthropic/OpenAI keys.

Usage:
    python3 tools/content-machine/content_scripter.py                       # 2 reels + 1 YouTube
    python3 tools/content-machine/content_scripter.py --reels 3 --youtube 2
    python3 tools/content-machine/content_scripter.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
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


SIGNAL_DIR = ROOT / ".tmp" / "_signal"
DRAFT_DIR = ROOT / ".tmp" / "_scripts"
# Per client, from the repo's .env, never hardcoded. One operator runs several clients and a
# ref left over from the last one writes this client's scripts into that client's board.
#   SUPABASE_PROJECT_REF=  the client's Supabase project ref
#   CONTENT_AGENCY_ID=     the client's workspace id on it
PROJECT_REF = _cfg("SUPABASE_PROJECT_REF")
AGENCY_ID = _cfg("CONTENT_AGENCY_ID")

FREE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = "gemini-2.5-flash"
GROQ_MODEL = "llama-3.3-70b-versatile"  # free fallback when Gemini hits its 20/day cap

BRAIN_DOC = "Content Strategist Brain"
TOOLKIT_DOC = "Scripting Toolkit"
PROOF_FILE = ROOT / "knowledge" / "PROOF_INVENTORY.md"
BRAIN_CHARS = 60_000
# The analysis stage only needs the doctrine plus the signal to choose angles, and the free
# fallback provider has a per-minute token limit far below Gemini's. Sending the whole brain made
# the fallback fail with a 413 exactly when Gemini's daily cap had been hit.
ANALYSIS_BRAIN_CHARS = 18_000

# Who the scripts are written AS. One short paragraph in knowledge/WHO.md: their name and handle,
# what they actually do, who they do it for, what they are NOT, and what their proof is. Written
# in phase 1 from the onboarding call. A persona hardcoded here is how one client's positioning
# ends up in another client's scripts.
WHO_FILE = ROOT / "knowledge" / "WHO.md"
WHO = WHO_FILE.read_text().strip() if WHO_FILE.exists() else ""

# Named so the writer can be told to beat them, because "write a good hook" is not an instruction.
WEAK_HOOKS = """
"Your lead qualification process is obsolete."      vague, no image, could be any of 10,000 accounts
"Stop building complex AI just to impress."         a scold, and the viewer was not doing that
"Your content team is done for."                    a threat with no evidence behind it
"Here is how to scale with AI."                     a topic, not a hook
"Most coaches get this wrong."                      no stakes, no specificity, endlessly recycled
"""

STRONG_HOOK_TESTS = """
1. Could ONLY this operator say it? If a generic AI account could post it, it is dead.
2. Does it put a concrete picture in the head in the first four words? A number, an object, a
   scene, a named tool. Not a category.
3. Does it create a gap the viewer needs closed, or does it just announce a subject?
4. Would it survive being said out loud to one person across a table?
"""


_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF\U0000FE00-\U0000FE0F\U0000200D]"
)
_ARROW = re.compile(r"\s*[←-⇿➔➡]\s*")


# "You don't have an an ad problem" shipped to the board. A doubled word is invisible when reading
# for meaning and glaring when reading aloud, which is exactly how a script gets used.
_DOUBLED = re.compile(r"\b(\w+)(\s+)\1\b", re.IGNORECASE)


def flatten(value) -> str:
    """Coerce whatever a free model returned into a string.

    The prompt asks for a string, but OmniRoute may serve any of four providers and they disagree:
    one returns "a. b. c", the next ["a", "b", "c"], another {"text": "..."}. A list reaching
    "\\n\\n".join() raises TypeError and takes the entire batch down with it, so the shape is
    normalised at the boundary rather than trusted."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "\n".join(flatten(v) for v in value if v is not None)
    if isinstance(value, dict):
        for key in ("text", "value", "content", "script"):
            if key in value:
                return flatten(value[key])
        return "\n".join(flatten(v) for v in value.values())
    return str(value)


def repair_control_chars(text: str) -> str:
    """Escape real newlines, returns and tabs that appear INSIDE a JSON string.

    We ask the model for a script with line breaks between beats, and it obliges by putting literal
    newlines inside the JSON string value, which is invalid JSON. json.loads then rejects a reply
    that starts with { and ends with } and is not truncated, so the failure looks like anything but
    what it is. One script was silently lost to this on 2026-07-30.

    Port of repairControlChars() in the dashboard's src/lib/content. Walk the text tracking
    whether we are inside a string, and escape only there, so real JSON formatting is untouched.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    for ch in text:
        if escaped:
            out.append(ch)
            escaped = False
            continue
        if ch == "\\":
            out.append(ch)
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            out.append(ch)
            continue
        if in_string:
            if ch == "\n":
                out.append("\\n")
                continue
            if ch == "\r":
                out.append("\\r")
                continue
            if ch == "\t":
                out.append("\\t")
                continue
        out.append(ch)
    return "".join(out)


def sanitize(text: str) -> str:
    """Strip what the house style bans. Enforced in code because prompts do not hold."""
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = _ARROW.sub(" to ", text)
    text = _EMOJI.sub("", text)
    text = _DOUBLED.sub(r"\1", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


# A first-person number attached to a result metric. The model invented "I got 80+ million views
# in the last 6 months" despite the prompt forbidding invented results, because it read that rule
# as being about CLIENT results only. Prompts do not hold, so this is checked in code: any script
# claiming a personal performance figure is rejected and rewritten.
_METRIC = r"(views?|followers?|subscribers?|clients?|customers?|leads?|sales|revenue|mrr|months?|days?|weeks?)"
# Quantities written as words slip past a digit-only pattern: "I have reviewed hundreds of
# automation setups" is exactly as unverifiable as "I reviewed 400 of them".
_QUANTITY = r"(?:\d[\d,.]*\s*(?:\+\s*)?(?:k|m|million|billion|x)?|hundreds|thousands|dozens|millions|countless|hundreds of thousands)"
_BRAG = re.compile(
    r"\b(i|we|my|our)\b[^.!?\n]{0,60}?\b" + _QUANTITY + r"\s+(?:of\s+)?[\w\s]{0,20}?" + _METRIC,
    re.IGNORECASE,
)
# Word-quantities attached to anything the operator claims to have personally done or seen.
_VAGUE_BRAG = re.compile(
    r"\b(?:i|we)\b[^.!?\n]{0,40}?\b(?:hundreds|thousands|dozens|millions|countless)\b",
    re.IGNORECASE,
)
_CURRENCY = re.compile(r"\b(?:i|we|my|our)\b[^.!?\n]{0,60}?[$£€]\s?\d", re.IGNORECASE)


_OVERPROMISE = re.compile(
    r"\b(personally|myself|i(?:'| wi)?ll (?:reply|respond|dm you back)|reply to everyone"
    r"|every single (?:comment|dm))\b",
    re.IGNORECASE,
)


def overpromises(text: str) -> list[str]:
    """CTAs promising a personal reply. Delivery is automated; the promise cannot be kept."""
    return [m.group(0) for m in _OVERPROMISE.finditer(text or "")]


# A figure inside quotation marks is being reported, not claimed. The guard used to drop the best
# story a client had, an AI inventing "I got 80 million views" inside one of their own scripts,
# because it read the quoted mistake as the client making the claim. Telling that story requires
# repeating the number.
_QUOTED = re.compile(r"[\"'\u201c\u2018][^\"'\u201d\u2019]{0,200}[\"'\u201d\u2019]")


def unverifiable_claims(text: str) -> list[str]:
    """Sentences that claim a personal result with a number in them. Empty list means clean."""
    hits = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n", text or ""):
        s = sentence.strip()
        if not s:
            continue
        # Strip quoted spans before checking, so reporting a claim is allowed and making one is not.
        unquoted = _QUOTED.sub(" ", s)
        if _BRAG.search(unquoted) or _CURRENCY.search(unquoted) or _VAGUE_BRAG.search(unquoted):
            hits.append(s[:120])
    return hits


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


def q(value) -> str:
    """SQL literal. None becomes NULL; strings are single-quote escaped."""
    if value is None or value == "":
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def record_run(scripts: int, signal_date: str) -> None:
    """Log the scripting run for the app's flow map. Never fails the run itself."""
    try:
        run_sql(
            "insert into public.content_machine_runs "
            "(agency_id, stage, scripts_written, detail) values "
            f"('{AGENCY_ID}', 'script', {int(scripts)}, "
            + q(json.dumps({"signal": signal_date})) + "::jsonb)"
        )
    except Exception as e:  # noqa: BLE001
        print(f"  could not log the run: {e}", file=sys.stderr)


def load_brain() -> tuple[str, str]:
    rows = run_sql(
        "select title, content_text from public.knowledge_docs "
        f"where agency_id = '{AGENCY_ID}' and title in ({q(BRAIN_DOC)}, {q(TOOLKIT_DOC)})"
    )
    docs = {r["title"]: r.get("content_text") or "" for r in rows}
    brain, toolkit = docs.get(BRAIN_DOC, ""), docs.get(TOOLKIT_DOC, "")
    if not brain or not toolkit:
        missing = [t for t, v in ((BRAIN_DOC, brain), (TOOLKIT_DOC, toolkit)) if not v]
        raise SystemExit(
            f"missing from knowledge_docs: {', '.join(missing)}. "
            "Load them with tools/content-machine/load_knowledge_doc.py, see phase 4.")
    return brain[:BRAIN_CHARS], toolkit


def load_proof() -> str:
    """What the client can actually show on camera. Optional, but scripts are markedly less specific
    without it: the Scripter falls back to claims any account could make."""
    if not PROOF_FILE.exists():
        print("  no proof inventory found, scripts will be less specific", file=sys.stderr)
        return ""
    return PROOF_FILE.read_text()


def load_taste() -> str:
    """What the client said yes and no to, from the buttons in their morning email.

    This is the only input that is about HIM rather than about content in general. The Brain knows
    what works in the lane and the proof inventory knows what he can film, but neither knows that
    he killed three attribution angles last week. Without this the machine re-pitches rejected
    ideas forever, which is exactly what it did before 2026-07-31.

    Rejections are worth more than acceptances here: an accepted angle is already on the board, a
    rejected one is a mistake about to be repeated.
    """
    try:
        rows = run_sql(
            "select verdict, reason, card_title, card_hook from public.content_feedback "
            f"where agency_id = '{AGENCY_ID}' "
            "order by created_at desc limit 60"
        )
    except Exception as e:  # noqa: BLE001
        print(f"  could not read past feedback: {e}", file=sys.stderr)
        return ""
    if not rows:
        return ""

    def lines(verdict: str) -> list[str]:
        out = []
        for r in rows:
            if r.get("verdict") != verdict:
                continue
            hook = (r.get("card_hook") or r.get("card_title") or "").strip()[:120]
            why = (r.get("reason") or "").strip()[:160]
            out.append(f'  - "{hook}"' + (f"   HE SAID: {why}" if why else ""))
        return out

    yes, no, fix = lines("accepted"), lines("rejected"), lines("revise")
    parts = []
    if no:
        parts.append("He REJECTED these. Do not pitch this angle or this hook shape again:\n"
                     + "\n".join(no[:20]))
    if fix:
        parts.append("He wanted these REWRITTEN. The idea was fine, the execution was not:\n"
                     + "\n".join(fix[:10]))
    if yes:
        parts.append("He CHOSE to record these. More like them:\n" + "\n".join(yes[:20]))
    if not parts:
        return ""
    print(f"  taste: {len(yes)} accepted, {len(no)} rejected, {len(fix)} to rewrite")
    return "\n\n".join(parts)


def load_signal() -> dict:
    if not SIGNAL_DIR.exists():
        raise SystemExit("no signal yet, run tools/content-machine/content_signal_parser.py first")
    # Date-shaped names only. A looser glob picks up anything else written into this directory
    # (a dry run's scripts file sorts last and was silently loaded as signal once).
    files = sorted(p for p in SIGNAL_DIR.glob("[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].json"))
    if not files:
        raise SystemExit("no signal yet, run tools/content-machine/content_signal_parser.py first")
    latest = files[-1]
    data = json.loads(latest.read_text())
    print(f"signal: {latest.name}, {data['outliers_analysed']} analysed patterns "
          f"from {data['creators_read']} creators")
    return data


OMNIROUTE_BASE = "http://localhost:20128/v1"


def omniroute_up() -> bool:
    try:
        req = urllib.request.Request(f"{OMNIROUTE_BASE}/models", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def providers() -> list[tuple[str, str, str]]:
    """Free providers in preference order: (name, base_url, model).

    OmniRoute goes FIRST when it is running. Gemini allows 20 free requests a day and one run plus
    any testing exhausts it; the old Gemini-to-Groq pair then fell to Groq alone, whose context and
    per-minute limits are far below Gemini's, so the fallback died 413 then 429 exactly when it was
    needed (2026-07-30). OmniRoute spreads the same call across Gemini, Groq, Mistral and
    OpenRouter and fails over between them, so one exhausted provider is no longer the end of the
    run. Direct keys stay listed underneath so the pipeline still works with the daemon stopped.
    Every provider here is free; no paid key is ever used.
    """
    out = []
    if omniroute_up():
        out.append(("omniroute", OMNIROUTE_BASE, "auto"))
    gem = os.environ.get("GEMINI_API_KEY") or env_value("GEMINI_API_KEY")
    if gem:
        out.append(("gemini", FREE_BASE, MODEL))
    try:
        groq = os.environ.get("GROQ_API_KEY") or env_value("GROQ_API_KEY")
    except SystemExit:
        groq = ""
    if groq:
        out.append(("groq", "https://api.groq.com/openai/v1", GROQ_MODEL))
    if not out:
        raise SystemExit("no free LLM route found (OmniRoute, GEMINI_API_KEY or GROQ_API_KEY)")
    return out


def _key_for(name: str) -> str:
    # OmniRoute is a local gateway holding the real keys itself; it needs a non-empty string only
    # because the OpenAI client insists on one. Looking up OMNIROUTE_API_KEY would raise instead.
    if name == "omniroute":
        return "local"
    return os.environ.get(f"{name.upper()}_API_KEY") or env_value(f"{name.upper()}_API_KEY")


def ask(prompt: str, temperature: float, label: str):
    """One JSON call. Retries within a provider, then falls through to the next free provider."""
    from openai import OpenAI

    last = ""
    for name, base, model in providers():
        for attempt in range(1, 4):
            try:
                resp = OpenAI(api_key=_key_for(name), base_url=base).chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=temperature,
                )
                raw = (resp.choices[0].message.content or "").strip()
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
                parsed = json.loads(repair_control_chars(raw))
                if parsed:
                    return parsed
                last = "model returned an empty result"
            except Exception as e:  # noqa: BLE001
                last = str(e)
                # A daily quota wall will not clear by waiting; move to the next provider now.
                if "RESOURCE_EXHAUSTED" in last or "PerDay" in last:
                    print(f"  {label}: {name} daily quota exhausted, trying the next free provider",
                          file=sys.stderr)
                    break
            print(f"  {label} {name} attempt {attempt} failed: {last[:110]}", file=sys.stderr)
            time.sleep(15 * attempt)
    raise SystemExit(f"{label} failed on every free provider: {last[:200]}")


def as_list(parsed) -> list:
    """Accept an array, or the single-key object some models wrap one in ({"ideas": [...]}).

    Different free providers answer the same "return an array" instruction differently, and a
    strict isinstance check made the fallback provider useless.
    """
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        lists = [v for v in parsed.values() if isinstance(v, list)]
        if len(lists) == 1:
            return lists[0]
    return []


# ---------------------------------------------------------------- stage A: analyse

def analyse(brain: str, toolkit: str, proof: str, signal: dict, reels: int, youtube: int,
            taste: str = "") -> list[dict]:
    """Pick the angles worth making, and say why. Briefs, not scripts."""
    patterns = [
        {
            "creator": s["creator"],
            "platform": s.get("platform", "instagram"),
            "beat_their_own_average_by": f"{s['multiple']}x",
            "their_hook": s.get("caption_hook", "")[:200],
            "hook_type": s.get("hook_type"),
            "hook_template": s.get("hook_template"),
            "format": s.get("format"),
            "ask": s.get("ask"),
            "why_it_worked": s.get("why_it_worked"),
            "url": s.get("url"),
        }
        for s in signal["signal"] if s.get("hook_type")
    ]
    total = reels + youtube
    today = datetime.now(timezone.utc)

    prompt = f"""You are a content strategist. Do NOT write any scripts yet. Your only job right now
is to decide what is worth making, and to justify each choice.

TODAY IS {today.strftime('%d %B %Y')}.

THE OPERATOR
{WHO}

WHAT HE KNOWS ABOUT MAKING CONTENT (the doctrine at the front of his brain)
{brain[:ANALYSIS_BRAIN_CHARS]}

HOOK PATTERNS THAT WORK IN HIS LANE
{hook_section(toolkit)}

WHAT HE CAN ACTUALLY PUT ON CAMERA
This is the decisive input. Every idea you choose must point at something specific in here: a
system he can screen-record, a thing that broke and what it taught him, a real position he holds.
An idea that does not map to something in this list is not an idea he can film.
{proof}

WHAT IS MEASURABLY WORKING IN HIS LANE RIGHT NOW
Each of these beat its OWN creator's average by the multiple shown, so they are real breakouts
rather than big accounts being big.
{json.dumps(patterns, ensure_ascii=False, indent=1)}
{f'''
HIS OWN VERDICTS ON WHAT YOU SENT BEFORE
This outranks everything above. The patterns are what works for other people; this is what HE will
actually record. Repeating a rejected angle wastes the only thing he cannot make more of, which is
his attention at 7am.
{taste}
''' if taste else ''}

DECIDE
Choose {total} ideas: {reels} for Instagram reels and {youtube} for YouTube. Each must take a
mechanism that is measurably working and run it on something only this operator can talk about:
the systems he has actually built, what he has seen inside other people's businesses, the specific
unglamorous work of making automation earn money.

Reject any idea that:
  - could be posted by any other AI or automation account
  - requires inventing a client result, a revenue number, or a testimonial
  - is a topic ("AI for coaches") rather than a specific claim or story
  - repeats another idea in this same set

Return STRICT JSON, an array of exactly {total} objects:
  "platform": "instagram" or "youtube"
  "angle": one sentence, the specific thing this piece argues or shows
  "why_him": one sentence on why only he can make this credibly
  "the_gap": what the viewer does not know yet that makes them stay
  "pattern": the hook type from the signal this runs
  "inspired_by": the creator it came from
  "inspired_by_url": that post's url
  "payoff": what the viewer can actually do differently after watching
  "proof": the exact thing from the proof inventory he puts on screen. Name it. "The Creators tab
           with 36 accounts and the pause switches" beats "his dashboard"

Output JSON only. No prose, no code fences."""
    briefs = as_list(ask(prompt, 0.85, "analysis"))
    if not briefs:
        raise SystemExit("analysis did not return any briefs")

    # Catch a fabricated result while it is still an angle. The writer's guard would strip it, but
    # an angle built on "increased revenue by 300%" has nothing left once the claim is removed.
    clean = []
    for b in briefs:
        blob = " ".join(str(b.get(k) or "") for k in ("angle", "why_him", "proof", "payoff"))
        bad = unverifiable_claims(blob)
        if bad:
            print(f"  dropped an angle built on an invented result: {bad[0][:80]}")
            continue
        clean.append(b)
    if not clean:
        raise SystemExit("every angle was built on an invented result")
    return clean[:total]


# ---------------------------------------------------------------- stage B: write

REEL_SHAPE = """Write an Instagram reel: 30 to 60 seconds of speech, roughly 90 to 150 words.
Structure: the hook, then the turn (why the obvious approach fails), then the specific thing he
did or would do, then the payoff, then the ask. Every sentence has to earn the next one."""

YOUTUBE_SHAPE = """Write a YouTube video: 6 to 10 minutes, so give the full spoken open plus a
beat-by-beat outline of the body. The first 30 seconds decide everything, so the open is written
out in full. The body is beats, each with what he says and what is on screen. YouTube viewers
chose this video, so it can go deeper than a reel and must deliver something a reel cannot.

The thumbnail follows the layout that wins in this format: their face cut out and centred, serious
rather than smiling, two to four huge words across the bottom, and context objects flanking the
head. Your job is the words and the props, not the design."""


def hook_section(toolkit: str, limit: int = 9_000) -> str:
    """The part of the toolkit a writer actually needs: the hook swipe file.

    Passing the whole 38k-char toolkit into every per-script call bought nothing over this and
    exceeded Groq's per-minute token limit, which killed the fallback exactly when it was needed.
    """
    lowered = toolkit.lower()
    start = lowered.find("hook swipe")
    if start == -1:
        start = 0
    return toolkit[start:start + limit]


def write_one(brief: dict, brain_excerpt: str, toolkit: str, proof: str, index: int, total: int) -> dict | None:
    platform = (brief.get("platform") or "instagram").lower()
    is_yt = platform.startswith("y")
    shape = YOUTUBE_SHAPE if is_yt else REEL_SHAPE
    today = datetime.now(timezone.utc)

    extra = ""
    if is_yt:
        extra = """  "title": the YouTube title, under 60 characters, specific and clickable without lying
  "thumbnail_text": 2 to 4 words, and they must NOT repeat the title. The title carries the
                    information, the thumbnail carries the emotion, so they do different jobs.
                    Write a verdict or a reaction, the thing a viewer would say out loud about
                    this video. Sentence case, not all caps. Think "This Actually Works" or
                    "Get Addicted", never "How To Build An AI Agent"
  "thumbnail_props": what sits either side of his face in the shot, using only his real screens
                     (a dashboard, a board of cards, a terminal, an attribution graph), never
                     generic app logos
"""

    prompt = f"""You are writing ONE piece of content. Take your time on it.

TODAY IS {today.strftime('%d %B %Y')}. The current year is {today.year}. Never present a year
earlier than {today.year} as current or upcoming.

THE OPERATOR
{WHO}

HOOK PATTERNS THAT WORK IN HIS LANE
{hook_section(toolkit)}

RELEVANT CRAFT FROM HIS BRAIN
{brain_excerpt}

WHAT HE CAN PUT ON CAMERA
Write the specific thing, never the category. "36 accounts scraped every morning" not "my
scraping system". If the brief names a screen, describe what is on it.
{proof}

THE BRIEF YOU ARE WRITING
{json.dumps(brief, ensure_ascii=False, indent=1)}

WHAT YOU ARE MAKING
{shape}

THE HOOK IS THE JOB
Write SIX different hooks for this brief first. Make them genuinely different from each other, not
six rewordings. Then score each against these tests and pick the winner.

{STRONG_HOOK_TESTS}

These are the kinds of hooks that FAIL. Do not produce anything in this family:
{WEAK_HOOKS}

VOICE
Short sentences. Concrete nouns. He says "I built", "I watched", "here is the actual number on my
screen". No emoji, no em dashes, no en dashes, no arrows. No "here's the thing", "let me be
honest", "game changer", "the truth is". Write from the viewer's side: their time, their money,
their problem.

NUMBERS, THE HARD RULE
You do not know a single one of his results. You have never seen his analytics, his revenue, or
his client outcomes. So he NEVER claims a performance figure about himself or a client: no view
counts, no follower counts, no revenue, no client counts, no "in 6 months", no "80 million views".
Not in the hook, not in the script, not as a throwaway. Writing one is the single worst thing you
can do here, because he would have to post a lie or bin the script.

What you CAN be specific about is the WORK, which is verifiable by showing the screen: how many
steps the system has, what each part does, what it scrapes, what it writes, what it costs to run,
how long it takes. "My content machine reads 33 competitor accounts every morning" is allowed if
the brief supports it. "I got 80 million views" is not, ever.

Return STRICT JSON, ONE object:
  "hook_options": array of the six hooks you wrote
  "hook": the winner, exactly as it appears in hook_options
  "hook_reasoning": one sentence on why it beat the other five
{extra}  "title": 4 to 8 words naming this on a board
  "on_screen": the text on screen during the hook, under 8 words
  "script": the full script, line breaks between beats, filmable as written
  "cta": the last line. Verb-first, one specific action. The pattern that wins in this lane is the
         comment gate: name ONE keyword and what they get for commenting it. Never a rhetorical
         question, never "link in bio". Never promise a personal reply: no "personally", no "I will
         DM you back myself", no "I will reply to everyone". The delivery is automated and
         promising otherwise is a promise he cannot keep at scale
  "keyword": the single comment-gate word in caps, or "" if this one does not use a gate

Output JSON only. No prose, no code fences."""

    print(f"  [{index}/{total}] {platform}: {str(brief.get('angle'))[:64]}")

    out = None
    attempt_prompt = prompt
    for pass_no in range(1, 4):
        try:
            candidate = ask(attempt_prompt, 0.9, f"script {index}")
        except SystemExit as e:
            print(f"    skipped: {e}", file=sys.stderr)
            return None
        if not isinstance(candidate, dict):
            print(f"    skipped: writer returned {type(candidate).__name__}, expected an object",
                  file=sys.stderr)
            return None

        # A fabricated performance claim is not a style problem, it is something he would have to
        # post as a lie. Send it back with the offending lines quoted rather than shipping it.
        blob = " ".join(str(candidate.get(k) or "") for k in ("hook", "script", "cta", "title"))
        offenders = unverifiable_claims(blob)
        promised = overpromises(str(candidate.get("cta") or ""))
        # A script with no ask is a script that earns nothing. One shipped to the board without one.
        missing_cta = len(str(candidate.get("cta") or "").strip()) < 10
        if not offenders and not promised and not missing_cta:
            out = candidate
            break

        notes = []
        if missing_cta:
            print(f"    pass {pass_no}: rejected, no call to action")
            notes.append(
                "The script has no call to action. Every piece ends with one specific ask, and the "
                "pattern that wins here is a comment gate: name ONE keyword and say what they get "
                "for commenting it."
            )
        if offenders:
            print(f"    pass {pass_no}: rejected an invented result claim: {offenders[0]}")
            notes.append(
                "These lines claim a personal performance figure you cannot possibly know:\n"
                + "\n".join(f"  {o}" for o in offenders)
                + "\nRemove every one. Be specific about what the system DOES instead, which can be "
                  "shown on screen. Do not swap a number for a vaguer number."
            )
        if promised:
            print(f"    pass {pass_no}: rejected a personal-reply promise: {promised[0]}")
            notes.append(
                f"The call to action promises a personal reply ({', '.join(promised)}). Delivery is "
                "automated, so that is a promise he cannot keep. Rewrite the CTA without it."
            )
        attempt_prompt = prompt + "\n\nYOUR PREVIOUS ATTEMPT WAS REJECTED.\n" + "\n\n".join(notes)

    if out is None:
        print(f"    skipped: kept inventing results after 3 passes", file=sys.stderr)
        return None

    out["platform"] = platform
    for k in ("inspired_by", "inspired_by_url", "pattern"):
        out.setdefault(k, brief.get(k))
    for k in ("title", "hook", "on_screen", "script", "cta", "hook_reasoning", "thumbnail_text"):
        if isinstance(out.get(k), str):
            out[k] = sanitize(out[k])
    return out


# ---------------------------------------------------------------- board

def file_cards(scripts: list[dict], date: str) -> int:
    """File each script as a card on the board, newest at the top of the Scripted column."""
    base = run_sql(
        "select coalesce(min(position), 0) as p from public.content_cards "
        f"where agency_id = '{AGENCY_ID}' and stage = 'scripted'"
    )[0]["p"]

    values = []
    for i, s in enumerate(scripts):
        is_yt = (s.get("platform") or "").startswith("y")
        # Every field goes through flatten(): asking several different free models for the same
        # JSON gets several different shapes back, and one returning ["beat one", "beat two"]
        # where Gemini returns a string used to kill the whole run with a TypeError and file
        # nothing, losing every script in the batch (2026-07-30).
        body = "\n\n".join(filter(None, [
            f"TITLE: {flatten(s['title'])}" if is_yt and s.get("title") else None,
            f"THUMBNAIL: {flatten(s['thumbnail_text'])}" if is_yt and s.get("thumbnail_text") else None,
            f"HOOK: {flatten(s.get('hook', ''))}",
            f"ON SCREEN: {flatten(s['on_screen'])}" if s.get("on_screen") else None,
            flatten(s.get("script", "")),
            f"CTA: {flatten(s['cta'])}" if s.get("cta") else None,
        ]))
        others = [h for h in (s.get("hook_options") or []) if h != s.get("hook")][:5]
        notes = "\n".join(filter(None, [
            f"Pattern: {s['pattern']}" if s.get("pattern") else None,
            f"Hook chosen because: {s['hook_reasoning']}" if s.get("hook_reasoning") else None,
            f"Inspired by {s['inspired_by']}: {s.get('inspired_by_url')}" if s.get("inspired_by") else None,
            ("\nOther hooks considered:\n" + "\n".join(f"  {h}" for h in others)) if others else None,
        ]))
        history = json.dumps([{"stage": "scripted", "at": datetime.now(timezone.utc).isoformat()}])
        values.append("(" + ",".join([
            q(AGENCY_ID), "'scripted'", str(base - (i + 1)),
            q(sanitize(s.get("title") or "Untitled script")[:200]),
            "'long_form'" if is_yt else "'reel'",
            "'yt'" if is_yt else "'ig'",
            q(sanitize(s.get("hook", ""))[:1000]),
            q(sanitize(body)[:20000]),
            q(f"Content machine {date}"),
            q(sanitize(notes)[:5000]),
            q(history) + "::jsonb",
            "'agent:content_scripter'",
        ]) + ")")

    run_sql(f"""
insert into public.content_cards
  (agency_id, stage, position, title, format, platform, hook, script, source, notes,
   stage_history, created_by)
values {",".join(values)}
""")
    return len(values)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--reels", type=int, default=2, help="Instagram reel scripts")
    ap.add_argument("--youtube", type=int, default=1, help="YouTube scripts")
    ap.add_argument("--dry-run", action="store_true", help="print the scripts, write no cards")
    args = ap.parse_args()
    total = args.reels + args.youtube
    if total < 1:
        raise SystemExit("nothing to write, ask for at least one script")

    brain, toolkit = load_brain()
    print(f"brain: {len(brain):,} chars, toolkit: {len(toolkit):,} chars")
    proof = load_proof()
    print(f"proof inventory: {len(proof):,} chars")
    signal = load_signal()

    print(f"\nanalysing: choosing {args.reels} reels and {args.youtube} YouTube ideas...")
    briefs = analyse(brain, toolkit, proof, signal, args.reels, args.youtube, load_taste())
    for b in briefs:
        print(f"  {b.get('platform', '?'):<10} {str(b.get('angle'))[:72]}")

    # The writer gets the craft, not the whole corpus: it is writing one piece, and a 60k-char
    # brain in every one of N calls buys nothing over the toolkit it already has.
    brain_excerpt = brain[:6_000]
    print(f"\nwriting {len(briefs)} scripts, one call each...")
    scripts = [s for i, b in enumerate(briefs, 1)
               if (s := write_one(b, brain_excerpt, toolkit, proof, i, len(briefs)))]

    if not scripts:
        raise SystemExit("every script failed to write")
    if len(scripts) < len(briefs):
        print(f"\n{len(briefs) - len(scripts)} of {len(briefs)} scripts failed and were dropped")

    for s in scripts:
        print(f"\n  [{s['platform']}] {s.get('title')}")
        print(f"    hook: {s.get('hook')}")
        print(f"    cta:  {s.get('cta')}")

    if args.dry_run:
        DRAFT_DIR.mkdir(parents=True, exist_ok=True)
        out = DRAFT_DIR / f"scripts-{signal['date']}.json"
        out.write_text(json.dumps(scripts, indent=2, ensure_ascii=False))
        print(f"\ndry run, wrote {out.relative_to(ROOT)}, no cards filed")
        return

    n = file_cards(scripts, signal["date"])
    record_run(n, signal["date"])
    print(f"\nfiled {n} cards on the content board, stage Scripted")


if __name__ == "__main__":
    main()
