"""Measure the bedroom crew: did every crab keep to its planned path and get its
things under the furniture, and do the six crabs, drawn together, ever overlap.

    upstream/jumper/.venv/bin/python tools/film/check_crew.py

The six takes are separate simulations, so a crab cannot feel another; on screen they
share the floor. Per pair of crabs and per frame this measures the gap between their
bodies (each crab's collision geoms as bounding spheres, conservative), and between a
crab and the other crabs' things. Each crab's own contacts are physics and need no
check.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import bedroom_scene as B
from stage import TAKE_FPS, Take


def main() -> int:
    crew = range(len(B.LANES))
    takes = [Take(f"crab{k}", group="crew") for k in crew]
    n = min(t.frames for t in takes)
    bodies, things = [], []
    ok = True
    for k, take in zip(crew, takes, strict=True):
        m, d = take.model, take.data
        geoms = [g for g in take.robot_geoms() if m.geom_contype[g] or m.geom_conaffinity[g]]
        items = [take.body(f"item{i}/item") for i in range(len(B.ITEMS[k]))]
        cs, ip, lag = [], [], []
        for f in range(n):
            take.pose(f / TAKE_FPS)
            cs.append(np.array([d.geom_xpos[g] for g in geoms]))
            ip.append(np.array([d.xpos[b] for b in items]))
            lag.append(np.linalg.norm(d.xpos[take.root][:2] - np.array(B.reference(k, f / TAKE_FPS)[:2])))
        bodies.append((np.array(cs), np.array([m.geom_rbound[g] for g in geoms])))
        things.append(np.array(ip))
        lag = np.array(lag)
        under = [float(p[1] - B.KINDS[B.ITEMS[k][i][0]][0][1] - B.BED[2]) for i, p in enumerate(ip[-1])]
        done = all(u > 0 for u in under)
        ok &= done and lag.max() < 0.15
        print(f"crab{k}: off its path {lag.mean() * 100:.1f} cm mean, {lag.max() * 100:.1f} cm worst "
              f"(at {lag.argmax() / TAKE_FPS:.1f} s); things "
              + ", ".join(f"{u * 100:+.0f} cm" for u in under) + " under the front edge"
              + ("" if done else "  <- NOT UNDER"))
    for a, b in itertools.combinations(crew, 2):
        (ca, ra), (cb, rb) = bodies[a], bodies[b]
        worst, when = np.inf, 0
        for f in range(0, n, 2):
            gap = np.linalg.norm(ca[f][:, None, :] - cb[f][None, :, :], axis=2) - ra[:, None] - rb[None, :]
            if gap.min() < worst:
                worst, when = gap.min(), f
        if worst < 0.02:
            print(f"  crab{a} and crab{b}: bounding spheres {worst * 100:.1f} cm apart at {when / TAKE_FPS:.1f} s")
            ok &= worst > -0.03
    for a, b in itertools.permutations(crew, 2):
        (ca, ra) = bodies[a]
        worst, when = np.inf, 0
        for f in range(0, n, 2):
            gap = np.linalg.norm(ca[f][:, None, :] - things[b][f][None, :, :], axis=2) - ra[:, None] - 0.06
            if gap.min() < worst:
                worst, when = gap.min(), f
        if worst < 0.0:
            print(f"  crab{a} meets crab{b}'s things: {worst * 100:.1f} cm at {when / TAKE_FPS:.1f} s")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
