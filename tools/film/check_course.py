"""Measure the vault run: did the crab clear every pillar, pass under every beam
crouched, push the crate, and where was it when.

    upstream/jumper/.venv/bin/python tools/film/check_course.py

Pillars by exact geom distance (`mj_geomDistance`) between each pillar and every
robot collision geom; beams by each robot geom's world bounding box (conservative,
so a real gap is at least the one printed). Exits non-zero on a touch.
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vault_scene as V
from stage import Take


def main() -> int:
    take = Take("course")
    m, d = take.model, take.data
    robot = [g for g in take.robot_geoms() if m.geom_contype[g] or m.geom_conaffinity[g]]
    pillars = [mujoco.mj_name2id(m, mujoco.mjtObj.mjOBJ_GEOM, f"pillar_{i}") for i in range(len(V.PILLARS))]
    crate = take.body("crate/crate")
    near = [(np.inf, 0.0)] * len(pillars)
    beam = (np.inf, 0.0, 0.0)
    for f in range(take.frames):
        t = f / 25.0
        take.pose(t)
        for i, pg in enumerate(pillars):
            for g in robot:
                dist = mujoco.mj_geomDistance(m, d, pg, g, 0.5, None)
                if dist < near[i][0]:
                    near[i] = (dist, t)
        for g in take.robot_geoms():
            c, h = m.geom_aabb[g, :3], m.geom_aabb[g, 3:]
            R = d.geom_xmat[g].reshape(3, 3)
            centre = d.geom_xpos[g] + R @ c
            reach = np.abs(R) @ h
            for x in V.GATE_X:
                if abs(centre[0] - x) <= reach[0]:
                    gap = V.BEAM_Z - (centre[2] + reach[2])
                    if gap < beam[0]:
                        beam = (gap, t, x)
    ok = True
    for (x, y), (dist, t) in zip(V.PILLARS, near, strict=True):
        print(f"pillar ({x:.2f}, {y:+.2f}): closest {dist * 1000:6.1f} mm at {t:5.2f} s")
        ok &= dist > 0.0
    print(f"laser gate: lowest gap under a beam {beam[0] * 1000:.1f} mm (beam x {beam[2]:.2f}, {beam[1]:.2f} s)")
    ok &= beam[0] > 0.0
    for t in np.arange(0.0, take.duration + 1e-6, 2.0):
        take.pose(t)
        print(f"{t:5.1f} s  crab {d.xpos[take.root].round(3)}  crate {d.xpos[crate].round(3)}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
