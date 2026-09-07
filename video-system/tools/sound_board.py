#!/usr/bin/env python3
"""Numbered sound-review board: every SFX plays once with number (from 0), name,
category on a PIL-rendered card. Chunked videos + manifest for verdicts."""
import os, subprocess, math
from PIL import Image, ImageDraw, ImageFont

ENGINE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "engine")
SFX = os.path.join(ENGINE, "public", "sfx")
OUT = os.path.join(ENGINE, "out", "soundboard")
os.makedirs(OUT, exist_ok=True)
CHUNK = 10000
W, H = 1280, 720

font_big = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 240)
font_mid = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 54)
font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 36)

items = []
for f in sorted(x for x in os.listdir(SFX) if x.lower().endswith((".wav", ".mp3"))):
    items.append(("core", os.path.splitext(f)[0], os.path.join(SFX, f)))
for f in sorted(os.listdir(os.path.join(SFX, "meme"))):
    if f.lower().endswith((".wav", ".mp3")):
        items.append(("meme", os.path.splitext(f)[0], os.path.join(SFX, "meme", f)))
packs = os.path.join(SFX, "packs")
for cat in sorted(os.listdir(packs)):
    d = os.path.join(packs, cat)
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith((".wav", ".mp3")):
                items.append((cat, os.path.splitext(f)[0], os.path.join(d, f)))
print("total sounds:", len(items))

def adur(path):
    try:
        r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                            "-of", "csv=p=0", path], capture_output=True, text=True, timeout=20)
        return float(r.stdout.strip())
    except Exception:
        return 1.0

def card(n, name, cat, path):
    img = Image.new("RGB", (W, H), (11, 14, 19))
    d = ImageDraw.Draw(img)
    num = str(n)
    bb = d.textbbox((0, 0), num, font=font_big)
    d.text(((W - (bb[2] - bb[0])) / 2, 110), num, font=font_big, fill=(255, 255, 255))
    nm = name[:42]
    bb = d.textbbox((0, 0), nm, font=font_mid)
    d.text(((W - (bb[2] - bb[0])) / 2, 460), nm, font=font_mid, fill=(52, 199, 89))
    bb = d.textbbox((0, 0), cat, font=font_sm)
    d.text(((W - (bb[2] - bb[0])) / 2, 545), cat, font=font_sm, fill=(142, 142, 147))
    img.save(path)

seg_dir = os.path.join(OUT, "segs")
card_dir = os.path.join(OUT, "cards")
os.makedirs(seg_dir, exist_ok=True)
os.makedirs(card_dir, exist_ok=True)
manifest, segs = [], []
for n, (cat, name, path) in enumerate(items, start=1):
    dur = min(3.2, max(1.1, adur(path) + 0.35))
    seg = os.path.join(seg_dir, f"s{n:04d}.mp4")
    manifest.append(f"{n}\t{cat}\t{os.path.relpath(path, SFX)}")
    if not os.path.exists(seg):
        png = os.path.join(card_dir, f"c{n:04d}.png")
        card(n, name, cat, png)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", png,
                        "-i", path, "-t", str(dur), "-r", "25",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-tune", "stillimage",
                        "-c:a", "aac", "-ar", "48000", "-ac", "2", seg], check=True)
    segs.append(seg)
    if n % 50 == 0:
        print("seg", n)

with open(os.path.join(SFX, "sounds_manifest.txt"), "w") as fh:
    fh.write("\n".join(manifest))

nvids = math.ceil(len(segs) / CHUNK)
outs = []
for v in range(nvids):
    lst = os.path.join(OUT, f"list{v}.txt")
    with open(lst, "w") as fh:
        for s in segs[v * CHUNK:(v + 1) * CHUNK]:
            fh.write(f"file '{s}'\n")
    a, b = v * CHUNK, min(len(segs), (v + 1) * CHUNK) - 1
    outp = os.path.join(OUT, "sounds_all.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
                    "-i", lst, "-c", "copy", outp], check=True)
    outs.append(outp)
    print("wrote", outp)
print("DONE", len(items), "sounds,", nvids, "videos")
