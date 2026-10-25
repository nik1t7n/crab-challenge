"""Measure a prop the crab handles: where it goes, and does anything pass through it.

    upstream/jumper/.venv/bin/python tools/film/check_prop.py push gold/gold

Per frame of the recorded take: the bar's height above the floor, its distance from
the claw's mouth, which robot parts touch it and how deep the deepest contact goes
(MuJoCo's own collision detection on the recorded poses; a contact a few millimetres
deep is the soft contact model at work, a deep one is something passing through).
"""

from __future__ import annotations

import sys
from pathlib import Path

import mujoco

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stage import Take


def main() -> int:
    take = Take(sys.argv[1] if len(sys.argv) > 1 else "push")
    prop = sys.argv[2] if len(sys.argv) > 2 else "gold/gold"
    m, d = take.model, take.data
    m.opt.disableflags &= ~int(mujoco.mjtDisableBit.mjDSBL_CONTACT)
    bar_body = take.body(prop)
    bar = [g for g in range(m.ngeom) if m.geom_bodyid[g] == bar_body]
    robot = set(take.robot_geoms().tolist())
    deepest = (0.0, 0.0, "")
    print(f"{'t':>5} {'prop xy':>16} {'z mm':>6} {'deepest mm':>11}  touching")
    for f in range(take.frames):
        t = f / 25.0
        take.pose(t)
        mujoco.mj_forward(m, d)
        touching, deep = set(), 0.0
        for i in range(d.ncon):
            c = d.contact[i]
            pair = {int(c.geom1), int(c.geom2)}
            if pair & set(bar) and pair & robot:
                other = (pair - set(bar)).pop()
                touching.add(mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_GEOM, other).split("/")[-1].replace("_meshcol", ""))
                deep = min(deep, c.dist)
        if deep < deepest[0]:
            deepest = (deep, t, ", ".join(sorted(touching)))
        if f % 12 == 0:
            x, y, z = d.xpos[bar_body]
            print(f"{t:5.2f} {x:7.3f} {y:7.3f} {z * 1000:6.1f} {deep * 1000:11.2f}  {', '.join(sorted(touching))}")
    print(f"deepest robot-prop contact: {deepest[0] * 1000:.2f} mm at {deepest[1]:.2f} s ({deepest[2]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
