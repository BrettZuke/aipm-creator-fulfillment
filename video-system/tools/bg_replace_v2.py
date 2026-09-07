#!/usr/bin/env python3
"""Background replacement v2: REAL designed plates (Canva-generated), feathered
matte, lighting match. Demos 3s over paris.jpg + office.jpg."""
import os, subprocess
from PIL import Image, ImageFilter, ImageStat
from rembg import remove, new_session

ENGINE = os.path.join(os.path.dirname(__file__), "..", "engine")
SRC = os.environ.get("SRC_VIDEO") or os.path.join(ENGINE, "public", "source.mp4")
PLATES = {
    "paris": os.path.join(ENGINE, "public", "bgplates", "paris.jpg"),
    "office": os.path.join(ENGINE, "public", "bgplates", "office.jpg"),
}
WORK = os.path.join(ENGINE, "out", "bgdemo")
W, H = 540, 960
FPS, SECS, START = 25, 3, 4.0

frames_dir = os.path.join(WORK, "frames")
os.makedirs(frames_dir, exist_ok=True)
if not any(f.endswith(".png") for f in os.listdir(frames_dir)):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", str(START), "-t", str(SECS),
                    "-i", SRC, "-vf", f"fps={FPS},scale={W}:{H}", os.path.join(frames_dir, "f%04d.png")], check=True)
frames = sorted(f for f in os.listdir(frames_dir) if f.endswith(".png"))
print("frames:", len(frames))

def load_plate(path):
    img = Image.open(path).convert("RGB")
    # cover-crop to W:H
    sw, sh = img.size
    scale = max(W / sw, H / sh)
    img = img.resize((int(sw * scale) + 1, int(sh * scale) + 1))
    left = (img.width - W) // 2
    top = (img.height - H) // 2
    img = img.crop((left, top, left + W, top + H))
    return img.filter(ImageFilter.GaussianBlur(2.2))  # slight depth separation

plates = {k: load_plate(p) for k, p in PLATES.items()}
session = new_session("u2net_human_seg")
outdirs = {}
for name in plates:
    d = os.path.join(WORK, f"v2_{name}")
    os.makedirs(d, exist_ok=True)
    outdirs[name] = d

def luma(img):
    s = ImageStat.Stat(img.convert("L"))
    return s.mean[0]

for i, fname in enumerate(frames):
    frame = Image.open(os.path.join(frames_dir, fname)).convert("RGB")
    fg = remove(frame, session=session)  # RGBA
    # feather the matte edge
    a = fg.split()[3].filter(ImageFilter.GaussianBlur(1.6))
    fg.putalpha(a)
    subj_luma = luma(frame)
    for name, plate in plates.items():
        p = plate.copy()
        # nudge plate brightness toward subject lighting (30% of the way)
        pl = luma(p)
        if pl > 1:
            k = 1 + 0.3 * ((subj_luma / pl) - 1)
            k = max(0.6, min(1.25, k))
            p = Image.eval(p, lambda v, k=k: int(min(255, v * k)))
        p.paste(fg, (0, 0), fg)
        p.save(os.path.join(outdirs[name], fname))
    if i % 25 == 0:
        print("seg", i)

for name in plates:
    out = os.path.join(WORK, f"bg_{name}_v2.mp4")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS),
                    "-i", os.path.join(outdirs[name], "f%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", out], check=True)
    print("wrote", out)
print("DONE")
