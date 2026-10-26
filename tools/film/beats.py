"""Tempo, beat grid and loudness sections of a music file, light enough for the render
host (numpy and ffmpeg only; earshot's full timeline needs its models).

    python tools/film/beats.py audio/track.mp3 [--json out.json]

Onset strength from a spectral flux of the decoded mono signal; tempo by the
autocorrelation peak between 70 and 180 BPM; beat phase by the best-aligned comb;
downbeats every fourth beat from the strongest of the four phases. Sections are runs
of similar loudness (1 s windows), split where the level jumps by 4 dB.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess

import numpy as np

SR = 22050
HOP = 512


def decode(path: str) -> np.ndarray:
    ffmpeg = os.environ.get("FFMPEG", "ffmpeg")
    raw = subprocess.run([ffmpeg, "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def analyse(x: np.ndarray) -> dict:
    n = (len(x) - 2048) // HOP
    frames = np.lib.stride_tricks.sliding_window_view(x, 2048)[::HOP][:n] * np.hanning(2048)
    mag = np.log1p(np.abs(np.fft.rfft(frames, axis=1)))
    flux = np.maximum(0.0, np.diff(mag, axis=0)).sum(axis=1)
    flux = (flux - flux.mean()) / (flux.std() or 1.0)
    fps = SR / HOP
    ac = np.correlate(flux, flux, "full")[len(flux) - 1:]
    lags = np.arange(len(ac))
    ok = (lags > fps * 60 / 180) & (lags < fps * 60 / 70)
    lag = int(lags[ok][np.argmax(ac[ok])])
    bpm = 60 * fps / lag
    phases = [flux[p::lag].sum() for p in range(lag)]
    p0 = int(np.argmax(phases))
    beats = np.arange(p0, len(flux), lag) / fps
    strength = [flux[int(b * fps)] if int(b * fps) < len(flux) else 0 for b in beats]
    down0 = int(np.argmax([sum(strength[i::4]) for i in range(4)]))
    win = int(SR)
    rms = np.array([np.sqrt(np.mean(x[i:i + win] ** 2)) + 1e-9 for i in range(0, len(x) - win, win)])
    db = 20 * np.log10(rms)
    sections, start = [], 0
    for i in range(1, len(db)):
        if abs(db[i] - np.median(db[start:i])) > 4 and i - start >= 3:
            sections.append((start, i, round(float(np.median(db[start:i])), 1)))
            start = i
    sections.append((start, len(db), round(float(np.median(db[start:])), 1)))
    return {"tempo": round(bpm, 1), "beats": [round(float(b), 3) for b in beats],
            "downbeats": [round(float(b), 3) for b in beats[down0::4]], "duration": round(len(x) / SR, 2),
            "sections": [{"start": a, "end": b, "db": v} for a, b, v in sections]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--json")
    a = ap.parse_args()
    out = analyse(decode(a.path))
    if a.json:
        with open(a.json, "w") as f:
            json.dump(out, f)
    print(f"{a.path}: {out['duration']} s, {out['tempo']} BPM, first downbeats {out['downbeats'][:6]}")
    for s in out["sections"]:
        print(f"  {s['start']:4d}-{s['end']:4d} s  {s['db']} dB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
