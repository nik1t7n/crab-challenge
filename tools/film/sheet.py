"""A contact sheet of shots: frames at given fractions of each clip, tiled.

    upstream/jumper/.venv/bin/python tools/film/sheet.py OUT.png clip.mp4 ... [--at 0.2 0.5 0.8]
"""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("clips", nargs="+")
    ap.add_argument("--at", nargs="+", type=float, default=[0.2, 0.5, 0.85])
    ap.add_argument("--width", type=int, default=320)
    args = ap.parse_args()
    w = args.width
    h = w * 9 // 16
    sheet = Image.new("RGB", (w * len(args.at), h * len(args.clips)))
    with tempfile.TemporaryDirectory() as tmp:
        for r, clip in enumerate(args.clips):
            dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                        "csv=p=0", clip], capture_output=True, text=True).stdout)
            for c, frac in enumerate(args.at):
                png = Path(tmp) / f"{r}_{c}.png"
                subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-ss", f"{dur * frac:.3f}", "-i", clip,
                                "-frames:v", "1", "-vf", f"scale={w}:{h}", str(png)], check=True)
                tile = Image.open(png)
                ImageDraw.Draw(tile).text((4, 4), f"{Path(clip).stem} {frac:.2f}", fill=(255, 255, 0))
                sheet.paste(tile, (c * w, r * h))
    sheet.save(args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
