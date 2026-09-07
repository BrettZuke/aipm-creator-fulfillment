#!/usr/bin/env python3
"""Parse scraped competitor content into today's signal.

Stage 3 of the content machine (scrape -> PARSE -> script). Reads what the scrapers collected
for every ACTIVE creator on the roster and answers one question: what is actually working in this
client's lane right now.

Two passes, deliberately split:
  1. Deterministic maths, no LLM. A post is an outlier when it beats that creator's OWN median
     views, so a 1.5M-view account and a 15k-view account are judged on the same scale and a big
     account cannot drown out a small one.
  2. Free Gemini reads ONLY the outliers and names the pattern behind each (hook type, format,
     what the call to action asks for).

Roster comes from Supabase, not a local file, so pausing a creator in the dashboard actually stops them
feeding the scripts. Paused creators and non-'emulate' roles are skipped: strategists teach craft
to the Brain, they are not copy targets.

FREE keys only (CLAUDE.md money rule): GEMINI_API_KEY. Never the paid Anthropic/OpenAI keys.

Writes .tmp/_signal/<date>.json for the scripter to read.

Usage:
    python3 tools/content-machine/content_signal_parser.py
    python3 tools/content-machine/content_signal_parser.py --min-multiple 2.5 --top 30
    python3 tools/content-machine/content_signal_parser.py --no-llm     # maths only, no API calls
"""
from __future__ import annotations

import argparse
import json
import os
import re
import statistics
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


TMP = ROOT / ".tmp"
SIGNAL_DIR = TMP / "_signal"
# Per client, from the repo's .env, never hardcoded. One operator runs several clients and a
# ref left over from the last one writes this client's scripts into that client's board.
#   SUPABASE_PROJECT_REF=  the client's Supabase project ref
#   CONTENT_AGENCY_ID=     the client's workspace id on it
PROJECT_REF = _cfg("SUPABASE_PROJECT_REF")
AGENCY_ID = _cfg("CONTENT_AGENCY_ID")

FREE_BASE = "https://generativelanguage.googleapis.com/v1beta/openai/"
MODEL = "gemini-2.5-flash"


# ---------------------------------------------------------------- house style

_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF"
    "\U0001F1E6-\U0001F1FF\U0000FE00-\U0000FE0F\U0000200D]"
)
_ARROW = re.compile(r"\s*[←-⇿➔➡]\s*")


def sanitize(text: str) -> str:
    """Strip what the house style bans. Enforced in code because prompts do not hold."""
    text = re.sub(r"\s*[—–]\s*", ", ", text)
    text = _ARROW.sub(" to ", text)
    text = _EMOJI.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


# ---------------------------------------------------------------- roster

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


def active_copy_targets() -> list[dict]:
    """Creators the operator currently wants copied. Pausing one in the dashboard drops it from here."""
    return run_sql(
        "select handle, name, instagram, youtube, role, min_score from public.content_creators "
        f"where agency_id = '{AGENCY_ID}' and status = 'active' and role = 'emulate' "
        "order by name"
    )


def record_run(stage: str, **fields) -> str | None:
    """Log this run so the app can show what the machine did. Never fails the run itself:
    a missing log line is a cosmetic problem, a crashed pipeline is not.
    Returns the run id so outlier rows can point back at the run that found them."""
    detail = fields.pop("detail", None)
    cols = ["agency_id", "stage"] + list(fields)
    vals = [f"'{AGENCY_ID}'", f"'{stage}'"] + [str(int(v)) for v in fields.values()]
    if detail is not None:
        cols.append("detail")
        vals.append("'" + json.dumps(detail).replace("'", "''") + "'::jsonb")
    try:
        rows = run_sql(f"insert into public.content_machine_runs ({', '.join(cols)}) "
                       f"values ({', '.join(vals)}) returning id")
        return rows[0]["id"] if rows else None
    except Exception as e:  # noqa: BLE001
        print(f"  could not log the run: {e}", file=sys.stderr)
        return None


def sql_str(value) -> str:
    """One SQL literal. Captions carry quotes, newlines and unicode, so everything that reaches
    the database goes through here rather than being interpolated raw."""
    if value is None or value == "":
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


OUTLIER_COLS = (
    "agency_id", "run_id", "url", "platform", "creator", "handle", "posted", "post_type",
    "metric", "score", "creator_median", "multiple", "views", "likes", "comments",
    "analysed", "caption_hook", "caption", "hook_type", "hook_template", "format", "ask",
    "why_it_worked",
)


def record_outliers(hits: list[dict], analysed_urls: set[str], run_id: str | None) -> None:
    """Persist every outlier, not just the ones the LLM studied.

    The signal file only ever held the analysed top N, so the other ~180 winners existed nowhere
    the app could reach and no client could see their own. Rows carry `metric` because carousels
    report no view count and are scored on engagement instead: a multiple without its metric
    misleads. Upserts on (agency_id, url) so re-running a day does not duplicate."""
    if not hits:
        return
    rows = []
    for h in hits:
        posted = h.get("posted")
        rows.append("(" + ", ".join([
            sql_str(AGENCY_ID), sql_str(run_id), sql_str(h.get("url")), sql_str(h.get("platform")),
            sql_str(h.get("creator")), sql_str(h.get("handle")),
            f"{sql_str(posted)}::date" if posted else "null", sql_str(h.get("type")),
            sql_str(h.get("metric")), sql_str(h.get("score")), sql_str(h.get("creator_median")),
            sql_str(h.get("multiple")), sql_str(h.get("views")), sql_str(h.get("likes")),
            sql_str(h.get("comments")),
            sql_str(h.get("url") in analysed_urls),
            sql_str(h.get("caption_hook")), sql_str(h.get("caption")), sql_str(h.get("hook_type")),
            sql_str(h.get("hook_template")), sql_str(h.get("format")), sql_str(h.get("ask")),
            sql_str(h.get("why_it_worked")),
        ]) + ")")

    # The five analysis columns (and the flag that says they exist) are only ever ADDED by an
    # upsert, never blanked. A plain `= excluded.<col>` on these was destructive: running with
    # --no-llm, or any run whose pattern pass came back empty, rewrote every previously analysed
    # row with nulls. On 2026-08-03 that wiped the analysis off all 232 outliers in one pass, and
    # the scripts kept coming only because the writer had a knowledge-base fallback. Re-analysing
    # a row still works, because a non-null value from the new pass wins.
    KEEP_IF_NEW_IS_NULL = ("hook_type", "hook_template", "format", "ask", "why_it_worked")
    parts = []
    for c in OUTLIER_COLS:
        if c in ("agency_id", "url"):
            continue
        if c in KEEP_IF_NEW_IS_NULL:
            parts.append(f"{c} = coalesce(excluded.{c}, public.content_outliers.{c})")
        elif c == "analysed":
            # Stays true once true: the row still carries the analysis it was given.
            parts.append("analysed = (excluded.analysed or public.content_outliers.analysed)")
        else:
            parts.append(f"{c} = excluded.{c}")
    updates = ", ".join(parts)
    written = 0
    # Chunked because a single statement carrying 200+ captions is large enough to be refused.
    for i in range(0, len(rows), 50):
        chunk = rows[i:i + 50]
        try:
            run_sql(
                f"insert into public.content_outliers ({', '.join(OUTLIER_COLS)}) "
                f"values {', '.join(chunk)} "
                f"on conflict (agency_id, url) do update set {updates}"
            )
            written += len(chunk)
        except Exception as e:  # noqa: BLE001
            print(f"  could not save outliers {i}-{i + len(chunk)}: {e}", file=sys.stderr)
    if written:
        print(f"saved {written} outliers to the dashboard ({len(analysed_urls)} with analysis)")


# ---------------------------------------------------------------- outlier maths

def views_of(post: dict) -> int:
    for key in ("videoPlayCount", "videoViewCount"):
        v = post.get(key)
        if isinstance(v, int) and v > 0:
            return v
    return 0


def engagement_of(post: dict) -> int:
    """Likes plus comments. Instagram hides likes on some posts, reported as -1, so guard both."""
    likes = post.get("likesCount")
    comments = post.get("commentsCount")
    total = 0
    for v in (likes, comments):
        if isinstance(v, int) and v > 0:
            total += v
    return total


def strength(multiple: float, score: float) -> float:
    """How instructive an outlier is, used for RANKING only. Never for qualification.

    There used to be an absolute floor here (5,000 views) and it was the wrong tool (the operator
    2026-08-03): views are not quality, and one number cannot fit creators whose baselines differ
    by three orders of magnitude. It also silently excluded whole channels, since @Jakub.Blonski
    has never had a video above 1,400.

    But the thing it was patching over is real, and it is a ranking problem. Sorting purely by
    multiple put a small account's 174x (a post with 3,823 views) above a large one's 104x (a post with
    5,007,724 views). The second is obviously more instructive; the first only looks bigger because
    a median of 22 makes anything look enormous.

    So rank on both: how far it beat its own baseline, damped by the scale it actually reached.
    log10 means a post with a million views counts about twice a post with a thousand, not a
    thousand times, so reach informs the order without simply handing it to the biggest account.
    Qualification stays purely relative: beat your own median, whatever size you are.
    """
    import math
    return multiple * math.log10(max(score, 10))


def reach_metric(posts: list[dict]) -> tuple[str, callable]:
    """Pick the yardstick this creator can actually be measured on.

    Carousel-first accounts get no view count from Instagram at all, so scoring them on views
    silently drops them from the signal. Falling back to likes plus comments keeps them in, and
    the metric name rides along so nothing pretends a carousel's engagement is a view count.
    """
    measurable_views = sum(1 for p in posts if views_of(p) > 0)
    if measurable_views >= max(5, len(posts) // 4):
        return "views", views_of
    return "engagement", engagement_of


def youtube_outliers_for(slug: str, min_multiple: float,
                         min_score: int | None = None) -> tuple[list[dict], dict]:
    """Same idea on YouTube: videos that beat their own channel's median view count.

    Titles are the hook on YouTube, and a channel's back catalogue reaches further back than an
    Instagram pull, so this surfaces what has held up rather than only what is recent.
    """
    path = TMP / slug / "youtube_videos.json"
    if not path.exists():
        return [], {}
    try:
        videos = json.loads(path.read_text())
    except Exception:
        return [], {}

    transcripts = {}
    tpath = TMP / slug / "youtube_transcripts.json"
    if tpath.exists():
        try:
            for r in json.loads(tpath.read_text()):
                text = (r.get("transcript") or "").strip()
                if r.get("id") and text:
                    transcripts[r["id"]] = text
        except Exception:
            pass

    scored = [(v, v.get("view_count") or 0) for v in videos]
    live = [n for _, n in scored if n > 0]
    if len(live) < 5:
        return [], {"videos": len(videos), "measurable": len(live), "median": 0}

    median = statistics.median(live)
    baseline = {"videos": len(videos), "measurable": len(live), "median": int(median)}
    hits = []
    for v, n in scored:
        if n <= 0 or n < median * min_multiple:
            continue
        vid = v.get("id")
        # The opening of a transcript is the spoken hook, which is the part worth copying. The
        # rest of the video is not sent anywhere: it would blow the prompt for no extra signal.
        opening = transcripts.get(vid, "")[:600]
        hits.append({
            "url": v.get("webpage_url") or (f"https://youtube.com/watch?v={vid}" if vid else None),
            "platform": "youtube",
            "metric": "views",
            "score": n,
            "views": n,
            "multiple": round(n / median, 1),
            "likes": v.get("like_count"),
            "comments": v.get("comment_count"),
            "posted": str(v.get("upload_date") or "")[:8],
            "type": "Video",
            "caption_hook": (v.get("title") or "")[:300],
            "caption": ((v.get("title") or "") + "\n\n" + opening)[:1200],
        })
    hits.sort(key=lambda h: strength(h["multiple"], h["score"]), reverse=True)
    return hits, baseline


def first_line(caption: str | None) -> str:
    """The caption hook: the line that has to earn the tap."""
    for line in (caption or "").splitlines():
        line = line.strip()
        if line:
            return line[:300]
    return ""


def outliers_for(slug: str, min_multiple: float,
                 min_score: int | None = None) -> tuple[list[dict], dict]:
    """Posts that beat this creator's own median by min_multiple, plus the baseline they beat."""
    path = TMP / slug / "posts_deep.json"
    if not path.exists():
        return [], {}
    try:
        posts = json.loads(path.read_text())
    except Exception:
        return [], {}

    metric_name, measure = reach_metric(posts)
    scored = [(p, measure(p)) for p in posts]
    live = [v for _, v in scored if v > 0]
    if len(live) < 5:
        # Too few measurable posts for a median to mean anything. Reporting a 12x outlier off
        # three data points would be noise dressed as signal.
        return [], {"posts": len(posts), "measurable": len(live), "median": 0, "metric": metric_name}

    median = statistics.median(live)
    baseline = {"posts": len(posts), "measurable": len(live),
                "median": int(median), "metric": metric_name}
    # A small account can have a median of 22, which turns almost anything into a "50x outlier".
    # The multiple stays honest, but a post also has to clear an absolute floor before it is worth
    # copying, otherwise noise from tiny accounts crowds out real breakouts from big ones.
    hits = []
    for p, v in scored:
        if v <= 0 or v < median * min_multiple:
            continue
        hits.append({
            "url": p.get("url"),
            "platform": "instagram",
            "metric": metric_name,
            "score": v,
            "views": v if metric_name == "views" else None,
            "multiple": round(v / median, 1),
            "likes": p.get("likesCount") if (p.get("likesCount") or 0) > 0 else None,
            "comments": p.get("commentsCount"),
            "posted": (p.get("timestamp") or "")[:10],
            "type": p.get("type"),
            "caption_hook": first_line(p.get("caption")),
            "caption": (p.get("caption") or "")[:1200],
        })
    hits.sort(key=lambda h: strength(h["multiple"], h["score"]), reverse=True)
    return hits, baseline


# ---------------------------------------------------------------- pattern pass

PATTERN_PROMPT = """You are a competitive content analyst for an operator who sells AI and automation
systems to coaches and creators. Below are posts that measurably beat their own creator's median
reach. For each one, name the pattern so it can be reused.

A YouTube item gives you its title and the opening of what was actually said; an Instagram item
gives you its caption. Judge each on what it is: a long-form title and a reel hook do different jobs.

Return STRICT JSON, an array, one object per post, in the same order, each with:
  "hook_type": 2 to 4 words naming the hook pattern (for example "Contrarian callout",
               "Specific number promise", "Tool discovery", "Pain point callout")
  "hook_template": the hook rewritten as a reusable template with [BRACKETS] for the variables
  "format": one of "talking head", "screen recording", "b-roll voiceover", "text on screen",
            "carousel", "unclear"
  "ask": what the call to action asks the viewer to do, in under 8 words, or "none"
  "why_it_worked": one sentence, concrete, about the mechanism not the topic
  "steal_it": one sentence on how to run this same pattern in this client's own world

Rules: no emoji. No em dashes or en dashes. No arrows. Plain sentences.
Output JSON only, no prose around it, no code fences.

POSTS:
"""


OMNIROUTE_BASE = "http://localhost:20128/v1"
OMNIROUTE_MODEL = "auto"


def omniroute_up() -> bool:
    """OmniRoute is a local gateway that fans one request across every free provider configured
    (Gemini, Groq, Mistral, OpenRouter) and fails over when one runs dry. Gemini's free tier is
    20 requests a day and one run uses about seven, so unattended runs hit the cap within days.
    Checked rather than assumed: the daemon may not be running, in which case direct Gemini still
    works exactly as before."""
    try:
        req = urllib.request.Request(f"{OMNIROUTE_BASE}/models", method="GET")
        with urllib.request.urlopen(req, timeout=3) as r:
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


def client() -> tuple[object, str]:
    """Returns (client, model). Prefers OmniRoute so a Gemini quota wall becomes a fallback
    rather than a failed run; falls back to calling Gemini directly when it is not running."""
    from openai import OpenAI
    if omniroute_up():
        print("  routing through OmniRoute (free providers with automatic fallback)")
        return OpenAI(api_key="local", base_url=OMNIROUTE_BASE), OMNIROUTE_MODEL
    key = os.environ.get("GEMINI_API_KEY") or env_value("GEMINI_API_KEY")
    if not key:
        raise SystemExit("GEMINI_API_KEY (free) not set and OmniRoute is not running")
    print("  OmniRoute not running, calling free Gemini directly")
    return OpenAI(api_key=key, base_url=FREE_BASE), MODEL


def name_patterns(hits: list[dict]) -> list[dict]:
    """Ask the free model to name the pattern behind each outlier. Order-matched to hits."""
    if not hits:
        return []
    payload = [
        {"n": i + 1, "creator": h["creator"], "platform": h.get("platform", "instagram"),
         "metric": h["metric"], "score": h["score"], "multiple": h["multiple"],
         "type": h["type"], "caption": h["caption"][:700]}
        for i, h in enumerate(hits)
    ]
    body = PATTERN_PROMPT + json.dumps(payload, ensure_ascii=False)

    last = ""
    # Resolved once, not per attempt: four retries against a dead gateway should not re-probe it
    # four times, and the chosen route must stay the same across retries.
    llm, model = client()
    for attempt in range(1, 5):
        try:
            resp = llm.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": body}],
                temperature=0.3,
            )
            raw = (resp.choices[0].message.content or "").strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
            parsed = json.loads(raw)
            if isinstance(parsed, list) and parsed:
                return parsed
            last = "model returned an empty or non-list result"
        except Exception as e:  # noqa: BLE001
            last = str(e)
        print(f"  pattern pass attempt {attempt} failed: {last[:120]}", file=sys.stderr)
        time.sleep(20 * attempt)
    raise SystemExit(f"pattern pass failed after 4 attempts: {last}")


# ---------------------------------------------------------------- main

def main():
    global AGENCY_ID
    ap = argparse.ArgumentParser()
    ap.add_argument("--agency", default=AGENCY_ID,
                    help="which workspace's roster to score and whose outliers to write. The "
                         "scrape output in .tmp/ is shared, so the same folders can be parsed "
                         "into a second workspace without re-scraping anything.")
    ap.add_argument("--min-multiple", type=float, default=2.0,
                    help="how far above a creator's own median a post must land to count")
    ap.add_argument("--top", type=int, default=25, help="max outliers sent to the pattern pass")
    ap.add_argument("--no-llm", action="store_true", help="outlier maths only, no API calls")
    args = ap.parse_args()
    AGENCY_ID = args.agency

    creators = active_copy_targets()
    if not creators:
        raise SystemExit("no active 'emulate' creators on the roster, nothing to parse")
    print(f"{len(creators)} active copy targets on the roster")

    all_hits: list[dict] = []
    skipped: list[str] = []
    def attribute(hits: list[dict], creator: dict, median: int) -> None:
        for h in hits:
            h["creator"] = creator["name"]
            h["handle"] = creator["handle"]
            h["creator_median"] = median

    for c in creators:
        found = False

        # scrape_creator_deep names its output folder after the Instagram handle, so resolve the
        # same way; handle is only the fallback for a creator with no Instagram on file.
        ig_hits, ig_base = outliers_for(c.get("instagram") or c["handle"], args.min_multiple,
                                        c.get("min_score"))
        if ig_base.get("median"):
            attribute(ig_hits, c, ig_base["median"])
            all_hits.extend(ig_hits)
            found = True
            print(f"  {c['name']:<22} IG median {ig_base['median']:>8,} "
                  f"{ig_base['metric']:<10} outliers {len(ig_hits)}")
        elif ig_base:
            print(f"  {c['name']:<22} IG only {ig_base['measurable']} posts with "
                  f"{ig_base['metric']} to measure, skipped")

        # YouTube runs whatever Instagram did. A creator can be YouTube-only (a second channel with
        # no Instagram at all), and reading it inside the Instagram branch silently dropped one.
        # scrape_youtube_creator.py files by roster slug, so this resolves on handle.
        yt_hits, yt_base = youtube_outliers_for(c["handle"], args.min_multiple,
                                                c.get("min_score"))
        if yt_base.get("median"):
            attribute(yt_hits, c, yt_base["median"])
            all_hits.extend(yt_hits)
            found = True
            print(f"  {c['name']:<22} YT median {yt_base['median']:>8,} "
                  f"{'views':<10} outliers {len(yt_hits)}")

        if not found:
            skipped.append(c["name"])

    if skipped:
        print(f"  no usable data: {', '.join(skipped)}")

    all_hits.sort(key=lambda h: strength(h["multiple"], h["score"]), reverse=True)
    top = all_hits[: args.top]
    if len(all_hits) > args.top:
        print(f"pattern pass covers the top {args.top} of {len(all_hits)} outliers")

    patterns: list[dict] = []
    if top and not args.no_llm:
        print("naming patterns on free Gemini...")
        patterns = name_patterns(top)
        for h, p in zip(top, patterns):
            for k in ("hook_type", "hook_template", "format", "ask", "why_it_worked", "steal_it"):
                v = p.get(k)
                h[k] = sanitize(str(v)) if isinstance(v, str) else v

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    SIGNAL_DIR.mkdir(parents=True, exist_ok=True)
    out = SIGNAL_DIR / f"{today}.json"
    out.write_text(json.dumps({
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "min_multiple": args.min_multiple,
        "creators_read": len(creators),
        "creators_skipped": skipped,
        "outliers_found": len(all_hits),
        "outliers_analysed": len(top),
        "signal": top,
    }, indent=2, ensure_ascii=False))

    run_id = record_run(
        stage="parse",
        creators_read=len(creators) - len(skipped),
        creators_skipped=len(skipped),
        outliers_found=len(all_hits),
        outliers_analysed=len(top),
        detail={"skipped": skipped, "min_multiple": args.min_multiple},
    )

    # Analysed means the LLM actually explained it, not merely that it made the top N.
    # --no-llm reaches here with a populated `top` and no analysis, and marking those rows
    # analysed would promise the dashboard a "why" that does not exist.
    record_outliers(all_hits, {h["url"] for h in top if h.get("why_it_worked")}, run_id)

    print(f"\n{len(all_hits)} outliers from {len(creators) - len(skipped)} creators, "
          f"{len(patterns)} patterns named")
    print(f"wrote {out.relative_to(ROOT)}")
    for h in top[:5]:
        print(f"  {h['multiple']:>5}x  {h['creator']:<20} {h.get('hook_type') or ''}")


if __name__ == "__main__":
    main()
