"""Measure OPERATION: COOKIE's takes and keep the best as renders/stealth/stealth.

    upstream/jumper/.venv/bin/python tools/film/check_stealth.py

A take counts when the crab never touches the vacuum (every collision geom's
bounding sphere clear of the vacuum's cylinder, per frame), the vacuum never
touches the cookie, and the cookie ends fully under the furniture; among those the
one that kept closest to the timetable wins. Prints the closest call too: the film
plays it up, so it should be close, but clear.
"""

from __future__ import annotations

import math
import shutil
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import stealth_scene as T
from stage import RENDERS, TAKE_FPS, Take

FOLDER = RENDERS / "stealth"


def score(take: Take):
    m, d = take.model, take.data
    geoms = [g for g in take.robot_geoms() if m.geom_contype[g] or m.geom_conaffinity[g]]
    vac, cookie = take.body("vacuum/vacuum"), take.body("cookie/cookie")
    gap, gap_t, lag, cookie_gap = np.inf, 0.0, [], np.inf
    for f in range(take.frames):
        t = f / TAKE_FPS
        take.pose(t)
        v = d.xpos[vac][:2]
        for g in geoms:
            if d.geom_xpos[g][2] - m.geom_rbound[g] > T.VAC_H + 0.004:
                continue  # above the vacuum's top
            c = np.linalg.norm(d.geom_xpos[g][:2] - v) - T.VAC_R - m.geom_rbound[g]
            if c < gap:
                gap, gap_t = c, t
        cookie_gap = min(cookie_gap, float(np.linalg.norm(d.xpos[cookie][:2] - v)) - T.VAC_R - T.COOKIE_R)
        lag.append(math.hypot(*(d.xpos[take.root][:2] - np.array(T.reference(min(t, T.END))[:2]))))
    take.pose((take.frames - 1) / TAKE_FPS)
    under = d.xpos[cookie][1] - T.COOKIE_R - T.BED[2]
    ok = gap > 0.0 and cookie_gap > 0.0 and under > 0.02
    note = (f"closest to the vacuum {gap * 100:.1f} cm at {gap_t:.1f} s; cookie {cookie_gap * 100:.0f} cm from it, "
            f"ends {under * 100:+.0f} cm under; path worst {max(lag) * 100:.1f} cm")
    return ok, max(lag), note


def main() -> int:
    rated = []
    for npz in sorted(FOLDER.glob("stealth_*.npz")):
        ok, s, note = score(Take(npz.stem, group="stealth"))
        rated.append((not ok, s, npz))
        print(f"  {npz.stem}: {'ok ' if ok else 'bad'} {note}")
    failed, _, best = min(rated, key=lambda r: (r[0], r[1]))
    for ext in (".npz", ".mjb"):
        shutil.copyfile(best.with_suffix(ext), FOLDER / f"stealth{ext}")
    print(f"stealth <- {best.stem}{'  (none passed)' if failed else ''}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
