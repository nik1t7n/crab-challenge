"""Bring recorded poses (.npz) and scene models (.mjb) back from the render host.

    CRAB_RENDER_HOST=user@host python3 tools/fetch_poses.py [--host user@host] [--remote isolated/crab-challenge]

Each clip's .mjb is about 80 MB and no two are byte-identical (fields randomised per
run), yet they differ by a few kilobytes. rsync's delta transfer sends only what
differs from the file already at the destination, so each model is first seeded
locally with the closest one we have: an earlier clip of the same scene, else any
model. Measured on 2026-10-25: an 81 MB model moved as about 36 KB in 1.4 s, against
34 s for a plain copy over the VPN.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RENDERS = ROOT / "renders"


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--host", default=os.environ.get("CRAB_RENDER_HOST"), required="CRAB_RENDER_HOST" not in os.environ)
    ap.add_argument("--remote", default="isolated/crab-challenge")
    args = ap.parse_args()
    src = f"{args.host}:{args.remote}/renders/"

    started = time.monotonic()
    subprocess.run(["rsync", "-a", "--include=*/", "--include=*.npz", "--include=index.json",
                    "--exclude=*", src, f"{RENDERS}/"], check=True)
    scene_of = {f"{r['group']}/{r['name']}": r["scene"]
                for r in json.loads((RENDERS / "index.json").read_text())}

    clips = sorted(RENDERS.glob("*/*.npz"))
    clips.sort(key=lambda p: scene_of.get(f"{p.parent.name}/{p.stem}", ""))
    bases: dict[str, Path] = {}
    any_base: Path | None = None
    for npz in clips:
        key = f"{npz.parent.name}/{npz.stem}"
        scene = scene_of.get(key, key)
        mjb = npz.with_suffix(".mjb")
        base = bases.get(scene, any_base)
        if not mjb.exists() and base is not None:
            shutil.copyfile(base, mjb)
        t = time.monotonic()
        got = subprocess.run(["rsync", "-a", "--no-whole-file",
                              f"{args.host}:{args.remote}/renders/{key}.mjb", str(mjb)], capture_output=True)
        if got.returncode == 23:  # made here (a picked best take), not on the host
            continue
        got.check_returncode()
        seeded = "seeded" if base is not None else "full copy"
        print(f"[fetch] {key:<30} {seeded:<9} {time.monotonic() - t:5.1f} s", flush=True)
        bases.setdefault(scene, mjb)
        any_base = any_base or mjb
    print(f"[fetch] {len(clips)} clips in {time.monotonic() - started:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
