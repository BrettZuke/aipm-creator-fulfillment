#!/usr/bin/env python3
"""Beat grid for music-driven (lifestyle) edits: BPM, beat times, and the big hits.

Numpy-only onset/tempo detection (no librosa): spectral flux -> autocorrelation
tempo -> phase-aligned beat grid + the strongest onsets (drops/impacts) for
placing hard cuts and speed-ramp moments.

    python3 tools/beat_grid.py engine/public/beat.mp3 -o beat_grid.json

Output: {"bpm": float, "beats": [sec...], "bars": [every 4th beat], "hits": [sec...]}
Cut rule of thumb: normal cuts on beats, hero moments (car rev, boat spray) on hits.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

SR = 22050
HOP = 512
WIN = 1024


def load_audio(path):
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.close()
    r = subprocess.run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", str(SR),
                        "-f", "wav", tmp.name], capture_output=True)
    if r.returncode != 0:
        sys.exit("ffmpeg failed: " + r.stderr.decode()[-300:])
    import wave
    with wave.open(tmp.name, "rb") as w:
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    os.unlink(tmp.name)
    return data.astype(np.float32) / 32768.0


def spectral_flux(y):
    n = (len(y) - WIN) // HOP
    window = np.hanning(WIN)
    prev = None
    flux = np.zeros(n)
    for i in range(n):
        seg = y[i * HOP:i * HOP + WIN] * window
        mag = np.abs(np.fft.rfft(seg))
        if prev is not None:
            flux[i] = np.sum(np.maximum(0, mag - prev))
        prev = mag
    if flux.max() > 0:
        flux = flux / flux.max()
    # local-mean subtraction sharpens peaks
    k = 8
    pad = np.pad(flux, k, mode="edge")
    local = np.array([pad[i:i + 2 * k + 1].mean() for i in range(n)])
    return np.maximum(0, flux - local)


def _grid_score(flux, bpm):
    fps = SR / HOP
    period = fps * 60.0 / bpm
    best = -1.0
    for phase in np.arange(0, period, period / 24):
        idx = np.arange(phase, len(flux), period).astype(int)
        idx = idx[idx < len(flux)]
        s = flux[idx].sum() / max(len(idx), 1)
        best = max(best, s)
    return best


def detect_bpm(flux):
    best_bpm, best_score = 120.0, -1.0
    for bpm in np.arange(60, 200, 0.25):
        score = _grid_score(flux, bpm)
        if score > best_score:
            best_score, best_bpm = score, float(bpm)
    # octave check: half-tempo often wins the raw score; prefer the doubled
    # tempo when it captures a comparable amount of energy (dance/rap edits
    # want the faster grid)
    if best_bpm * 2 <= 200 and _grid_score(flux, best_bpm * 2) >= 0.72 * best_score:
        best_bpm *= 2
    return best_bpm


def beat_grid(flux, bpm):
    fps = SR / HOP
    period = fps * 60.0 / bpm
    # phase: shift the grid to catch the most energy
    best_phase, best_score = 0.0, -1.0
    for phase in np.arange(0, period, period / 24):
        idx = np.arange(phase, len(flux), period).astype(int)
        idx = idx[idx < len(flux)]
        score = flux[idx].sum()
        if score > best_score:
            best_score, best_phase = score, phase
    beats = np.arange(best_phase, len(flux), period) / fps
    return [round(float(b), 3) for b in beats]


def top_hits(flux, count=12, min_gap=1.2):
    fps = SR / HOP
    order = np.argsort(flux)[::-1]
    hits = []
    for i in order:
        t = i / fps
        if all(abs(t - h) > min_gap for h in hits):
            hits.append(t)
        if len(hits) >= count:
            break
    return sorted(round(float(h), 3) for h in hits)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("audio")
    ap.add_argument("-o", "--output")
    ap.add_argument("--hits", type=int, default=12)
    args = ap.parse_args()
    y = load_audio(args.audio)
    flux = spectral_flux(y)
    bpm = detect_bpm(flux)
    beats = beat_grid(flux, bpm)
    hits = top_hits(flux, args.hits)
    print("bpm: %.1f | %d beats | first beats: %s" % (bpm, len(beats),
          ", ".join("%.2f" % b for b in beats[:8])))
    print("hits (hard-cut moments): %s" % ", ".join("%.2f" % h for h in hits))
    if args.output:
        with open(args.output, "w") as f:
            json.dump({"bpm": round(bpm, 2), "beats": beats,
                       "bars": beats[::4], "hits": hits}, f, indent=2)
        print("wrote", args.output)


if __name__ == "__main__":
    main()
