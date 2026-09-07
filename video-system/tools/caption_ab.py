#!/usr/bin/env python3
"""Render the two caption styles side by side so you can pick one.

Left is the approved style (presets/captions-approved.md), right is the
cinematic style (presets/captions-cinematic.md). If only the cinematic render
exists, this runs captions.py on the same cut to produce the approved side, so
both panels come from identical footage and the only variable is the captions.

The side-by-side is a REVIEW COPY, never a deliverable. It re-encodes both
panels to stack them; source colour tags are carried through so the footage
still reads ungraded while he judges it, but ship the individual renders.

    python3 tools/caption_ab.py --cut renders/roughcut.mp4 \
        --b renders/cinematic.mp4 --out renders/compare
    python3 tools/caption_ab.py --a renders/approved.mp4 \
        --b renders/cinematic.mp4 --out renders/compare
"""
import argparse, json, os, subprocess, sys, tempfile
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CAPTIONS = os.path.join(ROOT, "tools", "captions.py")
LAB_FONT = os.path.join(ROOT, "assets", "fonts", "Coolvetica Rg Cond.otf")

LAB_SIZE = 46            # tuned at 1920 tall, scales off the panel height
LAB_PAD = 34
WHITE = (210, 210, 210)  # not 255: matches captions.py, HLG peak glares
REF_H = 1920


def probe(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height,color_space,color_transfer,color_primaries,"
         "color_range", "-show_entries", "format=duration", "-of", "json",
         path], capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    s, f = d["streams"][0], d["format"]
    return dict(w=s["width"], h=s["height"], dur=float(f["duration"]),
                cs=s.get("color_space"), trc=s.get("color_transfer"),
                prim=s.get("color_primaries"), rng=s.get("color_range"))


def color_flags(info):
    flags = []
    for flag, key in [("-colorspace", "cs"), ("-color_trc", "trc"),
                      ("-color_primaries", "prim"), ("-color_range", "rng")]:
        if info[key] and info[key] != "unknown":
            flags += [flag, info[key]]
    return flags


def label_png(text, h, path):
    """Draw the panel label with PIL and save it as an RGBA overlay.

    This ffmpeg build has no drawtext (compiled without libfreetype), which is
    the same reason captions.py rasterises text in PIL: make the pixels here,
    let ffmpeg composite them.
    """
    k = h / REF_H
    size, pad = max(10, int(LAB_SIZE * k)), max(8, int(LAB_PAD * k))
    font = ImageFont.truetype(LAB_FONT, size)
    probe_draw = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    tw = probe_draw.textlength(text, font=font)
    asc, desc = font.getmetrics()
    img = Image.new("RGBA", (int(tw + pad * 2), int(asc + desc + pad)),
                    (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, img.width - 1, img.height - 1],
                        radius=int(10 * k), fill=(0, 0, 0, 158))
    d.text((pad, pad / 2), text, font=font, fill=(*WHITE, 236))
    img.save(path)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b", required=True, help="cinematic render")
    ap.add_argument("--a", help="approved render (rendered from --cut if omitted)")
    ap.add_argument("--cut", help="locked cut, required when --a is omitted")
    ap.add_argument("--out", required=True, help="output directory")
    ap.add_argument("--stills", type=int, default=6,
                    help="paired stills to pull, evenly spaced (0 to skip)")
    ap.add_argument("--crf", default="18")
    a = ap.parse_args()

    if not a.a and not a.cut:
        sys.exit("need --a (an approved render) or --cut (to render one)")
    os.makedirs(a.out, exist_ok=True)

    approved = a.a
    if not approved:
        approved = os.path.join(a.out, "approved.mp4")
        print(f"rendering approved side from {a.cut} ...", flush=True)
        subprocess.run([sys.executable, CAPTIONS, "--video", a.cut,
                        "--out", approved, "--crf", a.crf], check=True)

    ia, ib = probe(approved), probe(a.b)
    if ia["h"] != ib["h"]:
        print(f"note: heights differ ({ia['h']} vs {ib['h']}), "
              f"scaling cinematic to {ia['h']}")
    dur = min(ia["dur"], ib["dur"])
    if abs(ia["dur"] - ib["dur"]) > 0.5:
        print(f"warning: durations differ by {abs(ia['dur'] - ib['dur']):.2f}s; "
              f"comparing the first {dur:.2f}s. Are both from the same cut?")

    sxs = os.path.join(a.out, "side-by-side.mp4")
    pad = max(8, int(LAB_PAD * ia["h"] / REF_H))
    with tempfile.TemporaryDirectory() as td:
        la = label_png("APPROVED", ia["h"], os.path.join(td, "la.png"))
        lb = label_png("CINEMATIC", ia["h"], os.path.join(td, "lb.png"))
        fc = (f"[0:v][2:v]overlay={pad}:{pad}[l];"
              f"[1:v]scale=-2:{ia['h']}[rs];[rs][3:v]overlay={pad}:{pad}[r];"
              f"[l][r]hstack=inputs=2[v]")
        subprocess.run(
            ["ffmpeg", "-v", "error", "-i", approved, "-i", a.b,
             "-i", la, "-i", lb,
             "-filter_complex", fc, "-map", "[v]", "-map", "0:a?",
             "-t", str(dur), "-c:v", "libx264", "-preset", "medium",
             "-crf", a.crf, "-pix_fmt", "yuv420p"] + color_flags(ia) +
            ["-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
             sxs, "-y"], check=True)

    stills = []
    for i in range(a.stills):
        t = dur * (i + 1) / (a.stills + 1)
        p = os.path.join(a.out, f"still-{i + 1:02d}.png")
        subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", sxs,
                        "-frames:v", "1", p, "-y"], check=True)
        stills.append(p)

    print(f"{sxs}: {dur:.2f}s, {ia['w'] + int(ia['h'] * ib['w'] / ib['h'])}x{ia['h']}, "
          f"colour {ia['cs']}/{ia['trc']} preserved")
    for p in stills:
        print(f"  {p}")
    print("review copy only - ship the individual renders, not this")


if __name__ == "__main__":
    main()
