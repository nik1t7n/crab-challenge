"""Measure a recorded take: where the robot is, how high its top and bottom reach.

    python tools/film/inspect_take.py renders/film/sneak.npz [--every 0.5]

The set has to be built around the motion, not the other way round: a laser the
crab passes under must sit above the highest point of the crouched robot, and one
it jumps over below the lowest point at the top of the jump. Both come from the
recorded poses, per frame, over the robot's own geoms (every geom under the free
body), from each geom's bounding box turned into the world.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import mujoco
import numpy as np


def robot_root(model: mujoco.MjModel) -> int:
    """The robot's free body: the first body with a free joint that has children."""
    for j in range(model.njnt):
        if model.jnt_type[j] == mujoco.mjtJoint.mjJNT_FREE:
            b = model.jnt_bodyid[j]
            if np.any(model.body_parentid == b):
                return int(b)
    raise SystemExit("no articulated free body in this model")


def subtree(model: mujoco.MjModel, root: int) -> np.ndarray:
    inside = np.zeros(model.nbody, bool)
    inside[root] = True
    for b in range(root + 1, model.nbody):
        inside[b] = inside[model.body_parentid[b]]
    return inside


def geom_z_extent(model, data, geoms: np.ndarray) -> tuple[float, float]:
    """Lowest and highest world z over `geoms`' oriented bounding boxes."""
    lo, hi = np.inf, -np.inf
    for g in geoms:
        c, h = model.geom_aabb[g, :3], model.geom_aabb[g, 3:]
        R = data.geom_xmat[g].reshape(3, 3)
        zc = data.geom_xpos[g, 2] + R[2] @ c
        zr = np.abs(R[2]) @ h
        lo, hi = min(lo, zc - zr), max(hi, zc + zr)
    return lo, hi


def measure(npz: Path) -> dict[str, np.ndarray]:
    rec = np.load(npz)
    model = mujoco.MjModel.from_binary_path(str(npz.with_suffix(".mjb")))
    data = mujoco.MjData(model)
    root = robot_root(model)
    body_in = subtree(model, root)
    geoms = np.flatnonzero(body_in[model.geom_bodyid] & (model.geom_group < 3))
    out = {"pos": [], "low": [], "high": []}
    for q in rec["qpos"]:
        data.qpos[:] = q
        mujoco.mj_kinematics(model, data)
        lo, hi = geom_z_extent(model, data, geoms)
        out["pos"].append(data.xpos[root].copy())
        out["low"].append(lo)
        out["high"].append(hi)
    return {k: np.asarray(v) for k, v in out.items()}


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("take", type=Path)
    ap.add_argument("--fps", type=float, default=25.0)
    ap.add_argument("--every", type=float, default=0.5, help="seconds between printed rows")
    args = ap.parse_args()
    m = measure(args.take)
    step = max(1, round(args.every * args.fps))
    print(f"{'t':>5} {'x':>7} {'y':>7} {'body z':>7} {'low':>6} {'high':>6}")
    for i in range(0, len(m["low"]), step):
        x, y, z = m["pos"][i]
        print(f"{i / args.fps:5.2f} {x:7.3f} {y:7.3f} {z:7.3f} {m['low'][i]:6.3f} {m['high'][i]:6.3f}")
    print(f"max high {m['high'].max():.3f} m, max low {m['low'].max():.3f} m "
          f"at {m['low'].argmax() / args.fps:.2f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
