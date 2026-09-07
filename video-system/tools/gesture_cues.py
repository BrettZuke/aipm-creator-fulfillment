#!/usr/bin/env python3
"""Find pointing gestures in footage so edits can land WHEN and WHERE the speaker points.

Uses mediapipe Pose. A frame counts as "pointing" when a wrist is extended well away
from its shoulder (arm reach > 1.18x shoulder width). Consecutive pointing frames merge
into gesture windows with the median wrist position and a rough direction.

    python3 tools/gesture_cues.py <your-clip>.mp4 \
        -o gestures.json

Output: [{"start": s, "end": s, "hand": "left|right", "x": px, "y": px, "dir": "down|left|right|up"}]
in 1080x1920 output space (x/y also given normalized as nx/ny). Feed these to the reel
assembly: time a docked scene to `start`, place it near (x, y).
"""
import argparse
import json
import os
import statistics
import sys

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

L_SHOULDER, R_SHOULDER = 11, 12
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
NOSE = 0
MODEL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "models",
                     "pose_landmarker_lite.task")


def analyze(path, every=3, reach=1.18, min_frames=3):
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit("Cannot open %s" % path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    lmk = vision.PoseLandmarker.create_from_options(vision.PoseLandmarkerOptions(
        base_options=mp_python.BaseOptions(model_asset_path=MODEL),
        running_mode=vision.RunningMode.VIDEO))
    events = []  # per-sample: (t, hand, nx, ny, dirx, diry)
    idx = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if idx % every:
            idx += 1
            continue
        t = idx / fps
        idx += 1
        small = cv2.resize(frame, (270, 480))
        img = mp.Image(image_format=mp.ImageFormat.SRGB,
                       data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        res = lmk.detect_for_video(img, int(t * 1000))
        if not res.pose_landmarks:
            continue
        lm = res.pose_landmarks[0]
        sw = abs(lm[L_SHOULDER].x - lm[R_SHOULDER].x) or 1e-6
        for hand, sh, wr, hip in (("left", L_SHOULDER, L_WRIST, L_HIP),
                                  ("right", R_SHOULDER, R_WRIST, R_HIP)):
            if (lm[wr].visibility or 0) < 0.55:
                continue
            dx, dy = lm[wr].x - lm[sh].x, lm[wr].y - lm[sh].y
            extended = (dx * dx + dy * dy) ** 0.5 / sw > reach
            # pointing at the ground: wrist clearly below the hip line
            below_hip = (lm[hip].visibility or 0) > 0.4 and lm[wr].y - lm[hip].y > 0.045
            if extended or below_hip:
                events.append((t, hand, lm[wr].x, lm[wr].y, dx, dy))
    cap.release()
    lmk.close()

    # merge consecutive samples (gap <= every*2 frames) into gesture windows per hand
    out = []
    for hand in ("left", "right"):
        h = [e for e in events if e[1] == hand]
        if not h:
            continue
        gap = (every * 2 + 1) / fps
        group = [h[0]]
        for e in h[1:]:
            if e[0] - group[-1][0] <= gap:
                group.append(e)
            else:
                out.append(_window(group, hand))
                group = [e]
        out.append(_window(group, hand))
    out = [w for w in out if w["frames"] >= min_frames]
    out.sort(key=lambda w: w["start"])
    return out


def _window(group, hand):
    xs = [e[2] for e in group]
    ys = [e[3] for e in group]
    dx = statistics.median(e[4] for e in group)
    dy = statistics.median(e[5] for e in group)
    if abs(dy) >= abs(dx):
        d = "down" if dy > 0 else "up"
    else:
        d = "right" if dx > 0 else "left"  # mirrored later if needed; screen-space x
    nx, ny = statistics.median(xs), statistics.median(ys)
    return {"start": round(group[0][0], 2), "end": round(group[-1][0], 2), "hand": hand,
            "nx": round(nx, 3), "ny": round(ny, 3),
            "x": round(nx * 1080), "y": round(ny * 1920), "dir": d,
            "frames": len(group)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("-o", "--output")
    ap.add_argument("--every", type=int, default=3, help="analyze every Nth frame")
    ap.add_argument("--reach", type=float, default=1.18,
                    help="arm extension vs shoulder width to count as pointing")
    args = ap.parse_args()
    wins = analyze(args.video, every=args.every, reach=args.reach)
    for w in wins:
        print("%6.2fs-%6.2fs  %5s hand  %-5s  at (%d, %d)  [%d samples]" %
              (w["start"], w["end"], w["hand"], w["dir"], w["x"], w["y"], w["frames"]))
    print("%d gesture windows" % len(wins))
    if args.output:
        with open(args.output, "w") as f:
            json.dump(wins, f, indent=2)
        print("wrote", args.output)


if __name__ == "__main__":
    main()
