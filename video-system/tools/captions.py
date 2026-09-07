#!/usr/bin/env python3
"""The approved caption style, as a reusable tool.

Style spec and the reasoning behind each choice:
    video-system/presets/captions-approved.md

Transcribes the cut, renders word-synced captions to a transparent track, and
lets ffmpeg composite them. The footage is never decoded to RGB and re-encoded,
because that shifts the colour on HDR phone footage; source colour tags are
carried onto the output.

    python3 tools/captions.py --video cut.mp4 --out final.mp4
    python3 tools/captions.py --video cut.mp4 --out final.mp4 \
        --label "PATIENT DATA REDACTED" --label-range 7.7:32.1
"""
import argparse, json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

FONTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "assets", "fonts")
CAP_FONT = os.path.join(FONTS, "Coolvetica Rg.otf")
LAB_FONT = os.path.join(FONTS, "Coolvetica Rg Cond.otf")

# tuned at 1080x1920; everything below scales off REF_H
REF_H = 1920
CAP_SIZE = 78
BASELINE = 1560          # text bottom; clears his face and his hands
SIDE_MARGIN = 150
WHITE = (210, 210, 210)  # not 255: HLG peak glares on HDR displays
ACCENT = (104, 198, 138)
BOXA = 150
STROKE = 5
LAB_SIZE = 40
LAB_Y = 130


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,r_frame_rate,color_space,color_transfer,"
         "color_primaries,color_range", "-show_entries", "format=duration",
         "-of", "json", path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s, f = d["streams"][0], d["format"]
    num, den = s["r_frame_rate"].split("/")
    return dict(w=s["width"], h=s["height"], fps=float(num) / float(den),
                dur=float(f["duration"]),
                cs=s.get("color_space"), trc=s.get("color_transfer"),
                prim=s.get("color_primaries"), rng=s.get("color_range"))


def transcribe(path):
    from faster_whisper import WhisperModel
    m = WhisperModel("small.en", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(path, word_timestamps=True, vad_filter=False)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": round(w.start, 3), "e": round(w.end, 3)})
    return words


def chunk_words(words, font, draw, max_w):
    """Break at clause ends and long pauses, not on width alone."""
    out, cur = [], []
    for i, w in enumerate(words):
        trial = cur + [w]
        if cur and draw.textlength(" ".join(x["w"].upper() for x in trial),
                                   font=font) > max_w:
            out.append(cur); cur = [w]
        else:
            cur = trial
        ends = w["w"].rstrip()[-1:] in ".,?!;:"
        gap = (words[i + 1]["s"] - w["e"]) if i + 1 < len(words) else 0
        if cur and (ends or gap > 0.35) and len(cur) >= 2:
            out.append(cur); cur = []
    if cur:
        out.append(cur)
    return out


def render_state(chunk, active, font, W, H, k):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    words = [x["w"].upper() for x in chunk]
    space = d.textlength(" ", font=font)
    widths = [d.textlength(t, font=font) for t in words]
    total = sum(widths) + space * (len(words) - 1)
    x = (W - total) / 2
    asc, desc = font.getmetrics()
    top = BASELINE * k - (asc + desc)
    pad = 26 * k
    d.rounded_rectangle([x - pad, top - pad * 0.55, x + total + pad,
                         BASELINE * k + pad * 0.45],
                        radius=int(18 * k), fill=(0, 0, 0, BOXA))
    for i, t in enumerate(words):
        d.text((x, top), t, font=font,
               fill=(*(ACCENT if i == active else WHITE), 255),
               stroke_width=max(1, int(STROKE * k)), stroke_fill=(0, 0, 0, 210))
        x += widths[i] + space
    return img


def render_label(text, font, W, H, k):
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    tw = d.textlength(text, font=font)
    x, y = (W - tw) / 2, LAB_Y * k
    d.rounded_rectangle([x - 26 * k, y - 14 * k, x + tw + 26 * k,
                         y + LAB_SIZE * k + 18 * k],
                        radius=int(10 * k), fill=(0, 0, 0, 140))
    d.text((x, y), text, font=font, fill=(*WHITE, 236))
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--words", help="pre-computed word timings JSON (skips transcribe)")
    ap.add_argument("--label", action="append", default=[])
    ap.add_argument("--label-range", action="append", default=[],
                    help="start:end seconds, paired with --label")
    ap.add_argument("--crf", default="18")
    ap.add_argument("--cap-size", type=int,
                    help="caption font px override (default: CAP_SIZE scaled by height)")
    ap.add_argument("--max-width", type=int,
                    help="caption line width cap in px (default: frame minus margins). "
                         "Landscape wants ~60%% of the frame or lines run subtitle-long.")
    a = ap.parse_args()

    info = probe(a.video)
    W, H, fps = info["w"], info["h"], info["fps"]
    k = H / REF_H
    font = ImageFont.truetype(CAP_FONT, a.cap_size or max(8, int(CAP_SIZE * k)))
    lfont = ImageFont.truetype(LAB_FONT, max(6, int(LAB_SIZE * k)))
    probe_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))

    words = (json.load(open(a.words)) if a.words else transcribe(a.video))
    if not words:
        sys.exit("no speech found")
    chunks = chunk_words(words, font, probe_draw, a.max_width or (W - SIDE_MARGIN * k))

    state = {}
    for ci, ch in enumerate(chunks):
        for wi, w in enumerate(ch):
            end = ch[wi + 1]["s"] if wi + 1 < len(ch) else w["e"] + 0.12
            for f in range(int(w["s"] * fps), int(end * fps) + 1):
                state[f] = (ci, wi)

    labels = []
    for text, rng in zip(a.label, a.label_range):
        t0, t1 = (float(x) for x in rng.split(":"))
        labels.append((text, t0, t1))

    n_frames = int(info["dur"] * fps) + 1
    with tempfile.TemporaryDirectory() as td:
        ov = os.path.join(td, "ov.mov")
        p = subprocess.Popen(
            ["ffmpeg", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
             "-s", f"{W}x{H}", "-r", str(fps), "-i", "-",
             "-c:v", "qtrle", "-pix_fmt", "argb", ov, "-y"],
            stdin=subprocess.PIPE)
        blank = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        cache, lcache = {}, {}
        for i in range(n_frames):
            t = i / fps
            img = None
            for text, t0, t1 in labels:
                if t0 <= t <= t1:
                    if text not in lcache:
                        lcache[text] = render_label(text, lfont, W, H, k)
                    img = lcache[text]
                    break
            if i in state:
                key = state[i]
                if key not in cache:
                    cache[key] = render_state(chunks[key[0]], key[1], font, W, H, k)
                img = cache[key] if img is None else Image.alpha_composite(img, cache[key])
            p.stdin.write((img or blank).tobytes())
        p.stdin.close()
        if p.wait() != 0:
            sys.exit("overlay render failed")

        color = []
        for flag, key in [("-colorspace", "cs"), ("-color_trc", "trc"),
                          ("-color_primaries", "prim"), ("-color_range", "rng")]:
            if info[key] and info[key] != "unknown":
                color += [flag, info[key]]

        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", a.video, "-i", ov,
             "-filter_complex", "[0:v][1:v]overlay=0:0:format=auto[v]",
             "-map", "[v]", "-map", "0:a?", "-c:v", "libx264", "-preset", "medium",
             "-crf", a.crf, "-pix_fmt", "yuv420p"] + color +
            ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", a.out, "-y"],
            check=True)

    print(f"{a.out}: {len(chunks)} caption lines, {n_frames} frames, "
          f"colour {info['cs']}/{info['trc']} preserved")


if __name__ == "__main__":
    main()
