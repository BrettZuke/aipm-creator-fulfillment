#!/usr/bin/env python3
"""
Render carousel slides: html/slide-*.html  ->  slides/slide-*.png  (1080x1350, 2x).

Uses headless Google Chrome, which is already installed on most machines.
No pip packages required.

Run from anywhere:
    python3 scripts/render.py

If Chrome is in a non-standard place, set the CHROME env var:
    CHROME="/path/to/chrome" python3 scripts/render.py
"""
import os
import sys
import glob
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)                 # the skill/build folder
HTML_DIR = os.path.join(ROOT, "html")
OUT_DIR = os.path.join(ROOT, "slides")

WIDTH, HEIGHT, SCALE = 1080, 1350, 2

CHROME_CANDIDATES = [
    os.environ.get("CHROME", ""),
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    shutil.which("google-chrome") or "",
    shutil.which("google-chrome-stable") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
    shutil.which("chrome") or "",
]


def find_chrome():
    for c in CHROME_CANDIDATES:
        if c and os.path.exists(c):
            return c
    return None


def main():
    chrome = find_chrome()
    if not chrome:
        sys.exit(
            "Could not find Google Chrome.\n"
            "Install it from https://www.google.com/chrome/ , or set CHROME=/path/to/chrome and rerun."
        )

    if not os.path.isdir(HTML_DIR):
        sys.exit(f"No html/ folder found at {HTML_DIR}. Put your slide-*.html files there first.")

    os.makedirs(OUT_DIR, exist_ok=True)
    slides = sorted(glob.glob(os.path.join(HTML_DIR, "*.html")))
    if not slides:
        sys.exit(f"No .html files found in {HTML_DIR}.")

    for path in slides:
        name = os.path.splitext(os.path.basename(path))[0]
        out = os.path.join(OUT_DIR, name + ".png")
        cmd = [
            chrome,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-sandbox",
            f"--force-device-scale-factor={SCALE}",
            f"--window-size={WIDTH},{HEIGHT}",
            f"--screenshot={out}",
            "file://" + os.path.abspath(path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        # Older Chrome builds use --headless instead of --headless=new
        if not os.path.exists(out):
            cmd[1] = "--headless"
            res = subprocess.run(cmd, capture_output=True, text=True)
        if os.path.exists(out):
            print(f"  rendered {os.path.relpath(out, ROOT)}")
        else:
            print(f"  FAILED  {name}: {res.stderr.strip()[:200]}")

    print(f"\nDone. Slides are in: {OUT_DIR}")


if __name__ == "__main__":
    main()
