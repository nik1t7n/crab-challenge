"""Measure UNDERCLAW's training takes and keep the best of each.

    upstream/jumper/.venv/bin/python tools/film/pick_rocky.py

Per take kind (rocky_<kind>_<n> in renders/rocky/), what it must show and how it is
scored; the best passing take is copied to rocky_<kind>:

  * climb: up all three ramps onto the summit (body 12 cm higher than on the floor at
    the end, centred on the summit, facing the room), never dropping back a tier;
  * fail: reaches the summit's south face and does not get up it;
  * push: the heavy book travels at least 0.6 m with the crab behind it;
  * shuffle: the side-to-side swing covers at least 0.45 m;
  * squats: the body goes down and up at least 3 cm (the full crouch is 3.6).
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rocky_scene as R
from stage import RENDERS, TAKE_FPS, Take

FOLDER = RENDERS / "rocky"


def track(take: Take, body: int | None = None):
    d = take.data
    out, yaw = [], []
    b = take.root if body is None else body
    for f in range(take.frames):
        take.pose(f / TAKE_FPS)
        out.append(d.xpos[b].copy())
        m = d.xmat[take.root].reshape(3, 3)
        yaw.append(math.atan2(m[1, 0], m[0, 0]))
    return np.array(out), np.array(yaw)


def score(kind: str, take: Take) -> tuple[bool, float, str]:
    p, yaw = track(take)
    z0 = p[: int(TAKE_FPS), 2].mean()
    if kind == "climb":
        tx, ty, h = R.SUMMIT_TOP
        rise = p[-1, 2] - z0
        off = math.hypot(p[-1, 0] - tx, p[-1, 1] - ty)
        face = abs(math.degrees(math.atan2(math.sin(yaw[-1] + math.pi / 2), math.cos(yaw[-1] + math.pi / 2))))
        drop = max(0.0, float((np.maximum.accumulate(p[:, 2]) - p[:, 2]).max()))
        ok = abs(rise - h) < 0.02 and off < 0.12 and face < 20 and drop < 0.03
        return ok, off + drop, f"rise {rise * 100:.1f} cm, {off * 100:.0f} cm from the top, facing off {face:.0f} deg, drop {drop * 100:.1f} cm"
    if kind == "fail":
        wall = R.SUMMIT[0], R.STAIR_Y - R.HALF_W
        reach = p[:, 1].max()
        climbed = p[:, 2].max() - z0
        ok = reach > wall[1] - 0.30 and climbed < 0.03
        return ok, abs(reach - (wall[1] - 0.22)), f"front of body reaches y {reach + 0.2:.2f} (wall {wall[1]:.2f}), up {climbed * 100:.1f} cm"
    if kind == "push":
        b, _ = track(take, take.body("weight/weight"))
        moved = float(np.linalg.norm(b[-1, :2] - b[0, :2]))
        tilt_z = float(np.ptp(b[:, 2]))
        ok = moved > 0.6 and tilt_z < 0.03
        return ok, -moved, f"book moved {moved:.2f} m, bounced {tilt_z * 100:.1f} cm"
    if kind == "shuffle":
        swing = float(np.ptp(p[int(TAKE_FPS):, 0]))
        drift = float(np.ptp(p[int(TAKE_FPS):, 1]))
        return swing > 0.45, drift - swing, f"swing {swing:.2f} m, drift {drift * 100:.0f} cm"
    if kind == "squats":
        depth = float(np.ptp(p[int(TAKE_FPS):, 2]))
        walk = float(np.linalg.norm(p[-1, :2] - p[0, :2]))
        return depth > 0.03, walk - depth, f"depth {depth * 100:.1f} cm, wandered {walk * 100:.0f} cm"
    raise ValueError(kind)


def main() -> int:
    bad = 0
    for kind in ("climb", "fail", "push", "shuffle", "squats"):
        rated = []
        for npz in sorted(FOLDER.glob(f"rocky_{kind}_*.npz")):
            ok, s, note = score(kind, Take(npz.stem, group="rocky"))
            rated.append((not ok, s, npz))
            print(f"  {npz.stem}: {'ok ' if ok else 'bad'} {note}")
        if not rated:
            continue
        failed, _, best = min(rated, key=lambda r: (r[0], r[1]))
        for ext in (".npz", ".mjb"):
            shutil.copyfile(best.with_suffix(ext), FOLDER / f"rocky_{kind}{ext}")
        print(f"rocky_{kind} <- {best.stem}{'  (none passed)' if failed else ''}")
        bad += failed
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
